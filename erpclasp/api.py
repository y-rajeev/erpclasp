"""Frappe REST API client for Server Script documents."""

from __future__ import annotations

import json
import logging
from typing import Any
from urllib.parse import quote

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from erpclasp.config import AppConfig

logger = logging.getLogger(__name__)

SERVER_SCRIPT_DOCTYPE = "Server Script"
DEFAULT_TIMEOUT = (10, 60)  # connect, read
DEFAULT_PAGE_SIZE = 1000
DEFAULT_RETRIES = 3
DEFAULT_BACKOFF = 0.5


class FrappeAPIError(Exception):
    """Raised for API errors with optional HTTP status."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


def _resource_base_path() -> str:
    encoded = quote(SERVER_SCRIPT_DOCTYPE, safe="")
    return f"/api/resource/{encoded}"


def _doc_path(name: str) -> str:
    base = _resource_base_path()
    return f"{base}/{quote(name, safe='')}"


def _build_session(config: AppConfig) -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "Authorization": f"token {config.api_key}:{config.api_secret}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
    )
    retry = Retry(
        total=DEFAULT_RETRIES,
        connect=DEFAULT_RETRIES,
        read=DEFAULT_RETRIES,
        status_forcelist=(502, 503, 504),
        backoff_factor=DEFAULT_BACKOFF,
        allowed_methods=frozenset(["GET", "PUT", "POST"]),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def _check_response(resp: requests.Response, context: str) -> None:
    if resp.status_code < 400:
        return
    try:
        detail = json.dumps(resp.json())[:500]
    except Exception:
        detail = (resp.text or "")[:500]
    raise FrappeAPIError(
        f"{context} failed ({resp.status_code}): {detail}",
        status_code=resp.status_code,
    )


class FrappeClient:
    """Thin wrapper around Server Script REST endpoints."""

    def __init__(self, config: AppConfig, timeout: tuple[float, float] | float = DEFAULT_TIMEOUT) -> None:
        self._config = config
        self._timeout = timeout
        self._session = _build_session(config)

    @property
    def base_url(self) -> str:
        return self._config.base_url

    def ping(self) -> None:
        """Verify base URL and credentials (``frappe.ping``)."""
        url = f"{self._config.base_url}/api/method/frappe.ping"
        logger.debug("GET %s", url)
        resp = self._session.get(url, timeout=self._timeout)
        _check_response(resp, "Ping (frappe.ping)")

    def list_server_script_names(self) -> list[str]:
        """Paginate through all Server Script names."""
        names: list[str] = []
        limit_start = 0
        while True:
            params: dict[str, str | int] = {
                "fields": json.dumps(["name"]),
                "limit_page_length": DEFAULT_PAGE_SIZE,
                "limit_start": limit_start,
            }
            url = f"{self._config.base_url}{_resource_base_path()}"
            logger.debug("GET %s params=%s", url, params)
            resp = self._session.get(url, params=params, timeout=self._timeout)
            _check_response(resp, "List Server Script")
            payload = resp.json()
            batch = payload.get("data") or []
            if not batch:
                break
            for row in batch:
                if isinstance(row, dict) and "name" in row:
                    names.append(str(row["name"]))
            if len(batch) < DEFAULT_PAGE_SIZE:
                break
            limit_start += DEFAULT_PAGE_SIZE
        return names

    def get_server_script(self, name: str) -> dict[str, Any]:
        """Return full document JSON (``data`` object)."""
        url = f"{self._config.base_url}{_doc_path(name)}"
        logger.debug("GET %s", url)
        resp = self._session.get(url, timeout=self._timeout)
        _check_response(resp, f"Get Server Script {name!r}")
        payload = resp.json()
        data = payload.get("data")
        if not isinstance(data, dict):
            raise FrappeAPIError(f"Unexpected response for {name!r}: missing data object")
        return data

    def get_script_field(self, name: str) -> str:
        doc = self.get_server_script(name)
        raw = doc.get("script")
        if raw is None:
            return ""
        return str(raw)

    def update_server_script(self, name: str, script_body: str) -> None:
        """Update script code; retry with full-document PUT if partial update is rejected."""
        url = f"{self._config.base_url}{_doc_path(name)}"
        partial = {"script": script_body}
        logger.debug("PUT %s (partial)", url)
        resp = self._session.put(url, json=partial, timeout=self._timeout)
        if resp.status_code < 400:
            return
        if resp.status_code in (400, 417) or resp.status_code == 500:
            logger.debug("Partial PUT failed (%s); retrying with merged full document", resp.status_code)
            doc = self.get_server_script(name)
            doc["script"] = script_body
            resp2 = self._session.put(url, json=doc, timeout=self._timeout)
            _check_response(resp2, f"Update Server Script {name!r} (full doc)")
            return
        _check_response(resp, f"Update Server Script {name!r}")
