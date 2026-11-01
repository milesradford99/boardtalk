"""Measure 8: the lecture board as the model's memory, against S0's per-turn flash board and S0's summary.

All three arms get the task verbatim and the raw live window after S0's last fold, so only the compressed
part differs. Same answerer and judge for every arm (flash); identifier questions by exact match.
Usage: python context.py answer|grade [trajectory_id ...]
Output: data/out/<tid>/answers.json, contexts/<arm>.txt, memory_judge.json, memory_scores.json
"""
import json
import random
import sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

import base as b
from base import c

S0 = c.OUT    # S0's outputs (questions, summary, board_flash)
ARMS = ["lecture", "board_flash", "summary"]

A_SYSTEM = """You are a software agent resuming your own work after a context compaction. Your memory
is given below. Answer each question using ONLY that memory. If the memory does not contain the
answer, answer exactly NOT_IN_CONTEXT. When the answer involves an exact identifier (path, name,
command, error message, number), quote it exactly."""

A_SCHEMA = {"type": "object", "properties": {"answers": {"type": "array", "items": {
    "type": "object", "properties": {"id": {"type": "integer"}, "answer": {"type": "string"}},
    "required": ["id", "answer"], "additionalProperties": False}}},
    "required": ["answers"], "additionalProperties": False}

J_SYSTEM = """You grade answers against a gold answer. For each answer label, return a grade:
"correct" (captures the gold answer's key facts; extra detail is fine), "partial" (some key facts,
or vague), or "wrong" (incorrect, missing, or NOT_IN_CONTEXT). Judge only against the gold answer."""

J_SCHEMA = {"type": "object", "properties": {"grades": {"type": "array", "items": {
    "type": "object", "properties": {"qid": {"type": "integer"}, "label": {"type": "string"},
                                     "grade": {"type": "string", "enum": ["correct", "partial", "wrong"]}},
    "required": ["qid", "label", "grade"], "additionalProperties": False}}},
    "required": ["grades"], "additionalProperties": False}
SCORE = {"correct": 1.0, "partial": 0.5, "wrong": 0.0}


def questions(tid: str) -> list[dict]:
    return [q for q in json.loads((S0 / tid / "questions.json").read_text())["questions"] if q["valid"]]


def context(traj: dict, arm: str) -> list[str]:
    tid = traj["trajectory_id"]
    last = c.fold_points(traj)[-1]
    live = "Live window (raw, since the last compaction):\n\n" + c.render_turns(
        [t for t in traj["turns"] if t["idx"] > last])
    if arm == "summary":
        s = json.loads((S0 / tid / "summary.json").read_text())["summaries"][str(last)]
        return [c.card0_text(traj), "Summary of earlier work:\n\n" + s, live]
    if arm == "board_flash":
        return json.loads((S0 / tid / "board_flash.json").read_text())["snapshots"][str(last)] + [live]
    lec = b.lecture(tid)
    cards = [x for x in lec["cards"] if x["turn"] <= last]
    marks = [m for m in lec["marks"] if m["turn"] <= last]
    return [c.card0_text(traj), "Whiteboard of earlier work:\n\n" + b.serialize(cards, marks), live]


def answer(client, ledger, tid: str) -> None:
    path = b.OUT / tid / "answers.json"
    if path.exists():
        print(f"skip {tid} answers (done)")
        return
    traj, qs = c.load(tid), questions(tid)
    qtext = "\n".join(f"{q['id']}. {q['question']}" for q in qs)
    (b.OUT / tid / "contexts").mkdir(parents=True, exist_ok=True)
    answers = {}
    for arm in ARMS:
        blocks = context(traj, arm)
        (b.OUT / tid / "contexts" / f"{arm}.txt").write_text("\n\n".join(blocks))
        out = c.call_json(client, ledger, model=b.MODEL, tag=f"answer:{arm}:{tid}", system=A_SYSTEM,
                          max_tokens=16000, schema=A_SCHEMA,
                          content=["=== YOUR MEMORY ===\n\n" + "\n\n".join(blocks), "Questions:\n" + qtext])
        answers[arm] = {str(a["id"]): a["answer"] for a in out["answers"]}
    path.write_text(json.dumps(answers, indent=1))
    print(f"answered {tid}, tokens so far {ledger.tokens:,}")


def grade(client, ledger, tid: str) -> list[dict]:
    qs, answers = questions(tid), json.loads((b.OUT / tid / "answers.json").read_text())
    jpath = b.OUT / tid / "memory_judge.json"
    judged = [q for q in qs if q["category"] != "identifier"]
    if jpath.exists():
        grades = json.loads(jpath.read_text())["grades"]
    else:
        rng = random.Random(f"{tid}-s1-judge")
        labels, lines = {}, []
        for q in judged:
            arms = ARMS[:]
            rng.shuffle(arms)
            labels[str(q["id"])] = {chr(65 + i): a for i, a in enumerate(arms)}
            lines.append(f"Q{q['id']}: {q['question']}\nGOLD: {q['gold']}")
            lines += [f"  {chr(65 + i)}: {answers[a].get(str(q['id']), 'NOT_IN_CONTEXT')}" for i, a in enumerate(arms)]
        out = c.call_json(client, ledger, model=b.MODEL, tag=f"memory_judge:{tid}", system=J_SYSTEM,
                          max_tokens=16000, schema=J_SCHEMA, content=["\n".join(lines)])
        grades = defaultdict(dict)
        for g in out["grades"]:
            arm = labels.get(str(g["qid"]), {}).get(g["label"])
            if arm:
                grades[arm][str(g["qid"])] = g["grade"]
        jpath.write_text(json.dumps({"grades": grades, "labels": labels}, indent=1))
    rows = []
    for q in qs:
        for arm in ARMS:
            a = answers[arm].get(str(q["id"]), "")
            s = (1.0 if c.norm_ws(q["exact"]) in c.norm_ws(a) else 0.0) if q["category"] == "identifier" \
                else SCORE[grades.get(arm, {}).get(str(q["id"]), "wrong")]
            rows.append({"tid": tid, "qid": q["id"], "category": q["category"], "arm": arm, "score": s})
    return rows


def main() -> None:
    step, ids = sys.argv[1], sys.argv[2:] or c.all_ids()
    client, ledger = c.make_client(), b.ledger()
    with ThreadPoolExecutor(max_workers=10) as ex:
        if step == "answer":
            for f in [ex.submit(answer, client, ledger, tid) for tid in ids]:
                f.result()
        else:
            rows = [r for rs in ex.map(lambda t: grade(client, ledger, t), ids) for r in rs]
            (b.OUT / "memory_scores.json").write_text(json.dumps(rows, indent=1))
            print(f"graded {len(ids)} trajectories, {len(rows)} rows")


if __name__ == "__main__":
    main()
