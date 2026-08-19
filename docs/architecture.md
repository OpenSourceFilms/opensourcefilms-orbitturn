# Architecture

This describes the actual H3-based pipeline as implemented in
`custom_nodes/osf_h3_hybrid/` and `custom_nodes/osf_h3_maxq/`. **These two
packages are not yet wired into the saved
`workflows/OrbitTurn_H3_comparison_workflow.json`** — that graph predates
both (see the README's Status section for the exact timeline). What follows
is a description of what the node code actually does, verified by reading
it, not a description of a finished end-to-end saved graph. This document
also doesn't describe the other comparison branches present in that
workflow file (Bernini-R, FlexAM, Ditto/Editto, LTX clean-plate) — see the
README's Status section for why those aren't documented here either.

## Why H3 needs a conditioning adapter at all

MiniMax H3 is a reference-to-video model: it can take reference images and a
driving/reference video and generate new video guided by them. Two things
the OrbitTurn shot needed that stock H3 doesn't give you directly:

1. **Hard first/last-frame anchoring.** For a shot that has to cut cleanly
   into and out of surrounding footage, the generated result's first and
   last frames need to land on specific target frames exactly, not just
   "be guided toward" them.
2. **Combining hard keyframes with reference conditioning at the same time.**
   Stock H3 (as of the v0.33.1 support that landed in ComfyUI core) has a
   real bug here: when both keyframe conditioning (`minimax_keyframes`) and
   reference conditioning (`minimax_refs`) are supplied together, its
   `extra_conds` overwrites the keyframe visual latents with the reference
   latents, and calculates keyframe temporal position from the wrong origin
   (text-segment length instead of where the target video segment actually
   starts once reference blocks are also present). Both are silent
   correctness bugs, not crashes — you'd get an image, just a subtly wrong
   one.

`custom_nodes/osf_h3_hybrid/__init__.py` addresses both, as a runtime patch
to `comfy.model_base.MiniMaxH3.extra_conds` installed on import (not a
ComfyUI-core edit — it's applied via monkeypatch so the package stays a
normal drop-in custom node with no core modifications required).

## Pass A: conditioning and generation

`OSFMiniMaxH3HybridAnchoredReferenceToVideo` is the entry point. Given:

- a `first_frame` and `last_frame` (hard keyframes),
- a `midpoint_ref` image (a reference for content partway through the shot),
- the full `driver_video` (the original photographed footage, used both as
  a video reference and as the source of the exact camera-move/geometry
  H3 should track),
- and a text `prompt`,

it:

1. Encodes `first_frame`/`last_frame` as hard keyframe latents at indices
   `0` and `frame_count - 1`.
2. Temporally resamples `driver_video` onto H3's own valid frame count via
   nearest-neighbour index mapping (`_temporal_nearest`) — chosen
   specifically because it's endpoint-preserving: the resampled source's
   last frame is guaranteed to be H3's internal last frame, avoiding a
   multi-frame "hold" at the tail that a naive interpolation would
   introduce.
3. Builds H3's `minimax_ref_items` presentation list (the images/video H3's
   text encoder sees alongside the prompt) from the first/midpoint/last
   images plus a sparsely sampled (every `FPS/2` frames) view of the
   resampled driver video, each frame timestamped.
4. Encodes the midpoint reference and the full driver video as separate
   `minimax_refs` entries (image-kind and video-kind respectively).
5. Tokenizes and encodes the prompt with that presentation attached, then
   attaches the keyframe/ref/frame-count metadata onto the conditioning via
   `node_helpers.conditioning_set_values` — which is what the runtime patch
   above later reads out of `extra_conds`.

Output is a `(CONDITIONING, LATENT)` pair, fed into H3's own sampler nodes
(unmodified stock ComfyUI-core nodes) the same as any other H3 generation.

## Pass B: checkpoint, upscale, repaint

H3's joint audio/video latent is a `NestedTensor` — video `[B,C,T,H,W]`
(24 channels) and audio `[B,C,2,T]` (32 channels) as one object, which is
awkward to save/reload with ComfyUI's stock latent nodes. `osf_h3_maxq`
exists because a full-resolution H3 generation in one pass is expensive
enough that being able to checkpoint after Pass A and iterate on Pass B
separately (different upscale target, different repaint strength) without
re-running generation is materially useful:

- **`OSFH3SaveAVLatent`** unbinds the NestedTensor into its video/audio
  parts and writes both to a single `.safetensors` file (with shape
  metadata), under `folder_paths.get_output_directory()` by default.
- **`OSFH3LoadAVLatent`** reloads that file and re-wraps it as a
  `NestedTensor` latent dict, ready to feed back into ComfyUI-core H3 nodes.
  `IS_CHANGED` always returns NaN (i.e. "always re-read") since the same
  filename may legitimately be overwritten by a re-run of Pass A.
- **`OSFH3UpscaleRepaintAV`** spatially upscales only the video latent
  (audio is untouched), and attaches a `NestedTensor` noise mask built from
  two independent strength values — one for video, one for audio — so a
  downstream sampler can be told "mostly keep this, regenerate lightly"
  (low strength) versus "regenerate more" (high strength) per stream. This
  mask is a source-latent noise level, explicitly not a calibrated
  perceptual blend amount — the node's own report output says so, so it
  doesn't get treated as one downstream by mistake.
- **`OSFSavePNG16`** writes final frames as 16-bit-per-channel RGB PNG
  (constructed directly, not via a third-party image library's 16-bit path)
  rather than ComfyUI's default 8-bit preview save — relevant once frames
  are headed into a production colour pipeline rather than being reviewed
  as a quick preview.

## What isn't here

Model loading, sampling, and VAE encode/decode all use stock ComfyUI-core
MiniMax H3 nodes (`comfy_extras/nodes_minimax_h3.py` in the pinned ComfyUI
commit — see `RUNPOD.md`) — this repository only adds the conditioning
adapter and the checkpoint/upscale/export layer around them. The actual
model weights are not included or referenced by path; obtain them per
ComfyUI's own MiniMax H3 setup documentation.
