# Spike S0b: board vs summary at equal token budget

Status: **done** 2026-10-25. Results: `s0b-results.md`. Reuses S0's trajectories, questions, boards and Ark setup.

## Question

S0 showed the board recalls ~96% vs ~60% for a summary, but the boards were 61–95% the size of
the raw text, while the summary was 5.6%. **At the same token budget, does the board's structure
still win?**

## Arms (per trajectory, per budget B ∈ {2k, 5k, 10k} tokens)

The budget covers only the compressed part (everything before the last fold). Card #0 (the task)
and the live window after the last fold are given to every arm and not counted. Tokens ≈ chars/4,
as in S0.

- **summary@B:** simple compaction exactly as in S0 (same retention prompt, recursive at every
  fold), plus a hard length limit of B. Outputs over 1.15×B are retried with feedback, up to 3
  attempts; the achieved size is reported.
- **board_pro@B / board_flash@B:** the S0 board at the last fold, brought under B by a
  **second-level fold**. Pages are the cards of one fold window, including its handoff card.
  - Keep the newest pages verbatim while they fit in B/2.
  - Fold each older page **once** into a digest. Each digest is written by `deepseek-v4-pro` from that
    page's cards only, keeps card ids as anchors, and has a per-page share of the remaining budget.
  - If a share would be under 150 tokens, the older pages are digested together into one digest.
  - This matches the online behavior in ADR 0001 §7: a page is digested once when it ages out, and
    old content is never re-summarized again and again. The recursive summary, by contrast,
    rewrites its history at every fold. This structural difference is part of what is being
    tested.
- **No retrieval** (`board_read(id)`) in this test. That makes it conservative for the board,
  whose real design can fetch a card by id.

## Scoring

The same 199 questions, the same answering prompt and model (`deepseek-v4-pro`), and the same
grading: exact match for identifiers, and a blind `kimi-k3` judge for the rest. The judge sees one
budget group at a time (3 answers per question, shuffled).

## Reading the result

- **board@B ≥ summary@B at 2k and 5k:** structure does the work; ADR 0001's cost case stands.
- **board wins only at 10k or above:** the board is a better *record* that costs tokens. ADR 0001
  narrows to that value case.
- **summary ≥ board at every budget:** S0's gap was size. Rethink before building.
