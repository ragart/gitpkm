import unittest

from scripts.automation import process_issue_form


class ProcessIssueFormTests(unittest.TestCase):
    def test_parse_issue_sections(self) -> None:
        body = """### Dataset
people

### Entity Name
Alex Doe
"""
        sections = process_issue_form.parse_issue_sections(body)
        self.assertEqual(sections["Dataset"], "people")
        self.assertEqual(sections["Entity Name"], "Alex Doe")

    def test_build_entity_command_includes_extra_fields(self) -> None:
        sections = {
            "Dataset": "people",
            "Entity Name": "Alex Doe",
            "Entity ID (Optional)": "people_alex_doe",
            "Dataset Columns (Optional)": "status,rarity",
            "Additional Fields (Optional)": "email=alex@example.com\nstatus=active",
        }
        cmd = process_issue_form.build_entity_command(sections)
        self.assertEqual(cmd[1:5], ["pkm.py", "new", "people", "Alex Doe"])
        self.assertIn("--id", cmd)
        self.assertIn("people_alex_doe", cmd)
        self.assertIn("--columns", cmd)
        self.assertIn("status,rarity", cmd)
        self.assertEqual(cmd.count("--set"), 2)
        self.assertIn("email=alex@example.com", cmd)
        self.assertIn("status=active", cmd)

    def test_build_link_command_includes_optional_fields(self) -> None:
        sections = {
            "Source ID": "people_alex_doe",
            "Target ID": "programs_mentorship",
            "Relationship Table (Optional)": "participations",
            "Relationship ID (Optional)": "participations_people_alex_doe_programs_mentorship",
            "Role (Optional)": "mentor",
            "Additional Fields (Optional)": "status=active",
        }
        cmd = process_issue_form.build_link_command(sections)
        self.assertEqual(cmd[1:5], ["pkm.py", "link", "people_alex_doe", "programs_mentorship"])
        self.assertIn("--table", cmd)
        self.assertIn("participations", cmd)
        self.assertIn("--id", cmd)
        self.assertIn("--role", cmd)
        self.assertIn("mentor", cmd)
        self.assertEqual(cmd.count("--set"), 1)
        self.assertIn("status=active", cmd)

    def test_parse_kv_lines_rejects_invalid_pairs(self) -> None:
        with self.assertRaisesRegex(ValueError, "invalid key=value pair"):
            process_issue_form.parse_kv_lines("not-a-pair")


if __name__ == "__main__":
    unittest.main()