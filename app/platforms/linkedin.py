"""LinkedIn page helpers.

DOM extraction happens in the browser extension. This module keeps
server-side platform metadata and future HTML parsing hooks.
"""

LINKEDIN_SAFE_MODE = True

PLATFORM_NAME = "linkedin"

SUBMIT_AUTOMATION_ALLOWED = False

KNOWN_EXTERNAL_REDIRECTS = [
    "greenhouse.io",
    "lever.co",
    "ashbyhq.com",
    "workday.com",
    "myworkdayjobs.com",
    "smartrecruiters.com",
]
