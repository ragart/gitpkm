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

    def test_replace_readme_with_directory_page_when_data_and_indexes_exist(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_dir = root / "data"
            notes_dir = root / "notes"
            indexes_dir = notes_dir / "indexes"
            people_dir = notes_dir / "people"

            data_dir.mkdir(parents=True)
            indexes_dir.mkdir(parents=True)
            people_dir.mkdir(parents=True)

            (root / "README.md").write_text("Original README\n", encoding="utf-8")
            (data_dir / "people.csv").write_text("id,name\nperson_a,Alpha\n", encoding="utf-8")
            (indexes_dir / "all_people.md").write_text(
                "# All People\n\n| name |\n| --- |\n| [Alpha](../people/person_a.md) |\n",
                encoding="utf-8",
            )
            (people_dir / "person_a.md").write_text("# Alpha\n", encoding="utf-8")

            replaced = eps.replace_readme_with_directory_page(root)

            self.assertTrue(replaced)
            readme = (root / "README.md").read_text(encoding="utf-8")
            self.assertIn("# Public Knowledge Directory", readme)
            self.assertIn("| [people.csv](data/people.csv) | 1 | 2 |", readme)
            self.assertIn("| [all_people.md](notes/indexes/all_people.md) | All People | entity_table |", readme)
            self.assertIn("| [people/](notes/people/) | 1 |", readme)

    def test_replace_readme_with_directory_page_skips_when_data_empty(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_dir = root / "data"
            indexes_dir = root / "notes" / "indexes"

            data_dir.mkdir(parents=True)
            indexes_dir.mkdir(parents=True)

            original = "Original README\n"
            (root / "README.md").write_text(original, encoding="utf-8")
            (data_dir / "people.csv").write_text("id,name\n", encoding="utf-8")
            (indexes_dir / "all_people.md").write_text("# All People\n\n- [person_a](../people/person_a.md)\n", encoding="utf-8")

            replaced = eps.replace_readme_with_directory_page(root)

            self.assertFalse(replaced)
            self.assertEqual((root / "README.md").read_text(encoding="utf-8"), original)

    def test_replace_readme_with_directory_page_skips_without_indexes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_dir = root / "data"
            notes_dir = root / "notes"

            data_dir.mkdir(parents=True)
            notes_dir.mkdir(parents=True)

            original = "Original README\n"
            (root / "README.md").write_text(original, encoding="utf-8")
            (data_dir / "people.csv").write_text("id,name\nperson_a,Alpha\n", encoding="utf-8")

            replaced = eps.replace_readme_with_directory_page(root)

            self.assertFalse(replaced)
            self.assertEqual((root / "README.md").read_text(encoding="utf-8"), original)


if __name__ == "__main__":
    unittest.main()
