# CLAUDE.md - beam.omarchy

> Identity and global operating rules live in `~/.claude/CLAUDE.md`.
> This file is ONLY the context for this project.

## What this is

**Beam** (`nixfred.beam`) is an Omarchy plugin that puts the desktop you are sitting at onto
an iPad, using Sunshine to send and Moonlight to show. A guided wizard takes a first-timer
from nothing to a live picture; an expert screen does the whole job in one click.

`PRD.md` is the spec and it is normative. **Astra6 (`gpt-6-astra`) builds from it, clean.**
`prototype/` holds a working first cut kept as reference: read it to see how something was
done, do not copy it wholesale. Where anything in this repo disagrees with the PRD, the PRD
wins.

## The rule that shapes everything

**Beam does not know or care what kind of machine it is on.** Laptop, desktop, VM, a server
with a monitor hanging off it: if there is an Omarchy session with a display and an address,
Beam works. There must be no VM-specific, laptop-specific or GPU-specific code path anywhere
in it. This project began as a VM-specific runbook and was deliberately widened on
2026-09-19; do not let host assumptions creep back in.

The second rule: **the CLI owns every fact and every action, the QML only asks and relays.**
The bar dot, the wizard and a terminal can then never tell the user three different stories,
and the whole product is testable without a GUI.

## Two things Beam must never do

- **Never handle a sudo password.** The one step needing root opens a terminal the human can
  see and type into.
- **Never create, store or read the Sunshine admin password.** It detects only that a
  `username` line exists in `sunshine.conf`.

## Layout

```
PRD.md                  the spec. Normative. Astra6 builds from this.
CLAUDE.md               this file
docs/original-runbook.md  the 2,400-word runbook Beam exists to replace
prototype/              a working first cut. Reference, not gospel.
  bin/omarchy-beam      the CLI. Run, JSON validated, one real bug fixed in it.
  *.qml, manifest.json  never loaded into a shell. A sketch. Unverified.
```

## Verified on gus, 2026-09-19

Full list with evidence is PRD.md section 4. The two that trip people up:

- **The stock Sunshine installer is broken.** `omarchy-install-service-sunshine` runs under
  `set -e` and enables `sunshine.service`, but the package ships
  `app-dev.lizardbyte.app.Sunshine.service`. It dies before the firewall, web app and
  autostart steps. Beam installs the package directly and reuses the stock firewall/web-app functions, avoiding the broken service-enable step. Repair also fixes older interrupted installs.
- **A render node does not mean hardware encoding.** virtio-gpu shows `/dev/dri/renderD128`
  and cannot encode a frame. The only honest source is Sunshine's own
  `Found H.264 encoder:` log line. Never infer it from a DRM device.

## House rules that bind this repo

- **Law 17, nothing scrolls.** All plugin information and controls must fit without
  scrolling, clipping or unreadable text. No subsection or log-box exception. Expert mode
  uses grouped columns and a concise action report. See PRD section 7.4 and the live host
  references in `docs/style-reference.md`.
- QML gotchas that have already cost time are listed in PRD.md section 9. Read them before
  writing QML, not after.
- No em-dashes anywhere.
- Any file path quoted to Fred in chat is a full `file:///home/pi/...` URL.
- This repo is **public** (`github.com/nixfred/beam`). Sanitize before every push, and run
  `git remote -v` first.
