from __future__ import annotations

import binascii
import json
import os
import struct
import tempfile
import zlib
from pathlib import Path

import numpy as np
import torch
import safetensors.torch

import comfy.model_management
import comfy.nested_tensor
import comfy.utils
import folder_paths


def _av_parts(latent, name="latent"):
    if not isinstance(latent, dict) or "samples" not in latent:
        raise ValueError(f"{name} must be a LATENT dictionary containing 'samples'")
    samples = latent["samples"]
    if not getattr(samples, "is_nested", False):
        raise ValueError(f"{name} must be a MiniMax H3 joint AV NestedTensor")
    parts = tuple(samples.unbind())
    if len(parts) != 2:
        raise ValueError(f"{name} must contain exactly video and audio streams")
    video, audio = parts
    if not isinstance(video, torch.Tensor) or video.ndim != 5:
        raise ValueError(f"H3 video latent must be [B,C,T,H,W], got {getattr(video, 'shape', None)}")
    if not isinstance(audio, torch.Tensor) or audio.ndim != 4:
        raise ValueError(f"H3 audio latent must be [B,C,2,T], got {getattr(audio, 'shape', None)}")
    return video, audio


def _output_path(filename: str, default: str, suffix: str = "") -> Path:
    """Resolve a MaxQ output under ComfyUI's configured output directory.

    Absolute paths *inside* the output root remain supported. A custom prefix
    must not escape the output tree via absolute paths, '..', or existing
    parent-directory symlinks. This is not an openat-style adversarial race
    defence: the output tree must remain under the ComfyUI operator's control.
    """
    if not isinstance(filename, str):
        raise ValueError("output filename must be a string")
    raw = filename.strip() or default
    if suffix and not raw.lower().endswith(suffix):
        raw += suffix
    requested = Path(raw)
    if ".." in requested.parts:
        raise ValueError("output filename must not contain '..' path components")
    root = Path(folder_paths.get_output_directory()).resolve(strict=True)
    target = requested if requested.is_absolute() else root / requested
    parent = target.parent.resolve(strict=False)
    if not parent.is_relative_to(root):
        raise ValueError("output filename escapes ComfyUI output directory")
    parent.mkdir(parents=True, exist_ok=True)
    parent = parent.resolve(strict=True)
    if not parent.is_relative_to(root):
        raise ValueError("output filename escapes ComfyUI output directory")
    return parent / target.name


def _exclusive_write(path: Path, writer) -> None:
    """Write a same-directory temp and publish by create-only hard link.

    An existing destination (even a symlink) raises FileExistsError. The
    published file is complete before its name becomes visible to readers.
    """
    fd, temp_name = tempfile.mkstemp(prefix=".osf-maxq-", suffix=".tmp", dir=str(path.parent))
    os.close(fd)
    temp = Path(temp_name)
    try:
        writer(temp)
        os.link(temp, path, follow_symlinks=False)
    finally:
        temp.unlink(missing_ok=True)


def _latent_output_path(filename_prefix: str) -> Path:
    return _output_path(
        filename_prefix, "OrbitTurn_H3_MAXQ/passA/OrbitTurn_PASS_A", ".safetensors"
    )


def _png_output_prefix(filename_prefix: str) -> Path:
    return _output_path(
        filename_prefix, "OrbitTurn_H3_MAXQ/PassB/frames16/h3"
    )


def _latent_input_path(filename: str) -> Path:
    filename = (filename or "").strip()
    if not filename:
        raise ValueError("filename cannot be empty")
    p = Path(filename)
    candidates = [p] if p.is_absolute() else [
        Path(folder_paths.get_output_directory()) / p,
        Path(folder_paths.get_input_directory()) / p,
        p,
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError(
        "OSF H3 AV latent not found. Checked: " + ", ".join(str(x) for x in candidates)
    )


class OSFH3SaveAVLatent:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "latent": ("LATENT",),
                "filename_prefix": ("STRING", {
                    "default": "OrbitTurn_H3_MAXQ/PassA_1024x544/OrbitTurn_PASS_A_1024x544_seed42"
                }),
            }
        }

    RETURN_TYPES = ("LATENT", "STRING")
    RETURN_NAMES = ("latent", "saved_path")
    FUNCTION = "save"
    OUTPUT_NODE = True
    CATEGORY = "OSF/H3 MaxQ"

    def save(self, latent, filename_prefix):
        video, audio = _av_parts(latent, "latent")
        path = _latent_output_path(filename_prefix)

        tensors = {
            "video": video.detach().to("cpu").contiguous(),
            "audio": audio.detach().to("cpu").contiguous(),
        }
        metadata = {
            "format": "OSF_H3_AV_LATENT",
            "version": "1",
            "video_shape": json.dumps(list(video.shape)),
            "audio_shape": json.dumps(list(audio.shape)),
        }
        _exclusive_write(
            path, lambda temp: safetensors.torch.save_file(tensors, str(temp), metadata=metadata)
        )
        return (latent, str(path))


class OSFH3LoadAVLatent:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "filename": ("STRING", {
                    "default": "OrbitTurn_H3_MAXQ/PassA_1024x544/OrbitTurn_PASS_A_1024x544_seed42.safetensors"
                }),
            }
        }

    RETURN_TYPES = ("LATENT", "STRING")
    RETURN_NAMES = ("latent", "loaded_path")
    FUNCTION = "load"
    CATEGORY = "OSF/H3 MaxQ"

    @classmethod
    def IS_CHANGED(cls, filename):
        # Always re-read: Pass A may have just replaced the file.
        return float("nan")

    def load(self, filename):
        path = _latent_input_path(filename)
        tensors = safetensors.torch.load_file(str(path), device="cpu")
        if "video" not in tensors or "audio" not in tensors:
            raise ValueError(f"{path} is not an OSF H3 AV latent file")

        device = comfy.model_management.intermediate_device()
        video = tensors["video"].to(device=device)
        audio = tensors["audio"].to(device=device)
        latent = {
            "samples": comfy.nested_tensor.NestedTensor((video, audio))
        }
        return (latent, str(path))


class OSFH3UpscaleRepaintAV:
    """
    Spatially enlarge only the H3 VIDEO latent, retain the audio stream, and attach
    a NestedTensor noise_mask. This is deliberately analogous to the source-video
    repaint/remix mechanism: 0 = lock source, 1 = full regeneration.
    """

    METHODS = ["bicubic", "bislerp", "bilinear", "nearest-exact", "area"]

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "av_latent": ("LATENT",),
                "width": ("INT", {"default": 2048, "min": 32, "max": 16384, "step": 32}),
                "height": ("INT", {"default": 1088, "min": 32, "max": 16384, "step": 32}),
                "upscale_method": (cls.METHODS, {"default": "bicubic"}),
                "video_repaint_strength": ("FLOAT", {
                    "default": 0.20, "min": 0.0, "max": 1.0, "step": 0.01
                }),
                "audio_repaint_strength": ("FLOAT", {
                    "default": 0.0, "min": 0.0, "max": 1.0, "step": 0.01
                }),
            }
        }

    RETURN_TYPES = ("LATENT", "STRING")
    RETURN_NAMES = ("latent", "report")
    FUNCTION = "prepare"
    CATEGORY = "OSF/H3 MaxQ"

    def prepare(self, av_latent, width, height, upscale_method,
                video_repaint_strength, audio_repaint_strength):
        if width % 32 or height % 32:
            raise ValueError("H3 target width and height must be divisible by 32")
        if upscale_method not in self.METHODS:
            raise ValueError(f"Unsupported upscale_method: {upscale_method}")

        video, audio = _av_parts(av_latent, "av_latent")
        if video.shape[1] != 24:
            raise ValueError(f"Expected H3 24-channel video latent, got C={video.shape[1]}")
        if audio.shape[1] != 32:
            raise ValueError(f"Expected H3 32-channel audio latent, got C={audio.shape[1]}")

        source_h = int(video.shape[-2]) * 16
        source_w = int(video.shape[-1]) * 16
        target_lw = width // 16
        target_lh = height // 16

        resized_video = comfy.utils.common_upscale(
            video, target_lw, target_lh, upscale_method, "disabled"
        )

        out = {
            k: v for k, v in av_latent.items()
            if k not in {"samples", "noise_mask"}
        }
        out["samples"] = comfy.nested_tensor.NestedTensor((resized_video, audio))

        video_mask = torch.full_like(resized_video, float(video_repaint_strength))
        audio_mask = torch.full_like(audio, float(audio_repaint_strength))
        out["noise_mask"] = comfy.nested_tensor.NestedTensor((video_mask, audio_mask))

        report = {
            "status": "ready",
            "source_pixels": [source_w, source_h],
            "target_pixels": [int(width), int(height)],
            "source_video_latent_shape": list(video.shape),
            "target_video_latent_shape": list(resized_video.shape),
            "audio_latent_shape": list(audio.shape),
            "upscale_method": upscale_method,
            "video_repaint_strength": float(video_repaint_strength),
            "audio_repaint_strength": float(audio_repaint_strength),
            "note": (
                "The repaint strength is a source-latent noise mask, not a calibrated "
                "perceptual linear denoise percentage."
            ),
        }
        return (out, json.dumps(report, indent=2))


def _png_chunk(kind: bytes, data: bytes) -> bytes:
    return (
        struct.pack(">I", len(data))
        + kind
        + data
        + struct.pack(">I", binascii.crc32(kind + data) & 0xFFFFFFFF)
    )


def _write_png16_rgb(path: Path, rgb_u16: np.ndarray, compression: int):
    if rgb_u16.dtype != np.uint16 or rgb_u16.ndim != 3 or rgb_u16.shape[2] != 3:
        raise ValueError("Expected uint16 RGB HxWx3 array")
    h, w, _ = rgb_u16.shape
    # PNG stores 16-bit samples big-endian. Filter type 0 is deterministic and robust.
    be = rgb_u16.astype(">u2", copy=False)
    raw = b"".join(b"\x00" + be[y].tobytes(order="C") for y in range(h))
    payload = zlib.compress(raw, level=int(compression))
    png = (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 16, 2, 0, 0, 0))
        + _png_chunk(b"IDAT", payload)
        + _png_chunk(b"IEND", b"")
    )
    _exclusive_write(path, lambda temp: temp.write_bytes(png))


class OSFSavePNG16:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "images": ("IMAGE",),
                "filename_prefix": ("STRING", {
                    "default": "OrbitTurn_H3_MAXQ/PassB/frames16/h3"
                }),
                "compression": ("INT", {"default": 6, "min": 0, "max": 9, "step": 1}),
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("saved_range",)
    FUNCTION = "save"
    OUTPUT_NODE = True
    CATEGORY = "OSF/H3 MaxQ"

    def save(self, images, filename_prefix, compression):
        if not isinstance(images, torch.Tensor) or images.ndim != 4:
            raise ValueError("images must be Comfy IMAGE [N,H,W,C]")
        prefix = _png_output_prefix(filename_prefix)

        arr = images[..., :3].detach().to("cpu", dtype=torch.float32).numpy()
        arr = np.clip(arr, 0.0, 1.0)
        arr = np.rint(arr * 65535.0).astype(np.uint16)

        paths = []
        for i, frame in enumerate(arr):
            path = prefix.parent / f"{prefix.name}_{i:05d}.png"
            _write_png16_rgb(path, frame, int(compression))
            paths.append(path)

        if not paths:
            return ("no frames",)
        return (f"{paths[0]} ... {paths[-1]} ({len(paths)} frames)",)


NODE_CLASS_MAPPINGS = {
    "OSFH3SaveAVLatent": OSFH3SaveAVLatent,
    "OSFH3LoadAVLatent": OSFH3LoadAVLatent,
    "OSFH3UpscaleRepaintAV": OSFH3UpscaleRepaintAV,
    "OSFSavePNG16": OSFSavePNG16,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "OSFH3SaveAVLatent": "OSF H3 Save AV Latent",
    "OSFH3LoadAVLatent": "OSF H3 Load AV Latent",
    "OSFH3UpscaleRepaintAV": "OSF H3 Latent 2K Repaint",
    "OSFSavePNG16": "OSF Save RGB PNG 16-bit",
}
