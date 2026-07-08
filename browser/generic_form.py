"""
Safe ATS autofill helper (MVP 3).

Rules:
- Does NOT automate LinkedIn.
- Does NOT submit forms.
- Does NOT bypass CAPTCHA or anti-bot protections.
"""

from playwright.sync_api import sync_playwright

PROFILE = {
    "first name": "Your",
    "last name": "Name",
    "email": "your@email.com",
    "phone": "+0000000000",
    "linkedin": "https://www.linkedin.com/in/your-profile",
    "current company": "Example Corp",
    "current location": "City, Country",
}


def fill_known_fields(url: str, profile: dict | None = None) -> None:
    fields = profile or PROFILE

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=False)
        page = browser.new_page()
        page.goto(url)

        print("Open the application form if needed, then press Enter.")
        input()

        labels = page.locator("label").all()
        for label in labels:
            label_text = label.inner_text().strip().lower()
            for key, value in fields.items():
                if key not in label_text:
                    continue
                try:
                    input_id = label.get_attribute("for")
                    if input_id:
                        page.locator(f"#{input_id}").fill(value)
                        print(f"Filled: {label_text} -> {value}")
                except Exception as error:
                    print(f"Could not fill {label_text}: {error}")

        print("Review the form manually. This script will NOT submit it.")
        input("Press Enter to close the browser.")
        browser.close()


if __name__ == "__main__":
    fill_known_fields("https://example-ats.com/job/application")
