import tempfile
import unittest
from pathlib import Path

from scripts.automation import generate_pages


class GeneratePagesLinksTests(unittest.TestCase):
    def test_header_directive_refreshes_frontmatter_with_all_entity_columns(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_dir = root / "data"
            notes_dir = root / "notes"
            (notes_dir / "people").mkdir(parents=True)
            data_dir.mkdir(parents=True)

            (data_dir / "people.csv").write_text(
                "id,name,email,status\nperson_a,Alpha,alpha@example.com,active\n",
                encoding="utf-8",
            )

            note = notes_dir / "people" / "person_a.md"
            note.write_text(
                """---
id: person_a
type: people
---
<!-- GENERATED START: header -->
# stale
<!-- GENERATED END -->
""",
                encoding="utf-8",
            )

            old_root = generate_pages.ROOT
            old_data = generate_pages.DATA_DIR
            old_notes = generate_pages.NOTES_DIR
            try:
                generate_pages.ROOT = root
                generate_pages.DATA_DIR = data_dir
                generate_pages.NOTES_DIR = notes_dir
                code = generate_pages.generate()
            finally:
                generate_pages.ROOT = old_root
                generate_pages.DATA_DIR = old_data
                generate_pages.NOTES_DIR = old_notes

            self.assertEqual(code, 0)
            content = note.read_text(encoding="utf-8")
            self.assertIn('name: "Alpha"', content)
            self.assertIn('email: "alpha@example.com"', content)
            self.assertIn('status: "active"', content)
            self.assertIn("# Alpha", content)

    def test_list_directive_renders_relative_markdown_links(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_dir = root / "data"
            notes_dir = root / "notes"
            (notes_dir / "programs").mkdir(parents=True)
            data_dir.mkdir(parents=True)

            (data_dir / "people.csv").write_text(
                "id,name\nperson_b,Bravo\nperson_a,Alpha\n",
                encoding="utf-8",
            )
            (data_dir / "programs.csv").write_text(
                "id,name\nprog_alpha,Alpha Program\n",
                encoding="utf-8",
            )

            note = notes_dir / "programs" / "prog_alpha.md"
            note.write_text(
                """---
id: prog_alpha
type: programs
---
<!-- GENERATED START: list:people -->
- stale
<!-- GENERATED END -->
""",
                encoding="utf-8",
            )

            old_root = generate_pages.ROOT
            old_data = generate_pages.DATA_DIR
            old_notes = generate_pages.NOTES_DIR
            try:
                generate_pages.ROOT = root
                generate_pages.DATA_DIR = data_dir
                generate_pages.NOTES_DIR = notes_dir
                code = generate_pages.generate()
            finally:
                generate_pages.ROOT = old_root
                generate_pages.DATA_DIR = old_data
                generate_pages.NOTES_DIR = old_notes

            self.assertEqual(code, 0)
            content = note.read_text(encoding="utf-8")
            self.assertIn("- [person_a](../people/person_a.md)", content)
            self.assertIn("- [person_b](../people/person_b.md)", content)

    def test_table_directive_links_foreign_keys_to_entity_notes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_dir = root / "data"
            notes_dir = root / "notes"
            (notes_dir / "programs").mkdir(parents=True)
            data_dir.mkdir(parents=True)

            (data_dir / "people.csv").write_text(
                "id,name\nperson_a,Alpha\n",
                encoding="utf-8",
            )
            (data_dir / "programs.csv").write_text(
                "id,name\nprog_alpha,Alpha Program\n",
                encoding="utf-8",
            )
            (data_dir / "program_memberships.csv").write_text(
                "id,program_id,person_id\nmem_1,prog_alpha,person_a\n",
                encoding="utf-8",
            )

            note = notes_dir / "programs" / "prog_alpha.md"
            note.write_text(
                """---
id: prog_alpha
type: programs
---
<!-- GENERATED START: table:program_memberships -->
| stale |
<!-- GENERATED END -->
""",
                encoding="utf-8",
            )

            old_root = generate_pages.ROOT
            old_data = generate_pages.DATA_DIR
            old_notes = generate_pages.NOTES_DIR
            try:
                generate_pages.ROOT = root
                generate_pages.DATA_DIR = data_dir
                generate_pages.NOTES_DIR = notes_dir
                code = generate_pages.generate()
            finally:
                generate_pages.ROOT = old_root
                generate_pages.DATA_DIR = old_data
                generate_pages.NOTES_DIR = old_notes

            self.assertEqual(code, 0)
            content = note.read_text(encoding="utf-8")
            self.assertIn("[prog_alpha](prog_alpha.md)", content)
            self.assertIn("[person_a](../people/person_a.md)", content)
            self.assertIn("| mem_1 |", content)


if __name__ == "__main__":
    unittest.main()
