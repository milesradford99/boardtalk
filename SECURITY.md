# Security policy

## Reporting a vulnerability

Please **do not open a public issue.** Report it privately through GitHub's
**"Report a vulnerability"** button (Security tab → Advisories) on this repository. We aim to
acknowledge reports within 7 days. This is a best-effort project with no SLA.

## Supported versions

Pre-1.0: only the latest release receives fixes.

## Threat model in brief

boardtalk's pi extension runs **inside the pi process with the same permissions**. It can see
prompts, tool calls, file contents and command output, which often contain secrets. Our commitments:

- Session content is sent **only** to the model provider the user configured in pi, for the
  scribe. It goes to no other service, and there is no telemetry.
- The live canvas server binds to **localhost only**.
- Board events are stored in the user's own pi session file, and are never added to the model's
  context.
- Exported canvases are **redacted** for known secret patterns before writing, and export is
  always an explicit user action.
- Verbatim strings that cannot be verified against the source are marked as unverified, never
  shown as fact.

A report that breaks any of these is a security issue.
