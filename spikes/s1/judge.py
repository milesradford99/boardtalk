"""Model-judged measures: claim support and formality (2, 6), intent coverage (3), You-should-know (4, 5).

The judge always sees the source (cited turns, the request, or the whole transcript), never just the card.
Usage: python judge.py [trajectory_id ...]
Output: data/out/<tid>/judge_cards.json, intent.json, heads.json
"""
import json
import sys
from concurrent.futures import ThreadPoolExecutor

import base as b
from base import c

BATCH = 6

CARD_SYSTEM = """You check cards that a scribe wrote about a software agent's session. For each card you get
its text and the source turns it cites. Grade two things per card:
- support: "supported" (every claim in the card is stated or directly shown in the cited source),
  "partial" (some claim goes beyond the source or is imprecise), or "unsupported" (a main claim is
  not in the source or contradicts it).
- level: "design" (a statement about the problem, intent, a decision, a change, a result or a risk
  that a reviewer would keep) or "step" (narrates a tool action or a next step, e.g. "Opened file X",
  "Running the tests", "Will look at Y").
Judge only against the cited source."""

CARD_SCHEMA = {"type": "object", "properties": {"grades": {"type": "array", "items": {
    "type": "object",
    "properties": {"id": {"type": "integer"},
                   "support": {"type": "string", "enum": ["supported", "partial", "unsupported"]},
                   "level": {"type": "string", "enum": ["design", "step"]},
                   "why": {"type": "string"}},
    "required": ["id", "support", "level", "why"], "additionalProperties": False}}},
    "required": ["grades"], "additionalProperties": False}

REQ_SYSTEM = """You read a request given to a software agent and list its atomic requirements: each
separate thing the user asked for or constrained (behaviour to fix or add, constraints such as files
not to touch, required tests or checks). Skip generic boilerplate about the environment or how to
work, unless it is a constraint on the result. 2-10 requirements, each one short sentence."""

REQ_SCHEMA = {"type": "object", "properties": {"requirements": {"type": "array", "items": {"type": "string"}}},
              "required": ["requirements"], "additionalProperties": False}

COV_SYSTEM = """You check whether a whiteboard's intent cards record a list of requirements. For each
requirement answer "yes" (an intent card states it, in any words), "partial" (mentioned but missing a
key part), or "no"."""

COV_SCHEMA = {"type": "object", "properties": {"coverage": {"type": "array", "items": {
    "type": "object",
    "properties": {"n": {"type": "integer"}, "covered": {"type": "string", "enum": ["yes", "partial", "no"]}},
    "required": ["n", "covered"], "additionalProperties": False}}},
    "required": ["coverage"], "additionalProperties": False}

HEADS_SYSTEM = """You review "You should know" notes that a side agent added to a whiteboard while
watching a software agent work. A good note tells the user something TRUE that they might miss and
would want to know: an unflagged tradeoff, a limit, a result that may be off. You get the full
transcript and the notes. For each note decide:
- true: is it supported by the transcript (at the moment it was written)?
- new: did the agent NOT already say it plainly in its own messages up to that point?
- useful: would the user plausibly want to be told this?
Then, separately, the session outcome: you are told whether the agent's final change actually passed
the hidden tests. Answer `flags_problem`: if it FAILED, does any note point at a real reason the work
may be wrong or incomplete (for example the fix was never verified against the real tests, a
requirement was not met, an edge case is unhandled)? If it PASSED, does any note wrongly claim the work
is broken (a false alarm)? Explain in one sentence."""

HEADS_SCHEMA = {"type": "object", "properties": {
    "notes": {"type": "array", "items": {"type": "object", "properties": {
        "id": {"type": "integer"}, "true": {"type": "boolean"}, "new": {"type": "boolean"},
        "useful": {"type": "boolean"}, "why": {"type": "string"}},
        "required": ["id", "true", "new", "useful", "why"], "additionalProperties": False}},
    "flags_problem": {"type": "boolean"}, "outcome_why": {"type": "string"}},
    "required": ["notes", "flags_problem", "outcome_why"], "additionalProperties": False}


def card_text(x: dict) -> str:
    label = f" · {x['heads_label']}" if x.get("heads_label") else ""
    return f"Card #{x['id']} [{x['kind']}{label}] {x['title']}\n{x['body_md']}"


def cached(path, fn):
    if path.exists():
        return json.loads(path.read_text())
    out = fn()
    path.write_text(json.dumps(out, indent=1))
    return out


def judge_cards(client, ledger, tid, traj, lec) -> dict:
    def go():
        grades = {}
        cards = lec["cards"]
        for i in range(0, len(cards), BATCH):
            group = cards[i:i + BATCH]
            src = sorted({s for x in group for s in x["src_turns"]})
            out = c.call_json(client, ledger, model=b.MODEL, tag=f"judge_cards:{tid}:{i}", system=CARD_SYSTEM,
                              max_tokens=16000, schema=CARD_SCHEMA,
                              content=["## Cited source\n\n" + b.source_text(traj, src),
                                       "## Cards\n\n" + "\n\n".join(
                                           card_text(x) + f"\n(cites {b.turns_label(x['src_turns'])})" for x in group)])
            for g in out["grades"]:
                grades[str(g["id"])] = g
        return {"grades": grades}
    return cached(b.OUT / tid / "judge_cards.json", go)


def judge_intent(client, ledger, tid, traj, lec) -> dict:
    def go():
        reqs = c.call_json(client, ledger, model=b.MODEL, tag=f"requirements:{tid}", system=REQ_SYSTEM,
                           max_tokens=4000, schema=REQ_SCHEMA, content=[traj["task"]])["requirements"]
        intent = [x for x in lec["cards"] if x["kind"] == "intent"]
        cov = c.call_json(client, ledger, model=b.MODEL, tag=f"coverage:{tid}", system=COV_SYSTEM,
                          max_tokens=4000, schema=COV_SCHEMA,
                          content=["## Intent cards\n\n" + ("\n\n".join(card_text(x) for x in intent) or "(none)"),
                                   "## Requirements\n\n" + "\n".join(f"{n}. {r}" for n, r in enumerate(reqs))])
        got = {g["n"]: g["covered"] for g in cov["coverage"]}
        return {"requirements": [{"n": n, "text": r, "covered": got.get(n, "no")} for n, r in enumerate(reqs)]}
    return cached(b.OUT / tid / "intent.json", go)


def judge_heads(client, ledger, tid, traj, lec) -> dict:
    def go():
        notes = [x for x in lec["cards"] if x["kind"] == "heads_up"]
        outcome = ("PASSED: the final change passed the hidden tests." if traj["resolved"] else
                   "FAILED: the final change did not pass the hidden tests.")
        out = c.call_json(client, ledger, model=b.MODEL, tag=f"heads:{tid}", system=HEADS_SYSTEM,
                          max_tokens=24000, schema=HEADS_SCHEMA,
                          content=[b.task_block(traj), "## Transcript\n\n" + c.render_turns(traj["turns"]),
                                   "## Notes\n\n" + ("\n\n".join(card_text(x) + f"\n(written at turn {x['turn']})"
                                                                 for x in notes) or "(no notes)"),
                                   "## Outcome\n\n" + outcome])
        return {"resolved": traj["resolved"], **out}
    return cached(b.OUT / tid / "heads.json", go)


def run(client, ledger, tid: str) -> None:
    traj, lec = c.load(tid), b.lecture(tid)
    judge_cards(client, ledger, tid, traj, lec)
    judge_intent(client, ledger, tid, traj, lec)
    judge_heads(client, ledger, tid, traj, lec)
    print(f"judged {tid}, tokens so far {ledger.tokens:,}")


def main() -> None:
    ids = sys.argv[1:] or c.all_ids()
    client, ledger = c.make_client(), b.ledger()
    with ThreadPoolExecutor(max_workers=10) as ex:
        for f in [ex.submit(run, client, ledger, tid) for tid in ids]:
            f.result()


if __name__ == "__main__":
    main()
