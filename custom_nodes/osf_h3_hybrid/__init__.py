"""OSF MiniMax H3 hybrid hard-endpoint + reference conditioning.
Targeted at ComfyUI v0.33.1 for the OrbitTurn diagnostic.
"""
import copy
import math
import torch

import comfy.conds
import comfy.model_base
import node_helpers
from comfy_extras.nodes_minimax_h3 import (
    CANVAS_MULTIPLE, REF_IMAGE_SHORT_EDGE, FPS,
    _empty_av_latent, _resize, adapt_canvas,
)


def _temporal_nearest(images, target_length):
    n = int(images.shape[0])
    target_length = int(target_length)
    if n < 1:
        raise ValueError("Cannot temporal-resample an empty IMAGE batch")
    if target_length < 1:
        raise ValueError("target_length must be >= 1")
    if n == target_length:
        return images
    idx = torch.linspace(0, n - 1, target_length, device=images.device)
    idx = idx.round().long().clamp_(0, n - 1)
    return images.index_select(0, idx)


def _install_mixed_h3_payload_patch():
    cls = comfy.model_base.MiniMaxH3
    if getattr(cls, "_osf_hybrid_mixed_payload_patch", False):
        return
    original = cls.extra_conds

    def patched(self, **kwargs):
        out = original(self, **kwargs)
        keyframes = kwargs.get("minimax_keyframes")
        refs = kwargs.get("minimax_refs")
        if not keyframes or not refs:
            return out

        wrapped = out.get("minimax_payload")
        if wrapped is None or not hasattr(wrapped, "cond") or not isinstance(wrapped.cond, dict):
            return out
        payload = wrapped.cond.copy()

        # Stock v0.33.1 overwrites keyframe visual latents when refs are present.
        # PackedLayout orders keyframe condition rows first, then reference rows.
        payload["cond_video_latents"] = (
            [kf["latent"] for kf in keyframes]
            + [r["latent"] for r in refs if "latent" in r]
        )

        # In mixed mode the target video starts after the reference blocks, but
        # stock keyframe t coordinates are calculated from text_len. Shift only
        # hard-keyframe `cond` rows to the actual target-video temporal origin.
        layout = payload.get("layout")
        if layout is not None and hasattr(layout, "segments") and hasattr(layout, "position_ids"):
            text_seg = next((s for s in layout.segments if s[2] == "text"), None)
            video_seg = next((s for s in layout.segments if s[2] == "video"), None)
            cond_segs = [s for s in layout.segments if s[2] == "cond"]
            if text_seg and video_seg and cond_segs:
                expected_origin = float(text_seg[1])
                actual_origin = float(layout.position_ids[video_seg[0], 0].item())
                offset = actual_origin - expected_origin
                if abs(offset) > 1e-12:
                    shifted = copy.copy(layout)
                    shifted.position_ids = layout.position_ids.clone()
                    for a, b, _ in cond_segs:
                        shifted.position_ids[a:b, 0] += offset
                    payload["layout"] = shifted

        out["minimax_payload"] = comfy.conds.CONDConstant(payload)
        return out

    cls.extra_conds = patched
    cls._osf_hybrid_mixed_payload_patch = True
    cls._osf_hybrid_original_extra_conds = original
    print("[OSF H3 Hybrid] mixed keyframe+reference patch installed")


_install_mixed_h3_payload_patch()


class OSFMiniMaxH3HybridAnchoredReferenceToVideo:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "clip": ("CLIP",),
            "vae": ("VAE",),
            "first_frame": ("IMAGE",),
            "midpoint_ref": ("IMAGE",),
            "last_frame": ("IMAGE",),
            "driver_video": ("IMAGE",),
            "prompt": ("STRING", {"forceInput": True}),
            "width": ("INT", {"default": 896, "min": 32, "max": 16384, "step": 32}),
            "height": ("INT", {"default": 480, "min": 32, "max": 16384, "step": 32}),
            "length": ("INT", {"default": 277, "min": 5, "max": 3600, "step": 17}),
            "ref_image_size": (["match", "max"], {"default": "match"}),
        }}

    RETURN_TYPES=("CONDITIONING","LATENT")
    RETURN_NAMES=("positive","LATENT")
    FUNCTION="execute"
    CATEGORY="model/conditioning/minimax"
    DESCRIPTION="OSF experimental H3 hard first/last keyframes + midpoint image ref + full video ref, with uniform source↔H3 temporal-grid mapping."

    @staticmethod
    def _ref_image(img, width, height, ref_image_size):
        h,w=img.shape[1],img.shape[2]
        if ref_image_size=="match":
            scale=min(1.0, math.sqrt((width*height)/(w*h)))
        else:
            scale=min(1.0, REF_IMAGE_SHORT_EDGE/min(w,h))
        tw=max(CANVAS_MULTIPLE, round(w*scale/CANVAS_MULTIPLE)*CANVAS_MULTIPLE)
        th=max(CANVAS_MULTIPLE, round(h*scale/CANVAS_MULTIPLE)*CANVAS_MULTIPLE)
        return _resize(img[:1],tw,th,"disabled"),tw,th

    def execute(self, clip, vae, first_frame, midpoint_ref, last_frame, driver_video,
                prompt, width, height, length, ref_image_size):
        latent, frame_count = _empty_av_latent(width,height,length)

        first=_resize(first_frame[:1],width,height,"disabled")
        last=_resize(last_frame[:1],width,height,"center")
        keyframes=[
            {"resolved_frame_index":0,"latent":vae.encode(first)},
            {"resolved_frame_index":frame_count-1,"latent":vae.encode(last)},
        ]

        midpoint,mw,mh=self._ref_image(midpoint_ref,width,height,ref_image_size)
        midpoint_z=vae.encode(midpoint)

        # Exact source batch is uniformly expanded onto H3's valid frame grid.
        # Endpoint-preserving nearest mapping avoids a 13-frame tail hold and
        # guarantees source last frame == H3 internal last frame.
        source_frames=_temporal_nearest(driver_video, frame_count)
        vh,vw=source_frames.shape[1],source_frames.shape[2]
        cw,ch=adapt_canvas(vw,vh)
        if vw*vh < cw*ch:
            cw=max(CANVAS_MULTIPLE,round(vw/CANVAS_MULTIPLE)*CANVAS_MULTIPLE)
            ch=max(CANVAS_MULTIPLE,round(vh/CANVAS_MULTIPLE)*CANVAS_MULTIPLE)
        frames=_resize(source_frames,cw,ch,"disabled")
        driver_z=vae.encode(frames)

        sample_idx=list(range(0,frames.shape[0],FPS//2))
        qwen_frames=frames[sample_idx]
        presentation=[
            {"type":"image","data":first},
            {"type":"image","data":midpoint},
            {"type":"image","data":last},
            {"type":"video","data":qwen_frames,
             "timestamps":[i/2.0 for i in range(len(sample_idx))]},
        ]
        refs=[
            {"kind":"image","latent_h":mh//16,"latent_w":mw//16,"latent":midpoint_z},
            {"kind":"video","latent_t":driver_z.shape[2],"latent_h":ch//16,"latent_w":cw//16,
             "ref_audio_t":0,"latent":driver_z,"audio_latent":None},
        ]

        tokens=clip.tokenize(prompt,minimax_ref_items=presentation)
        cond=clip.encode_from_tokens_scheduled(tokens)
        cond=node_helpers.conditioning_set_values(cond,{
            "minimax_keyframes":keyframes,
            "minimax_frame_count":frame_count,
            "minimax_refs":refs,
        })
        return (cond,latent)


class OSFImageBatchTemporalResample:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "images": ("IMAGE",),
            "target_length": ("INT", {"default":264,"min":1,"max":100000,"step":1}),
        }}
    RETURN_TYPES=("IMAGE",)
    FUNCTION="execute"
    CATEGORY="image/batch"
    DESCRIPTION="Uniform endpoint-preserving nearest temporal resample of an IMAGE batch."

    def execute(self, images, target_length):
        return (_temporal_nearest(images,target_length),)


NODE_CLASS_MAPPINGS={
    "OSFMiniMaxH3HybridAnchoredReferenceToVideo":OSFMiniMaxH3HybridAnchoredReferenceToVideo,
    "OSFImageBatchTemporalResample":OSFImageBatchTemporalResample,
}
NODE_DISPLAY_NAME_MAPPINGS={
    "OSFMiniMaxH3HybridAnchoredReferenceToVideo":"OSF MiniMax H3 Hybrid Anchored Reference to Video",
    "OSFImageBatchTemporalResample":"OSF Image Batch Temporal Resample",
}
