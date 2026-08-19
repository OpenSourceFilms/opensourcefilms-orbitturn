# Running on RunPod

This was developed and tested on [RunPod](https://runpod.io/) GPU pods.
Everything in this document reflects the actual working environment as of
2026-08-19, not a guess.

## GPU

Full-quality H3 generation and the resolution/reference-count parameter
sweeps behind the current defaults were run on an **RTX PRO 6000 Blackwell,
97GB VRAM**. That's a real, high-end tier, not a minimum — the parameter
sweep in `docs/architecture.md`'s tuning history covered resolutions from
864x480 up through 2048x1088, and VRAM needs scale with resolution, frame
count, and reference-image count more than with anything fixed. If you're
on a smaller card, start at a lower resolution (864x480 is a reasonable
floor to try first) and work up rather than assuming you need 97GB.

No GPU was available on the coordination pod this repository was assembled
on — this document was written and the workflow JSON/dependency pins were
verified from the actual working ComfyUI installation's files and git
state, not from a live run performed while writing this document.

## Base environment

```text
ComfyUI core:  github.com/Comfy-Org/ComfyUI @ 57ce8e1a27dda3d4cedab081081fd3e1359c195b (2026-08-11) or later
               Must include LTX 2.5 support (PR #15499) and native MiniMax H3 support
               (comfy_extras/nodes_minimax_h3.py, comfy_extras/nodes_bernini.py)
Python:        3.12
PyTorch:       2.10.0+cu128
```

Pin to a commit at or after the one above — that's the earliest point both
LTX 2.5 and MiniMax H3 support exist natively in ComfyUI core. Any RunPod
pod template with a recent CUDA-enabled PyTorch base works as the starting
point; there's nothing here that depends on a specific template.

## Custom nodes

```text
rgthree-comfy                    github.com/rgthree/rgthree-comfy
ComfyUI-GGUF                      github.com/city96/ComfyUI-GGUF
ComfyUI-VideoHelperSuite          github.com/Kosinkadink/ComfyUI-VideoHelperSuite
ComfyUI-KJNodes                   github.com/kijai/ComfyUI-KJNodes
ComfyUI-Easy-Use                  github.com/yolain/ComfyUI-Easy-Use
ComfyUI-RMBG                      github.com/1038lab/ComfyUI-RMBG
ComfyUI-Manager                   github.com/Comfy-Org/ComfyUI-Manager
ComfyUI-LTXVideo                  github.com/Lightricks/ComfyUI-LTXVideo
comfyui_controlnet_aux            github.com/Fannovel16/comfyui_controlnet_aux
comfyui-mickmumpitz-nodes         (camera-tracking nodes; upstream not confirmed -- see THIRD_PARTY_LICENSES.md)
```

Install via [ComfyUI-Manager](https://github.com/Comfy-Org/ComfyUI-Manager)
or by cloning each into `custom_nodes/`. Exact commit pins weren't captured
for most of these (the working environment tracks recent `main` on each);
if you hit a breaking upstream change, that's the first place to look.

Then add this repository's own two node packages:

```bash
cp -r custom_nodes/osf_h3_hybrid  /path/to/ComfyUI/custom_nodes/
cp -r custom_nodes/osf_h3_maxq    /path/to/ComfyUI/custom_nodes/
```

## Optional: SageAttention

SageAttention (`pip install sageattention`, version 2.2.0 in the working
environment) was tested as an optional inference-speed acceleration during
the parameter sweeps, toggled on and off across otherwise-identical runs.
It's not required for correctness — treat it as a speed optimization to try
once the base pipeline is working, not a dependency to install first.

## Model weights

Not installed by anything here, and not bundled in this repository:

- **MiniMax H3**: `Comfy-Org/MiniMax-H3` on Hugging Face (repackaged for
  ComfyUI; original weights at `MiniMaxAI/MiniMax-H3` and
  `lightx2v/Minimax-h3-Turbo`). Follow ComfyUI's own
  [MiniMax H3 setup guide](https://docs.comfy.org/tutorials/video/minimax/minimax-h3).
- **LTX 2.5**: gated download from Lightricks' Hugging Face repository —
  you'll need to accept the model terms there before downloading.
- **Bernini-R**: referenced by `comfy_extras/nodes_bernini.py` in ComfyUI
  core; upstream source for its weights wasn't identified during this
  writeup (see `THIRD_PARTY_LICENSES.md`) — if you need this branch rather
  than H3, expect to do your own research here.

See [THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md) for what is and
isn't verified about each of these before committing to commercial use.

## Running the workflow

```bash
cd /path/to/ComfyUI
python main.py --listen 0.0.0.0 --port 8188
```

Use RunPod's exposed HTTP port to reach the ComfyUI web UI, then
**Workflow → Open** and pick
[`workflows/OrbitTurn_H3_comparison_workflow.json`](workflows/OrbitTurn_H3_comparison_workflow.json).
This is the real, current multi-branch development graph and it will load
with the dependencies above installed and the referenced models in place —
but read the README's Status section first: this saved copy uses stock
ComfyUI-core's `MiniMaxH3ReferenceToVideo` node, not the two OSF packages
below. Those exist as working, syntax-checked node source
(`custom_nodes/osf_h3_hybrid/`, `custom_nodes/osf_h3_maxq/`) that registers
correctly once installed, described end-to-end in `docs/architecture.md` —
wiring them into this graph (or a copy of it) in the ComfyUI GUI is a real
next step this repository doesn't hand you pre-done.
