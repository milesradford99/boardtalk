# Board UI: following Hyperknow's board

Status: draft, 2026-10-25. The user chose Hyperknow's board UI over three earlier drawn directions
(signal plates, field notebook, lightbox lanes), which are not kept. This page records what that UI does, measured on the
live product, and how boardtalk maps an agent session onto it.

Source: one live lesson on agent.hyperknow.io ("Rules, Machine Learning, and Generative AI"),
inspected through the DOM and computed styles. Values below are measured, not guessed. Where a
value is our own choice, it says so.

We follow the interaction and motion grammar. We do not copy Hyperknow's name, logo, chrome icons,
illustrations or copy. We also do not use its hand font: the board text is monospace (§4).

## 1. What Hyperknow's board is

- **No card boxes.** Ink sits directly on a dotted plane. A "card" is a block of text: a title, then
  a markdown body. There are no borders, fills or shadows. Tables get hand-drawn frames.
- **Plane:** background `#FCFCFC`, dots `rgb(212,212,212)` drawn as a `radial-gradient`, spacing
  28 board units (19.6 px at the default 70 % zoom). The dot grid pans with the camera, and can be
  turned off in settings.
- **Hand font:** Virgil for Latin, Xiaolai for CJK. A setting switches to a standard sans
  (MiSans). Inline code and table cells inherit the hand font.
- **Card geometry (board units):** column tile 514 wide, padding `0 15px 4px`, title 28 px,
  body 23 px, line height 1.5, list items `margin .32em`. Default render scale is 0.7, so on screen a
  card is 360 px wide with a 16 px body.
- **Title:** centred, violet `#6741D9`, regular weight, with a highlighter band
  `linear-gradient(transparent 55%, rgba(254,243,199,.78) 55%)` behind its lower half.
- **Body:** `#262626`. Bold uses the same colour. Lists are indented 1.25 em.
- **Layout:** 2–3 columns, 25 px gutter. Each column keeps a `nextY`; a new card goes below the
  last card in the active column. Coordinates come from code, never from the model.
- **Pages:** `‹ 1/1 ›` in the top bar. A new page starts a fresh plane.

## 2. Motion (measured)

| What | How | Timing |
|---|---|---|
| Card text writes in | Each character is a span; it goes from `opacity 0, blur(3px)` to sharp | 360 ms per char, about 110 chars/s |
| Title highlighter | Background size sweeps from 0 % to 100 % wide, after the title is written | 420 ms, ease |
| Table frame | `clip-path` reveals left to right; lines wobble via an SVG turbulence filter | 620 ms |
| Circle | SVG ellipse, stroke `#C2410C`, 2.5 px, turbulence displacement 1.2; stroke-dash draw | 1.8 s, ease |
| Highlight | Rounded rect `rgba(254,243,199,.62)` behind the text; clip width grows 0 → w | 1.8 s, spline (.22, 1, .36, 1) |
| Pointer | Amber stick (`#FDE68A` fill, `#B45309` stroke) taps the point being talked about, then idles | tap 420 ms; idle wobble 2.4 s; fade 380 ms |
| Caption | Speech appears 2 characters at a time, each chunk fading in from `blur(2px)`; blinking caret | about 110 ms per chunk; fade 600 ms |
| Camera | Eases to keep the active column and the newest card in view; older columns slide off the left | eased pan |

Annotations are anchored to text (`target_board_id` + snippet), never to model-chosen pixels.

## 3. Chrome around the board

- **Top left:** close button, then a pill with the session title and a connection indicator.
- **Top centre:** zoom `−  100 %  +`, page `‹ 1/1 ›`, share or export, settings, feedback.
- **Right panel, 380 px: "Chat history".** The transcript as plain text. Older paragraphs are grey
  and the newest is dark. User messages are right-aligned bubbles. Board actions show inline as
  small grey markers that you can click: ✎ for a card (by its title), ○ Circle, highlighter for
  Highlight, plus Figure. A live status row reads "Model is explaining".
- **Bottom centre:** the caption over the board, max 640 px wide, 16 px/500 `#1F1F1F`, on a
  `rgba(250,250,250,.82)` halo with a 2 px blur.
- **Input bar:** "Ask a question…", microphone, pause, stop.

## 4. What the board shows: an append-only lecture of the design

Decided by the user, 2026-10-25. The board keeps Hyperknow's lecture format: cards are appended in
reading order, filling one column top to bottom and then starting the next. Nothing already on the
board is edited or moved. What changes from a trajectory is the **content**: a card is a formal
statement about the work, never one card per tool call. The step-by-step trail lives in the
transcript panel.

**Card types,** each with a small eyebrow naming its source:

| Eyebrow | What it says | Example titles |
|---|---|---|
| **Your intent** | What the user asked for, constraints, and steering added mid-session | What you asked for · Constraints · You added a constraint |
| **Agent's design** | Understanding, decisions with rejected options, the change | Where it breaks · Decision · Change |
| **Evidence** | Results of checks | First test run · Full test run |
| **You should know** | What the user might have missed (see below) | [[]] becomes a String · No depth limit |
| **For you** | Questions the agent needs answered | Open question |

- **Revision is a new card.** "Decision, revised" is appended where the work is now. The old
  "Decision" card stays in place, struck through in grey, with a link: `revised: see "Decision, revised"`.
- **"You should know" notes are appended cards too,** placed at the moment the side agent notices
  something, with a violet rule and eyebrow, a short label ("Tradeoff", "Limit"), and two choices:
  **Knew this** and **Dismiss**. Modelled on Claude Code's "You should know" mod: a side agent with no
  tools rereads the session and surfaces a tradeoff chosen without calling it out, a limit, or a result
  that may be off. boardtalk's scribe already is such a side agent, so the notes come from the same
  call. Answering a note changes only how it looks; the card stays.
- **Low-level work** (each tool call) shows only as one quiet activity line above the caption
  ("pytest -q · 2.1 s"), and as a marker in the transcript.
- **Links back to intent:** when the agent's work meets a constraint or done-when item, that text is
  highlighted on the earlier intent card and the pointer taps it. A highlight is a decoration over an
  existing card, not an edit of it.
- **Box:** a precise rounded rectangle, violet `#6741D9`, 1.5 px, radius 5, drawn as one stroke in
  0.9 s, around the one key fact in a card. Replaces Hyperknow's rough circle at the user's request.
- **Static view:** the same log replayed without animation (`board.html#final`).

Our own choices (not from Hyperknow):

- **Board font:** JetBrains Mono (OFL-1.1, via Google Fonts) instead of a hand font, chosen by the
  user. Body 14 px / 1.6, titles 16 px semibold, columns 380 px wide.
- **Exact strings** (paths, commands, error text) appear as code chips on a light grey ground.
- **Quiet text** (eyebrows, struck-through cards) uses `#737373`, which passes WCAG AA on the plane
  (4.6:1).

## 5. Open points

- CJK text falls back to the system monospace or sans. Pick a CJK face only if non-Latin sessions need one.
- Reduced motion: text appears at once, and annotations show their final state without drawing.
- Dark mode: Hyperknow has none on the board. Proposal: a "chalkboard" variant later, not in v0.1.
- **Relation to ADR 0001.** Settled by S1 (`docs/spikes/s1-results.md`): lecture cards are not
  enough as model context. Per-turn notes stay in the log as the context; the lecture board is drawn
  from them as the human's view.
- **Long code chips** overflow the 380 px column (seen on real sessions in S1). They should wrap or
  scroll inside the card.
- **Event model.** Core events need an eyebrow kind (intent, design, evidence, heads-up, question),
  marks (box, highlight on a snippet) and the heads-up label. Corrections already use `supersedes`.
  That is a public API change, to be proposed separately.
