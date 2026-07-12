import unittest

from app.platforms.ats import _match_identity


PROFILE = {
    "identity": {
        "preferred_name": "Alex Doe",
        "legal_name": "Alexander Doe",
        "current_location": "Example City, Country",
        "email": "alex@example.test",
        "phone": "+10000000000",
        "telegram": "@alex_doe",
        "linkedin_url": "https://www.linkedin.com/in/alex-doe/",
    }
}


class AtsIdentityMatchTests(unittest.TestCase):
    def test_matches_contact_fields(self):
        cases = {
            "Email": "alex@example.test",
            "Phone": "+10000000000",
            "Telegram": "@alex_doe",
            "LinkedIn URL": "https://www.linkedin.com/in/alex-doe/",
            "LinkedIn Profile": "https://www.linkedin.com/in/alex-doe/",
            "First Name": "Alex",
            "Last Name": "Doe",
        }
        for label, expected in cases.items():
            with self.subTest(label=label):
                matched = _match_identity(label, PROFILE)
                self.assertIsNotNone(matched)
                self.assertEqual(matched["answer"], expected)
                self.assertEqual(matched["source"], "profile")


if __name__ == "__main__":
    unittest.main()
