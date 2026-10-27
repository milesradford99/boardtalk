"""Shared pieces for spike S1: paths, the lecture board's text form, and S0's client, ledger and rendering."""
import json
import os
import re
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent / "s0"))  # after s1, so s1/scribe.py wins
import common as c  # noqa: E402  (S0: load, render_turn, call_json, Ledger, make_client)

DATA = Path(__file__).parent / "data"
OUT = Path(os.environ.get("S1_OUT", DATA / "out"))
TOKEN_CAP = 15_000_000
BOARD = os.environ.get("S1_BOARD", "lecture")   # "lecture" (S1) or "lecture2" (S1b, written from notes)
S1B_CAP = 6_000_000
MODEL = "deepseek-v4.1-flash"     # every S1 call: scribe, judge, answering (user's choice)
KINDS = ["intent", "design", "evidence", "heads_up", "question"]
EYEBROW = {"intent": "Your intent", "design": "Agent's design", "evidence": "Evidence",
           "heads_up": "You should know", "question": "For you"}
REQUEST = -1                      # src_turns value for the user's request (the task)


def ledger() -> c.Ledger:
    """S1 and S1b keep separate ledgers and caps."""
    OUT.mkdir(parents=True, exist_ok=True)
    if BOARD == "lecture":
        return c.Ledger(OUT / "ledger.jsonl", cap=TOKEN_CAP)
    return c.Ledger(OUT / "ledger_s1b.jsonl", cap=S1B_CAP)


def suffix() -> str:
    """Suffix for per-board output files: "" for S1, "_2" for S1b."""
    return "" if BOARD == "lecture" else "_2"


def lecture(tid: str, board: str | None = None) -> dict:
    return json.loads((OUT / tid / f"{board or BOARD}.json").read_text())


def note_text(n: dict) -> str:
    """An S0 per-turn note, labelled "note N" so its id is not mistaken for a card id."""
    lines = [f"### note {n['id']} [{n['kind']}] {n['title'].strip()}", n["body_md"].strip()]
    if n.get("verbatim"):
        lines.append("verbatim: " + " | ".join(f"`{v}`" for v in n["verbatim"]))
    lines.append(f"(turn {n['src'][0]})")
    return "\n".join(lines)


def plain(md: str) -> str:
    """Text as the board shows it: no backticks, no list markers. Mark snippets must occur in this."""
    return "\n".join(re.sub(r"^\s*[-*]\s+", "", line) for line in md.replace("`", "").split("\n"))


def turns_label(src: list[int]) -> str:
    names = ["request" if s == REQUEST else str(s) for s in src]
    return "turn " + names[0] if len(names) == 1 else "turns " + ", ".join(names)


def serialize(cards: list[dict], marks: list[dict]) -> str:
    """The board as the scribe and the answerer read it. Append-only: a later card never changes an earlier
    card's text; revisions and marks are listed with the card that made them."""
    revised_by = {x["revises"]: x["id"] for x in cards if x.get("revises") is not None}
    out = []
    for x in cards:
        label = f" · {x['heads_label']}" if x.get("heads_label") else ""
        head = f"### #{x['id']} [{x['kind']}{label}] {x['title'].strip()}"
        if x.get("revises") is not None:
            head += f" (revises #{x['revises']})"
        src = ("notes " + ", ".join("request" if n == REQUEST else str(n) for n in x["src_notes"])
               if "src_notes" in x else turns_label(x["src_turns"]))
        lines = [head, x["body_md"].strip(), f"({src})"]
        if x["id"] in revised_by:
            lines.append(f"[superseded by #{revised_by[x['id']]}]")
        for m in marks:
            if m["card"] == x["id"]:
                lines.append(f"[{m['type']}: \"{m['snippet']}\"]")
        out.append("\n".join(lines))
    return "\n\n".join(out)


def task_block(traj: dict) -> str:
    return "## The user's request (turn \"request\", src_turns -1)\n\n" + traj["task"]


def source_text(traj: dict, src: list[int]) -> str:
    by_idx = {t["idx"]: t for t in traj["turns"]}
    parts = [task_block(traj) if s == REQUEST else c.render_turn(by_idx[s]) for s in sorted(set(src)) if
             s == REQUEST or s in by_idx]
    return "\n\n".join(parts)
