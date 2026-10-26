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

## 4. Mapping an agent session onto it

| Hyperknow | boardtalk |
|---|---|
| Lesson | One pi session |
| Tutor speech, as caption | The agent's assistant text, streamed as the caption |
| `board` card | Scribe card: title plus markdown body, written in with the same per-character dissolve |
| `*_pending` slot for slow figures | **Pending line**: the tool call, in grey, in a reserved slot the instant the tool starts. The scribe card writes into that slot. |
| Highlight on earlier text | A reference: the new card's evidence is highlighted on the older card it cites, and the pointer taps it |
| Circle | An error string, or the one key fact in a card |
| (none) | **Correction**: an orange strike drawn through the replaced card's title, plus a small "→ #6" note. The old card stays on the board (append-only). |
| New page | A fold: page 2 opens with a handoff card summarising page 1; `‹ 1/2 ›` leads back |
| Chat history markers | Transcript with markers for cards, tool calls (with a spinner while running), circles, highlights and page turns. Click a marker to fly the camera there. |
| "Model is explaining" | "Agent is working" while a turn runs |
| Input bar | Steering the agent: later work. The v0.1 viewer is read-only, so it shows replay controls. |

Our own choices (not from Hyperknow):

- **Card number:** a small grey `#n` before the title, because references and corrections cite cards by number.
- **Board font:** JetBrains Mono (OFL-1.1, via Google Fonts) instead of a hand font, chosen by the
  user. Body 14 px / 1.6, titles 16 px semibold, column 380 px wide (about 40 characters a line).
- **Exact strings** (paths, commands, error text) appear as code chips on a light grey ground. A claimed
  string that is not found in the tool output gets a dotted underline and the word "unverified".
- **Error titles** use the circle ink `#C2410C`. Every other title stays violet.

## 5. Open points

- CJK text falls back to the system monospace or sans. Pick a CJK face only if non-Latin sessions need one.
- Reduced motion: text appears at once, and annotations show their final state without drawing.
- Dark mode: Hyperknow has none on the board. Proposal: a "chalkboard" variant later, not in v0.1.
