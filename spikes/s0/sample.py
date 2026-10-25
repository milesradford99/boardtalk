"""Pick 10 trajectories (5 resolved, 5 unresolved, >=120 messages, distinct repos) with a fixed seed.

Stdlib only: rows come from the Hugging Face dataset viewer API, one row per request.
Output: data/trajectories/<trajectory_id>.json, normalized to a list of turns.
"""
import ast
import json
import random
import sys
import time
import urllib.request
from pathlib import Path

DATASET = "nebius/SWE-rebench-openhands-trajectories"
N_ROWS = 67074
SEED = 20261024
MIN_MESSAGES = 120
WANT = {True: 5, False: 5}
OUT = Path(__file__).parent / "data" / "trajectories"


def fetch_row(offset: int) -> dict:
    url = (
        "https://datasets-server.huggingface.co/rows?"
        f"dataset={DATASET}&config=default&split=train&offset={offset}&length=1"
    )
    for attempt in range(4):
        try:
            with urllib.request.urlopen(url, timeout=60) as r:
                return json.load(r)["rows"][0]["row"]
        except Exception as e:  # network flakiness; viewer API rate limits
            print(f"  retry {offset}: {e}", file=sys.stderr)
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"could not fetch row {offset}")


def parse_tool_calls(raw) -> list[dict]:
    if raw in (None, "None", ""):
        return []
    calls = raw if isinstance(raw, list) else ast.literal_eval(raw)
    out = []
    for c in calls:
        fn = c["function"]
        try:
            args = json.loads(fn["arguments"])
        except (json.JSONDecodeError, TypeError):
            args = {"_raw": fn["arguments"]}
        out.append({"id": c["id"], "name": fn["name"], "args": args})
    return out


def normalize(row: dict) -> dict:
    """Messages -> {task, turns[]}; a turn is one assistant message plus the tool results it caused."""
    msgs = row["trajectory"]
    task = next(m["content"] for m in msgs if m["role"] == "user")
    turns, cur = [], None
    for i, m in enumerate(msgs):
        if m["role"] == "assistant":
            cur = {"idx": len(turns), "msg_idx": i, "text": m["content"] or "",
                   "calls": parse_tool_calls(m.get("tool_calls")), "results": []}
            turns.append(cur)
        elif m["role"] == "tool" and cur is not None:
            cur["results"].append({"name": m.get("name"), "content": m["content"] or ""})
    return {"trajectory_id": row["trajectory_id"], "instance_id": row["instance_id"],
            "repo": row["repo"], "resolved": bool(row["resolved"]), "n_messages": len(msgs),
            "task": task, "turns": turns}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rng = random.Random(SEED)
    picked, repos, tried = {True: [], False: []}, set(), 0
    while any(len(picked[k]) < WANT[k] for k in WANT):
        offset = rng.randrange(N_ROWS)
        tried += 1
        row = fetch_row(offset)
        res = bool(row["resolved"])
        if len(row["trajectory"]) < MIN_MESSAGES or row["repo"] in repos or len(picked[res]) >= WANT[res]:
            continue
        t = normalize(row)
        t["offset"] = offset
        (OUT / f"{t['trajectory_id']}.json").write_text(json.dumps(t, indent=1))
        picked[res].append(t["trajectory_id"])
        repos.add(row["repo"])
        print(f"picked offset={offset} repo={row['repo']} resolved={res} msgs={t['n_messages']} turns={len(t['turns'])}")
    print(f"done: tried {tried} rows")


if __name__ == "__main__":
    main()
