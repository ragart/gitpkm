import tempfile
import unittest
from pathlib import Path

from scripts.automation import update_readme_directory as urd


class UpdateReadmeDirectoryTests(unittest.TestCase):
    def test_update_readme_writes_directory_when_ready(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "data").mkdir(parents=True)
            (root / "notes" / "indexes").mkdir(parents=True)
            (root / "notes" / "people").mkdir(parents=True)

            (root / "README.md").write_text("Original README\n", encoding="utf-8")
            (root / "data" / "people.csv").write_text("id,name\nperson_a,Alpha\n", encoding="utf-8")
            (root / "notes" / "indexes" / "all_people.md").write_text(
                "# All People\n\n| name |\n| --- |\n| [Alpha](../people/person_a.md) |\n",
                encoding="utf-8",
            )
            (root / "notes" / "people" / "person_a.md").write_text("# Alpha\n", encoding="utf-8")

            changed = urd.update_readme(root)

            self.assertTrue(changed)
            readme = (root / "README.md").read_text(encoding="utf-8")
            self.assertIn("# Knowledge Directory", readme)
            self.assertIn("| [people.csv](data/people.csv) | 1 | 2 |", readme)
            self.assertIn("| [all_people.md](notes/indexes/all_people.md) | All People | entity_table |", readme)

    def test_update_readme_skips_when_data_empty(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "data").mkdir(parents=True)
            (root / "notes" / "indexes").mkdir(parents=True)

            original = "Original README\n"
            (root / "README.md").write_text(original, encoding="utf-8")
            (root / "data" / "people.csv").write_text("id,name\n", encoding="utf-8")
            (root / "notes" / "indexes" / "all_people.md").write_text("# All People\n", encoding="utf-8")

            changed = urd.update_readme(root)

            self.assertFalse(changed)
            self.assertEqual((root / "README.md").read_text(encoding="utf-8"), original)

    def test_update_readme_skips_without_indexes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "data").mkdir(parents=True)
            (root / "notes").mkdir(parents=True)

            original = "Original README\n"
            (root / "README.md").write_text(original, encoding="utf-8")
            (root / "data" / "people.csv").write_text("id,name\nperson_a,Alpha\n", encoding="utf-8")

            changed = urd.update_readme(root)

            self.assertFalse(changed)
            self.assertEqual((root / "README.md").read_text(encoding="utf-8"), original)


if __name__ == "__main__":
    unittest.main()
