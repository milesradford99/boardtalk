"""Board arms: a scribe turns each agent turn into cards; at each fold the main model adds one handoff card.

Usage: python scribe.py flash|pro [trajectory_id ...]
Output: data/out/<tid>/board_<arm>.json with cards, append batches and the board snapshot at each fold.
"""
import json
import sys
from concurrent.futures import ThreadPoolExecutor

import common as c

SCRIBE_SYSTEM = """You are the scribe for a whiteboard that records a software agent's work loop.
The board is append-only and it REPLACES the raw transcript in the agent's memory after compaction:
anything you do not write down is gone for the agent (except card #0, the task, kept verbatim).

You receive the board so far, then ONE new agent turn (its message, tool calls and tool results).
Return 0-3 new cards for that turn. Rules:
- Record what a future reader needs to continue the work: what was done and learned, decisions and
  their reasons, failed attempts and why they failed, errors, and changes to the current state.
- Put exact identifiers in `verbatim`, copied character-for-character from the turn: file paths,
  function/class names, commands, error messages, test names, numbers, line numbers. Never invent or
  paraphrase a verbatim item.
- Keep `body_md` short and self-contained; do not repeat what earlier cards already say.
- `refs`: ids of earlier cards this one builds on. `supersedes`: id of an earlier card this one
  corrects or replaces, or -1 for none. Earlier cards are never edited.
- Return an empty list for turns with nothing new (e.g. a logged thought that only restates the plan).
"""

SCRIBE_SCHEMA = {
    "type": "object",
    "properties": {"cards": {"type": "array", "items": {
        "type": "object",
        "properties": {
            "kind": {"type": "string", "enum": [k for k in c.CARD_KINDS if k != "handoff"]},
            "title": {"type": "string"},
            "body_md": {"type": "string"},
            "verbatim": {"type": "array", "items": {"type": "string"}},
            "refs": {"type": "array", "items": {"type": "integer"}},
            "supersedes": {"type": "integer"},
        },
        "required": ["kind", "title", "body_md", "verbatim", "refs", "supersedes"],
        "additionalProperties": False,
    }}},
    "required": ["cards"],
    "additionalProperties": False,
}

HANDOFF_SYSTEM = """A software agent's context is about to be compacted. You are a note-taker, not the agent:
never continue its work or call its tools. Write ONE handoff card on the agent's behalf, based on its most recent work window: where things stand right now,
what it was about to do next, and open doubts or hypotheses. Copy exact identifiers into `verbatim`.
Be concise: this card is read together with the rest of the board."""

HANDOFF_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "body_md": {"type": "string"},
        "verbatim": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["title", "body_md", "verbatim"],
    "additionalProperties": False,
}

ARMS = c.SCRIBES


def handoff_card(client, ledger, traj: dict, fold_idx: int, window: list[dict]) -> dict:
    """Shared by both board arms (depends only on the raw window), so it is computed once and cached."""
    path = c.OUT / traj["trajectory_id"] / f"handoff_{fold_idx}.json"
    if path.exists():
        return json.loads(path.read_text())
    out = c.call_json(client, ledger, model=c.MAIN, tag=f"handoff:{traj['trajectory_id']}:{fold_idx}",
                      system=HANDOFF_SYSTEM, max_tokens=8000,
                      content=[c.card0_text(traj), "Most recent work window:\n\n" + c.render_turns(window)],
                      schema=HANDOFF_SCHEMA)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, indent=1))
    return out


def run(client, ledger, tid: str, arm: str) -> None:
    out_path = c.OUT / tid / f"board_{arm}.json"
    if out_path.exists():
        print(f"skip {tid} {arm} (done)")
        return
    traj = c.load(tid)
    folds = c.fold_points(traj)
    model = ARMS[arm]
    batches: list[list[dict]] = []   # one batch per turn (or per handoff); empty batches are kept for bookkeeping
    snapshots = {}                   # fold turn idx -> list of board blocks at that moment
    next_id, prev_fold = 1, -1
    failures: list[int] = []
    for t in traj["turns"]:
        blocks = c.board_blocks(traj, batches)
        try:
            new = c.call_json(client, ledger, model=model, tag=f"scribe:{arm}:{tid}:{t['idx']}",
                              system=SCRIBE_SYSTEM, max_tokens=8000,
                              content=blocks + ["New agent turn:\n\n" + c.render_turn(t)],
                              schema=SCRIBE_SCHEMA, cache_last_block=True)
        except RuntimeError as e:  # a scribe that fails on a turn simply writes nothing; counted in the report
            print(f"  scribe failure {tid} {arm} turn {t['idx']}: {e}")
            failures.append(t["idx"])
            new = {"cards": []}
        batch = []
        for card in new["cards"][:3]:
            card = {**card, "id": next_id, "src": [t["idx"]]}
            if card["supersedes"] < 0:
                card["supersedes"] = None
            batch.append(card)
            next_id += 1
        batches.append(batch)
        if t["idx"] in folds:
            window = [x for x in traj["turns"] if prev_fold < x["idx"] <= t["idx"]]
            try:
                h = handoff_card(client, ledger, traj, t["idx"], window)
            except RuntimeError as e:
                print(f"  handoff failure {tid} fold {t['idx']}: {e}")
                failures.append(f"handoff@{t['idx']}")
                h = None
            if h:
                batches.append([{"id": next_id, "kind": "handoff", "title": h["title"], "body_md": h["body_md"],
                             "verbatim": h["verbatim"], "refs": [], "supersedes": None,
                             "src": [window[0]["idx"], t["idx"]]}])
                next_id += 1
            snapshots[t["idx"]] = c.board_blocks(traj, batches)
            prev_fold = t["idx"]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps({"arm": arm, "model": model, "folds": folds, "batches": batches,
                                    "snapshots": snapshots, "failed_turns": failures}, indent=1))
    print(f"done {tid} {arm}: {next_id - 1} cards, tokens so far {ledger.tokens:,}")


def main() -> None:
    arm = sys.argv[1]
    ids = sys.argv[2:] or c.all_ids()
    client, ledger = c.make_client(), c.Ledger(c.OUT / "ledger.jsonl")
    c.OUT.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=10) as ex:
        for f in [ex.submit(run, client, ledger, tid, arm) for tid in ids]:
            f.result()


if __name__ == "__main__":
    main()
