import tempfile
import unittest
from pathlib import Path

from scripts.export import export_public_snapshot as eps


class ExportPublicSnapshotTests(unittest.TestCase):
    def test_sanitize_note_text_redacts_private_links(self) -> None:
        text = "Public [[person_public]] and private [[person_private]]"
        result = eps.sanitize_note_text(text, {"person_private"})
        self.assertEqual(result, "Public [[person_public]] and private [redacted]")

    def test_note_has_private_references(self) -> None:
        self.assertTrue(eps.note_has_private_references("[[a]] [[b]]", {"b"}))
        self.assertFalse(eps.note_has_private_references("[[a]] [[b]]", {"c"}))

    def test_export_notes_redact_policy_keeps_note(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            notes_dir = root / "notes"
            out_dir = root / "out"
            (notes_dir / "people").mkdir(parents=True)
            note = notes_dir / "people" / "person_public.md"
            note.write_text(
                "---\nid: person_public\n---\nMentor [[person_private]]",
                encoding="utf-8",
            )

            old_notes = eps.NOTES_DIR
            try:
                eps.NOTES_DIR = notes_dir
                eps.export_notes({"person_private"}, out_dir, note_policy="redact")
            finally:
                eps.NOTES_DIR = old_notes

            exported = out_dir / "people" / "person_public.md"
            self.assertTrue(exported.exists())
            self.assertIn("[redacted]", exported.read_text(encoding="utf-8"))

    def test_export_notes_drop_policy_drops_note(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            notes_dir = root / "notes"
            out_dir = root / "out"
            (notes_dir / "people").mkdir(parents=True)
            note = notes_dir / "people" / "person_public.md"
            note.write_text(
                "---\nid: person_public\n---\nMentor [[person_private]]",
                encoding="utf-8",
            )

            old_notes = eps.NOTES_DIR
            try:
                eps.NOTES_DIR = notes_dir
                eps.export_notes({"person_private"}, out_dir, note_policy="drop")
            finally:
                eps.NOTES_DIR = old_notes

            exported = out_dir / "people" / "person_public.md"
            self.assertFalse(exported.exists())

    def test_export_note_assets_copies_linked_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            notes_dir = root / "notes"
            out_dir = root / "out"
            (notes_dir / "people").mkdir(parents=True)
            (notes_dir / "assets").mkdir(parents=True)
            (out_dir / "people").mkdir(parents=True)

            source_asset = notes_dir / "assets" / "photo.png"
            source_asset.write_bytes(b"png")

            exported_note = out_dir / "people" / "person_public.md"
            exported_note.write_text(
                "![Photo](../assets/photo.png)",
                encoding="utf-8",
            )

            old_notes = eps.NOTES_DIR
            try:
                eps.NOTES_DIR = notes_dir
                copied = eps.export_note_assets(out_dir, [])
            finally:
                eps.NOTES_DIR = old_notes

            self.assertEqual(copied, 1)
            self.assertTrue((out_dir / "assets" / "photo.png").exists())

    def test_export_note_assets_respects_private_file_patterns(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            notes_dir = root / "notes"
            out_dir = root / "out"
            (notes_dir / "assets").mkdir(parents=True)
            (out_dir / "people").mkdir(parents=True)

            (notes_dir / "assets" / "private.png").write_bytes(b"png")
            (out_dir / "people" / "person_public.md").write_text(
                "![Private](../assets/private.png)",
                encoding="utf-8",
            )

            old_notes = eps.NOTES_DIR
            try:
                eps.NOTES_DIR = notes_dir
                copied = eps.export_note_assets(out_dir, ["assets/private.png"])
            finally:
                eps.NOTES_DIR = old_notes

            self.assertEqual(copied, 0)
            self.assertFalse((out_dir / "assets" / "private.png").exists())

if __name__ == "__main__":
    unittest.main()
