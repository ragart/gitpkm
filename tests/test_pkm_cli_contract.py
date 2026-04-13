import unittest
import tempfile
from pathlib import Path
from unittest import mock

import pkm


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


if __name__ == "__main__":
    unittest.main()
