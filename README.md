# erpclasp

Python **library** and **CLI** to **pull**, **push**, **diff**, **status**, and **watch** [ERPNext](https://erpnext.com/) **Server Scripts** on [Frappe Cloud](https://frappecloud.com/) (or any Frappe site) via the REST API—similar in spirit to [clasp](https://github.com/google/clasp) for Apps Script.

## Requirements

- Python 3.11+
- Frappe user with **API Key** and **API Secret** (User → API Access → Generate Keys)
- Permission on the **Server Script** DocType

## Install

```bash
pip install erpclasp
```

[PyPI project page](https://pypi.org/project/erpclasp/). For an isolated CLI: [`pipx install erpclasp`](https://pypa.github.io/pipx/).

**Development** (from a clone):

```bash
pip install -e ".[dev]"
```

Or: `pip install -r requirements.txt` then `pip install -e .`

### Library usage

```python
from pathlib import Path

from erpclasp import FrappeClient, load_app_config, pull_scripts, push_scripts

project = Path("/path/to/your/project")
cfg = load_app_config(project)
client = FrappeClient(cfg)
result = pull_scripts(client, project)
```

Public exports are listed in `erpclasp.__all__`; submodules (e.g. `erpclasp.api`) work too.

Each developer needs a **`.env`** with `BASE_URL`, `API_KEY`, `API_SECRET`—never commit it. For Git: you can commit `scripts/*.py`, `.erpclasp-map.json`, `.env.example`; keep `.env` and secrets out of version control (use `.gitignore`).

## Quick start

From your **project root** (where `.env` and project files live):

1. **`.env`** — copy [`.env.example`](.env.example) and fill in (or use `erpclasp login`):

   ```env
   BASE_URL=https://your-site.frappe.cloud
   API_KEY=…
   API_SECRET=…
   ```

   URL uses `https://`, no trailing slash. Legacy `ERPCLASP_*` env names still work.

2. **`erpclasp login`** — verifies the site, writes `.env`, adds a marker **`.erpclasp.json`** (no secrets). Options: `--skip-ping`; on Windows, `--plain-secret-prompt` or `--api-secret-file` if paste fails in the hidden prompt.

3. **`erpclasp init`** (optional) — creates `scripts/` and `.erpclasp-map.json` if missing.

4. **`erpclasp pull`** — downloads Server Scripts into `scripts/`, updates the map. Flags: `--files` / `-f` (log while pulling), `--backup` (save copies under `scripts/.backups/` before overwrite).

5. **Edit and push**

   ```bash
   erpclasp push
   erpclasp push my_script.py      # basename only
   erpclasp push --dry-run
   ```

   New local file ↔ ERP name:

   ```bash
   erpclasp add my_script.py "Exact Server Script Name"
   erpclasp add my_script.py --name "…"   # non-interactive
   ```

   Use **`--create`** to create an empty `.py`. Local filename and ERPNext script name differ (spaces allowed in ERP names).

6. **`erpclasp diff`** / **`erpclasp status`** — compare local vs server; `status` defaults to out-of-date files only; `status --all` lists everything. Exit code **1** when there are diffs/errors (good for CI).

7. **`erpclasp watch`** — auto-push on save (debounced).

8. **`erpclasp list`** — files in `scripts/` and mapped ERP names.

## Project layout

```
your-project/
├── .env
├── .erpclasp.json       # marker from login (no API keys)
├── .erpclasp-map.json   # filename.py → ERPNext script name
├── scripts/
│   └── .backups/        # optional (pull --backup)
└── …
```

Example map entry:

```json
{
  "sales_order_validate.py": "Sales Order Validate Script"
}
```

The map is updated on **`pull`**; edit by hand if you rename files.

## Authentication

Frappe-style header:

```http
Authorization: token <api_key>:<api_secret>
```

Credentials load from **`project/.env`** (project root comes from `.erpclasp.json`, `.erpclasp-map.json`, or walking up from the cwd).

## API behavior (library)

- **List**: `GET /api/resource/Server Script` (paginated)
- **Read**: `GET /api/resource/Server Script/{name}`
- **Update**: `PUT` with `{"script": "…"}`; on rejection, client retries with a **full document** from GET + updated `script`

## Troubleshooting

| Issue | What to try |
| ----- | ----------- |
| No project / missing credentials | `erpclasp init`, `erpclasp login`; ensure `.env` has the three variables. |
| Login or ping fails | URL (`https`), firewall, keys; `erpclasp login --skip-ping`. |
| `401` / `403` | Keys or Server Script permission. |
| `404` on push | Wrong mapping or script removed on site—`pull` or fix `.erpclasp-map.json`. |
| No mapping for `foo.py` | `erpclasp add` or `pull`. |

Use `erpclasp -v` for debug logs.

## Publishing to PyPI (maintainers)

Package: **[pypi.org/project/erpclasp](https://pypi.org/project/erpclasp/)**. New release:

1. Bump version in [`pyproject.toml`](pyproject.toml) and [`erpclasp/__init__.py`](erpclasp/__init__.py).
2. `python -m build` then `twine check dist/*` and `twine upload dist/*` (PyPI token as password for user `__token__`). Optional: TestPyPI first with `twine upload --repository testpypi dist/*`.
3. Set `[project.urls]` in `pyproject.toml` to the real repo/homepage.

## License

MIT — see [LICENSE](LICENSE).
