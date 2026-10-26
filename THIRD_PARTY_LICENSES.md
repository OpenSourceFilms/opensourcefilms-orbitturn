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

## Additional upstream terms verified 26 October 2026

The entries below replace the earlier August 2026 *unverified* guesses.
These are upstream contract readings, **not a clearance of any particular
production, model distribution, user location or film release**.

| Component | Authoritative source and rights | Important conditions |
|---|---|---|
| **MiniMax H3 original model weights** | [MiniMaxAI/MiniMax-H3 official Community License](https://huggingface.co/MiniMaxAI/MiniMax-H3/blob/main/LICENSE), dated 2 August 2026. A **custom, geographically restricted agreement**, not Apache, MIT or an OSI-approved licence. | Section I excludes **European Union, United Kingdom, Republic of Korea and United States of America** from the Applicable Territory. Section V.4 prohibits use, reproduction, modification, distribution or display of the model **or its Outputs** outside that territory, unless separate authorization is obtained. Australia is not expressly excluded. **This is a serious restriction for international distribution or display of H3-generated footage**, not just model hosting. |
| **MiniMax H3 commercial and redistribution terms** | [Same original licence](https://huggingface.co/MiniMaxAI/MiniMax-H3/blob/main/LICENSE), §§III–V, VI. | Commercial products/services generating **more than USD 20 million annual revenue** require prior written authorization; commercial UIs using H3 must prominently identify MiniMax H3. Distributors of model works must preserve the agreement and required NOTICE, and downstream services have safeguard and restricted-use obligations. The licence says MiniMax claims no ownership of generated Outputs, but **still contractually restricts their use outside the Applicable Territory**. Check the complete text and any separate approval. |
| **LTX 2.5 weights** | [Lightricks LTX-2.x Community License](https://github.com/Lightricks/LTX-2/blob/main/LICENSE-2_x), not a standard permissive software license; assess the actual checkpoint/version and accepted terms. | Entities with **at least USD 10 million annual revenue** generally need a paid agreement for uses outside specified non-commercial purposes. Below that threshold is **not unconditional public-domain or Apache use**; the agreement also has other contractual conditions. |
| **ComfyUI-LTXVideo code** | [Lightricks/ComfyUI-LTXVideo's own LICENSE](https://github.com/Lightricks/ComfyUI-LTXVideo/blob/master/LICENSE), titled **LTX-2 Community License Agreement**, 5 January 2026. | This custom agreement is **distinct from the LTX-2.x model-weights agreement**, and is not Apache/MIT merely because other ComfyUI nodes are. Check both installed node version and checkpoint terms separately. |
| **SageAttention source** | [thu-ml/SageAttention/LICENSE](https://github.com/thu-ml/SageAttention/blob/main/LICENSE), Apache-2.0. | The repository source license is permissive; third-party binary-wheel components, if redistributed, may have additional notices. Nothing from SageAttention is vendored here. |
| **Bernini-R upstream code and original model weights** | ByteDance's [Bernini source](https://github.com/bytedance/Bernini/blob/main/LICENSE) includes Apache-2.0; the [official ByteDance/Bernini-R model card](https://huggingface.co/ByteDance/Bernini-R) also declares **Apache-2.0** for the released renderer weights. The [Comfy-Org/Bernini-R repack](https://huggingface.co/Comfy-Org/Bernini-R) declares Apache-2.0 and identifies ByteDance as its base. | Upstream licensing is now identified. This is **not** verification of the historical on-disk checkpoint hash, exact quantization, third-party models bundled alongside it, or the precise variant installed in ComfyUI. |
| **Mickmumpitz ComfyUI node repository** | [mickmumpitz/ComfyUI-Mickmumpitz-Nodes](https://github.com/mickmumpitz/ComfyUI-Mickmumpitz-Nodes), [MIT LICENSE](https://github.com/mickmumpitz/ComfyUI-Mickmumpitz-Nodes/blob/main/LICENSE), Copyright (c) 2025 MickMumpitz. | The upstream author and source licence are identified. Exact historical installed tree/commit and the presence/licence of the particular camera-tracking node versions are **not independently established**; third-party model dependencies require separate checks. |

**Model-hosting geography is not the only question.** The MiniMax H3
agreement expressly covers use and display of Outputs, so a film or public
demo containing H3-generated footage distributed internationally requires
specific legal review, even when the footage was generated in Australia.
No model weights or H3 outputs are included in this GitHub repository.
If distribution in an excluded territory is contemplated, seek MiniMax's
written licence or legal advice before relying on this community licence.

## Still not independently verified

| Component | What is known | Remaining rights question |
|---|---|---|
| MiniMax H3 repack/turbo variants | Comfy-Org and lightx2v distribute variants; MiniMaxAI is the official original model. | Verify whether particular repack/checkpoint adds obligations beyond the original agreement and whether any separate authority applies. |

## How this list was produced

The "Verified" table reuses confirmed findings from Open Source Films'
existing ComfyUI licensing audit (the same one behind
[`opensourcefilms-comfyui-workflows`](https://github.com/OpenSourceFilms/opensourcefilms-comfyui-workflows)'s
own `THIRD_PARTY_LICENSES.md`), since several packages are shared across
both projects' environments. The original August 2026 audit could not determine rights for several
models. The 26 October 2026 update reads the linked **official upstream
licence files** directly and moves confirmed terms out of that unverified
list. It does not replace review of the checkpoint or service actually used.
