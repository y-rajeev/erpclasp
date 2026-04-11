"""Load credentials and optional project marker ``.erpclasp.json`` (no secrets in JSON)."""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv, set_key
from pydantic import BaseModel, Field, ValidationError, field_validator

from erpclasp.utils import CONFIG_FILENAME

# Preferred names in ``.env`` (single source of truth for secrets).
ENV_KEYS_BASE_URL: tuple[str, ...] = ("BASE_URL", "ERPCLASP_BASE_URL")
ENV_KEYS_API_KEY: tuple[str, ...] = ("API_KEY", "ERPCLASP_API_KEY")
ENV_KEYS_API_SECRET: tuple[str, ...] = ("API_SECRET", "ERPCLASP_API_SECRET")

# Marker written to ``.erpclasp.json`` — never contains API keys.
MARKER_CREDENTIALS_ENV = "environment"


def credential_from_flag_or_env(flag: str | None, *env_names: str) -> str | None:
    """CLI flag wins; otherwise first non-empty value among ``env_names`` in ``os.environ``."""
    if flag is not None and str(flag).strip():
        return str(flag).strip()
    for name in env_names:
        raw = os.environ.get(name)
        if raw is not None and str(raw).strip():
            return str(raw).strip()
    return None


class AppConfig(BaseModel):
    """API client configuration (from ``.env`` or legacy ``.erpclasp.json``)."""

    base_url: str = Field(..., description="Frappe site base URL, no trailing path")
    api_key: str = Field(..., min_length=1)
    api_secret: str = Field(..., min_length=1)

    @field_validator("base_url")
    @classmethod
    def normalize_base_url(cls, v: str) -> str:
        raw = v.strip().rstrip("/")
        if not raw:
            raise ValueError("base_url is empty")
        parsed = urlparse(raw)
        if parsed.scheme not in ("http", "https"):
            raise ValueError("base_url must start with http:// or https://")
        if not parsed.netloc:
            raise ValueError("base_url must include a hostname")
        return raw


def config_path(project_root: Path) -> Path:
    return project_root / CONFIG_FILENAME


def _load_dotenv_for_project(project_root: Path) -> None:
    """Load ``project_root/.env`` into ``os.environ``."""
    path = project_root / ".env"
    if path.is_file():
        load_dotenv(path)


def load_app_config(project_root: Path) -> AppConfig:
    """Load credentials from ``.env``, or fall back to legacy ``.erpclasp.json`` with keys."""
    _load_dotenv_for_project(project_root)

    u = credential_from_flag_or_env(None, *ENV_KEYS_BASE_URL)
    k = credential_from_flag_or_env(None, *ENV_KEYS_API_KEY)
    s = credential_from_flag_or_env(None, *ENV_KEYS_API_SECRET)
    if u and k and s:
        return AppConfig(base_url=u, api_key=k, api_secret=s)

    path = config_path(project_root)
    if not path.is_file():
        raise FileNotFoundError(
            f"Missing credentials. Add BASE_URL, API_KEY, and API_SECRET to {project_root / '.env'} "
            "or run `erpclasp login`."
        )

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {path}: {exc}") from exc

    if raw.get("credentials") == MARKER_CREDENTIALS_ENV and "base_url" not in raw:
        raise ValueError(
            "Credentials are stored in `.env` only, but BASE_URL / API_KEY / API_SECRET "
            f"are missing or empty. Fix {project_root / '.env'} or run `erpclasp login`."
        )

    try:
        return AppConfig.model_validate(raw)
    except ValidationError as exc:
        raise ValueError(
            f"Invalid configuration in {path}. Prefer credentials in `.env`; run `erpclasp login` to refresh.\n{exc}"
        ) from exc


def persist_credentials_to_env(project_root: Path, cfg: AppConfig) -> None:
    """Write ``BASE_URL``, ``API_KEY``, ``API_SECRET`` to ``project_root/.env`` (single source of truth)."""
    env_path = project_root / ".env"
    dotenv_path = str(env_path)
    set_key(dotenv_path, "BASE_URL", cfg.base_url, quote_mode="always")
    set_key(dotenv_path, "API_KEY", cfg.api_key, quote_mode="always")
    set_key(dotenv_path, "API_SECRET", cfg.api_secret, quote_mode="always")
    if os.name != "nt" and env_path.is_file():
        env_path.chmod(stat.S_IRUSR | stat.S_IWUSR)


def write_project_marker(project_root: Path) -> None:
    """Write ``.erpclasp.json`` marker (no secrets)."""
    path = config_path(project_root)
    data = {
        "erpclasp_version": 1,
        "credentials": MARKER_CREDENTIALS_ENV,
    }
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
