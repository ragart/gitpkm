import json
import tempfile
import unittest
from pathlib import Path

from scripts.automation import build_indexes


class BuildIndexesTests(unittest.TestCase):
    def test_auto_generates_entity_index_without_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_dir = root / "data"
            index_dir = root / "notes" / "indexes"
            data_dir.mkdir(parents=True)
            index_dir.mkdir(parents=True)

            (data_dir / "people.csv").write_text(
                "id,name\nperson_b,Bravo\nperson_a,Alpha\n",
                encoding="utf-8",
            )

            old_root = build_indexes.ROOT
            old_data = build_indexes.DATA_DIR
            old_index = build_indexes.INDEX_DIR
            old_config = build_indexes.AUTOMATION_CONFIG

            try:
                build_indexes.ROOT = root
                build_indexes.DATA_DIR = data_dir
                build_indexes.INDEX_DIR = index_dir
                build_indexes.AUTOMATION_CONFIG = root / "schema" / "automation.json"

                code = build_indexes.main()
            finally:
                build_indexes.ROOT = old_root
                build_indexes.DATA_DIR = old_data
                build_indexes.INDEX_DIR = old_index
                build_indexes.AUTOMATION_CONFIG = old_config

            self.assertEqual(code, 0)

            output_path = index_dir / "all_people.md"
            self.assertTrue(output_path.exists())
            content = output_path.read_text(encoding="utf-8")
            self.assertIn("# All People", content)
            self.assertIn("| name |", content)
            self.assertNotIn("| id |", content)
            self.assertIn("| [Alpha](../people/person_a.md) |", content)
            self.assertIn("| [Bravo](../people/person_b.md) |", content)

    def test_configured_output_has_priority_over_auto_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_dir = root / "data"
            schema_dir = root / "schema"
            index_dir = root / "notes" / "indexes"
            data_dir.mkdir(parents=True)
            schema_dir.mkdir(parents=True)
            index_dir.mkdir(parents=True)

            (data_dir / "programs.csv").write_text(
                "id,name\nprog_b,Bravo\nprog_a,Alpha\n",
                encoding="utf-8",
            )
            (data_dir / "games.csv").write_text(
                "id,name\ngame_z,Zeta\n",
                encoding="utf-8",
            )

            (schema_dir / "automation.json").write_text(
                json.dumps(
                    {
                        "indexes": [
                            {
                                "type": "entity_list",
                                "entity_table": "programs",
                                "entity_id_column": "id",
                                "title": "Configured Programs",
                                "output": "all_programs.md",
                                "remove_when_empty": True,
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            old_root = build_indexes.ROOT
            old_data = build_indexes.DATA_DIR
            old_index = build_indexes.INDEX_DIR
            old_config = build_indexes.AUTOMATION_CONFIG

            try:
                build_indexes.ROOT = root
                build_indexes.DATA_DIR = data_dir
                build_indexes.INDEX_DIR = index_dir
                build_indexes.AUTOMATION_CONFIG = schema_dir / "automation.json"

                code = build_indexes.main()
            finally:
                build_indexes.ROOT = old_root
                build_indexes.DATA_DIR = old_data
                build_indexes.INDEX_DIR = old_index
                build_indexes.AUTOMATION_CONFIG = old_config

            self.assertEqual(code, 0)

            programs_index = (index_dir / "all_programs.md").read_text(encoding="utf-8")
            self.assertIn("# Configured Programs", programs_index)

            games_index = index_dir / "all_games.md"
            self.assertTrue(games_index.exists())
            self.assertIn("# All Games", games_index.read_text(encoding="utf-8"))
            games_content = games_index.read_text(encoding="utf-8")
            self.assertIn("| name |", games_content)
            self.assertNotIn("| id |", games_content)
            self.assertIn("| [Zeta](../games/game_z.md) |", games_content)

    def test_auto_resolves_foreign_keys_to_linked_names(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_dir = root / "data"
            index_dir = root / "notes" / "indexes"
            data_dir.mkdir(parents=True)
            index_dir.mkdir(parents=True)

            (data_dir / "people.csv").write_text(
                "id,name\nperson_b,Bravo\nperson_a,Alpha\n",
                encoding="utf-8",
            )
            (data_dir / "games.csv").write_text(
                "id,name,owner_id\ngame_z,Zeta,person_a\n",
                encoding="utf-8",
            )

            old_root = build_indexes.ROOT
            old_data = build_indexes.DATA_DIR
            old_index = build_indexes.INDEX_DIR
            old_config = build_indexes.AUTOMATION_CONFIG

            try:
                build_indexes.ROOT = root
                build_indexes.DATA_DIR = data_dir
                build_indexes.INDEX_DIR = index_dir
                build_indexes.AUTOMATION_CONFIG = root / "schema" / "automation.json"

                code = build_indexes.main()
            finally:
                build_indexes.ROOT = old_root
                build_indexes.DATA_DIR = old_data
                build_indexes.INDEX_DIR = old_index
                build_indexes.AUTOMATION_CONFIG = old_config

            self.assertEqual(code, 0)

            games_content = (index_dir / "all_games.md").read_text(encoding="utf-8")
            self.assertIn("| name | owner_name |", games_content)
            self.assertNotIn("owner_id", games_content)
            self.assertNotIn("| person_a |", games_content)
            self.assertIn("| [Zeta](../games/game_z.md) | [Alpha](../people/person_a.md) |", games_content)

    def test_configured_entity_table_uses_name_link_rules(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_dir = root / "data"
            schema_dir = root / "schema"
            index_dir = root / "notes" / "indexes"
            data_dir.mkdir(parents=True)
            schema_dir.mkdir(parents=True)
            index_dir.mkdir(parents=True)

            (data_dir / "people.csv").write_text(
                "id,name\nperson_a,Alpha\n",
                encoding="utf-8",
            )
            (data_dir / "games.csv").write_text(
                "id,name,owner_id\ngame_z,Zeta,person_a\n",
                encoding="utf-8",
            )

            (schema_dir / "automation.json").write_text(
                json.dumps(
                    {
                        "indexes": [
                            {
                                "type": "entity_table",
                                "entity_table": "games",
                                "entity_id_column": "id",
                                "title": "Configured Games",
                                "output": "configured_games.md",
                                "remove_when_empty": True,
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            old_root = build_indexes.ROOT
            old_data = build_indexes.DATA_DIR
            old_index = build_indexes.INDEX_DIR
            old_config = build_indexes.AUTOMATION_CONFIG

            try:
                build_indexes.ROOT = root
                build_indexes.DATA_DIR = data_dir
                build_indexes.INDEX_DIR = index_dir
                build_indexes.AUTOMATION_CONFIG = schema_dir / "automation.json"

                code = build_indexes.main()
            finally:
                build_indexes.ROOT = old_root
                build_indexes.DATA_DIR = old_data
                build_indexes.INDEX_DIR = old_index
                build_indexes.AUTOMATION_CONFIG = old_config

            self.assertEqual(code, 0)

            content = (index_dir / "configured_games.md").read_text(encoding="utf-8")
            self.assertIn("# Configured Games", content)
            self.assertIn("| name | owner_name |", content)
            self.assertNotIn("| id |", content)
            self.assertNotIn("owner_id", content)
            self.assertIn("| [Zeta](../games/game_z.md) | [Alpha](../people/person_a.md) |", content)


if __name__ == "__main__":
    unittest.main()
