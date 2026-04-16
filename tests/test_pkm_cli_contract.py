import unittest
import tempfile
import json
import io
import importlib.util
from pathlib import Path
from unittest import mock
from contextlib import redirect_stdout

import pkm


def load_validate_import_mappings_module():
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "quality" / "validate_import_mappings.py"
    spec = importlib.util.spec_from_file_location("validate_import_mappings", script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PkmCliContractTests(unittest.TestCase):
    def test_infer_relation_table_uses_exact_dataset_names(self) -> None:
        table, source_fk, target_fk = pkm.infer_relation_table(
            "people",
            "programs",
            {
                "participations": (
                    ["id", "people_id", "programs_id", "role"],
                    [],
                )
            },
        )
        self.assertEqual(table, "participations")
        self.assertEqual(source_fk, "people_id")
        self.assertEqual(target_fk, "programs_id")

    def test_infer_relation_table_requires_unique_match(self) -> None:
        with self.assertRaises(ValueError):
            pkm.infer_relation_table(
                "people",
                "programs",
                {
                    "a": (["people_id", "programs_id"], []),
                    "b": (["people_id", "programs_id"], []),
                },
            )

    def test_new_allows_setting_additional_entity_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp) / "data"
            data_dir.mkdir(parents=True)
            (data_dir / "people.csv").write_text(
                "id,name,email,role\n",
                encoding="utf-8",
            )

            args = pkm.argparse.Namespace(
                entity_type="people",
                name="Alex Doe",
                id=None,
                columns="",
                set_values=["email=alex@example.com", "role=mentor"],
            )

            old_data_dir = pkm.DATA_DIR
            try:
                pkm.DATA_DIR = data_dir
                with mock.patch("pkm.run_automation"):
                    exit_code = pkm.command_new(args)
            finally:
                pkm.DATA_DIR = old_data_dir

            self.assertEqual(exit_code, 0)
            _, rows = pkm.read_table(data_dir / "people.csv")
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["id"], "people_alex_doe")
            self.assertEqual(rows[0]["name"], "Alex Doe")
            self.assertEqual(rows[0]["email"], "alex@example.com")
            self.assertEqual(rows[0]["role"], "mentor")

    def test_new_rejects_unknown_entity_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp) / "data"
            data_dir.mkdir(parents=True)
            (data_dir / "people.csv").write_text(
                "id,name,email\n",
                encoding="utf-8",
            )

            args = pkm.argparse.Namespace(
                entity_type="people",
                name="Alex Doe",
                id=None,
                columns="",
                set_values=["nickname=alex"],
            )

            old_data_dir = pkm.DATA_DIR
            try:
                pkm.DATA_DIR = data_dir
                with self.assertRaisesRegex(ValueError, "unknown columns for people: nickname"):
                    pkm.command_new(args)
            finally:
                pkm.DATA_DIR = old_data_dir

    def test_new_creates_missing_dataset_columns_from_set(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp) / "data"
            data_dir.mkdir(parents=True)

            args = pkm.argparse.Namespace(
                entity_type="vip_people",
                name="Iune Banderas, the Children of Fate",
                id=None,
                columns="",
                set_values=["status=GROWING"],
            )

            old_data_dir = pkm.DATA_DIR
            try:
                pkm.DATA_DIR = data_dir
                with mock.patch("pkm.run_automation"):
                    exit_code = pkm.command_new(args)
            finally:
                pkm.DATA_DIR = old_data_dir

            self.assertEqual(exit_code, 0)
            fieldnames, rows = pkm.read_table(data_dir / "vip_people.csv")
            self.assertEqual(fieldnames, ["id", "name", "status"])
            self.assertEqual(rows[0]["status"], "GROWING")

    def test_new_creates_missing_dataset_columns_from_columns_flag(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp) / "data"
            data_dir.mkdir(parents=True)

            args = pkm.argparse.Namespace(
                entity_type="vip_people",
                name="Iune Banderas",
                id=None,
                columns="status,rarity",
                set_values=[],
            )

            old_data_dir = pkm.DATA_DIR
            try:
                pkm.DATA_DIR = data_dir
                with mock.patch("pkm.run_automation"):
                    exit_code = pkm.command_new(args)
            finally:
                pkm.DATA_DIR = old_data_dir

            self.assertEqual(exit_code, 0)
            fieldnames, rows = pkm.read_table(data_dir / "vip_people.csv")
            self.assertEqual(fieldnames, ["id", "name", "status", "rarity"])
            self.assertEqual(rows[0]["status"], "")
            self.assertEqual(rows[0]["rarity"], "")

    def test_reprocess_notes_command_runs_generate_pages(self) -> None:
        with mock.patch("pkm.generate_pages.generate") as mocked_generate:
            exit_code = pkm.command_reprocess_notes(pkm.argparse.Namespace())

        self.assertEqual(exit_code, 0)
        mocked_generate.assert_called_once_with()

    def test_update_applies_fields_and_runs_automation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp) / "data"
            data_dir.mkdir(parents=True)
            (data_dir / "game_disc.csv").write_text(
                "id,name,game_title_id,status\ndisc_cusa,CUSA-19620,,draft\n",
                encoding="utf-8",
            )

            args = pkm.argparse.Namespace(
                entity_type="game_disc",
                entity_id="disc_cusa",
                set_values=["game_title_id=game_title_13_sentinels", "status=released"],
            )

            old_data_dir = pkm.DATA_DIR
            try:
                pkm.DATA_DIR = data_dir
                with mock.patch("pkm.run_automation") as mocked_run_automation:
                    exit_code = pkm.command_update(args)
            finally:
                pkm.DATA_DIR = old_data_dir

            self.assertEqual(exit_code, 0)
            mocked_run_automation.assert_called_once_with()
            _, rows = pkm.read_table(data_dir / "game_disc.csv")
            self.assertEqual(rows[0]["game_title_id"], "game_title_13_sentinels")
            self.assertEqual(rows[0]["status"], "released")

    def test_update_rejects_unknown_columns(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp) / "data"
            data_dir.mkdir(parents=True)
            (data_dir / "people.csv").write_text(
                "id,name\npeople_alex,Alex\n",
                encoding="utf-8",
            )

            args = pkm.argparse.Namespace(
                entity_type="people",
                entity_id="people_alex",
                set_values=["nickname=Lex"],
            )

            old_data_dir = pkm.DATA_DIR
            try:
                pkm.DATA_DIR = data_dir
                with self.assertRaisesRegex(ValueError, "unknown columns for people: nickname"):
                    pkm.command_update(args)
            finally:
                pkm.DATA_DIR = old_data_dir

    def test_update_requires_existing_entity_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp) / "data"
            data_dir.mkdir(parents=True)
            (data_dir / "people.csv").write_text(
                "id,name\npeople_alex,Alex\n",
                encoding="utf-8",
            )

            args = pkm.argparse.Namespace(
                entity_type="people",
                entity_id="people_bravo",
                set_values=["name=Bravo"],
            )

            old_data_dir = pkm.DATA_DIR
            try:
                pkm.DATA_DIR = data_dir
                with self.assertRaisesRegex(ValueError, "entity id not found in people: people_bravo"):
                    pkm.command_update(args)
            finally:
                pkm.DATA_DIR = old_data_dir

    def test_bulk_import_dry_run_does_not_write_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp) / "data"
            data_dir.mkdir(parents=True)
            source_csv = Path(tmp) / "import.csv"
            source_csv.write_text(
                "person_name,email\nAlex Doe,alex@example.com\n",
                encoding="utf-8",
            )
            mappings_dir = Path(tmp) / "mappings"
            mappings_dir.mkdir(parents=True)
            (mappings_dir / "people_only.json").write_text(
                json.dumps(
                    {
                        "match": {"source_columns": ["person_name", "email"]},
                        "entities": [
                            {
                                "key": "person",
                                "table": "people",
                                "id_template": "people_{slug:person_name}",
                                "name_column": "person_name",
                                "fields": {"email": "email"},
                            }
                        ],
                        "relations": [],
                    }
                ),
                encoding="utf-8",
            )
            (mappings_dir / "people_programs.json").write_text(
                json.dumps(
                    {
                        "match": {"source_columns": ["person_name", "program_name", "role"]},
                        "entities": [
                            {
                                "key": "person",
                                "table": "people",
                                "id_template": "people_{slug:person_name}",
                                "name_column": "person_name",
                                "fields": {"email": "email"},
                            }
                        ],
                        "relations": [],
                    }
                ),
                encoding="utf-8",
            )

            args = pkm.argparse.Namespace(
                input=str(source_csv),
                mapping="auto",
                mappings_dir=str(mappings_dir),
                apply=False,
                validate_only=False,
            )

            old_data_dir = pkm.DATA_DIR
            try:
                pkm.DATA_DIR = data_dir
                with mock.patch("pkm.run_automation") as mocked_run_automation:
                    exit_code = pkm.command_bulk_import(args)
            finally:
                pkm.DATA_DIR = old_data_dir

            self.assertEqual(exit_code, 0)
            mocked_run_automation.assert_not_called()
            self.assertFalse((data_dir / "people.csv").exists())

    def test_bulk_import_apply_creates_entities_and_relations(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp) / "data"
            data_dir.mkdir(parents=True)
            source_csv = Path(tmp) / "import.csv"
            source_csv.write_text(
                "person_name,program_name,role\nAlex Doe,Career Mentorship,mentee\nTaylor Ray,Career Mentorship,mentor\n",
                encoding="utf-8",
            )
            mappings_dir = Path(tmp) / "mappings"
            mappings_dir.mkdir(parents=True)
            (mappings_dir / "people_only.json").write_text(
                json.dumps(
                    {
                        "match": {"source_columns": ["person_name", "email"]},
                        "entities": [
                            {
                                "key": "person",
                                "table": "people",
                                "id_template": "people_{slug:person_name}",
                                "name_column": "person_name",
                                "fields": {"email": "email"},
                            }
                        ],
                        "relations": [],
                    }
                ),
                encoding="utf-8",
            )
            (mappings_dir / "people_programs.json").write_text(
                json.dumps(
                    {
                        "match": {"source_columns": ["person_name", "program_name", "role"]},
                        "entities": [
                            {
                                "key": "person",
                                "table": "people",
                                "id_template": "people_{slug:person_name}",
                                "name_column": "person_name",
                                "fields": {},
                            },
                            {
                                "key": "program",
                                "table": "programs",
                                "id_template": "programs_{slug:program_name}",
                                "name_column": "program_name",
                                "fields": {},
                            },
                        ],
                        "relations": [
                            {
                                "table": "participations",
                                "id_template": "participations_{ref:person}_{ref:program}",
                                "fields": {
                                    "people_id": "ref:person",
                                    "programs_id": "ref:program",
                                    "role": "role",
                                },
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            args = pkm.argparse.Namespace(
                input=str(source_csv),
                mapping="people_programs",
                mappings_dir=str(mappings_dir),
                apply=True,
                validate_only=False,
            )

            old_data_dir = pkm.DATA_DIR
            try:
                pkm.DATA_DIR = data_dir
                with mock.patch("pkm.run_automation") as mocked_run_automation:
                    exit_code = pkm.command_bulk_import(args)
            finally:
                pkm.DATA_DIR = old_data_dir

            self.assertEqual(exit_code, 0)
            mocked_run_automation.assert_called_once_with()

            _, people_rows = pkm.read_table(data_dir / "people.csv")
            _, program_rows = pkm.read_table(data_dir / "programs.csv")
            _, relation_rows = pkm.read_table(data_dir / "participations.csv")

            self.assertEqual(len(people_rows), 2)
            self.assertEqual(len(program_rows), 1)
            self.assertEqual(len(relation_rows), 2)

            self.assertEqual(people_rows[0]["id"], "people_alex_doe")
            self.assertEqual(program_rows[0]["id"], "programs_career_mentorship")

    def test_bulk_import_apply_updates_existing_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp) / "data"
            data_dir.mkdir(parents=True)
            (data_dir / "people.csv").write_text(
                "id,name,email\npeople_alex_doe,Alex Doe,old@example.com\n",
                encoding="utf-8",
            )

            source_csv = Path(tmp) / "import.csv"
            source_csv.write_text(
                "person_name,email\nAlex Doe,new@example.com\n",
                encoding="utf-8",
            )
            mappings_dir = Path(tmp) / "mappings"
            mappings_dir.mkdir(parents=True)
            (mappings_dir / "people_only.json").write_text(
                json.dumps(
                    {
                        "match": {"source_columns": ["person_name", "email"]},
                        "entities": [
                            {
                                "key": "person",
                                "table": "people",
                                "id_template": "people_{slug:person_name}",
                                "name_column": "person_name",
                                "fields": {"email": "email"},
                            }
                        ],
                        "relations": [],
                    }
                ),
                encoding="utf-8",
            )

            args = pkm.argparse.Namespace(
                input=str(source_csv),
                mapping="people_only",
                mappings_dir=str(mappings_dir),
                apply=True,
                validate_only=False,
            )

            old_data_dir = pkm.DATA_DIR
            try:
                pkm.DATA_DIR = data_dir
                with mock.patch("pkm.run_automation") as mocked_run_automation:
                    exit_code = pkm.command_bulk_import(args)
            finally:
                pkm.DATA_DIR = old_data_dir

            self.assertEqual(exit_code, 0)
            mocked_run_automation.assert_called_once_with()

            _, rows = pkm.read_table(data_dir / "people.csv")
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["email"], "new@example.com")

    def test_bulk_import_validate_only_does_not_process_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp) / "data"
            data_dir.mkdir(parents=True)
            source_csv = Path(tmp) / "import.csv"
            source_csv.write_text(
                "person_name,email\nAlex Doe,alex@example.com\n",
                encoding="utf-8",
            )
            mappings_dir = Path(tmp) / "mappings"
            mappings_dir.mkdir(parents=True)
            (mappings_dir / "people_only.json").write_text(
                json.dumps(
                    {
                        "match": {"source_columns": ["person_name", "email"]},
                        "entities": [
                            {
                                "key": "person",
                                "table": "people",
                                "id_template": "people_{slug:person_name}",
                                "name_column": "person_name",
                                "fields": {"email": "email"},
                            }
                        ],
                        "relations": [],
                    }
                ),
                encoding="utf-8",
            )

            args = pkm.argparse.Namespace(
                input=str(source_csv),
                mapping="people_only",
                mappings_dir=str(mappings_dir),
                apply=False,
                validate_only=True,
            )

            old_data_dir = pkm.DATA_DIR
            try:
                pkm.DATA_DIR = data_dir
                with mock.patch("pkm.run_automation") as mocked_run_automation:
                    exit_code = pkm.command_bulk_import(args)
            finally:
                pkm.DATA_DIR = old_data_dir

            self.assertEqual(exit_code, 0)
            mocked_run_automation.assert_not_called()
            self.assertFalse((data_dir / "people.csv").exists())

    def test_bulk_import_auto_fails_when_no_mapping_matches(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source_csv = Path(tmp) / "import.csv"
            source_csv.write_text(
                "person_name,email\nAlex Doe,alex@example.com\n",
                encoding="utf-8",
            )
            mappings_dir = Path(tmp) / "mappings"
            mappings_dir.mkdir(parents=True)
            (mappings_dir / "program_only.json").write_text(
                json.dumps(
                    {
                        "match": {"source_columns": ["program_name"]},
                        "entities": [
                            {
                                "key": "program",
                                "table": "programs",
                                "id_template": "programs_{slug:program_name}",
                                "name_column": "program_name",
                                "fields": {},
                            }
                        ],
                        "relations": [],
                    }
                ),
                encoding="utf-8",
            )

            args = pkm.argparse.Namespace(
                input=str(source_csv),
                mapping="auto",
                mappings_dir=str(mappings_dir),
                apply=False,
                validate_only=False,
            )

            with self.assertRaisesRegex(ValueError, "no import mapping matched the source columns"):
                pkm.command_bulk_import(args)

    def test_bulk_import_auto_fails_when_multiple_mappings_match(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source_csv = Path(tmp) / "import.csv"
            source_csv.write_text(
                "person_name,email\nAlex Doe,alex@example.com\n",
                encoding="utf-8",
            )
            mappings_dir = Path(tmp) / "mappings"
            mappings_dir.mkdir(parents=True)
            shared_mapping = {
                "entities": [
                    {
                        "key": "person",
                        "table": "people",
                        "id_template": "people_{slug:person_name}",
                        "name_column": "person_name",
                        "fields": {"email": "email"},
                    }
                ],
                "relations": [],
            }
            (mappings_dir / "a.json").write_text(json.dumps(shared_mapping), encoding="utf-8")
            (mappings_dir / "b.json").write_text(json.dumps(shared_mapping), encoding="utf-8")

            args = pkm.argparse.Namespace(
                input=str(source_csv),
                mapping="auto",
                mappings_dir=str(mappings_dir),
                apply=False,
                validate_only=False,
            )

            with self.assertRaisesRegex(ValueError, "multiple import mappings matched the source columns"):
                pkm.command_bulk_import(args)

    def test_bulk_import_auto_fails_on_invalid_mapping_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source_csv = Path(tmp) / "import.csv"
            source_csv.write_text(
                "person_name,email\nAlex Doe,alex@example.com\n",
                encoding="utf-8",
            )
            mappings_dir = Path(tmp) / "mappings"
            mappings_dir.mkdir(parents=True)
            (mappings_dir / "broken.json").write_text("{not-json}", encoding="utf-8")

            args = pkm.argparse.Namespace(
                input=str(source_csv),
                mapping="auto",
                mappings_dir=str(mappings_dir),
                apply=False,
                validate_only=False,
            )

            with self.assertRaisesRegex(ValueError, "invalid mapping file"):
                pkm.command_bulk_import(args)

    def test_bulk_import_auto_supports_required_csv_columns_alias(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source_csv = Path(tmp) / "import.csv"
            source_csv.write_text(
                "person_name,email\nAlex Doe,alex@example.com\n",
                encoding="utf-8",
            )
            mappings_dir = Path(tmp) / "mappings"
            mappings_dir.mkdir(parents=True)
            (mappings_dir / "people_only.json").write_text(
                json.dumps(
                    {
                        "required_csv_columns": ["person_name", "email"],
                        "entities": [
                            {
                                "key": "person",
                                "table": "people",
                                "id_template": "people_{slug:person_name}",
                                "name_column": "person_name",
                                "fields": {"email": "email"},
                            }
                        ],
                        "relations": [],
                    }
                ),
                encoding="utf-8",
            )

            args = pkm.argparse.Namespace(
                input=str(source_csv),
                mapping="auto",
                mappings_dir=str(mappings_dir),
                apply=False,
                validate_only=False,
            )

            with mock.patch("pkm.run_automation") as mocked_run_automation:
                exit_code = pkm.command_bulk_import(args)

            self.assertEqual(exit_code, 0)
            mocked_run_automation.assert_not_called()

    def test_mappings_list_reports_valid_and_invalid_mappings(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            mappings_dir = Path(tmp) / "mappings"
            mappings_dir.mkdir(parents=True)
            (mappings_dir / "valid.json").write_text(
                json.dumps(
                    {
                        "entities": [
                            {
                                "key": "person",
                                "table": "people",
                                "id_template": "people_{slug:person_name}",
                                "name_column": "person_name",
                                "fields": {},
                            }
                        ],
                        "relations": [],
                    }
                ),
                encoding="utf-8",
            )
            (mappings_dir / "invalid.json").write_text("[]", encoding="utf-8")

            args = pkm.argparse.Namespace(mappings_dir=str(mappings_dir))
            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = pkm.command_mappings_list(args)

            rendered = output.getvalue()
            self.assertEqual(exit_code, 0)
            self.assertIn("valid: valid", rendered)
            self.assertIn("invalid: invalid", rendered)

    def test_mappings_validate_requires_input_for_auto(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            mappings_dir = Path(tmp) / "mappings"
            mappings_dir.mkdir(parents=True)
            args = pkm.argparse.Namespace(mapping="auto", input=None, mappings_dir=str(mappings_dir))

            with self.assertRaisesRegex(ValueError, "--mapping auto requires --input"):
                pkm.command_mappings_validate(args)

    def test_mappings_validate_with_input_checks_compatibility(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source_csv = Path(tmp) / "import.csv"
            source_csv.write_text(
                "person_name,email\nAlex Doe,alex@example.com\n",
                encoding="utf-8",
            )
            mappings_dir = Path(tmp) / "mappings"
            mappings_dir.mkdir(parents=True)
            (mappings_dir / "people_only.json").write_text(
                json.dumps(
                    {
                        "entities": [
                            {
                                "key": "person",
                                "table": "people",
                                "id_template": "people_{slug:person_name}",
                                "name_column": "person_name",
                                "fields": {"email": "email"},
                            }
                        ],
                        "relations": [],
                    }
                ),
                encoding="utf-8",
            )

            args = pkm.argparse.Namespace(
                mapping="people_only",
                input=str(source_csv),
                mappings_dir=str(mappings_dir),
            )

            exit_code = pkm.command_mappings_validate(args)
            self.assertEqual(exit_code, 0)

    def test_validate_import_mappings_script_accepts_valid_contract_and_directory(self) -> None:
        validate_module = load_validate_import_mappings_module()

        with tempfile.TemporaryDirectory() as tmp:
            schema_path = Path(tmp) / "import_mapping.contract.schema.json"
            schema_path.write_text(
                json.dumps(
                    {
                        "$schema": "https://json-schema.org/draft/2020-12/schema",
                        "$id": "https://gitpkm.local/schema/import_mapping.contract.schema.json",
                        "title": "GitPKM Import Mapping Contract",
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["entities", "relations"],
                        "properties": {},
                        "$defs": {},
                    }
                ),
                encoding="utf-8",
            )
            mappings_dir = Path(tmp) / "mappings"
            mappings_dir.mkdir(parents=True)

            schema = validate_module.load_json(schema_path)
            validate_module.validate_contract_schema(schema)
            validate_module.validate_mapping_directory(mappings_dir)

    def test_validate_import_mappings_script_rejects_invalid_contract(self) -> None:
        validate_module = load_validate_import_mappings_module()

        with tempfile.TemporaryDirectory() as tmp:
            schema_path = Path(tmp) / "import_mapping.contract.schema.json"
            schema_path.write_text("[]", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "must contain a JSON object"):
                validate_module.load_json(schema_path)


if __name__ == "__main__":
    unittest.main()
