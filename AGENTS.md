# AGENTS.md

## Commands

- Node ≥ 22.18 runs TypeScript directly (type stripping); there is no build step yet.
- `npm ci` installs dev tools (TypeScript, `@types/node`). There are no runtime dependencies in
  `@boardtalk/core`.
- `npm run check`: typecheck plus all tests. Run it before every commit.
- One test file: `node --test packages/core/test/core.test.ts`.

## Gotchas

- Only erasable TypeScript syntax (`erasableSyntaxOnly`): no `enum`, `namespace` or constructor
  parameter properties. Node strips types; it does not compile them.
- Relative imports use the `.ts` extension (`./board.ts`).
- The board is **append-only**. Never add an API that edits or deletes an event; a correction is a
  new card with `supersedes`. Tests enforce this.
- `@boardtalk/core` must not import pi or any agent SDK (ADR 0002). Agent-specific code goes in
  its own package.
- `spikes/` is experiment code (Python), kept for reproducibility. It is not product code and
  not covered by `npm run check`. Its `.env` holds an API key and is gitignored.
- Design decisions live in `docs/adr/`. Read ADR 0001 and ADR 0002 before changing the board model
  or the pi integration.
