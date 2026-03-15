import tempfile
import unittest
from pathlib import Path

from scripts.automation import migrate_wikilinks


class MigrateWikiLinksTests(unittest.TestCase):
    def test_rewrites_resolved_links(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_dir = root / "data"
            notes_dir = root / "notes"
            people_dir = notes_dir / "people"
            programs_dir = notes_dir / "programs"
            data_dir.mkdir(parents=True)
            people_dir.mkdir(parents=True)
            programs_dir.mkdir(parents=True)

            (data_dir / "people.csv").write_text(
                "id,name\nperson_a,Alpha\n",
                encoding="utf-8",
            )
            (data_dir / "programs.csv").write_text(
                "id,name\nprog_x,Program X\n",
                encoding="utf-8",
            )

            (people_dir / "person_a.md").write_text("# Person A\n", encoding="utf-8")
            program_note = programs_dir / "prog_x.md"
            program_note.write_text("Mentor [[person_a]]\n", encoding="utf-8")

            old_root = migrate_wikilinks.ROOT
            old_data = migrate_wikilinks.DATA_DIR
            old_notes = migrate_wikilinks.NOTES_DIR
            try:
                migrate_wikilinks.ROOT = root
                migrate_wikilinks.DATA_DIR = data_dir
                migrate_wikilinks.NOTES_DIR = notes_dir
                files_changed, links_rewritten = migrate_wikilinks.migrate(notes_dir)
            finally:
                migrate_wikilinks.ROOT = old_root
                migrate_wikilinks.DATA_DIR = old_data
                migrate_wikilinks.NOTES_DIR = old_notes

            self.assertEqual(files_changed, 1)
            self.assertEqual(links_rewritten, 1)
            self.assertIn("[person_a](../people/person_a.md)", program_note.read_text(encoding="utf-8"))

    def test_leaves_unresolved_links_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            notes_dir = root / "notes"
            notes_dir.mkdir(parents=True)
            note = notes_dir / "free.md"
            note.write_text("Unknown [[missing_id]]\n", encoding="utf-8")

            old_notes = migrate_wikilinks.NOTES_DIR
            try:
                migrate_wikilinks.NOTES_DIR = notes_dir
                files_changed, links_rewritten = migrate_wikilinks.migrate(notes_dir)
            finally:
                migrate_wikilinks.NOTES_DIR = old_notes

            self.assertEqual(files_changed, 0)
            self.assertEqual(links_rewritten, 0)
            self.assertIn("[[missing_id]]", note.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
