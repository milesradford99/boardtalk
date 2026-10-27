# Spike S1 (throwaway)

Plan and results: `../../docs/spikes/s1-plan.md`, `s1-results.md`. Reuses S0's trajectories, questions,
client and ledger (`../s0/common.py`); S0's outputs in `../s0/data/out/` must exist. Every call uses
`deepseek-v4.1-flash`. The ledger stops at 15M tokens (`TOKEN_CAP` in `base.py`).

## Run order (each step is resumable)

```
python3 scribe.py             # lecture board per trajectory
python3 judge.py              # claim support, formality, intent coverage, You should know
python3 context.py answer     # measure 8: memory, three arms
python3 context.py grade
python3 render.py             # boards on the prototype
python3 gallery.py            # index page for review
python3 check.py              # writes report.md
```

S1b (two-stage, writes from S0's per-turn notes): set `S1_BOARD=lecture2` and run `lecture2.py`, then
`judge.py`, `render.py` and `check.py` (writes `report_2.md`); `gallery.py` shows both boards.

Run the real steps with `env -u ANTHROPIC_BASE_URL`. The key stays in `../s0/.env`.

Dry run, free: `S0_FAKE=1 S1_OUT=data/dry <step>`.
