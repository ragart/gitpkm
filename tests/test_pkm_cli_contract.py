import unittest

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


if __name__ == "__main__":
    unittest.main()
