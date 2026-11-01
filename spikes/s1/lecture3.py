"""S1c: S1b plus three fixes. (1) Note strings are checked against the session (notes_of in lecture2.py);
(2) a rejected card or mark gets one retry with the reason; (3) intent is written by one dedicated call.

Usage: S1_BOARD=lecture3 python lecture3.py [trajectory_id ...]
Output: data/out/<tid>/lecture3.json
"""
import json
import sys
from concurrent.futures import ThreadPoolExecutor

import base as b
from base import c
from lecture2 import SCHEMA, SYSTEM as S1B_SYSTEM, WINDOW, apply, notes_of, session_so_far

OLD_INTENT = """- intent: what the user asked for. Written from the request (src_notes [-1]) on the first call, 1-3
  cards. Cover each of: the behaviour to fix or add; files or areas not to touch; tests to write, run
  or keep passing; "minimal change" or similar constraints, when the request states them.
"""
assert OLD_INTENT in S1B_SYSTEM
SYSTEM = S1B_SYSTEM.replace(OLD_INTENT, """- intent: already on the board, written from the request by a separate step. Append one only if
  the notes show the request was reinterpreted.
""")

INTENT_SYSTEM = """You write the opening cards of a whiteboard: what the user asked a software agent to do.
You get only the request. Return 1-3 cards of kind "intent", ids from 1, src_notes [-1], revises -1,
heads_label "", and no marks. Title: a noun phrase of at most 6 words. Body: a markdown list.

List EVERY separate thing the request asks for or constrains, however small, each as its own line:
behaviour to fix or add (each case and each API surface separately), behaviour that must stay as it
is (compatibility, defaults), documentation to update, tests to write, run or keep passing, files or
areas not to touch, and "minimal change" or similar. Use only what the request says; add nothing
from your own knowledge of the project or how it was later solved. Skip instructions about the
environment. Exact strings go in `backticks`, copied character for character, and in `verbatim`."""


def write(client, ledger, tag, system, content, cards, marks, notes, traj, turn, session, dropped, retried):
    """One call and at most one retry. An operation counts as dropped only if the retry didn't replace it."""
    rejected = []
    try:
        out = c.call_json(client, ledger, model=b.MODEL, tag=tag, system=system, max_tokens=12000,
                          schema=SCHEMA, cache_last_block=True, content=content)
    except RuntimeError as e:
        print(f"  writer failure {tag}: {e}")
        return [], [], 0, False
    nc, nm = apply(out, cards, marks, notes, traj["task"], turn, rejected, session)
    emitted = len(out["cards"]) + len(out["marks"])
    if not rejected:
        return nc, nm, emitted, True
    retried.extend(rejected)
    now_cards, now_marks = cards + nc, marks + nm
    nxt = max((x["id"] for x in now_cards), default=0) + 1
    fix = "\n".join(f"- {r['why']}: {json.dumps(r['op'], ensure_ascii=False)}" for r in rejected)
    again = (f"\n\n---\nThese operations were rejected:\n{fix}\n\nReturn corrected versions of only these. "
             f"Next id: {nxt}. Exact strings must be copied from the cited notes or the request; if a string "
             "cannot be copied, write it as plain words without backticks. A mark's snippet must be copied "
             "from its card's body. Cards accepted in this call are already on the board.")
    try:
        out2 = c.call_json(client, ledger, model=b.MODEL, tag=tag + ":retry", system=system, max_tokens=12000,
                           schema=SCHEMA, cache_last_block=True, content=content[:-1] + [content[-1] + again])
        still = []
        nc2, nm2 = apply(out2, now_cards, now_marks, notes, traj["task"], turn, still, session)
    except RuntimeError as e:
        print(f"  retry failure {tag}: {e}")
        nc2, nm2 = [], []
    recovered = len(nc2) + len(nm2)
    dropped.extend(rejected[recovered:])
    return nc + nc2, nm + nm2, emitted, True


def run(client, ledger, tid: str) -> None:
    path = b.OUT / tid / "lecture3.json"
    if path.exists():
        print(f"skip {tid} (done)")
        return
    traj = c.load(tid)
    all_notes = notes_of(tid)
    notes = {n["id"]: n for n in all_notes}
    cards, marks, dropped, retried, failed, per_turn = [], [], [], [], [], []
    first, last_idx, prev = traj["turns"][0]["idx"], traj["turns"][-1]["idx"], -1
    nc, nm, emitted, ok = write(client, ledger, f"lecture3:{tid}:intent", INTENT_SYSTEM,
                                [traj["task"], "Write the intent cards for this request."], cards, marks, notes,
                                traj, first, c.norm_ws(traj["task"]), dropped, retried)
    cards += nc
    marks += nm
    if not ok:
        failed.append("intent")
    per_turn.append({"turn": first, "cards": [x["id"] for x in nc], "marks": len(nm), "emitted": emitted})
    for t in traj["turns"]:
        if (t["idx"] + 1) % WINDOW and t["idx"] != last_idx:
            continue
        new = [n for n in all_notes if prev < n["src"][0] <= t["idx"]]
        prev = t["idx"]
        if not new:
            continue
        nxt = max((x["id"] for x in cards), default=0) + 1
        n_heads = sum(1 for x in cards if x["kind"] == "heads_up")
        final = " The session ends after these notes." if t["idx"] == last_idx else ""
        head = (f"## New notes, up to agent turn {t['idx']} (next id: {nxt}).{final} Cards so far: {len(cards)} "
                f"(a long session ends near 15); You-should-know notes so far: {n_heads} of at most 3.\n\n")
        content = [b.task_block(traj).replace("src_turns -1", "src_notes -1"),
                   "## The lecture board so far\n\n" + b.serialize(cards, marks),
                   head + "\n\n".join(b.note_text(n) for n in new)]
        nc, nm, emitted, ok = write(client, ledger, f"lecture3:{tid}:{t['idx']}", SYSTEM, content, cards, marks,
                                    notes, traj, t["idx"], session_so_far(traj, t["idx"]), dropped, retried)
        if not ok:
            failed.append(t["idx"])
        cards += nc
        marks += nm
        p = next((x for x in per_turn if x["turn"] == t["idx"]), None)
        if p:   # a session's first turn can also end a window
            p["cards"] += [x["id"] for x in nc]
            p["marks"] += len(nm)
            p["emitted"] += emitted
        else:
            per_turn.append({"turn": t["idx"], "cards": [x["id"] for x in nc], "marks": len(nm), "emitted": emitted})
    path.write_text(json.dumps({"model": b.MODEL, "window": WINDOW, "cards": cards, "marks": marks, "dropped": dropped,
                                "retried": retried, "failed_turns": failed, "per_turn": per_turn}, indent=1))
    print(f"done {tid}: {len(cards)} cards, {len(marks)} marks, {len(retried)} retried, {len(dropped)} dropped, "
          f"tokens so far {ledger.tokens:,}")


def main() -> None:
    ids = sys.argv[1:] or c.all_ids()
    client, ledger = c.make_client(), b.ledger()
    with ThreadPoolExecutor(max_workers=10) as ex:
        for f in [ex.submit(run, client, ledger, tid) for tid in ids]:
            f.result()


if __name__ == "__main__":
    main()
