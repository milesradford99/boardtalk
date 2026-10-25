"""Baseline arm: simple compaction. At each fold Opus rewrites one summary from (previous summary + window).

Usage: python fold.py [trajectory_id ...]
Output: data/out/<tid>/summary.json with the summary text after each fold.
"""
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor

import common as c

# The retention prompt recommended for client-side compaction in the Claude API docs (2026-10),
# used verbatim plus two spike-specific sentences at the end.
SUMMARY_SYSTEM = """Summarize the transcript inside <summary></summary> tags. Include relevant information in the summary such that this conversation will be continued by a new context window without needing to redo work or be reprovided with relevant constraints or context. Be sure to preserve: (1) any difficulties or problems that came up, and how they were handled or resolved; (2) any possibilities, options, or approaches that were raised, tried, or set aside, and why; (3) anything that was asked for, decided, agreed, ruled out, or established as a preference, constraint, or boundary - stated exactly; (4) exactly where things stand now - what has been covered, settled, or completed so far; (5) anything still open, unresolved, promised, or expected to happen next; (6) specific details that would be hard to reconstruct - names, numbers, dates, exact wording, links or references - kept exactly. Be complete on these even at the cost of length; keep everything else concise. Weight the two voices differently: keep what the user said, asked for, shared, or established carefully and close to their own words; your own explanations and reasoning can be condensed much further, to what they concluded or produced - as long as nothing in the six items above is dropped. Do not call any tools while writing this summary; respond with text only.

The original task is kept verbatim separately; you do not need to repeat it. If a previous summary is given, the new summary must replace it completely (fold its content in)."""

def run(client, ledger, tid: str) -> None:
    out_path = c.OUT / tid / "summary.json"
    if out_path.exists():
        print(f"skip {tid} summary (done)")
        return
    traj = c.load(tid)
    folds = c.fold_points(traj)
    summary, prev, by_fold = "", -1, {}
    for f in folds:
        window = [t for t in traj["turns"] if prev < t["idx"] <= f]
        content = [c.card0_text(traj)]
        if summary:
            content.append("Previous summary:\n\n" + summary)
        content.append("Transcript since then:\n\n" + c.render_turns(window))
        for attempt in range(3):  # retry-on-invalid, same prompt: the model sometimes role-plays the agent
            text = c.call_text(client, ledger, model=c.MAIN, tag=f"summary:{tid}:{f}", system=SUMMARY_SYSTEM,
                               max_tokens=16000, content=content)
            m = re.search(r"<summary>(.*?)(?:</summary>|$)", text, re.S)
            summary = (m.group(1) if m else "").strip()
            if m and len(summary) >= 1500 and "<invoke" not in summary and "<tool_calls" not in summary:
                break
            print(f"  invalid summary {tid} fold {f} attempt {attempt}: {len(summary)} chars")
        else:
            raise RuntimeError(f"summary:{tid}:{f}: no valid summary after 3 attempts")
        by_fold[f] = summary
        prev = f
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps({"folds": folds, "summaries": by_fold}, indent=1))
    print(f"done {tid} summary, tokens so far {ledger.tokens:,}")


def main() -> None:
    ids = sys.argv[1:] or c.all_ids()
    client, ledger = c.make_client(), c.Ledger(c.OUT / "ledger.jsonl")
    c.OUT.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=10) as ex:
        for f in [ex.submit(run, client, ledger, tid) for tid in ids]:
            f.result()


if __name__ == "__main__":
    main()
