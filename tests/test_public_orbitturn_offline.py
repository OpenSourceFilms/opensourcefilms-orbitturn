"""CPU-only tests of actual public OrbitTurn helper source.

The test extracts two pure PNG-writing functions by AST. It does NOT import
ComfyUI, torch, safetensors or run H3. It validates the exact published helper
functions on synthetic NumPy arrays, plus the stored GUI graph's links.
"""
from __future__ import annotations

import ast
import binascii
import json
from pathlib import Path
import struct
import tempfile
import unittest
import zlib

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
HYBRID = ROOT / "custom_nodes/osf_h3_hybrid/__init__.py"
MAXQ = ROOT / "custom_nodes/osf_h3_maxq/__init__.py"
WORKFLOW = ROOT / "workflows/OrbitTurn_H3_comparison_workflow.json"


def load_png_helpers():
    """Execute only pure helpers extracted from the actual published source."""
    tree = ast.parse(MAXQ.read_text(encoding="utf-8"), filename=str(MAXQ))
    selected = [x for x in tree.body
                if isinstance(x, ast.FunctionDef) and
                x.name in ("_png_chunk", "_write_png16_rgb")]
    if len(selected) != 2:
        raise AssertionError("exactly two named PNG helpers required")
    code = compile(ast.Module(body=selected, type_ignores=[]), str(MAXQ), "exec")
    scope = {"struct": struct, "binascii": binascii, "zlib": zlib,
             "Path": Path, "np": np}
    exec(code, scope)
    return scope["_png_chunk"], scope["_write_png16_rgb"]


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
        chunk, writer = load_png_helpers()
        cls.make_chunk = staticmethod(chunk)
        cls.write_png = staticmethod(writer)

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
