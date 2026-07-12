import unittest

from app.memory import _build_skills_inventory, _normalized_skill_catalog


class SkillCatalogTests(unittest.TestCase):
    def test_catalog_is_personalizable_and_preserves_order(self):
        catalog = [
            {"label": "Playwright", "aliases": ["playwright", "pw"]},
            {"label": "Python", "aliases": ["python"]},
        ]

        inventory = _build_skills_inventory(
            {"tools": ["Playwright"]},
            "Automation with Python",
            catalog=catalog,
        )

        self.assertEqual(inventory, "Playwright; Python")

    def test_invalid_catalog_entries_are_ignored(self):
        normalized = _normalized_skill_catalog(
            [
                {"label": "Postman", "aliases": ["postman"]},
                {"label": "Broken", "aliases": "postman"},
                {"aliases": ["missing label"]},
            ]
        )

        self.assertEqual(normalized, [("Postman", ("postman", "postman"))])


if __name__ == "__main__":
    unittest.main()
