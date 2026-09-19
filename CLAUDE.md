# CLAUDE.md - beam.omarchy

> Identity and global operating rules live in `~/.claude/CLAUDE.md`.
> This file is ONLY the context for this project.

## What this is

**Beam** (`nixfred.beam`) is an Omarchy plugin that puts the desktop you are sitting at onto
an iPad, using Sunshine to send and Moonlight to show. A guided wizard takes a first-timer
from nothing to a live picture; an expert screen does the whole job in one click.

`PRD.md` is the spec and it is normative. **Astra6 (`gpt-6-astra`) builds from it, clean.**
A working prototype was written and then deliberately deleted so the build starts from the
spec, not from a sketch; everything it proved is written into the PRD, and it is recoverable
from commit `29cb14c` if ever needed. Where anything disagrees with the PRD, the PRD wins.

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
```

## Verified on gus, 2026-09-19

Full list with evidence is PRD.md section 4. The two that trip people up:

- **The stock Sunshine installer is broken.** `omarchy-install-service-sunshine` runs under
  `set -e` and enables `sunshine.service`, but the package ships
  `app-dev.lizardbyte.app.Sunshine.service`. It dies before the firewall, web app and
  autostart steps. Beam repairs around it; a separate upstream PR fixes it properly.
- **A render node does not mean hardware encoding.** virtio-gpu shows `/dev/dri/renderD128`
  and cannot encode a frame. The only honest source is Sunshine's own
  `Found H.264 encoder:` log line. Never infer it from a DRM device.

## House rules that bind this repo

- **Law 17, nothing scrolls.** No page-level scroller in either panel mode. The log box in
  expert mode is the single permitted scroller, and it scrolls in place.
- QML gotchas that have already cost time are listed in PRD.md section 9. Read them before
  writing QML, not after.
- No em-dashes anywhere.
- Any file path quoted to Fred in chat is a full `file:///home/pi/...` URL.
- This repo is **public** (`github.com/nixfred/beam`). Sanitize before every push, and run
  `git remote -v` first.
