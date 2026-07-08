# Publishing to GitHub

## Before the first public push

1. Ensure personal files are **not** tracked:
   ```bash
   git status
   ```
   You should see `data/*.example.*` staged, and **no** `data/candidate_profile.yaml`, `data/resume.md`, etc.

2. Personal files must stay local only (listed in `.gitignore`).

## Important: git history

If the repository was already pushed to GitHub **with real profile data** in `data/`,
that data remains in git history even after deleting the files.

**Options:**

### A. New clean repository (simplest)

1. Create a new empty repo on GitHub
2. Push only the sanitized current state:
   ```bash
   git remote set-url origin git@github.com:YOU/HR-Agent.git
   git push -u origin main --force
   ```
   Only do this if you accept rewriting remote history, or use a **new** repo URL.

### B. Rewrite history (keep same repo)

Install [git-filter-repo](https://github.com/newren/git-filter-repo), then from a fresh clone:

```bash
git filter-repo --force \
  --path data/candidate_profile.yaml \
  --path data/resume.md \
  --path data/standard_answers.yaml \
  --path data/interview_stories.yaml \
  --path data/missing_data.yaml \
  --invert-paths
```

Then force-push:

```bash
git push origin main --force
```

After rewrite, verify on GitHub that old commits no longer contain your name, salary, or project details.

## Recommended commit for open source

```bash
git add .
git status   # double-check no personal data/
git commit -m "Prepare repo for public release with profile templates"
git push
```

## What stays private

Never commit:

- `data/candidate_profile.yaml`
- `data/resume.md`
- `data/standard_answers.yaml`
- `data/interview_stories.yaml`
- `data/missing_data.yaml`
- `data/applications.db`
- `logs/`
- `.env`
