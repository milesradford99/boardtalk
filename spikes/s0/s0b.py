"""Spike S0b: board vs summary at equal token budget for the compressed part.

Usage: python s0b.py build|answer|grade [trajectory_id ...]
Outputs under data/out/<tid>/s0b/ and report_s0b.md.
"""
import json
import random
import re
import sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import common as c
from answer import A_SCHEMA, A_SYSTEM
from fold import SUMMARY_SYSTEM
from grade import J_SCHEMA, J_SYSTEM, SCORE

BUDGETS = [2_000, 5_000, 10_000]
BOARDS = ["board_pro", "board_flash"]
SLACK = 1.15
MIN_DIGEST = 150

DIGEST_SYSTEM = """You compress one page of an agent's whiteboard into a digest that will replace the
page in the agent's memory. Keep card ids (#n) as anchors, e.g. "#12: ...". Keep, in this order of
priority: what was decided and why; approaches that failed and why; the state reached; exact
identifiers likely to be needed again (file paths, function/test names, commands, error messages),
copied exactly. Drop narration and anything later cards supersede. Write the digest inside
<digest></digest> tags."""


def out_dir(tid: str) -> Path:
    d = c.OUT / tid / "s0b"
    d.mkdir(parents=True, exist_ok=True)
    return d


def text_within(client, ledger, *, tag: str, system: str, content: list[str], budget: int, open_tag: str) -> str:
    """Generate text in <open_tag> tags within ~budget tokens; retry with feedback; keep the shortest valid."""
    limit = int(budget * SLACK * 4)
    best = None
    note = ""
    # Same closing line for both arms: without it, models role-play the agent and try to do the task.
    content = content[:-1] + [content[-1] + (
        f"\n\n---\nYou are a note-taker, not the agent: do not do the task, run commands or call tools. "
        f"Output only the <{open_tag}>...</{open_tag}> block.")]
    for attempt in range(3):
        txt = c.call_text(client, ledger, model=c.MAIN, tag=f"{tag}:a{attempt}", system=system,
                          content=content[:-1] + [content[-1] + note], max_tokens=16000)
        m = re.search(rf"<{open_tag}>(.*?)(?:</{open_tag}>|$)", txt, re.S)
        body = (m.group(1) if m else "").strip()
        if not m or len(body) < 200 or "<invoke" in body or "<tool_calls" in body:
            print(f"  invalid {tag} attempt {attempt}: {len(body)} chars")
            continue
        if best is None or len(body) < len(best):
            best = body
        if len(body) <= limit:
            return body
        note = (f"\n\n---\nYour previous answer was {len(body)} characters; the hard limit is {limit} "
                f"characters (~{budget} tokens). Rewrite it shorter, keeping the most important facts.")
    if best is None:
        raise RuntimeError(f"{tag}: no valid output")
    print(f"  over budget {tag}: {len(best)} > {limit} chars (kept shortest)")
    return best


# ---------- summary@B ----------

def summary_at(client, ledger, traj: dict, budget: int) -> str:
    path = out_dir(traj["trajectory_id"]) / f"summary_{budget}.json"
    if path.exists():
        return json.loads(path.read_text())["summary"]
    system = SUMMARY_SYSTEM + (f"\n\nHard length limit: the summary must be at most ~{budget} tokens "
                               f"(about {budget * 4} characters). Prioritize within that limit.")
    summary, prev, by_fold = "", -1, {}
    for f in c.fold_points(traj):
        window = [t for t in traj["turns"] if prev < t["idx"] <= f]
        content = [c.card0_text(traj)]
        if summary:
            content.append("Previous summary:\n\n" + summary)
        content.append("Transcript since then:\n\n" + c.render_turns(window))
        summary = text_within(client, ledger, tag=f"s0b:summary{budget}:{traj['trajectory_id']}:{f}",
                              system=system, content=content, budget=budget, open_tag="summary")
        by_fold[f] = summary
        prev = f
    path.write_text(json.dumps({"summary": summary, "by_fold": by_fold}, indent=1))
    return summary


# ---------- board@B (second-level fold) ----------

def pages_of(traj: dict, board: dict) -> list[list[dict]]:
    """Cards grouped by fold window, oldest first, only up to the last fold."""
    folds = board["folds"]
    pages = [[] for _ in folds]
    for batch in board["batches"]:
        for card in batch:
            start = card["src"][0]
            for k, f in enumerate(folds):
                lo = folds[k - 1] if k else -1
                if lo < start <= f:
                    pages[k].append(card)
                    break
    return pages


def page_text(cards: list[dict]) -> str:
    return "\n\n".join(c.serialize_card(x) for x in cards)


def board_at(client, ledger, traj: dict, arm: str, budget: int) -> list[str]:
    tid = traj["trajectory_id"]
    path = out_dir(tid) / f"{arm}_{budget}.json"
    if path.exists():
        return json.loads(path.read_text())["blocks"]
    board = json.loads((c.OUT / tid / f"{arm}.json").read_text())
    pages = pages_of(traj, board)
    texts = [page_text(p) for p in pages]
    sizes = [c.approx_tokens(t) for t in texts]
    # keep the newest pages verbatim while they fit in half the budget
    keep, used = len(pages), 0
    while keep > 0 and used + sizes[keep - 1] <= budget // 2:
        keep -= 1
        used += sizes[keep]
    if sum(sizes) <= budget:          # whole board already fits: no fold needed
        keep, used = 0, sum(sizes)
    old = list(range(keep))
    blocks, meta = [], {"kept_pages": len(pages) - keep, "digested_pages": len(old), "digests": []}
    if old:
        room = budget - used
        if room // len(old) >= MIN_DIGEST:
            groups = [[k] for k in old]
            share = room // len(old)
        else:
            groups, share = [old], room
        for g in groups:
            cards = [x for k in g for x in pages[k]]
            ids = f"#{cards[0]['id']}–#{cards[-1]['id']}" if cards else "(empty)"
            body = text_within(client, ledger, tag=f"s0b:digest:{arm}{budget}:{tid}:{g[0]}-{g[-1]}",
                               system=DIGEST_SYSTEM, budget=share, open_tag="digest",
                               content=[c.card0_text(traj), f"Page cards {ids}:\n\n" + page_text(cards)])
            blocks.append(f"### Digest of cards {ids}\n{body}")
            meta["digests"].append({"pages": g, "share": share, "tok": c.approx_tokens(body)})
    blocks += [texts[k] for k in range(keep, len(pages)) if texts[k]]
    path.write_text(json.dumps({"blocks": blocks, "meta": meta}, indent=1))
    return blocks


ARMS = ["summary"] + BOARDS


def compressed(traj: dict, arm: str, budget: int) -> list[str]:
    tid = traj["trajectory_id"]
    if arm == "summary":
        return ["Summary of earlier work:\n\n" + json.loads((out_dir(tid) / f"summary_{budget}.json").read_text())["summary"]]
    return json.loads((out_dir(tid) / f"{arm}_{budget}.json").read_text())["blocks"]


def build(client, ledger, tid: str) -> None:
    traj = c.load(tid)
    for b in BUDGETS:
        summary_at(client, ledger, traj, b)
        for arm in BOARDS:
            board_at(client, ledger, traj, arm, b)
    print(f"built {tid}, tokens so far {ledger.tokens:,}")


# ---------- answer ----------

def answer(client, ledger, tid: str) -> None:
    path = out_dir(tid) / "answers.json"
    done = json.loads(path.read_text()) if path.exists() else {}
    traj = c.load(tid)
    qs = [q for q in json.loads((c.OUT / tid / "questions.json").read_text())["questions"] if q["valid"]]
    qtext = "\n".join(f"{q['id']}. {q['question']}" for q in qs)
    last = c.fold_points(traj)[-1]
    live = "Live window (raw, since the last compaction):\n\n" + c.render_turns(
        [t for t in traj["turns"] if t["idx"] > last])
    for b in BUDGETS:
        for arm in ARMS:
            key = f"{arm}@{b}"
            if key in done:
                continue
            blocks = [c.card0_text(traj)] + compressed(traj, arm, b) + [live]
            out = c.call_json(client, ledger, model=c.MAIN, tag=f"s0b:answer:{key}:{tid}", system=A_SYSTEM,
                              max_tokens=16000, schema=A_SCHEMA,
                              content=["=== YOUR MEMORY ===\n\n" + "\n\n".join(blocks), "Questions:\n" + qtext])
            done[key] = {str(a["id"]): a["answer"] for a in out["answers"]}
            path.write_text(json.dumps(done, indent=1))
    print(f"answered {tid}, tokens so far {ledger.tokens:,}")


# ---------- grade ----------

def judge_group(client, ledger, tid: str, b: int, qs: list[dict], answers: dict) -> dict:
    path = out_dir(tid) / f"judge_{b}.json"
    if path.exists():
        return json.loads(path.read_text())
    rng = random.Random(f"{tid}-s0b-{b}")
    labels, lines = {}, []
    for q in qs:
        arms = ARMS[:]
        rng.shuffle(arms)
        labels[str(q["id"])] = {chr(65 + i): a for i, a in enumerate(arms)}
        lines.append(f"Q{q['id']}: {q['question']}\nGOLD: {q['gold']}")
        lines += [f"  {chr(65 + i)}: {answers[f'{a}@{b}'].get(str(q['id']), 'NOT_IN_CONTEXT')}" for i, a in enumerate(arms)]
    out = c.call_json(client, ledger, model=c.EVAL, tag=f"s0b:judge{b}:{tid}", system=J_SYSTEM,
                      max_tokens=16000, content=["\n".join(lines)], schema=J_SCHEMA)
    res = defaultdict(dict)
    for g in out["grades"]:
        arm = labels.get(str(g["qid"]), {}).get(g["label"])
        if arm:
            res[arm][str(g["qid"])] = g["grade"]
    path.write_text(json.dumps(dict(res), indent=1))
    return dict(res)


def score(client, ledger, tid: str) -> list[dict]:
    qs = [q for q in json.loads((c.OUT / tid / "questions.json").read_text())["questions"] if q["valid"]]
    answers = json.loads((out_dir(tid) / "answers.json").read_text())
    rows = []
    for b in BUDGETS:
        judged = [q for q in qs if q["category"] != "identifier"]
        j = judge_group(client, ledger, tid, b, judged, answers)
        for q in qs:
            for arm in ARMS:
                a = answers[f"{arm}@{b}"].get(str(q["id"]), "")
                if q["category"] == "identifier":
                    s = 1.0 if c.norm_ws(q["exact"]) in c.norm_ws(a) else 0.0
                else:
                    s = SCORE[j.get(arm, {}).get(str(q["id"]), "wrong")]
                rows.append({"tid": tid, "budget": b, "arm": arm, "category": q["category"], "score": s})
    return rows


def report(client, ledger, ids: list[str]) -> None:
    with ThreadPoolExecutor(max_workers=10) as ex:
        rows = [r for rs in ex.map(lambda t: score(client, ledger, t), ids) for r in rs]
    sizes = defaultdict(list)
    for tid in ids:
        for b in BUDGETS:
            for arm in ARMS:
                sizes[(arm, b)].append(c.approx_tokens("\n\n".join(compressed(c.load(tid), arm, b))))

    def mean(f):
        v = [r["score"] for r in rows if f(r)]
        return 100 * sum(v) / len(v) if v else float("nan")

    cats = ["identifier", "decision", "dead_end", "state"]
    L = ["# Spike S0b results (equal budget)", "",
         f"Trajectories: {len(ids)} · total tokens in ledger: {c.Ledger(c.OUT / 'ledger.jsonl').tokens:,}", "",
         "| budget | arm | achieved tok (mean / max) | overall | " + " | ".join(cats) + " | wins vs summary (traj) |",
         "|---|---|---|---|" + "---|" * len(cats) + "---|"]
    for b in BUDGETS:
        per_traj_sum = {t: mean(lambda r, t=t: r["tid"] == t and r["budget"] == b and r["arm"] == "summary") for t in ids}
        for arm in ARMS:
            sz = sizes[(arm, b)]
            wins = "" if arm == "summary" else str(sum(
                mean(lambda r, t=t: r["tid"] == t and r["budget"] == b and r["arm"] == arm) > per_traj_sum[t] for t in ids))
            L.append(f"| {b} | {arm} | {sum(sz) // len(sz)} / {max(sz)} | "
                     f"{mean(lambda r: r['budget'] == b and r['arm'] == arm):.1f} | " + " | ".join(
                         f"{mean(lambda r, k=k: r['budget'] == b and r['arm'] == arm and r['category'] == k):.1f}" for k in cats)
                     + f" | {wins} |")
    Path(__file__).with_name("report_s0b.md").write_text("\n".join(L) + "\n")
    (c.OUT / "s0b_scores.json").write_text(json.dumps({"rows": rows, "sizes": {f"{a}@{b}": v for (a, b), v in sizes.items()}}))
    print("\n".join(L))


def main() -> None:
    cmd, ids = sys.argv[1], sys.argv[2:] or c.all_ids()
    client, ledger = c.make_client(), c.Ledger(c.OUT / "ledger.jsonl")
    if cmd == "grade":
        report(client, ledger, ids)
        return
    fn = {"build": build, "answer": answer}[cmd]
    with ThreadPoolExecutor(max_workers=10) as ex:
        for f in [ex.submit(fn, client, ledger, tid) for tid in ids]:
            f.result()


if __name__ == "__main__":
    main()
