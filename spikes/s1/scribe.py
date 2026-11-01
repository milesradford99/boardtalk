"""Lecture scribe: one call per agent turn appends design-level cards and marks to the board.

Usage: python scribe.py [trajectory_id ...]
Output: data/out/<tid>/lecture.json with every card and mark, the operations dropped as invalid,
and per-turn bookkeeping. Append-only rules are checked here, in code; nothing is ever repaired.
"""
import json
import sys
from concurrent.futures import ThreadPoolExecutor

import base as b
from base import c

SYSTEM = """You are the scribe for boardtalk, a whiteboard that shows the user what a software agent is
designing, as an append-only lecture. The reader is the person who asked for the work. They want the
design (what they asked, what the agent understood and decided, what the evidence shows, and what
they might miss), not the agent's steps.

Each call gives you the user's request, the board so far, and ONE new agent turn (its message, tool
calls and results). You append 0-3 cards and 0-2 marks. MOST TURNS APPEND NOTHING: append only when
this turn establishes something a reviewer would keep.

Card kinds:
- intent: what the user asked for: the problem, constraints, and what "done" means. Written from the
  request (src_turns [-1]) on the first call, 1-3 cards. Later only if the request is reinterpreted.
- design: the agent's understanding and decisions: where and why it breaks, the decision taken and the
  options it rejected, the change made (files, functions).
- evidence: a result that changes what is known about the design: the bug reproduced, the fix
  verified, a regression found. Not one card per test run: a further run gets a card only when its
  result differs from what the board already says (e.g. a wider suite fails). Usually 2-4 evidence
  cards per session. With exact numbers.
- heads_up: "You should know": something true that the user may miss and would want to know, which
  the agent has NOT said itself: a tradeoff chosen without saying so, a limit or untested case, a
  result that may be off (a test that did not really run, a fix checked only with the agent's own
  script, a requirement from the request not yet met). Set heads_label to one or two words
  (Tradeoff, Limit, Unverified, Scope, Risk). AT MOST 3 PER SESSION (the count so far is given
  below): keep them for what matters most to the outcome, never about the agent's scratch work, and
  never a second note on the same concern.
- question: something the agent needs the user to answer.

Rules:
- A whole session usually needs 8-15 cards. One card per idea: when a turn only refines what a card
  already says, append nothing.
- Never one card per tool call, and never narrate steps ("Ran grep", "Opened the file", "Next I will").
  A card is a statement. Title: a noun phrase of at most 6 words. Body: at most 3 markdown lines of
  at most ~90 characters each; put exact strings in `backticks`.
- Exact strings (paths, names, commands, error text, numbers) are copied character for character from
  the request or the turns, and also listed in `verbatim`. Never invent or paraphrase them.
- Append-only: earlier cards are never edited. When this turn overturns an earlier design or evidence
  card, append a new card with `revises` = that card's id (title it like "Decision, revised").
  Otherwise revises = -1. heads_label = "" unless kind is heads_up.
- ids: number new cards consecutively, starting at the "next id" given below.
- Marks decorate an existing card (or one you append in this call): a `box` around the one key fact of
  a card, or a `highlight` on an intent card's text when the work now meets that requirement.
  `snippet` is copied exactly, character for character, from that card's body as you wrote it: a
  short exact string such as the text of one code chip (at most 40 characters), without backticks or
  list markers. Never reword it.
- src_turns: the turn numbers each card or mark rests on (-1 = the user's request)."""

SCHEMA = {
    "type": "object",
    "properties": {
        "cards": {"type": "array", "items": {
            "type": "object",
            "properties": {
                "id": {"type": "integer"},
                "kind": {"type": "string", "enum": b.KINDS},
                "title": {"type": "string"},
                "body_md": {"type": "string"},
                "verbatim": {"type": "array", "items": {"type": "string"}},
                "src_turns": {"type": "array", "items": {"type": "integer"}},
                "revises": {"type": "integer"},
                "heads_label": {"type": "string"},
            },
            "required": ["id", "kind", "title", "body_md", "verbatim", "src_turns", "revises", "heads_label"],
            "additionalProperties": False,
        }},
        "marks": {"type": "array", "items": {
            "type": "object",
            "properties": {
                "type": {"type": "string", "enum": ["box", "highlight"]},
                "card": {"type": "integer"},
                "snippet": {"type": "string"},
                "src_turns": {"type": "array", "items": {"type": "integer"}},
            },
            "required": ["type", "card", "snippet", "src_turns"],
            "additionalProperties": False,
        }},
    },
    "required": ["cards", "marks"],
    "additionalProperties": False,
}


def apply(out: dict, cards: list[dict], marks: list[dict], turn: int, dropped: list[dict]) -> tuple[list, list]:
    """Validate one emission against the board. Valid operations are appended; invalid ones are dropped and
    recorded with the reason. Returns the new cards and marks."""
    new_cards, new_marks = [], []
    ids = {x["id"]: x for x in cards}
    revised = {x["revises"] for x in cards if x["revises"] is not None}

    def drop(op, why):
        dropped.append({"turn": turn, "why": why, "op": op})

    for x in out["cards"][:3]:
        last = max(ids, default=0)
        src = [s for s in x["src_turns"] if s == b.REQUEST or 0 <= s <= turn]
        if x["id"] <= last:
            drop(x, f"id {x['id']} not after {last}")
        elif not x["title"].strip() or not x["body_md"].strip():
            drop(x, "empty title or body")
        elif x["revises"] >= 0 and x["revises"] not in ids:
            drop(x, f"revises unknown #{x['revises']}")
        elif x["revises"] >= 0 and x["revises"] in revised:
            drop(x, f"#{x['revises']} already revised")
        elif not src:
            drop(x, f"src_turns {x['src_turns']} outside request..{turn}")
        else:
            card = {**x, "src_turns": src, "revises": x["revises"] if x["revises"] >= 0 else None,
                    "heads_label": x["heads_label"].strip() if x["kind"] == "heads_up" else "", "turn": turn}
            ids[card["id"]] = card
            if card["revises"] is not None:
                revised.add(card["revises"])
            new_cards.append(card)
    for m in out["marks"][:2]:
        target = ids.get(m["card"])
        snip = m["snippet"].replace("`", "").strip()
        if target is None:
            drop(m, f"mark on unknown #{m['card']}")
        elif not snip or "\n" in snip or len(snip) > 80:
            drop(m, "snippet empty, multi-line or too long")
        elif snip not in b.plain(target["body_md"]):
            drop(m, "snippet not in card body")
        else:
            new_marks.append({**m, "snippet": snip, "turn": turn})
    return new_cards, new_marks


def run(client, ledger, tid: str) -> None:
    path = b.OUT / tid / "lecture.json"
    if path.exists():
        print(f"skip {tid} (done)")
        return
    traj = c.load(tid)
    cards, marks, dropped, failed, per_turn = [], [], [], [], []
    last_idx = traj["turns"][-1]["idx"]
    for t in traj["turns"]:
        board = b.serialize(cards, marks) or "(empty: this is the first call; start with the intent cards)"
        nxt = max((x["id"] for x in cards), default=0) + 1
        final = " This is the agent's final turn: the session ends here." if t["idx"] == last_idx else ""
        n_heads = sum(1 for x in cards if x["kind"] == "heads_up")
        final += f" Cards so far: {len(cards)}; You-should-know notes so far: {n_heads} of at most 3."
        try:
            out = c.call_json(client, ledger, model=b.MODEL, tag=f"scribe:{tid}:{t['idx']}", system=SYSTEM,
                              max_tokens=6000, schema=SCHEMA, cache_last_block=True,
                              content=[b.task_block(traj), "## The board so far\n\n" + board,
                                       f"## New agent turn (next id: {nxt}).{final}\n\n" + c.render_turn(t)])
        except RuntimeError as e:   # a failed turn writes nothing; counted in the report
            print(f"  scribe failure {tid} turn {t['idx']}: {e}")
            failed.append(t["idx"])
            out = {"cards": [], "marks": []}
        nc, nm = apply(out, cards, marks, t["idx"], dropped)
        cards += nc
        marks += nm
        per_turn.append({"turn": t["idx"], "cards": [x["id"] for x in nc], "marks": len(nm),
                         "emitted": len(out["cards"]) + len(out["marks"])})
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"model": b.MODEL, "cards": cards, "marks": marks, "dropped": dropped,
                                "failed_turns": failed, "per_turn": per_turn}, indent=1))
    print(f"done {tid}: {len(cards)} cards, {len(marks)} marks, {len(dropped)} dropped, "
          f"tokens so far {ledger.tokens:,}")


def main() -> None:
    ids = sys.argv[1:] or c.all_ids()
    client, ledger = c.make_client(), b.ledger()
    with ThreadPoolExecutor(max_workers=10) as ex:
        for f in [ex.submit(run, client, ledger, tid) for tid in ids]:
            f.result()


if __name__ == "__main__":
    main()
