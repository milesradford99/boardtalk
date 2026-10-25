"""Grade answers, run the mechanical checks, and write report.md.

- identifier questions: exact match (the gold `exact` string appears in the answer, whitespace-normalized)
- other questions: blind Kimi judge; arm labels hidden, order shuffled with a fixed seed
- mechanical: verbatim hallucination rate, context sizes, board prefix property, scribe cache stats, cost

Usage: python grade.py
"""
import json
import random
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import common as c
from answer import ARMS

J_SYSTEM = """You grade answers against a gold answer. For each answer label, return a grade:
"correct" (captures the gold answer's key facts; extra detail is fine), "partial" (some key facts,
or vague), or "wrong" (incorrect, missing, or NOT_IN_CONTEXT). Judge only against the gold answer."""

J_SCHEMA = {
    "type": "object",
    "properties": {"grades": {"type": "array", "items": {
        "type": "object",
        "properties": {
            "qid": {"type": "integer"},
            "label": {"type": "string"},
            "grade": {"type": "string", "enum": ["correct", "partial", "wrong"]},
        },
        "required": ["qid", "label", "grade"],
        "additionalProperties": False,
    }}},
    "required": ["grades"],
    "additionalProperties": False,
}
SCORE = {"correct": 1.0, "partial": 0.5, "wrong": 0.0}


def judge(client, ledger, tid: str, qs: list[dict], answers: dict) -> dict:
    path = c.OUT / tid / "judge.json"
    if path.exists():
        return json.loads(path.read_text())
    rng = random.Random(f"{tid}-judge")
    labels, lines = {}, []
    for q in qs:
        arms = ARMS[:]
        rng.shuffle(arms)
        labels[str(q["id"])] = {chr(65 + i): arm for i, arm in enumerate(arms)}
        lines.append(f"Q{q['id']}: {q['question']}\nGOLD: {q['gold']}")
        lines += [f"  {chr(65 + i)}: {answers[arm].get(str(q['id']), 'NOT_IN_CONTEXT')}" for i, arm in enumerate(arms)]
    out = c.call_json(client, ledger, model=c.EVAL, tag=f"judge:{tid}", system=J_SYSTEM,
                      max_tokens=16000, content=["\n".join(lines)], schema=J_SCHEMA)
    res = defaultdict(dict)
    for g in out["grades"]:
        arm = labels.get(str(g["qid"]), {}).get(g["label"])
        if arm:
            res[arm][str(g["qid"])] = g["grade"]
    res = {"grades": dict(res), "labels": labels}
    path.write_text(json.dumps(res, indent=1))
    return res


def score_tid(client, ledger, tid: str) -> list[dict]:
    qs = [q for q in json.loads((c.OUT / tid / "questions.json").read_text())["questions"] if q["valid"]]
    answers = json.loads((c.OUT / tid / "answers.json").read_text())
    judged = [q for q in qs if q["category"] != "identifier"]
    j = judge(client, ledger, tid, judged, answers) if judged else {"grades": {}}
    rows = []
    for q in qs:
        for arm in ARMS:
            a = answers[arm].get(str(q["id"]), "")
            if q["category"] == "identifier":
                s = 1.0 if c.norm_ws(q["exact"]) in c.norm_ws(a) else 0.0
            else:
                s = SCORE[j["grades"].get(arm, {}).get(str(q["id"]), "wrong")]
            rows.append({"tid": tid, "qid": q["id"], "category": q["category"], "arm": arm, "score": s})
    return rows


def _strings(x):
    if isinstance(x, str):
        yield x
    elif isinstance(x, dict):
        for v in x.values():
            yield from _strings(v)
    elif isinstance(x, list):
        for v in x:
            yield from _strings(v)


def source_corpus(traj: dict) -> str:
    """Everything the scribe could legitimately copy from: task, rendered turns, decoded call args."""
    parts = [traj["task"], c.render_turns(traj["turns"])]
    for t in traj["turns"]:
        parts += list(_strings([x["args"] for x in t["calls"]]))
    return "\n".join(parts)


def mechanical(tid: str) -> dict:
    traj = c.load(tid)
    raw = c.norm_ws(source_corpus(traj))
    last = str(c.fold_points(traj)[-1])
    m = {"raw_tok": c.approx_tokens(c.render_turns([t for t in traj["turns"] if t["idx"] <= int(last)]))}
    s = json.loads((c.OUT / tid / "summary.json").read_text())["summaries"][last]
    m["summary_tok"] = c.approx_tokens(s)
    for arm in ("board_flash", "board_pro"):
        b = json.loads((c.OUT / tid / f"{arm}.json").read_text())
        cards = [x for batch in b["batches"] for x in batch if x["kind"] != "handoff"]
        verb = [v for x in cards for v in x["verbatim"] if v.strip()]
        miss = [v for v in verb if c.norm_ws(v) not in raw]
        snaps = [b["snapshots"][str(f)] for f in b["folds"]]
        prefix_ok = all("\n\n".join(snaps[i + 1]).startswith("\n\n".join(snaps[i]))
                        and snaps[i + 1][:len(snaps[i])] == snaps[i] for i in range(len(snaps) - 1))
        m[arm] = {"cards": len(cards), "verbatim": len(verb), "verbatim_miss": len(miss),
                  "miss_examples": miss[:3], "board_tok": c.approx_tokens("\n\n".join(b["snapshots"][last])),
                  "prefix_ok": prefix_ok, "failed_turns": len(b.get("failed_turns", []))}
    return m


def scribe_cache_stats() -> dict:
    agg = defaultdict(lambda: defaultdict(float))
    by_kind = defaultdict(float)
    for line in (c.OUT / "ledger.jsonl").read_text().splitlines():
        e = json.loads(line)
        kind = e["tag"].split(":")[0] + (":" + e["tag"].split(":")[1] if e["tag"].startswith(("scribe", "answer")) else "")
        by_kind[kind] += e["in"] + e["out"] + e["cache_read"] + e["cache_write"]
        if e["tag"].startswith("scribe"):
            for k in ("in", "out", "cache_read", "cache_write"):
                agg[e["model"]][k] += e[k]
    return {"cache": {m: dict(v) for m, v in agg.items()}, "cost": dict(by_kind)}


def pct(x: float) -> str:
    return f"{100 * x:.1f}"


def main() -> None:
    client, ledger = c.make_client(), c.Ledger(c.OUT / "ledger.jsonl")
    ids = c.all_ids()
    with ThreadPoolExecutor(max_workers=10) as ex:
        rows = [r for rs in ex.map(lambda t: score_tid(client, ledger, t), ids) for r in rs]
    mech = {tid: mechanical(tid) for tid in ids}
    stats = scribe_cache_stats()
    (c.OUT / "scores.json").write_text(json.dumps({"rows": rows, "mechanical": mech, "stats": stats}, indent=1))

    def mean(f):
        v = [r["score"] for r in rows if f(r)]
        return sum(v) / len(v) if v else float("nan")

    cats = ["identifier", "decision", "dead_end", "state"]
    L = ["# Spike S0 results", "", f"Trajectories: {len(ids)} · valid questions: "
         f"{len({(r['tid'], r['qid']) for r in rows})} · total tokens: {ledger.tokens:,}", "",
         "## Recall by arm (% score; identifier = exact match, others = blind judge, partial = 0.5)", "",
         "| arm | overall | " + " | ".join(cats) + " |", "|---|---|" + "---|" * len(cats)]
    for arm in ARMS:
        L.append(f"| {arm} | {pct(mean(lambda r: r['arm'] == arm))} | " + " | ".join(
            pct(mean(lambda r, k=k: r['arm'] == arm and r['category'] == k)) for k in cats) + " |")
    L += ["", "## Per trajectory (overall %)", "", "| trajectory | repo | " + " | ".join(ARMS) + " |",
          "|---|---|" + "---|" * len(ARMS)]
    for tid in ids:
        L.append(f"| {tid[:12]} | {c.load(tid)['repo']} | " + " | ".join(
            pct(mean(lambda r, a=a: r['tid'] == tid and r['arm'] == a)) for a in ARMS) + " |")
    L += ["", "## Mechanical checks", "",
          "| trajectory | raw tok (compressed part) | summary tok | board_flash tok | board_pro tok | "
          "verbatim miss flash | verbatim miss pro | prefix ok |", "|---|---|---|---|---|---|---|---|"]
    for tid, m in mech.items():
        h, s = m["board_flash"], m["board_pro"]
        L.append(f"| {tid[:12]} | {m['raw_tok']} | {m['summary_tok']} | {h['board_tok']} | {s['board_tok']} | "
                 f"{h['verbatim_miss']}/{h['verbatim']} | {s['verbatim_miss']}/{s['verbatim']} | "
                 f"{h['prefix_ok'] and s['prefix_ok']} |")
    for arm in ("board_flash", "board_pro"):
        v = sum(m[arm]["verbatim"] for m in mech.values())
        miss = sum(m[arm]["verbatim_miss"] for m in mech.values())
        ft = sum(m[arm]["failed_turns"] for m in mech.values())
        L.append(f"\n{arm}: scribe turns that failed after retry (left empty): {ft}")
        L.append(f"{arm}: verbatim hallucination rate {pct(miss / v if v else 0)}% ({miss}/{v}); examples: "
                 + "; ".join(f"`{x}`" for m in mech.values() for x in m[arm]["miss_examples"][:1])[:600])
    L += ["", "## Scribe prompt-cache stats (tokens)", ""]
    for model, v in stats["cache"].items():
        total_in = v["in"] + v["cache_read"] + v["cache_write"]
        L.append(f"- {model}: input {int(v['in'])}, cache read {int(v['cache_read'])}, cache write "
                 f"{int(v['cache_write'])}, output {int(v['out'])} · read share "
                 f"{pct(v['cache_read'] / total_in if total_in else 0)}%")
    L += ["", "## Tokens by step (Ark agent plan is flat-rate)", ""] + [f"- {k}: {int(v):,}" for k, v in sorted(stats["cost"].items())]
    Path(__file__).with_name("report.md").write_text("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
