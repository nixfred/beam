# README graphics

All README assets are stored in this directory and use relative links. No
external image host, tracking badge, or live metric service is required.

| Asset | Origin |
| --- | --- |
| `beam-hero.png` | Original conceptual banner, generated with the built-in imagegen tool. |
| `beam-flow.svg` | Editable vector diagram authored for Beam. |
| `beam-states.svg` | Editable vector illustration of the four bar states. |
| `beam-expert-dark.png` | Native panel capture, Tokyo Night theme. |
| `beam-expert-light.png` | Native panel capture, Catppuccin Latte theme. |
| `beam-guided.png` | Native panel capture of the computer setup step. |

The screenshots are real captures from the isolated Omarchy test VM at
1280x800. The region was taken directly from the live panel's measured bounds
using `grim -g`. Its content was not retouched or generated. For publication,
the VM's UI receives the documentation-only address `192.0.2.10` before capture;
both its text and QR code use that fixture. No private network address appears
in these public captures. Installation is real; no iPad stream or completed
pairing is implied. The fixture is not part of production code.

For this later README capture pass, Sunshine was reinstalled in the existing
task VM. The VM was stopped afterward with that screenshot setup preserved.
The earlier removal test and its saved evidence remain unchanged.

GitHub's `<picture>` support selects the expert screenshot matching the reader's
color preference. Explicit full-size links remain available for either theme.
The SVGs use system fonts, contain no scripts, and have accessible titles and
descriptions. The hero is illustrative and separate from the product captures.

## Hero generation

Generated using the **built-in imagegen tool**, with no CLI or API fallback.
Final asset: [beam-hero.png](beam-hero.png), 1983x793 PNG. The generated output
was copied into this repository unchanged.

Prompt:

```text
Use case: ads-marketing
Asset type: a striking ultrawide GitHub README hero banner for the open-source Omarchy plugin Beam.
Primary request: Make an exceptionally polished, bold technology launch graphic. Beam helps stream an existing Linux desktop to an iPad through Sunshine and Moonlight.
Composition: panoramic 2.5:1 landscape, generous safe margins. The left 42 percent is elegant typography and dark negative space. On the right, a beautifully rendered thin desktop monitor and a landscape tablet are linked by an energetic luminous ribbon of light, suggesting the desktop travelling onto the tablet. The tablet is in the foreground, monitor behind; both show matching abstract midnight mountain/wave wallpapers and tiny restrained desktop panels. This is conceptual artwork, never imitate a real application screenshot.
Text, verbatim and only these three lines: "AN OMARCHY PLUGIN", "BEAM", "Your desktop. On your iPad."
Make BEAM very large, heavy, confident modern sans serif with carefully spaced letters and a subtle metallic-white finish. The other two lines are crisp, small, completely readable, aligned with the title.
Style: premium editorial 3D technology illustration, dark anodized hardware, restrained bloom, fine grain, crisp edges, intentional depth and gorgeous reflected light. Deep midnight navy, luminous periwinkle and icy cyan, a small warm peach highlight echoing the plugin's dark-theme screenshots. A thin orbital/light-path motif and a subtle distant grid may support the connection, without becoming busy.
Lighting: dramatic edge light with a bright elegant beam passing between the screens. The devices must be legible against the backdrop. Strong composition that stays impressive when downscaled to GitHub's 900px content width.
Constraints: no Apple logo, no other logos, no people, no hands, no nonsense UI text, no extra captions, no performance claims, no fake badges, no watermarks, no frames around the entire image. Deliver one finished landscape banner.
```
