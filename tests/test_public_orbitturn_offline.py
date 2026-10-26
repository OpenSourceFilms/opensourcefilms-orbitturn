"""CPU-only tests of actual public OrbitTurn helper source.

The test extracts two pure PNG-writing functions by AST. It does NOT import
ComfyUI, torch, safetensors or run H3. It validates the exact published helper
functions on synthetic NumPy arrays, plus the stored GUI graph's links.
"""
from __future__ import annotations

import ast
import binascii
import json
import os
from pathlib import Path
import struct
import tempfile
from types import SimpleNamespace
import unittest
import zlib

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
HYBRID = ROOT / "custom_nodes/osf_h3_hybrid/__init__.py"
MAXQ = ROOT / "custom_nodes/osf_h3_maxq/__init__.py"
WORKFLOW = ROOT / "workflows/OrbitTurn_H3_comparison_workflow.json"


class _FakeFolderPaths:
    root: Path | None = None

    def get_output_directory(self):
        assert self.root is not None
        return str(self.root)


class _FakeImage:
    """Synthetic stand-in only for Comfy IMAGE's methods used in save()."""
    ndim = 4

    def __init__(self, array):
        self.array = array

    def __getitem__(self, index):
        return _FakeImage(self.array[index])

    def detach(self):
        return self

    def to(self, *args, **kwargs):
        return self

    def numpy(self):
        return self.array


class _FakeLatentPart:
    def __init__(self, shape):
        self.shape = shape

    def detach(self):
        return self

    def to(self, *args, **kwargs):
        return self

    def contiguous(self):
        return self


def load_png_helpers():
    """Execute real source helpers and export wrappers with inert dependencies.

    Only AST-selected code is executed. No ComfyUI, GPU, torch, model loading
    or real safetensors library is imported. Save operations target temp dirs.
    """
    tree = ast.parse(MAXQ.read_text(encoding="utf-8"), filename=str(MAXQ))
    funcs = {
        "_output_path", "_exclusive_write", "_latent_output_path",
        "_png_output_prefix", "_png_chunk", "_write_png16_rgb",
    }
    classes = {"OSFSavePNG16", "OSFH3SaveAVLatent"}
    selected = [x for x in tree.body if
                (isinstance(x, ast.FunctionDef) and x.name in funcs)
                or (isinstance(x, ast.ClassDef) and x.name in classes)]
    if len(selected) != len(funcs) + len(classes):
        raise AssertionError("required MaxQ helpers or wrappers absent")
    code = compile(ast.Module(body=selected, type_ignores=[]), str(MAXQ), "exec")
    fake_folder = _FakeFolderPaths()
    def fake_save_file(tensors, filename, metadata):
        assert set(tensors) == {"video", "audio"}
        assert metadata["format"] == "OSF_H3_AV_LATENT"
        Path(filename).write_bytes(b"SYNTHETIC-CHECKPOINT")
    scope = {
        "struct": struct, "binascii": binascii, "zlib": zlib,
        "Path": Path, "np": np, "os": os, "tempfile": tempfile,
        "folder_paths": fake_folder,
        "torch": SimpleNamespace(Tensor=_FakeImage, float32=np.float32),
        "safetensors": SimpleNamespace(torch=SimpleNamespace(save_file=fake_save_file)),
        "_av_parts": lambda latent, name: (latent["video"], latent["audio"]),
        "json": json,
    }
    exec(code, scope)
    return scope, fake_folder


def chunks(data):
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise AssertionError("PNG signature missing")
    position = 8
    result = []
    while position < len(data):
        if position + 12 > len(data):
            raise AssertionError("truncated PNG chunk")
        size = struct.unpack(">I", data[position:position+4])[0]
        kind = data[position+4:position+8]
        raw = data[position+8:position+8+size]
        crc_bytes = data[position+8+size:position+12+size]
        if len(raw) != size or len(crc_bytes) != 4:
            raise AssertionError("truncated PNG chunk data")
        expected = binascii.crc32(kind + raw) & 0xffffffff
        if struct.unpack(">I", crc_bytes)[0] != expected:
            raise AssertionError("PNG CRC mismatch")
        result.append((kind, raw))
        position += 12 + size
    if position != len(data):
        raise AssertionError("trailing PNG bytes")
    return result


class OrbitTurnOfflineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.maxq, cls.fake_folder = load_png_helpers()
        cls.make_chunk = staticmethod(cls.maxq["_png_chunk"])
        cls.write_png = staticmethod(cls.maxq["_write_png16_rgb"])

    def test_both_custom_node_modules_parse(self):
        for module in (HYBRID, MAXQ):
            with self.subTest(file=str(module.relative_to(ROOT))):
                ast.parse(module.read_text(encoding="utf-8"))

    def test_png_chunk_crc(self):
        raw = self.make_chunk(b"tEXt", b"synthetic")
        self.assertEqual(raw[:4], struct.pack(">I", 9))
        self.assertEqual(raw[4:8], b"tEXt")
        self.assertEqual(struct.unpack(">I", raw[-4:])[0],
                         binascii.crc32(b"tEXtsynthetic") & 0xffffffff)

    def test_png16_writer_preserves_all_sample_bits_and_endianness(self):
        frame = np.array([
            [[0, 1, 255], [256, 32768, 65535]],
            [[65535, 0, 256], [12345, 54321, 42]],
        ], dtype=np.uint16)
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "synthetic.png"
            self.write_png(path, frame, 6)
            content = path.read_bytes()
        parts = chunks(content)
        self.assertEqual([kind for kind, _ in parts],
                         [b"IHDR", b"IDAT", b"IEND"])
        width, height, depth, color, compression, filtering, interlace = (
            struct.unpack(">IIBBBBB", parts[0][1])
        )
        self.assertEqual((width, height, depth, color, compression,
                          filtering, interlace), (2, 2, 16, 2, 0, 0, 0))
        stream = zlib.decompress(parts[1][1])
        expected = b"".join(
            b"\x00" + frame[y].astype(">u2").tobytes(order="C")
            for y in range(frame.shape[0])
        )
        self.assertEqual(stream, expected)
        self.assertEqual(stream[1:7], bytes.fromhex("0000000100ff"))
        self.assertEqual(len(stream), 2 * (1 + 2 * 3 * 2))

    def test_png16_compression_extremes_decode_identically(self):
        frame = np.arange(36, dtype=np.uint16).reshape((3, 4, 3)) * 1001
        results = []
        with tempfile.TemporaryDirectory() as td:
            for compression in (0, 9):
                path = Path(td) / f"{compression}.png"
                self.write_png(path, frame, compression)
                pieces = chunks(path.read_bytes())
                results.append(zlib.decompress(pieces[1][1]))
        self.assertEqual(results[0], results[1])

    def test_png16_rejects_wrong_dtype(self):
        bad = np.zeros((2, 2, 3), dtype=np.uint8)
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaisesRegex(ValueError, "uint16"):
                self.write_png(Path(td) / "bad.png", bad, 6)
            self.assertFalse((Path(td) / "bad.png").exists())

    def test_png16_rejects_nonrgb_or_wrong_rank(self):
        with tempfile.TemporaryDirectory() as td:
            for shape in ((2, 2, 4), (2, 2), (2, 2, 1)):
                with self.subTest(shape=shape):
                    with self.assertRaisesRegex(ValueError, "RGB"):
                        self.write_png(Path(td) / "bad.png",
                                       np.zeros(shape, dtype=np.uint16), 6)

    def test_png16_export_is_create_only_without_truncating_previous_frame(self):
        old = np.full((2, 3, 3), 12345, dtype=np.uint16)
        new = np.full((2, 3, 3), 54321, dtype=np.uint16)
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "frame.png"
            self.write_png(path, old, 6)
            original = path.read_bytes()
            with self.assertRaises(FileExistsError):
                self.write_png(path, new, 6)
            self.assertEqual(path.read_bytes(), original)
            self.assertEqual(list(Path(td).glob(".osf-maxq-*.tmp")), [])

    def test_maxq_output_paths_reject_escape_and_symlinked_parent(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "comfy-output"
            outside = Path(td) / "outside"
            root.mkdir()
            outside.mkdir()
            self.fake_folder.root = root
            output_path = self.maxq["_latent_output_path"]
            prefix_path = self.maxq["_png_output_prefix"]
            for get in (output_path, prefix_path):
                for raw in ("../outside/malicious", str(outside / "malicious"),
                            "safe/../../outside/malicious"):
                    with self.subTest(fn=get.__name__, path=raw):
                        with self.assertRaisesRegex(ValueError, "output filename"):
                            get(raw)
                (root / "escape").symlink_to(outside, target_is_directory=True)
                with self.assertRaisesRegex(ValueError, "escapes"):
                    get("escape/unwanted")
                (root / "escape").unlink()
            self.assertEqual(
                output_path("inside/checkpoint").parent, root / "inside"
            )
            self.assertEqual(
                output_path(str(root / "inside" / "checkpoint")).name,
                "checkpoint.safetensors",
            )
            self.assertEqual(prefix_path("inside/frames").name, "frames")
            self.assertFalse((outside / "malicious").exists())

    def test_png_save_wrapper_uses_contained_create_only_publication(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "output"
            root.mkdir()
            self.fake_folder.root = root
            images = _FakeImage(np.full((1, 3, 4, 3), 0.5, dtype=np.float32))
            node = self.maxq["OSFSavePNG16"]()
            report = node.save(images, "PassB/frames/test", 6)[0]
            path = root / "PassB/frames/test_00000.png"
            self.assertIn(str(path), report)
            baseline = path.read_bytes()
            with self.assertRaises(FileExistsError):
                node.save(images, "PassB/frames/test", 6)
            self.assertEqual(path.read_bytes(), baseline)
            with self.assertRaisesRegex(ValueError, "output filename"):
                node.save(images, "../not-allowed", 6)
            self.assertEqual(list(root.rglob(".osf-maxq-*.tmp")), [])

    def test_av_checkpoint_wrapper_uses_contained_create_only_publication(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "output"
            root.mkdir()
            self.fake_folder.root = root
            latent = {
                "video": _FakeLatentPart((1, 24, 2, 3, 4)),
                "audio": _FakeLatentPart((1, 32, 2, 3)),
            }
            node = self.maxq["OSFH3SaveAVLatent"]()
            _, path = node.save(latent, "PassA/latent")
            target = root / "PassA/latent.safetensors"
            self.assertEqual(path, str(target))
            self.assertEqual(target.read_bytes(), b"SYNTHETIC-CHECKPOINT")
            with self.assertRaises(FileExistsError):
                node.save(latent, "PassA/latent")
            self.assertEqual(target.read_bytes(), b"SYNTHETIC-CHECKPOINT")
            with self.assertRaisesRegex(ValueError, "output filename"):
                node.save(latent, "../escape")
            self.assertEqual(list(root.rglob(".osf-maxq-*.tmp")), [])

    def test_gui_workflow_nodes_links_and_slots(self):
        data = json.loads(WORKFLOW.read_text(encoding="utf-8"))
        nodes = data["nodes"]
        links = data["links"]
        self.assertGreater(len(nodes), 0)
        self.assertGreater(len(links), 0)
        ids = [n["id"] for n in nodes]
        self.assertTrue(all(type(i) is int for i in ids))
        self.assertEqual(len(ids), len(set(ids)), "duplicate GUI node IDs")
        index = {n["id"]: n for n in nodes}
        link_ids = []
        for l in links:
            self.assertIsInstance(l, list)
            self.assertGreaterEqual(len(l), 6)
            lid, origin, output_slot, target, input_slot = l[:5]
            self.assertTrue(all(type(i) is int for i in
                                (lid, origin, output_slot, target, input_slot)))
            self.assertIn(origin, index)
            self.assertIn(target, index)
            out = index[origin].get("outputs", [])
            inp = index[target].get("inputs", [])
            self.assertIsInstance(out, list)
            self.assertIsInstance(inp, list)
            self.assertGreaterEqual(output_slot, 0)
            self.assertLess(output_slot, len(out))
            self.assertGreaterEqual(input_slot, 0)
            self.assertLess(input_slot, len(inp))
            link_ids.append(lid)
        self.assertEqual(len(link_ids), len(set(link_ids)),
                         "duplicate GUI link IDs")

    def test_gui_workflow_does_not_claim_custom_node_wiring(self):
        data = json.loads(WORKFLOW.read_text(encoding="utf-8"))
        types = {node.get("type") for node in data["nodes"]}
        self.assertIn("MiniMaxH3ReferenceToVideo", types)
        self.assertNotIn("OSFMiniMaxH3HybridAnchoredReferenceToVideo", types)
        self.assertNotIn("OSFH3UpscaleRepaintAV", types)


if __name__ == "__main__":
    unittest.main()
