"""Answer every question from each arm's end-of-trajectory context.

Arms: raw (ceiling), summary (baseline), board_flash, board_pro.
Usage: python answer.py [trajectory_id ...]
Output: data/out/<tid>/answers.json and contexts/<arm>.txt (what the model saw, for inspection)
"""
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor

import common as c

ARMS = ["raw", "summary", "board_flash", "board_pro"]

A_SYSTEM = """You are a software agent resuming your own work after a context compaction. Your memory
is given below. Answer each question using ONLY that memory. If the memory does not contain the
answer, answer exactly NOT_IN_CONTEXT. When the answer involves an exact identifier (path, name,
command, error message, number), quote it exactly."""

A_SCHEMA = {
    "type": "object",
    "properties": {"answers": {"type": "array", "items": {
        "type": "object",
        "properties": {"id": {"type": "integer"}, "answer": {"type": "string"}},
        "required": ["id", "answer"],
        "additionalProperties": False,
    }}},
    "required": ["answers"],
    "additionalProperties": False,
}


def context(traj: dict, arm: str) -> list[str]:
    """Blocks the model sees at the end of the trajectory for this arm."""
    tid = traj["trajectory_id"]
    if arm == "raw":
        return [c.card0_text(traj), c.render_turns(traj["turns"])]
    last = c.fold_points(traj)[-1]
    live = "Live window (raw, since the last compaction):\n\n" + c.render_turns(
        [t for t in traj["turns"] if t["idx"] > last])
    if arm == "summary":
        s = json.loads((c.OUT / tid / "summary.json").read_text())["summaries"][str(last)]
        return [c.card0_text(traj), "Summary of earlier work:\n\n" + s, live]
    board = json.loads((c.OUT / tid / f"{arm}.json").read_text())["snapshots"][str(last)]
    return board + [live]


def run(client, ledger, tid: str) -> None:
    out_path = c.OUT / tid / "answers.json"
    only = [a for a in os.environ.get("S0_ONLY_ARMS", "").split(",") if a]
    if out_path.exists() and not only:
        print(f"skip {tid} answers (done)")
        return
    prev = json.loads(out_path.read_text()) if out_path.exists() else {}
    traj = c.load(tid)
    qs = [q for q in json.loads((c.OUT / tid / "questions.json").read_text())["questions"] if q["valid"]]
    qtext = "\n".join(f"{q['id']}. {q['question']}" for q in qs)
    (c.OUT / tid / "contexts").mkdir(parents=True, exist_ok=True)
    answers = dict(prev)
    for arm in (only or ARMS):
        blocks = context(traj, arm)
        (c.OUT / tid / "contexts" / f"{arm}.txt").write_text("\n\n".join(blocks))
        out = c.call_json(client, ledger, model=c.MAIN, tag=f"answer:{arm}:{tid}", system=A_SYSTEM,
                          max_tokens=16000,
                          content=["=== YOUR MEMORY ===\n\n" + "\n\n".join(blocks), "Questions:\n" + qtext],
                          schema=A_SCHEMA)
        answers[arm] = {str(a["id"]): a["answer"] for a in out["answers"]}
    out_path.write_text(json.dumps(answers, indent=1))
    print(f"done {tid} answers, tokens so far {ledger.tokens:,}")


def main() -> None:
    ids = sys.argv[1:] or c.all_ids()
    client, ledger = c.make_client(), c.Ledger(c.OUT / "ledger.jsonl")
    with ThreadPoolExecutor(max_workers=10) as ex:
        for f in [ex.submit(run, client, ledger, tid) for tid in ids]:
            f.result()


if __name__ == "__main__":
    main()
