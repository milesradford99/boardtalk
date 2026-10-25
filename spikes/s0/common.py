"""Shared pieces for spike S0: transcript rendering, fold points, cards, the Ark client and its token ledger."""
import json
import os
import re
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

DATA = Path(__file__).parent / "data"
TRAJ = DATA / "trajectories"
OUT = Path(os.environ.get("S0_OUT", DATA / "out"))

FOLD_TOKENS = 10_000          # forced fold every ~10k rendered tokens (3-5 folds per trajectory), at turn boundaries
RESULT_CHARS = 2_500          # tool results are clipped the same way for every arm
ARG_CHARS = 1_500
TOKEN_CAP = 60_000_000        # safety stop on total tokens (flat-rate Ark plan); raised from 40M for S0b

# Roles. Writers (scribe/summary/handoff/answers) are DeepSeek; evaluation (questions, judge) is a different
# family (Kimi) to avoid a model grading its own family's output.
MAIN = "deepseek-v4-pro"            # plays the main agent: summary baseline, handoff card, answering
EVAL = "kimi-k3"                    # question generation and blind judging
SCRIBES = {"flash": "deepseek-v4.1-flash", "pro": "deepseek-v4-pro"}


def approx_tokens(s: str) -> int:
    return len(s) // 4


def load(tid: str) -> dict:
    return json.loads((TRAJ / f"{tid}.json").read_text())


def all_ids() -> list[str]:
    return sorted(p.stem for p in TRAJ.glob("*.json"))


def _clip(s: str, n: int) -> str:
    if len(s) <= n:
        return s
    head = int(n * 0.7)
    return f"{s[:head]}\n…[{len(s) - n} chars clipped]…\n{s[-(n - head):]}"


def render_turn(t: dict) -> str:
    """One agent turn as plain text. Every arm sees exactly this rendering."""
    parts = [f"=== turn {t['idx']} ==="]
    if t["text"].strip():
        parts.append(f"[assistant] {t['text'].strip()}")
    for c in t["calls"]:
        args = json.dumps(c["args"], ensure_ascii=False)
        parts.append(f"[call {c['name']}] {_clip(args, ARG_CHARS)}")
    for r in t["results"]:
        parts.append(f"[result {r['name']}] {_clip(r['content'], RESULT_CHARS)}")
    return "\n".join(parts)


def render_turns(turns: list[dict]) -> str:
    return "\n\n".join(render_turn(t) for t in turns)


def fold_points(traj: dict) -> list[int]:
    """Turn indices after which a fold happens (the window [prev, k] gets compressed)."""
    points, acc = [], 0
    for t in traj["turns"]:
        acc += approx_tokens(render_turn(t))
        if acc >= FOLD_TOKENS:
            points.append(t["idx"])
            acc = 0
    if points and points[-1] == traj["turns"][-1]["idx"]:
        points.pop()  # a fold at the very end leaves no live window; drop it
    return points


# ---------- cards ----------

CARD_KINDS = ["goal", "plan", "action", "observation", "decision", "error", "state", "handoff"]


def serialize_card(c: dict) -> str:
    """Stable text form. Never re-rendered after it is written (the log is append-only)."""
    lines = [f"### #{c['id']} [{c['kind']}] {c['title'].strip()}"]
    if c["body_md"].strip():
        lines.append(c["body_md"].strip())
    if c.get("verbatim"):
        lines.append("verbatim: " + " | ".join(f"`{v}`" for v in c["verbatim"]))
    tail = []
    if c.get("refs"):
        tail.append("refs: " + " ".join(f"#{r}" for r in c["refs"]))
    if c.get("supersedes") is not None:
        tail.append(f"supersedes #{c['supersedes']}")
    if tail:
        lines.append(" · ".join(tail))
    lines.append(f"(turns {c['src'][0]}–{c['src'][-1]})" if len(c["src"]) > 1 else f"(turn {c['src'][0]})")
    return "\n".join(lines)


def card0_text(traj: dict) -> str:
    return f"### #0 [goal] Original task (verbatim)\n{traj['task']}"


def board_blocks(traj: dict, batches: list[list[dict]]) -> list[str]:
    """Board as a list of text blocks: card #0, then one block per append batch."""
    return [card0_text(traj)] + ["\n\n".join(serialize_card(c) for c in b) for b in batches if b]


def norm_ws(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


# ---------- client + ledger ----------

class BudgetExceeded(RuntimeError):
    pass


class Ledger:
    """Token ledger; one JSON line per call. Stops everything past TOKEN_CAP."""

    def __init__(self, path: Path, cap: int = TOKEN_CAP):
        self.path, self.cap, self.lock = path, cap, threading.Lock()
        self.tokens = 0
        if path.exists():
            for line in path.read_text().splitlines():
                e = json.loads(line)
                self.tokens += e["in"] + e["out"] + e["cache_read"] + e["cache_write"]

    def check(self) -> None:
        if self.tokens > self.cap:
            raise BudgetExceeded(f"used {self.tokens} tokens of {self.cap}")

    def record(self, model: str, tag: str, usage: dict, seconds: float) -> None:
        u = {"in": usage.get("input_tokens", 0), "out": usage.get("output_tokens", 0),
             "cache_read": usage.get("cache_read_input_tokens", 0) or 0,
             "cache_write": usage.get("cache_creation_input_tokens", 0) or 0}
        with self.lock:
            self.tokens += sum(u.values())
            with self.path.open("a") as f:
                f.write(json.dumps({"model": model, "tag": tag, "s": round(seconds, 1), **u}) + "\n")


class ArkClient:
    """Minimal Anthropic-Messages client over stdlib HTTP for Volcengine Ark's agent-plan endpoint."""

    def __init__(self):
        env = dict(line.split("=", 1) for line in (Path(__file__).parent / ".env").read_text().split())
        self.base, self._key = env["ARK_BASE_URL"].rstrip("/"), env["ARK_API_KEY"]

    def create(self, body: dict) -> dict:
        req = urllib.request.Request(
            self.base + "/v1/messages", data=json.dumps(body).encode(),
            headers={"Authorization": f"Bearer {self._key}", "anthropic-version": "2023-06-01",
                     "content-type": "application/json"})
        for attempt in range(6):
            try:
                with urllib.request.urlopen(req, timeout=600) as r:
                    return json.loads(r.read())
            except urllib.error.HTTPError as e:
                msg = e.read()[:300].decode(errors="replace").replace(self._key, "<KEY>")
                if e.code in (429, 500, 502, 503, 504, 529) and attempt < 5:
                    time.sleep(5 * 2 ** attempt)
                    continue
                raise RuntimeError(f"HTTP {e.code}: {msg}") from None
            except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
                if attempt < 5:
                    time.sleep(5 * 2 ** attempt)
                    continue
                raise RuntimeError(f"network: {e}") from None


def make_client():
    if os.environ.get("S0_FAKE"):
        from fake_client import FakeClient
        return FakeClient()
    return ArkClient()


def _coerce(obj, schema):
    """Fix common type slips from models that don't enforce the tool schema (string for list, "3" for 3)."""
    t = schema.get("type")
    if t == "object" and isinstance(obj, dict):
        return {k: _coerce(v, schema.get("properties", {}).get(k, {})) for k, v in obj.items()}
    if t == "array":
        if isinstance(obj, str):
            try:
                v = json.loads(obj)
                obj = v if isinstance(v, list) else [obj]
            except ValueError:
                obj = [obj] if obj.strip() else []
        if isinstance(obj, list):
            return [_coerce(x, schema.get("items", {})) for x in obj]
    if t == "integer" and isinstance(obj, str) and obj.strip().lstrip("-").isdigit():
        return int(obj)
    return obj


def _missing(obj, schema) -> list[str]:
    """Shallow+nested check of required keys (Ark does not enforce tool schemas)."""
    if schema.get("type") == "object":
        if not isinstance(obj, dict):
            return ["<not an object>"]
        out = [k for k in schema.get("required", []) if k not in obj]
        for k, sub in schema.get("properties", {}).items():
            if k in obj:
                out += [f"{k}.{m}" for m in _missing(obj[k], sub)]
        return out
    if schema.get("type") == "array":
        if not isinstance(obj, list):
            return ["<not an array>"]
        return [m for x in obj for m in _missing(x, schema["items"])][:5]
    return []


def call_json(client, ledger: Ledger, *, model: str, tag: str, system: str, content: list[str], schema: dict,
              max_tokens: int = 16000, cache_last_block: bool = False) -> dict:
    """One structured call via a forced `emit` tool (Ark ignores output_config schemas). Retries once on bad output."""
    fields = ", ".join(schema.get("required", []))
    content = content[:-1] + [content[-1] + (
        "\n\n---\nYou are not the agent in this transcript: do not continue its work or use its tools. "
        f"Respond only by calling the `emit` tool with the fields: {fields}.")]
    blocks = [{"type": "text", "text": t} for t in content]
    if cache_last_block and len(blocks) >= 2:
        blocks[-2]["cache_control"] = {"type": "ephemeral"}   # breakpoint on the last board block
    body = {
        "model": model, "max_tokens": max_tokens,
        "system": [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
        "messages": [{"role": "user", "content": blocks}],
        "tools": [{"name": "emit", "description": "Return the result. Call exactly once.", "input_schema": schema}],
        "tool_choice": {"type": "any"},   # one tool, so "any" forces it; kimi-k3 rejects {"type": "tool"}
    }
    last_err = None
    for _ in range(2):
        ledger.check()
        t0 = time.time()
        resp = client.create(body)
        ledger.record(model, tag, resp.get("usage", {}), time.time() - t0)
        if resp.get("stop_reason") == "max_tokens":
            last_err = "hit max_tokens"
            continue
        use = next((b for b in resp.get("content", []) if b.get("type") == "tool_use"), None)
        if use is not None:
            obj = use["input"]
        else:  # some models occasionally answer in text despite tool_choice; accept a JSON object there
            text = "".join(b.get("text", "") for b in resp.get("content", []) if b.get("type") == "text")
            try:
                obj = json.loads(text[text.index("{"):text.rindex("}") + 1])
            except ValueError:
                last_err = f"no tool_use and no JSON (stop={resp.get('stop_reason')})"
                continue
        obj = _coerce(obj, schema)
        miss = _missing(obj, schema)
        if miss:
            last_err = f"missing {miss}"
            continue
        return obj
    raise RuntimeError(f"{tag}: {last_err}")


def call_text(client, ledger: Ledger, *, model: str, tag: str, system: str, content: list[str],
              max_tokens: int = 16000) -> str:
    """Plain text call (no tools). Used where the prompt itself forbids tool calls."""
    body = {"model": model, "max_tokens": max_tokens,
            "system": [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            "messages": [{"role": "user", "content": [{"type": "text", "text": t} for t in content]}]}
    ledger.check()
    t0 = time.time()
    resp = client.create(body)
    ledger.record(model, tag, resp.get("usage", {}), time.time() - t0)
    if resp.get("stop_reason") == "max_tokens":
        raise RuntimeError(f"{tag}: hit max_tokens")
    return "".join(b.get("text", "") for b in resp.get("content", []) if b.get("type") == "text")
