"""S1b stage two: write lecture cards from S0's per-turn notes, every WINDOW agent turns and at the end.

Stage one is S0's flash notes (board_flash.json), reused unchanged; handoff cards are left out (they
came from another model). Cards cite note ids; their exact strings must occur in the cited notes or
the request, checked here. Output: data/out/<tid>/lecture2.json, readable by judge/check/render
(src_turns is derived from the cited notes).

Usage: python lecture2.py [trajectory_id ...]
"""
import json
import sys
from concurrent.futures import ThreadPoolExecutor

import base as b
from base import c
from scribe import SCHEMA as S1_SCHEMA

WINDOW = 5

SYSTEM = """You are the lecture writer for boardtalk, a whiteboard that shows the user what a software
agent is designing, as an append-only lecture. The reader is the person who asked for the work. They
want the design (what they asked, what the agent understood and decided, what the evidence shows, and
what they might miss), not the agent's steps.

A note-taker has already written exact per-turn notes of the session ("note N"; cite them by N). Each call gives you the
user's request, the lecture board so far, and the notes added since your last call. You append 0-3
cards and 0-2 marks. Append only what a reviewer would keep.

Card kinds:
- intent: what the user asked for. Written from the request (src_notes [-1]) on the first call, 1-3
  cards. Cover each of: the behaviour to fix or add; files or areas not to touch; tests to write, run
  or keep passing; "minimal change" or similar constraints, when the request states them.
- design: where and why it breaks, the decision taken and the options rejected, the change made.
- evidence: a result that changes what is known: the bug reproduced, the fix verified, a regression
  found. Not one card per test run; usually 2-4 per session. With exact numbers.
- heads_up: "You should know": something true that the user may miss and would want to know, which
  the agent has NOT said itself: a tradeoff chosen without saying so, a limit or untested case, a
  result that may be off (a test that did not really run, a fix checked only with the agent's own
  script, a requirement not yet met). heads_label: one or two words (Tradeoff, Limit, Unverified,
  Scope, Risk). AT MOST 3 PER SESSION (count given below), for what matters most to the outcome,
  never a second note on the same concern.
- question: something the agent needs the user to answer.

Rules:
- A whole session usually needs 8-15 cards, so MOST CALLS APPEND 0 OR 1 CARD. Append a card only when
  a decision, a result or a risk changes; never for progress ("fix not applied yet", "located the
  method", "edit window"). Code locations (line numbers, enclosing functions) go into a card only
  when they are the point of a decision. One card per idea; never narrate steps.
- Title: a noun phrase of at most 6 words. Body: at most 3 markdown lines of at most ~90 characters;
  exact strings in `backticks`.
- src_notes: the note ids each card rests on (-1 = the request). Cite every note a claim depends on,
  including earlier ones.
- Exact strings (in backticks and in `verbatim`) must be copied character for character from the
  cited notes or the request. Never join, shorten or invent them (no `file.py:123` unless that exact
  text appears).
- Append-only: earlier cards are never edited. When new notes overturn a design or evidence card,
  append a new card with `revises` = its id (title like "Decision, revised"); otherwise -1.
  heads_label = "" unless kind is heads_up.
- ids: number new cards consecutively from the "next id" given.
- Marks decorate an existing card or one you append now: a `box` around the one key fact, or a
  `highlight` on an intent card's text when the work now meets it. `snippet` is copied exactly from
  that card's body (at most 40 characters, no backticks or list markers).
- Marks cite src_notes too."""


def _swap(schema: dict) -> dict:
    """S1's schema with src_turns renamed to src_notes."""
    s = json.loads(json.dumps(schema))
    for part in ("cards", "marks"):
        item = s["properties"][part]["items"]
        item["properties"]["src_notes"] = item["properties"].pop("src_turns")
        item["required"] = ["src_notes" if r == "src_turns" else r for r in item["required"]]
    return s


SCHEMA = _swap(S1_SCHEMA)


def notes_of(tid: str) -> list[dict]:
    bf = json.loads((c.OUT / tid / "board_flash.json").read_text())
    return [x for batch in bf["batches"] for x in batch if x["kind"] != "handoff"]


def chips(md: str) -> list[str]:
    return [s for i, s in enumerate(md.split("`")) if i % 2]


def check_card(x: dict, notes: dict, task: str, turn: int) -> str | None:
    """Reason to drop the card, or None. Exact strings must occur in the cited notes or the request."""
    cited = [n for n in x["src_notes"] if n != b.REQUEST]
    if any(n not in notes or notes[n]["src"][0] > turn for n in cited):
        return f"cites unknown note {[n for n in cited if n not in notes]}"
    if not x["src_notes"]:
        return "no src_notes"
    pool = c.norm_ws("\n".join([b.note_text(notes[n]) for n in cited] + [task]))   # the request is always citable
    bad = [v for v in dict.fromkeys(x["verbatim"] + chips(x["body_md"])) if v.strip() and c.norm_ws(v) not in pool]
    return f"exact strings not in cited sources: {bad[:3]}" if bad else None


def apply(out: dict, cards: list, marks: list, notes: dict, task: str, turn: int, dropped: list):
    new_cards, new_marks = [], []
    ids = {x["id"]: x for x in cards}
    revised = {x["revises"] for x in cards if x["revises"] is not None}

    def drop(op, why):
        dropped.append({"turn": turn, "why": why, "op": op})

    for x in out["cards"][:3]:
        last = max(ids, default=0)
        why = None
        if x["id"] <= last:
            why = f"id {x['id']} not after {last}"
        elif not x["title"].strip() or not x["body_md"].strip():
            why = "empty title or body"
        elif x["revises"] >= 0 and (x["revises"] not in ids or x["revises"] in revised):
            why = f"revises unknown or already revised #{x['revises']}"
        else:
            why = check_card(x, notes, task, turn)
        if why:
            drop(x, why)
            continue
        src_turns = sorted({b.REQUEST} if b.REQUEST in x["src_notes"] else set()) + sorted(
            {notes[n]["src"][0] for n in x["src_notes"] if n != b.REQUEST})
        card = {**x, "src_turns": src_turns, "revises": x["revises"] if x["revises"] >= 0 else None,
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
    path = b.OUT / tid / "lecture2.json"
    if path.exists():
        print(f"skip {tid} (done)")
        return
    traj = c.load(tid)
    all_notes = notes_of(tid)
    notes = {n["id"]: n for n in all_notes}
    cards, marks, dropped, failed, per_turn = [], [], [], [], []
    last_idx, prev = traj["turns"][-1]["idx"], -1
    for t in traj["turns"]:
        if (t["idx"] + 1) % WINDOW and t["idx"] != last_idx:
            continue
        new = [n for n in all_notes if prev < n["src"][0] <= t["idx"]]
        prev = t["idx"]
        if not new and cards:
            per_turn.append({"turn": t["idx"], "cards": [], "marks": 0, "emitted": 0})
            continue
        nxt = max((x["id"] for x in cards), default=0) + 1
        n_heads = sum(1 for x in cards if x["kind"] == "heads_up")
        final = " The session ends after these notes." if t["idx"] == last_idx else ""
        head = (f"## New notes, up to agent turn {t['idx']} (next id: {nxt}).{final} Cards so far: {len(cards)} "
                f"(a long session ends near 15); "
                f"You-should-know notes so far: {n_heads} of at most 3.\n\n")
        board = b.serialize(cards, marks) or "(empty: start with the intent cards)"
        try:
            out = c.call_json(client, ledger, model=b.MODEL, tag=f"lecture2:{tid}:{t['idx']}", system=SYSTEM,
                              max_tokens=6000, schema=SCHEMA, cache_last_block=True,
                              content=[b.task_block(traj).replace("src_turns -1", "src_notes -1"),
                                       "## The lecture board so far\n\n" + board,
                                       head + ("\n\n".join(b.note_text(n) for n in new) or "(no new notes)")])
        except RuntimeError as e:
            print(f"  writer failure {tid} turn {t['idx']}: {e}")
            failed.append(t["idx"])
            out = {"cards": [], "marks": []}
        nc, nm = apply(out, cards, marks, notes, traj["task"], t["idx"], dropped)
        cards += nc
        marks += nm
        per_turn.append({"turn": t["idx"], "cards": [x["id"] for x in nc], "marks": len(nm),
                         "emitted": len(out["cards"]) + len(out["marks"])})
    path.write_text(json.dumps({"model": b.MODEL, "window": WINDOW, "cards": cards, "marks": marks,
                                "dropped": dropped, "failed_turns": failed, "per_turn": per_turn}, indent=1))
    print(f"done {tid}: {len(cards)} cards, {len(marks)} marks, {len(dropped)} dropped, tokens so far {ledger.tokens:,}")


def main() -> None:
    ids = sys.argv[1:] or c.all_ids()
    client, ledger = c.make_client(), b.ledger()
    with ThreadPoolExecutor(max_workers=10) as ex:
        for f in [ex.submit(run, client, ledger, tid) for tid in ids]:
            f.result()


if __name__ == "__main__":
    main()
