"""Mechanical measures (1 verbatim, 7 anchors and append-only, 9 latency and tokens) plus the judged ones,
gathered into report.md with the pass criteria.

Usage: python check.py
"""
import json
import statistics
from collections import Counter
from pathlib import Path

import base as b
from base import c
from context import ARMS
from grade import source_corpus   # S0's corpus: task, rendered turns, decoded call arguments
from lecture2 import notes_of

S1B = b.BOARD != "lecture"


def pct(n, d) -> str:
    return f"{100 * n / d:.1f}" if d else "–"


def verbatim_strings(x: dict) -> list[str]:
    chips = [s for i, s in enumerate(x["body_md"].split("`")) if i % 2]
    return [v for v in dict.fromkeys(x["verbatim"] + chips) if v.strip()]


def mechanical(tid: str) -> dict:
    traj, lec = c.load(tid), b.lecture(tid)
    raw = c.norm_ws(source_corpus(traj))
    verb = [(x["id"], v) for x in lec["cards"] for v in verbatim_strings(x)]
    miss = [(i, v) for i, v in verb if c.norm_ws(v) not in raw]
    note_miss = 0
    if S1B:   # also against each card's own cited notes (and the request)
        notes = {n["id"]: n for n in notes_of(tid)}
        for x in lec["cards"]:
            pool = c.norm_ws("\n".join([b.note_text(notes[n]) for n in x["src_notes"] if n in notes]
                                       + ([traj["task"]] if b.REQUEST in x["src_notes"] else [])))
            note_miss += sum(1 for v in verbatim_strings(x) if c.norm_ws(v) not in pool)
    delays = [x["turn"] - max(s for s in x["src_turns"] if s != b.REQUEST) for x in lec["cards"]
              if any(s != b.REQUEST for s in x["src_turns"])]
    ops = sum(p["emitted"] for p in lec["per_turn"])
    turns_with = sum(1 for p in lec["per_turn"] if p["cards"])
    return {"turns": len(traj["turns"]), "cards": len(lec["cards"]), "marks": len(lec["marks"]),
            "kinds": Counter(x["kind"] for x in lec["cards"]), "turns_with_cards": turns_with,
            "verbatim": len(verb), "verbatim_miss": len(miss), "miss_examples": miss[:3], "note_miss": note_miss,
            "delays": delays,
            "ops": ops, "dropped": len(lec["dropped"]),
            "dropped_marks": sum(1 for d in lec["dropped"] if "snippet" in d["op"]),
            "emitted_marks": len(lec["marks"]) + sum(1 for d in lec["dropped"] if "snippet" in d["op"]),
            "drop_reasons": Counter(d["why"].split(" #")[0].split(" ")[0] for d in lec["dropped"]),
            "failed_turns": len(lec["failed_turns"]),
            "revisions": sum(1 for x in lec["cards"] if x["revises"] is not None)}


def ledger_stats() -> dict:
    by_step, lat, cache = Counter(), [], Counter()
    for line in (b.OUT / ("ledger_s1b.jsonl" if S1B else "ledger.jsonl")).read_text().splitlines():
        e = json.loads(line)
        tot = e["in"] + e["out"] + e["cache_read"] + e["cache_write"]
        by_step[e["tag"].split(":")[0]] += tot
        if e["tag"].startswith(("lecture2", "scribe")):
            lat.append(e["s"])
            for k in ("in", "out", "cache_read", "cache_write"):
                cache[k] += e[k]
    lat.sort()
    q = lambda p: lat[min(len(lat) - 1, int(p * len(lat)))] if lat else float("nan")
    return {"by_step": by_step, "p50": q(.5), "p95": q(.95), "cache": cache, "calls": len(lat)}


def load(tid, name):
    p = b.OUT / tid / name
    return json.loads(p.read_text()) if p.exists() else None


def main() -> None:
    ids = c.all_ids()
    mech = {tid: mechanical(tid) for tid in ids}
    sx = b.suffix()
    jc = {tid: load(tid, f"judge_cards{sx}.json") for tid in ids}
    it = {tid: load(tid, f"coverage{sx}.json") for tid in ids}
    it_old = {tid: load(tid, "intent.json") for tid in ids} if not S1B else {}
    hd = {tid: load(tid, f"heads{sx}.json") for tid in ids}
    mem = [] if S1B else json.loads((b.OUT / "memory_scores.json").read_text())
    st = ledger_stats()
    res = {}

    V = sum(m["verbatim"] for m in mech.values())
    VM = sum(m["verbatim_miss"] for m in mech.values())
    res[1] = VM / V <= .02 if V else False
    grades = [g for j in jc.values() if j for g in j["grades"].values()]
    sup = Counter(g["support"] for g in grades)
    lvl = Counter(g["level"] for g in grades)
    G = len(grades)
    res[2] = G > 0 and sup["supported"] / G >= .9 and sup["unsupported"] / G <= .03
    reqs = [r for i in it.values() if i for r in i["requirements"]]
    cov = Counter(r["covered"] for r in reqs)
    res[3] = bool(reqs) and cov["yes"] / len(reqs) >= .9
    old = [r for i in it_old.values() if i for r in i["requirements"]]
    old_yes = sum(r["covered"] == "yes" for r in old)
    delays = sorted(d for m in mech.values() for d in m["delays"])
    NM = sum(m["note_miss"] for m in mech.values())
    notes = [n for h in hd.values() if h for n in h["notes"]]
    precise = sum(1 for n in notes if n["true"] and n["new"])
    per_session = [sum(1 for x in b.lecture(t)["cards"] if x["kind"] == "heads_up") for t in ids]
    cards_per = [m["cards"] for m in mech.values()]
    res[4] = bool(notes) and precise / len(notes) >= .7 and statistics.median(per_session) <= 3
    failed_runs = [h for h in hd.values() if h and not h["resolved"]]
    flagged = sum(1 for h in failed_runs if h["flags_problem"])
    false_alarm = sum(1 for h in hd.values() if h and h["resolved"] and h["flags_problem"])
    res[5] = flagged >= 3
    res[6] = G > 0 and lvl["step"] / G <= .1
    EM = sum(m["emitted_marks"] for m in mech.values())
    DM = sum(m["dropped_marks"] for m in mech.values())
    OPS = sum(m["ops"] for m in mech.values())
    DR = sum(m["dropped"] for m in mech.values())
    res[7] = (EM == 0 or (EM - DM) / EM >= .95) and (OPS == 0 or DR / OPS <= .05)
    res[9] = st["p50"] <= 15

    def mean(f):
        v = [r["score"] for r in mem if f(r)]
        return sum(v) / len(v) if v else float("nan")

    L = [f"# Spike {'S1b' if S1B else 'S1'} results (generated by check.py, board: {b.BOARD})", "",
         f"Trajectories: {len(ids)} · model: {b.MODEL} · total tokens: {sum(st['by_step'].values()):,}", "",
         "## Pass / fail", "",
         "| # | measure | result | target | met |", "|---|---|---|---|---|",
         f"| 1 | verbatim not found | {pct(VM, V)} % ({VM}/{V})"
         + (f"; not in cited notes {pct(NM, V)} %" if S1B else "") + f" | ≤ 2 % | {res[1]} |",
         f"| 2 | claim support | {pct(sup['supported'], G)} % supported, {pct(sup['partial'], G)} % partial, "
         f"{pct(sup['unsupported'], G)} % unsupported ({G} cards) | ≥ 90 %, ≤ 3 % | {res[2]} |",
         f"| 3 | intent coverage | {pct(cov['yes'], len(reqs))} % yes, {pct(cov['partial'], len(reqs))} % partial "
         f"({len(reqs)} requirements, strict lists)" + (f"; first S1 lists: {pct(old_yes, len(old))} % yes" if old else "")
         + f" | ≥ 90 % | {res[3]} |",
         f"| 4 | You-should-know precision | {pct(precise, len(notes))} % true and new ({precise}/{len(notes)}); "
         f"median {statistics.median(per_session) if per_session else '–'} per session | ≥ 70 %, ≤ 3 | {res[4]} |",
         f"| 5 | flags the problem on failed runs | {flagged} of {len(failed_runs)} (false alarms on resolved: "
         f"{false_alarm}) | ≥ 3 of 5 | {res[5]} |",
         f"| 6 | step narration | {pct(lvl['step'], G)} % | ≤ 10 % | {res[6]} |",
         f"| 7 | marks valid / ops dropped | {pct(EM - DM, EM)} % valid ({EM - DM}/{EM}); {pct(DR, OPS)} % "
         f"dropped ({DR}/{OPS}) | ≥ 95 %, ≤ 5 % | {res[7]} |",
         f"| 9 | scribe latency | p50 {st['p50']} s, p95 {st['p95']} s ({st['calls']} calls); card delay median "
         f"{statistics.median(delays) if delays else '–'} turns, max {max(delays, default='–')} | p50 ≤ 15 s | {res[9]} |",
         "", f"Cards per session: {sorted(cards_per)} (budget 8-15)",
         "", f"Measures 1, 2, 3, 7 all met: {all(res[k] for k in (1, 2, 3, 7))} · 4 or 5 met: {res[4] or res[5]} "
             "· human review: see s1-results.md", "",
         *([] if S1B else ["## Measure 8: memory (% score; identifier = exact match, others = blind flash judge, partial = 0.5)", "",
         "| arm | overall | identifier | decision | dead_end | state |", "|---|---|---|---|---|---|"])]
    for arm in ([] if S1B else ARMS):
        L.append(f"| {arm} | {100 * mean(lambda r: r['arm'] == arm):.1f} | " + " | ".join(
            f"{100 * mean(lambda r, k=k: r['arm'] == arm and r['category'] == k):.1f}"
            for k in ["identifier", "decision", "dead_end", "state"]) + " |")
    L += ["", "## Per trajectory", "",
          "| trajectory | repo | resolved | turns | cards (intent/design/evidence/heads/question) | turns with cards "
          "| marks | revisions | verbatim miss | dropped | failed turns | memory lecture / flash / summary |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for tid, m in mech.items():
        traj = c.load(tid)
        k = m["kinds"]
        mm = " / ".join(f"{100 * mean(lambda r, a=a: r['tid'] == tid and r['arm'] == a):.0f}" for a in ARMS)
        L.append(f"| {tid[:16]} | {traj['repo']} | {traj['resolved']} | {m['turns']} | {m['cards']} ("
                 + "/".join(str(k[x]) for x in b.KINDS) + f") | {m['turns_with_cards']} | {m['marks']} | "
                 f"{m['revisions']} | {m['verbatim_miss']}/{m['verbatim']} | {m['dropped']} | {m['failed_turns']} | {mm} |")
    L += ["", "Verbatim misses (examples): " + "; ".join(f"#{i} `{v}`" for m in mech.values()
                                                         for i, v in m["miss_examples"][:1])[:900],
          "", "Drop reasons: " + ", ".join(f"{k}: {v}" for k, v in
                                          sum((m["drop_reasons"] for m in mech.values()), Counter()).items()),
          "", "## You should know, outcome check", ""]
    for tid, h in hd.items():
        if h:
            L.append(f"- {tid[:16]} ({'resolved' if h['resolved'] else 'unresolved'}): flags_problem="
                     f"{h['flags_problem']}. {h['outcome_why']}")
    ca = st["cache"]
    tin = ca["in"] + ca["cache_read"] + ca["cache_write"]
    L += ["", "## Tokens", "", f"Scribe cache-read share: {pct(ca['cache_read'], tin)} % · output {ca['out']:,}", ""]
    L += [f"- {k}: {v:,}" for k, v in sorted(st["by_step"].items())]
    Path(__file__).with_name(f"report{sx}.md").write_text("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
