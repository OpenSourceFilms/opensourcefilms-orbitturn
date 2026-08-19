# Third-party licenses

Open Source Films' own code in this repository (`custom_nodes/osf_h3_hybrid/`,
`custom_nodes/osf_h3_maxq/`, and the documentation) is MIT — see
[LICENSE](LICENSE). Everything below is third-party, keeps its own license,
and is not redistributed by this repository — you obtain it yourself
following the pointers in [RUNPOD.md](RUNPOD.md). This is Open Source
Films' own reading of what's publicly documented, not legal advice; verify
independently before commercial use, especially anything below listed as
not yet verified.

## Verified

Confirmed by a prior Open Source Films licensing audit of the same shared
ComfyUI environment (2026-07-22 and 2026-08-19 passes):

| Component | Upstream | License | Commercial use |
|---|---|---|---|
| ComfyUI core | github.com/Comfy-Org/ComfyUI | GPL-3.0 | Permitted — GPL imposes distribution/copyleft obligations, it is not a non-commercial license. |
| rgthree-comfy | github.com/rgthree/rgthree-comfy | MIT | Permitted. |
| ComfyUI-GGUF | github.com/city96/ComfyUI-GGUF | Apache-2.0 | Permitted. |
| ComfyUI-VideoHelperSuite | github.com/Kosinkadink/ComfyUI-VideoHelperSuite | GPL-3.0 | Permitted. |
| comfyui-kjnodes (KJNodes) | github.com/kijai/ComfyUI-KJNodes | GPL-3.0 | Permitted. |
| ComfyUI-Easy-Use | github.com/yolain/ComfyUI-Easy-Use | GPL-3.0 | Permitted. |
| ComfyUI-RMBG | github.com/1038lab/ComfyUI-RMBG | GPL-3.0 | Permitted. |
| ComfyUI-Manager | github.com/Comfy-Org/ComfyUI-Manager | GPL-3.0 | Permitted. |

## Not yet verified

Checked as of 2026-08-19 (a `ds_research` pass found no definitive license
text for any of these — see note below); do not assume permissive or
commercial-safe until someone actually reads the terms:

| Component | Upstream | What's known | Open question |
|---|---|---|---|
| ComfyUI-LTXVideo | github.com/Lightricks/ComfyUI-LTXVideo | A `LICENSE`/`LICENSE.md` exists in Lightricks' `LTX-2` repo (contents not read). | Exact license text; whether it covers the ComfyUI node package specifically. |
| LTX 2.5 model weights | huggingface.co (Lightricks) | Gated download, requires accepting Hugging Face model terms. | What those terms actually permit commercially. |
| MiniMax H3 model weights | huggingface.co/Comfy-Org/MiniMax-H3, repackaged from huggingface.co/MiniMaxAI/MiniMax-H3 and huggingface.co/lightx2v/Minimax-h3-Turbo | ComfyUI's own docs describe it as "open weights." | "Open weights" is not itself a license; exact terms and commercial-use permission unread. |
| Bernini-R model weights | (native ComfyUI core support, `comfy_extras/nodes_bernini.py`) | Nothing found — no license, terms, or even a clear upstream project page turned up. | Everything. |
| SageAttention | PyPI `sageattention` | Used for optional inference acceleration; version 2.2.0 installed in the working environment. | License/terms not checked. |
| comfyui-mickmumpitz-nodes | (installed without a git remote in the working environment; upstream not confirmed) | Provides camera-tracking-adjacent nodes (`VideoToTrackingPredict`/`VideoToTrackingVisualizeAll`) used in the comparison workflow. | Upstream repo, license — not confirmed. |

## How this list was produced

The "Verified" table reuses confirmed findings from Open Source Films'
existing ComfyUI licensing audit (the same one behind
[`opensourcefilms-comfyui-workflows`](https://github.com/OpenSourceFilms/opensourcefilms-comfyui-workflows)'s
own `THIRD_PARTY_LICENSES.md`), since several packages are shared across
both projects' environments. The "Not yet verified" table is new to this
repository and reflects an actual research attempt (three real pages
fetched: Lightricks' `LTX-2` GitHub repo, ComfyUI's own MiniMax H3 tutorial
page, and the `Comfy-Org/MiniMax-H3` Hugging Face repo) that came back
without definitive license text rather than a guess — see the individual
"What's known" cells for exactly what those pages did and didn't say.
