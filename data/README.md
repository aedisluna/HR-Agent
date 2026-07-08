# Profile data

This folder holds **your personal candidate profile**. Real files are **not** committed to git.

## Quick setup

```bash
python scripts/setup_profile_data.py
```

Copies `*.example.*` → local files **only if they do not exist**.

## Files

| Local file (gitignored) | Template (in repo) |
|-------------------------|-------------------|
| `candidate_profile.yaml` | `candidate_profile.example.yaml` |
| `resume.md` | `resume.example.md` |
| `standard_answers.yaml` | `standard_answers.example.yaml` |
| `interview_stories.yaml` | `interview_stories.example.yaml` |
| `missing_data.yaml` | `missing_data.example.yaml` |

Runtime (also gitignored): `applications.db`, `logs/`

## What to edit first

1. **`candidate_profile.yaml`** — identity, projects, **`current_project_details`** (detailed current employer/project)
2. **`resume.md`** — short public summary used in every LLM prompt
3. **`standard_answers.yaml`** — form answers under sections like `current_project`, `hh_ru`
4. **`interview_stories.yaml`** — behavioral stories in RU + EN under `stories:`
5. **`missing_data.yaml`** — facts the agent must confirm before claiming

Current project details live inside **`candidate_profile.yaml`** → `current_project_details`, not in a separate file.

After editing YAML:

```bash
curl -X POST http://127.0.0.1:8001/import-profile
```

## Example templates

The `*.example.*` files use fictional data (Alex Doe, ShopStream, Example Corp) but show the **full structure** the agent understands, including nested `current_project_details` with NDA policy, architecture, and process.

Replace every fictional name, metric and answer with your real information.
