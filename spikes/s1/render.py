"""Render each scribe log onto the board prototype: agent text -> caption, tool calls -> activity line,
cards and marks -> the board. One self-contained page per trajectory, in data/out/boards/<tid>.html.

Usage: python render.py [trajectory_id ...]
"""
import json
import re
import sys
from pathlib import Path

import base as b
from base import c

PROTO = Path(__file__).resolve().parents[2] / "docs" / "design" / "prototypes" / "board.html"
START, END = "  const ASK = ", "  // ---------- geometry ----------"
TOOL_MS, MAX_TOOLS = 450, 5


def clip(s: str, n: int) -> str:
    s = re.sub(r"\s+", " ", s).strip()
    return s if len(s) <= n else s[:n - 1].rstrip() + "…"


def caption(text: str) -> str:
    """Agent text as speech: markdown headings, emphasis and emoji dropped."""
    text = re.sub(r"(?m)^\s*#+\s*", "", text)
    text = re.sub(r"[*_]{2}|[\U0001F300-\U0001FAFF☀-➿]️?", "", text)
    return clip(text, 220)


def tool_label(call: dict) -> str:
    a = call["args"] if isinstance(call["args"], dict) else {}
    if "command" in a and "path" in a:
        detail = f"{a['command']} {a['path']}"
    else:
        detail = next((v for v in a.values() if isinstance(v, str) and v.strip()), "")
    return clip(f"{call['name']} {detail}", 72)


def request_text(task: str) -> str:
    m = re.search(r"<issue_description>(.*?)</issue_description>", task, re.S)
    return (m.group(1) if m else task).strip()


def steps(traj: dict, lec: dict) -> list[dict]:
    cards = {x["id"]: x for x in lec["cards"]}
    marks_at = {}
    for m in lec["marks"]:
        marks_at.setdefault(m["turn"], []).append(m)
    by_idx = {t["idx"]: t for t in traj["turns"]}
    out, pending = [{"user": request_text(traj["task"])}], []
    for p in lec["per_turn"]:
        t = by_idx[p["turn"]]
        pending += [tool_label(x) for x in t["calls"]]
        if not p["cards"] and p["turn"] not in marks_at:
            continue
        shown = pending[-MAX_TOOLS:]
        if len(pending) > MAX_TOOLS:
            shown = [f"… {len(pending) - MAX_TOOLS} earlier tool calls"] + shown
        st = {"tools": [[label, TOOL_MS] for label in shown]}
        if t["text"].strip():
            st["say"] = caption(t["text"])
        st["write"] = []
        for i in p["cards"]:
            x = cards[i]
            w = {"id": f"c{i}", "from": b.EYEBROW[x["kind"]], "title": x["title"].strip(), "body": x["body_md"].strip()}
            if x["revises"] is not None:
                w["revises"] = f"c{x['revises']}"
            if x["kind"] == "heads_up":
                w["heads"] = x["heads_label"] or "Note"
            st["write"].append(w)
        st["ann"] = [{"type": "box" if m["type"] == "box" else "hl", "id": f"c{m['card']}", "text": m["snippet"]}
                     for m in marks_at.get(p["turn"], [])]
        out.append(st)
        pending = []
    last = traj["turns"][-1]
    if pending or last["text"].strip():
        out.append({"tools": [[label, TOOL_MS] for label in pending[-MAX_TOOLS:]], "say": caption(last["text"])})
    return out


def page(traj: dict, lec: dict) -> str:
    html = PROTO.read_text()
    i, j = html.index(START), html.index(END)
    data = json.dumps(steps(traj, lec), ensure_ascii=False, indent=1).replace("</", "<\\/")
    html = html[:i] + f"  const STEPS = {data};\n\n" + html[j:]
    title = f"{traj['repo']}: {'resolved' if traj['resolved'] else 'unresolved'}"
    html = html.replace('<span class="ttl">Fix DAS crash on empty lists</span>', f'<span class="ttl">{title}</span>')
    html = html.replace("<title>Boardtalk Live Board</title>", f"<title>{traj['repo'].split('/')[-1]} board</title>")
    return "<!doctype html>\n" + html


def main() -> None:
    ids = sys.argv[1:] or c.all_ids()
    d = b.OUT / "boards"
    d.mkdir(parents=True, exist_ok=True)
    for tid in ids:
        (d / f"{tid}.html").write_text(page(c.load(tid), b.lecture(tid)))
        print(f"rendered {tid}")


if __name__ == "__main__":
    main()
