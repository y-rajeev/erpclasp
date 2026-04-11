# erpclasp

Python **library** and **CLI** to **pull**, **push**, **diff**, **status**, and **watch** [ERPNext](https://erpnext.com/) **Server Scripts** on [Frappe Cloud](https://frappecloud.com/) (or any Frappe site) using the REST API—similar in spirit to [clasp](https://github.com/google/clasp) for Apps Script.

## Requirements

- Python 3.11+
- A Frappe user with a valid **API Key** and **API Secret** (User → API Access → Generate Keys)
- Permission to read/update the **Server Script** DocType

## Install

From the repository root:

```bash
pip install -e .
```

Or with `requirements.txt`:

```bash
pip install -r requirements.txt
pip install -e .
```

The `erpclasp` command is installed on your PATH.

### Python library

Use the same logic from code (automation, tests, notebooks). Import from the top-level package; public names are listed in `erpclasp.__all__`.

```python
from pathlib import Path

from erpclasp import FrappeClient, load_app_config, pull_scripts, push_scripts

project = Path("/path/to/your/project")  # contains .env and/or .erpclasp.json
cfg = load_app_config(project)
client = FrappeClient(cfg)

result = pull_scripts(client, project)
print("pulled:", result.pulled, "errors:", result.errors)

# push_scripts(client, project, only_filenames={"my_script.py"})
```

You can still import submodules directly (e.g. `from erpclasp.api import FrappeClient`) if you prefer; the package root re-exports the stable surface.

### Sharing the tool with others

Anyone with **Python 3.11+** can use the same CLI:

| How | Command / notes |
| --- | --- |
| **From a cloned repo** | `git clone … && cd erpclasp && python -m venv .venv` then activate venv and run `pip install -e .` |
| **Install from Git without cloning first** | `pip install "git+https://github.com/YOUR_ORG/erpclasp.git#egg=erpclasp"` (adjust URL and branch/tag) |
| **Isolated global CLI (recommended for “just the command”)** | [pipx](https://pypa.github.io/pipx/): `pipx install .` from the repo root, or after you publish: `pipx install erpclasp` |
| **Publish to PyPI** (optional) | Build with `python -m build` and upload; then others run `pip install erpclasp` from any machine |

**What each developer needs**

- Their own **`.env`** with `BASE_URL`, `API_KEY`, `API_SECRET` (or keys for a bot user your team agrees on). Never commit `.env`.
- A **project folder** for scripts: either clone your team repo that contains `scripts/` and `.erpclasp-map.json`, or start fresh with `erpclasp init` + `erpclasp login` + `erpclasp pull`.

**What you can commit to Git** (for the team): `scripts/*.py`, `.erpclasp-map.json`, `.env.example`, and this tool’s source. **Do not** commit `.env` or `.erpclasp.json` if they contain secrets (your `.gitignore` already ignores typical cases).

## Quick start

Run these from the directory you want to use as the project root (where `.env` and project files live).

1. **Configure credentials** — in your project directory, create a **`.env`** file (you can copy **`.env.example`**; keep `.env` secret — it is gitignored if you use the provided `.gitignore`):

   ```env
   BASE_URL=https://your-site.frappe.cloud
   API_KEY=your_api_key_here
   API_SECRET=your_api_secret_here
   ```

   The site URL should include `https://` and no trailing slash. Legacy names `ERPCLASP_BASE_URL`, `ERPCLASP_API_KEY`, and `ERPCLASP_API_SECRET` still work if you already use them.

2. **Log in** — verifies the server, **updates `.env`** with `BASE_URL`, `API_KEY`, and `API_SECRET` (your **single source of truth**), and writes a small **`.erpclasp.json` marker** (no secrets in that file):

   ```bash
   erpclasp login
   ```

   No prompts if all three variables are set. You can override any value with `--base-url`, `--api-key`, or `--api-secret`.

   **`pull` / `push` / `diff` / `status` / `watch`** read credentials from **`.env`** first. Older projects may still have keys only in `.erpclasp.json`; that still works until you run `login` again (which migrates toward `.env`-only).

   - **`erpclasp login --skip-ping`** — if `frappe.ping` is blocked but credentials are valid.
   - **Windows / interactive only:** hidden secret prompts often block paste — use **`--plain-secret-prompt`**, **`--api-secret-file path.txt`**, or rely on **`API_SECRET` in `.env`** (recommended).

3. **Initialize** project files (optional but convenient):

   ```bash
   erpclasp init
   ```

   Creates `scripts/` and an empty `.erpclasp-map.json` if missing.

4. **Pull** all Server Scripts from the site:

   ```bash
   erpclasp pull
   ```

   By default you get a summary plus **each filename** under `scripts/`. Use **`erpclasp pull --files`** (`-f`) to print ERP script name → file **while** downloading. **`erpclasp pull --backup`** logs backup paths when overwriting.

   - Fetches `/api/resource/Server Script` (paginated)
   - Writes one `.py` file per script under `scripts/`
   - Maintains `.erpclasp-map.json`: **local filename → ERPNext script name**

5. **Edit** files under `scripts/`, then **push** to ERPNext:

   ```bash
   erpclasp push                    # all mapped .py files
   erpclasp push test.py            # only scripts/test.py (basename)
   erpclasp push --dry-run          # show what would be pushed
   ```

   **New file** (the Server Script must already exist on ERPNext, or create it there first):

   ```bash
   erpclasp add my_script.py "Exact Server Script Name"   # path + ERP name in one go
   erpclasp add my_script.py                              # terminal prompts for the ERP name
   erpclasp add my_script.py --name "Exact Server Script Name"   # non-interactive (CI/scripts)
   erpclasp push my_script.py
   ```

   The **file path** (`my_script.py` → `scripts/my_script.py`) and **Server Script name** in ERPNext are two different things (names can include spaces). **`erpclasp pull`** fills the map automatically for scripts that already exist on the site—you only need **`add`** when linking a new local file to an existing ERP name. Use **`--create`** if the `.py` file should be created empty.

6. **Diff** local vs server:

   ```bash
   erpclasp diff
   erpclasp diff my_script.py
   ```

   Exits with status **1** if there are differences or errors (useful in CI).

7. **Status** — what needs a **push** (or fix): by default only **modified** (local ≠ server) and **error** rows; if everything matches, prints a short “nothing to push” line. **Unmapped** `.py` files (not in `.erpclasp-map.json`) are listed separately when present.

   ```bash
   erpclasp status
   erpclasp status --all   # every mapped file, including clean (full audit)
   ```

   Exits **1** if any mapped script is modified or errored; **0** when all mapped files are clean (unmapped files alone do not fail the exit code).

8. **Watch** for saves and auto-push (debounced):

   ```bash
   erpclasp watch
   ```

**List what’s in `scripts/`** (files + mapped ERP names):

```bash
erpclasp list
```

## Project layout

```
your-project/
├── .env                 # BASE_URL, API_KEY, API_SECRET — single source of truth (do not commit)
├── .erpclasp.json       # small marker from `login` (no secrets; do not commit)
├── .erpclasp-map.json   # "filename.py" -> "ERPNext Server Script Name"
├── scripts/             # local Python files
│   └── .backups/        # optional; created when using pull --backup
└── ...
```

### Mapping file

ERPNext script **names** can contain spaces and arbitrary casing; local filenames must be portable. The map ties them together, for example:

```json
{
  "sales_order_validate.py": "Sales Order Validate Script"
}
```

The map is **updated automatically** on `pull`. You can edit it by hand if you rename files—keep keys aligned with files in `scripts/`.

### Pull backups

To copy existing files to `scripts/.backups/` before overwriting:

```bash
erpclasp pull --backup
```

## Authentication

Requests use the standard Frappe header:

```http
Authorization: token <api_key>:<api_secret>
Content-Type: application/json
```

On each run, `erpclasp` loads **`project/.env`** (project root is detected from `.erpclasp.json`, `.erpclasp-map.json`, or your working tree). **Secrets live only in `.env`.** **`erpclasp login`** checks the server, writes those three variables into `.env`, and writes **`.erpclasp.json`** as a marker without API keys. Change keys by editing `.env` (or re-run `login`); other commands pick up changes on the next invocation.

## API behavior

- **List**: `GET /api/resource/Server Script` with pagination (`limit_page_length`, `limit_start`)
- **Read**: `GET /api/resource/Server Script/{name}`
- **Update**: `PUT` with `{"script": "..."}`; if the server rejects a partial body, the client **retries with a full document** merged from GET + updated `script` field

## Troubleshooting

| Issue | What to try |
| ----- | ----------- |
| No project found / missing credentials | Run `erpclasp init` and `erpclasp login` from the project root. Parent directories are searched for `.erpclasp.json` or `.erpclasp-map.json`. Ensure `.env` contains `BASE_URL`, `API_KEY`, and `API_SECRET`. |
| Login / ping fails | Check URL (https), firewall, and API keys. Try `erpclasp login --skip-ping`. |
| `401` / `403` | Invalid key/secret or user lacks permission on Server Script. |
| `404` on push | Script was deleted on server or mapping name is wrong—run `pull` again or fix `.erpclasp-map.json`. |
| `No mapping for foo.py` | Add a line in `.erpclasp-map.json` or run `pull` so filenames are registered. |
| Network timeouts | Default timeouts are set on every request; unstable links may need retries (built-in) or a stable connection. |

Use `erpclasp -v` / `--verbose` for debug logs.

## Publishing to PyPI (`pip install erpclasp`)

After you [create a PyPI account](https://pypi.org/account/register/) and (recommended) [enable 2FA](https://pypi.org/help/#twofa), create an **API token** at [pypi.org → Account settings → API tokens](https://pypi.org/manage/account/token/) with scope “Entire account” (or per-project once the name exists).

1. **Install build tools** (once):

   ```bash
   pip install build twine
   ```

   Or: `pip install -e ".[dev]"` — dev extras include `build` and `twine`.

2. **Bump the version** in [`pyproject.toml`](pyproject.toml) (`[project] version = "0.1.0"`) and in [`erpclasp/__init__.py`](erpclasp/__init__.py) (`__version__`) so each upload is unique.

3. **Build** the wheel and sdist from the repo root:

   ```bash
   python -m build
   ```

   This creates `dist/erpclasp-0.1.0-py3-none-any.whl` and `dist/erpclasp-0.1.0.tar.gz`.

4. **Check** the artifacts:

   ```bash
   twine check dist/*
   ```

5. **Upload** (use a **test** run first against TestPyPI):

   ```bash
   twine upload --repository testpypi dist/*
   pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ "erpclasp==0.1.0"
   ```

   Then upload to the real index:

   ```bash
   twine upload dist/*
   ```

   Twine will ask for credentials: use `__token__` as the username and your **API token** (including the `pypi-` prefix) as the password, or configure [`~/.pypirc`](https://twine.readthedocs.io/en/stable/#configuration).

6. **Update** `[project.urls]` in `pyproject.toml` to your real GitHub (or other) URLs before publishing.

**Note:** The project name `erpclasp` must be **available** on PyPI. If it is taken, change `name = "erpclasp"` in `pyproject.toml` to something unique (e.g. `erpnext-server-scripts-cli`).

## Development

```bash
pip install -e ".[dev]"
```

## License

MIT — see [LICENSE](LICENSE).
