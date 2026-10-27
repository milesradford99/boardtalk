"""Gallery page for the rendered boards: one row per session with its numbers, the 3 boards picked for
human review (by seed: 2 resolved, 1 unresolved), and the requirement lists for spot-checking.

Usage: python gallery.py   (after render.py; writes data/out/gallery/index.html and copies the boards)
"""
import html
import json
import random
import shutil

import base as b
from base import c

SEED = 20261026


def review_ids(ids: list[str]) -> list[str]:
    rng = random.Random(SEED)
    res = sorted(t for t in ids if c.load(t)["resolved"])
    unres = sorted(t for t in ids if not c.load(t)["resolved"])
    return rng.sample(res, 2) + rng.sample(unres, 1)


def load(tid, name):
    p = b.OUT / tid / name
    return json.loads(p.read_text()) if p.exists() else None


CSS = """
/* Layout: one reading column on the board's dotted plane; each session is a row of facts, not a card. */
:root {
  --plane: #FCFCFC; --dot: #D4D4D4; --ink: #262626; --quiet: #6B6B6B; --violet: #6741D9;
  --hl: rgba(254, 243, 199, .78); --rule: #E5E5E5; --chip: #F1F0F4;
  --mono: "JetBrains Mono", ui-monospace, Menlo, Consolas, monospace;
  --sans: "Figtree", system-ui, -apple-system, "Segoe UI", sans-serif;
}
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) {
  --plane: #17161B; --dot: #34323C; --ink: #E8E6EE; --quiet: #A09DAA; --violet: #A58BFF;
  --hl: rgba(161, 126, 20, .45); --rule: #2E2C35; --chip: #24222B; color-scheme: dark } }
:root[data-theme="dark"] {
  --plane: #17161B; --dot: #34323C; --ink: #E8E6EE; --quiet: #A09DAA; --violet: #A58BFF;
  --hl: rgba(161, 126, 20, .45); --rule: #2E2C35; --chip: #24222B; color-scheme: dark }
body { background: var(--plane); background-image: radial-gradient(var(--dot) 1px, transparent 1.2px);
  background-size: 19.6px 19.6px; color: var(--ink); font: 15px/1.6 var(--sans); }
main { max-width: 860px; margin: 0 auto; padding-block: 40px 64px;
  padding-left: max(16px, env(safe-area-inset-left, 0px)); padding-right: max(16px, env(safe-area-inset-right, 0px));
  display: grid; gap: 36px; }
h1 { font: 600 22px/1.3 var(--mono); margin: 0; text-wrap: balance; }
h1 span { background: linear-gradient(transparent 55%, var(--hl) 55%); }
h2 { font: 600 15px/1.4 var(--mono); color: var(--violet); margin: 0 0 12px; letter-spacing: .02em; }
p { margin: 0; max-width: 65ch; }
.lede { display: grid; gap: 10px; }
.quiet { color: var(--quiet); }
code, .mono { font-family: var(--mono); font-size: 13px; }
code { background: var(--chip); padding: 1px 5px; border-radius: 4px; }
.scroll { overflow-x: auto; }
table { border-collapse: collapse; width: 100%; font-variant-numeric: tabular-nums; min-width: 640px; }
th, td { text-align: left; padding: 9px 10px; border-bottom: 1px solid var(--rule); vertical-align: top; }
th { font: 500 12px/1.3 var(--mono); color: var(--quiet); letter-spacing: .04em; text-transform: uppercase; }
td.n { text-align: right; font-family: var(--mono); font-size: 13px; }
a { color: var(--violet); text-underline-offset: 3px; }
a:focus-visible { outline: 2px solid var(--violet); outline-offset: 2px; border-radius: 3px; }
.tag { font: 500 12px var(--mono); padding: 1px 7px; border-radius: 999px; border: 1px solid var(--rule); white-space: nowrap; }
.tag.no { border-color: var(--violet); color: var(--violet); }
.review { display: grid; gap: 14px; }
.review li { display: grid; gap: 4px; }
ol, ul { margin: 0; padding-left: 1.3em; display: grid; gap: 8px; }
details { border-top: 1px solid var(--rule); padding-block: 10px; }
summary { cursor: pointer; font-family: var(--mono); font-size: 13px; }
summary:focus-visible { outline: 2px solid var(--violet); outline-offset: 2px; }
details ol { margin-top: 10px; gap: 4px; }
.cov { font: 500 12px var(--mono); color: var(--quiet); }
"""


def counts(lec: dict) -> dict:
    return {k: sum(1 for x in lec["cards"] if x["kind"] == k) for k in b.KINDS}


def supported(tid: str, sx: str) -> str:
    jc = load(tid, f"judge_cards{sx}.json")
    return f"{sum(g['support'] == 'supported' for g in jc['grades'].values())}/{len(jc['grades'])}" if jc else "–"


def main() -> None:
    ids = c.all_ids()
    picks = review_ids(ids)
    two = all((b.OUT / t / "lecture2.json").exists() for t in ids)
    gdir = b.OUT / "gallery"
    for d in ("boards", "boards2"):
        (gdir / d).mkdir(parents=True, exist_ok=True)
    rows, reqs = [], []
    for tid in ids:
        traj, lec = c.load(tid), b.lecture(tid, "lecture")
        shutil.copy(b.OUT / "boards" / f"{tid}.html", gdir / "boards" / f"{tid}.html")
        k1 = counts(lec)
        state = '<span class="tag">resolved</span>' if traj["resolved"] else '<span class="tag no">unresolved</span>'
        s1 = (f"<a href=\"boards/{tid}.html\">S1</a> · {len(lec['cards'])} cards, {k1['heads_up']} notes, "
              f"{supported(tid, '')} supported")
        s2 = "–"
        if two:
            shutil.copy(b.OUT / "boards_2" / f"{tid}.html", gdir / "boards2" / f"{tid}.html")
            lec2 = b.lecture(tid, "lecture2")
            s2 = (f"<a href=\"boards2/{tid}.html\">S1b</a> · {len(lec2['cards'])} cards, "
                  f"{counts(lec2)['heads_up']} notes, {supported(tid, '_2')} supported")
        rows.append(f"<tr><td>{html.escape(traj['repo'])}</td><td>{state}</td><td class=\"n\">{len(traj['turns'])}</td>"
                    f"<td>{s1}</td><td>{s2}</td></tr>")
        rq = load(tid, "requirements.json")
        if rq:
            cov1 = {r["n"]: r["covered"] for r in (load(tid, "coverage.json") or {"requirements": []})["requirements"]}
            cov2 = {r["n"]: r["covered"] for r in (load(tid, "coverage_2.json") or {"requirements": []})["requirements"]}
            items = "".join(f"<li>{html.escape(r)} <span class=\"cov\">· S1: {cov1.get(n, '–')} · S1b: {cov2.get(n, '–')}</span></li>"
                            for n, r in enumerate(rq["requirements"]))
            reqs.append(f"<details><summary>{html.escape(traj['repo'])}</summary><ol start=\"0\">{items}</ol></details>")

    def links(t):
        r = c.load(t)
        both = (f'<a href="boards/{t}.html">S1 board</a>' +
                (f' · <a href="boards2/{t}.html">S1b board</a>' if two else ""))
        return (f"<li><strong>{html.escape(r['repo'])}</strong> <span class=\"quiet\">({'resolved' if r['resolved'] else 'unresolved'}, "
                f"{len(r['turns'])} turns)</span><br>{both}</li>")
    review = "".join(links(t) for t in picks)
    page = f"""<title>S1 Lecture Boards</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Figtree:wght@400;500;600&family=JetBrains+Mono:wght@400;500;600&display=swap">
<style>{CSS}</style>
<main>
  <section class="lede">
    <h1><span>S1 lecture boards</span></h1>
    <p>Ten real agent sessions from SWE-rebench (OpenHands, CC-BY-4.0), each drawn twice by
    <code>deepseek-v4.1-flash</code>. <strong>S1</strong>: the scribe read the raw session one turn at a time.
    <strong>S1b</strong>: the writer read the per-turn notes every five turns and cites them.
    Add <code>#final</code> to a board's address for the finished board without animation.</p>
  </section>
  <section class="review">
    <h2>Your review: three sessions, two boards each</h2>
    <p>For each board: <strong>would you keep this as the record of the session?</strong>
    Yes, with fixes, or no, plus one line on why. Then: which of the two do you prefer?</p>
    <ol>{review}</ol>
  </section>
  <section>
    <h2>All sessions</h2>
    <div class="scroll"><table>
      <thead><tr><th>Session</th><th>Outcome</th><th>Turns</th><th>S1 (raw turns)</th><th>S1b (from notes)</th></tr></thead>
      <tbody>{''.join(rows)}</tbody>
    </table></div>
  </section>
  <section>
    <h2>Requirement lists to spot-check</h2>
    <p class="quiet">Intent coverage is scored against these lists, which the model extracted from each request.
    Please check that two of them match what the request actually asks.</p>
    {''.join(reqs) or '<p class="quiet">Not judged yet.</p>'}
  </section>
</main>
"""
    (gdir / "index.html").write_text(page)
    print(f"gallery: {gdir / 'index.html'} · review: {', '.join(t[:16] for t in picks)}")


if __name__ == "__main__":
    main()
