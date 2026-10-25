"""Hindsight questions: Kimi reads the full rendered trajectory and writes 20 questions about early details.

Usage: python questions.py [trajectory_id ...]
Output: data/out/<tid>/questions.json
"""
import json
import sys
from concurrent.futures import ThreadPoolExecutor

import common as c

CATEGORIES = ["identifier", "decision", "dead_end", "state"]

Q_SYSTEM = """You write evaluation questions for an AI agent's memory. You get the full transcript of
a software agent working on a task. Later the agent will only see a compressed memory of the early
part, and we test what survived.

Write exactly 20 questions, 5 per category, whose answers are found in turns 0..{cutoff} ONLY, and
that an agent continuing this work could plausibly need:
- identifier: an exact file path, function/class/test name, command, error message, or number.
  `exact` = the shortest distinctive string (<= 60 chars) that must appear verbatim in a correct
  answer, copied character-for-character from the transcript.
- decision: what was decided and why.
- dead_end: an approach that was tried and failed or was abandoned, and why.
- state: what had been established or completed by turn {cutoff} (not later).
Avoid questions answerable from the task description alone. `gold` is a complete short answer.
`exact` is "" for non-identifier questions. `src_turn` is the turn where the answer appears."""

Q_SCHEMA = {
    "type": "object",
    "properties": {"questions": {"type": "array", "items": {
        "type": "object",
        "properties": {
            "category": {"type": "string", "enum": CATEGORIES},
            "question": {"type": "string"},
            "gold": {"type": "string"},
            "exact": {"type": "string"},
            "src_turn": {"type": "integer"},
        },
        "required": ["category", "question", "gold", "exact", "src_turn"],
        "additionalProperties": False,
    }}},
    "required": ["questions"],
    "additionalProperties": False,
}


def cutoff(traj: dict) -> int:
    """Second fold point: everything up to it is compressed (twice, for the summary arm) by the end."""
    return c.fold_points(traj)[1]


def run(client, ledger, tid: str) -> None:
    out_path = c.OUT / tid / "questions.json"
    if out_path.exists():
        print(f"skip {tid} questions (done)")
        return
    traj = c.load(tid)
    k = cutoff(traj)
    out = c.call_json(client, ledger, model=c.EVAL, tag=f"questions:{tid}",
                      system=Q_SYSTEM.format(cutoff=k), max_tokens=16000,
                      content=[c.card0_text(traj), c.render_turns(traj["turns"])], schema=Q_SCHEMA)
    qs = []
    for i, q in enumerate(out["questions"]):
        q["id"] = i
        q["valid"] = q["src_turn"] <= k and (q["category"] != "identifier" or bool(q["exact"].strip()))
        qs.append(q)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps({"cutoff": k, "questions": qs}, indent=1))
    print(f"done {tid} questions: {sum(q['valid'] for q in qs)}/{len(qs)} valid")


def main() -> None:
    ids = sys.argv[1:] or c.all_ids()
    client, ledger = c.make_client(), c.Ledger(c.OUT / "ledger.jsonl")
    c.OUT.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=10) as ex:
        for f in [ex.submit(run, client, ledger, tid) for tid in ids]:
            f.result()


if __name__ == "__main__":
    main()
