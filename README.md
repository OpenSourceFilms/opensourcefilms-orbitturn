# OrbitTurn / H3

Experimental generative-video tooling for propagating a deliberately altered
scene through an existing photographed camera move, developed by
[Open Source Films](https://github.com/OpenSourceFilms) during production
R&D for LifeR.

## Upstream credit and contribution boundary

**OrbitTurn is an OSF-developed workflow and set of extensions using other creators' generative-video technology, not an original video-generation model.** The primary production path described here uses [MiniMax's H3 model](https://github.com/MiniMax-AI/MiniMax-H3) through [ComfyUI](https://github.com/Comfy-Org/ComfyUI); the evaluation also considered upstream LTX, Wan, FlexAM and other independent projects. Those creators retain credit and licensing authority over their own systems.

OSF's contributions are the shot-specific conditioning approach, integration nodes, orchestration, evaluation and frame-output engineering described below. Neither OSF's MIT licence nor the published workflow redistributes or relicenses upstream models, weights or core software. See [THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md) for the known rights boundaries and unresolved checks.

## Important H3 and LTX licence limits

MiniMax H3 is **not** under the repository's MIT licence. Its
[official Community License](https://huggingface.co/MiniMaxAI/MiniMax-H3/blob/main/LICENSE)
excludes the **United States, European Union, United Kingdom and Republic
of Korea** from the standard licensed territory and restricts use and
display of **model Outputs** outside the permitted territory. This
potentially affects the international release or exhibition of footage
generated with H3, even if generation took place in Australia.
Certain commercial products/services also require written permission,
prominent MiniMax identification and downstream safeguards.

LTX 2.5 weights and the ComfyUI-LTXVideo extension likewise use
Lightricks **custom community agreements**, not generic permissive
open-source licences. See [the checked model and node terms](THIRD_PARTY_LICENSES.md).
No H3, LTX or other third-party weights are distributed by this repository.
The GitHub MIT licence applies only to original OSF-authored source; it
**does not clear any particular film or distribution territory**.

## Problem

Take a photographed shot — the original camera move, the real scene geometry
— and a deliberately altered version of what's in frame (a different set,
different set dressing, a different look). Propagate the altered look across
the whole shot while retaining as much of the original camera movement and
scene structure as practical. This is generative video editing constrained
by an existing performance and camera move, not free generation from a text
prompt.

"OrbitTurn" is the reference shot this tooling was developed and tuned
against (a camera move that orbits and turns around its subject — a
deliberately hard case, since it stresses both temporal consistency and
geometric consistency more than a static or simply-panning shot would).
"H3" is [MiniMax's](https://minimax3.com/) H3 reference-to-video model,
which became the core of the approach that's actually in production use as
of this writing, after evaluating it against several other approaches (see
Status below).

## Current approach

The production path runs on [ComfyUI](https://github.com/comfyui) with
native MiniMax H3 support (landed in ComfyUI core in August 2026 — see
RUNPOD.md for the exact commit this depends on), combined with two small
custom node packages Open Source Films wrote for this project:

- **`custom_nodes/osf_h3_hybrid/`** — `OSFMiniMaxH3HybridAnchoredReferenceToVideo`,
  which conditions H3 generation on a *hard first frame, a midpoint reference
  image, and a hard last frame*, plus the full driving video as an additional
  reference, with the source video uniformly resampled onto H3's native
  frame grid so the source's first and last frames land exactly on H3's
  internal first/last frames. It also patches a real bug in stock H3
  (v0.33.1): when both hard keyframes and reference conditioning are present
  together, stock H3 overwrites the keyframe latents and miscalculates their
  temporal position — this package's `_install_mixed_h3_payload_patch`
  fixes both, at runtime, without touching ComfyUI core.
- **`custom_nodes/osf_h3_maxq/`** — a two-pass, checkpoint-and-resume
  pipeline for quality beyond what fits in one generation pass: save H3's
  joint audio/video latent to disk after Pass A, reload it, upscale and
  apply a partial-strength repaint (a source-latent noise mask, not a
  perceptual blend) for Pass B, and export final frames as 16-bit PNG rather
  than the usual 8-bit preview output.

See [`docs/architecture.md`](docs/architecture.md) for the full data-flow
description. **Note the published workflow graph predates the two node
packages above** — see Status below for exactly what that means.

## Status

**Active experimental/production tooling, not a solved general-purpose
system.** H3-based generation is the current production path for the
OrbitTurn shot as of August 2026, arrived at after evaluating it alongside
several other approaches on the same shot (Bernini-R, a Wan 2.2-Fun +
FlexAM motion-transfer branch, Ditto/Editto, and a LTX 2.3 clean-plate
baseline). Those other approaches aren't published here — they didn't
become the production path, and shipping every comparison arm as its own
artifact wouldn't be honest about what's actually in use. The one workflow
graph published in `workflows/` is the real, current, multi-branch ComfyUI
development graph H3 was built and selected within (not a fictionally
cleaned-up H3-only extract) — it will parse and load.

**Important gap, stated plainly rather than papered over:** the saved graph
(`workflows/OrbitTurn_H3_comparison_workflow.json`, last saved 2026-08-15)
uses stock ComfyUI-core's `MiniMaxH3ReferenceToVideo` node directly — it
predates `custom_nodes/osf_h3_hybrid/` (added later the same day) and
`custom_nodes/osf_h3_maxq/` (added 2026-08-19), so neither is wired into
this saved copy. The two-pass checkpoint/upscale work that produced the
most recent production output (`OrbitTurn_H3_MAXQ/`) was run and iterated
directly in the ComfyUI browser session and/or via API submission rather
than through a resaved GUI file, so that exact graph wiring isn't
recoverable from disk as of this writing. What's real and verifiable here:
the node source code (`custom_nodes/`, described in full in
`docs/architecture.md`), and the base multi-branch graph showing how stock
H3 conditioning is wired into the same production ComfyUI environment. What
isn't yet captured: a single saved graph showing the OSF nodes connected
end-to-end. That's a real next step, not a gap this document is hiding.

Extensive parameter sweeps (resolution, tiling, reference-image count,
SageAttention on/off) were run against this shot between 2026-08-15 and
2026-08-19; that tuning experience is reflected in the defaults in the two
node packages, not published as raw data here.

## Offline reproducibility checks

The public repository includes [12 CPU-only regression tests](tests/test_public_orbitturn_offline.py)
run automatically by [GitHub Actions](.github/workflows/offline-acceptance.yml).
These checks use small synthetic 16-bit RGB images to exercise the **exact**
published `_png_chunk` and `_write_png16_rgb` helpers from the MaxQ node
module, verifying PNG signature, IHDR, CRC, big-endian sample bytes,
compression and invalid input rejection. They also exercise MaxQ's public
PNG/AV checkpoint writer wrappers with inert ComfyUI, torch and safetensors
stand-ins, checking that existing output files cannot be overwritten and
user-supplied output names remain within the configured ComfyUI output tree.
The checks parse both custom node modules and inspect the 220-node, 280-link
saved UI graph for valid node IDs and link endpoints.

The relevant functions and save wrappers are extracted from the published
source by Python's AST rather than importing ComfyUI, torch or safetensors.
NumPy is the only runtime test dependency. This tests **serialization and
file-publication contracts**, not a live ComfyUI instance or H3 generation.

The test also confirms the saved UI graph still uses **stock H3**, not OSF's
later hybrid/MaxQ nodes. This is the historical documentation gap described
above, not an assertion of working end-to-end MaxQ wiring. A passing run
does not establish node compatibility with current ComfyUI, usable model
weights, successful inference, temporal consistency, or production
quality. No production frames or latent checkpoints are needed.

### MaxQ export collision and directory safety

`OSFH3SaveAVLatent` and `OSFSavePNG16` now publish output files **create-only**.
A same-directory temporary file is fully written before its name is claimed
using a hard link. If that destination already exists, the node raises
`FileExistsError` and leaves the original checkpoint/frame intact. To
rerun a shot, use a **new filename prefix**. Do not manually delete a
previously verified result merely to clear the collision.

Filename prefixes are limited to ComfyUI's configured output directory,
including absolute paths *within* that directory. Parent-directory symlinks
leading outside the output tree and `..` components are rejected. The
load-latent node retains its existing read-path behaviour; these restrictions
apply only to **writes**. The output directory must be operator-controlled:
these checks are not a defence against malicious concurrent filesystem
mutation. Check available disk capacity before full-resolution H3 exports.

## Runpod

Development and testing run on [RunPod](https://runpod.io/) GPU pods. See
[`RUNPOD.md`](RUNPOD.md) for a concrete setup path, including the exact
ComfyUI core commit, custom node pins, and the GPU tier this was actually
run on.

## Licensing

Open Source Films' own code — `custom_nodes/osf_h3_hybrid/`,
`custom_nodes/osf_h3_maxq/`, and this repository's documentation — is MIT
licensed; see [`LICENSE`](LICENSE). ComfyUI core, third-party custom node
packages, and the MiniMax H3 / LTX / Bernini-R models this depends on remain
under their own separate licences — see
[`THIRD_PARTY_LICENSES.md`](THIRD_PARTY_LICENSES.md), which distinguishes
verified from not-yet-independently-verified terms rather than guessing.
This is Open Source Films' own reading of the available terms, not legal
advice — verify independently before any commercial use.

## What's not here

No LifeR production footage, source plates, review frames, or proprietary
model weights are published in this repository. The workflow graph
references output paths and node parameters, not embedded media — nothing
here requires or includes footage from the actual production. Model weights
are your own responsibility to obtain from their respective upstream
sources; see `RUNPOD.md`.
