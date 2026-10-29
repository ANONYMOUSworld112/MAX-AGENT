"""Small Firecrawl REST client for LAYA web interactions.

LAYA remains local and deterministic. Browser tasks use Firecrawl's hosted
interactive browser after LAYA routes them to BrowserAgent.
"""

from __future__ import annotations

import json
import os
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import Request, urlopen


class FirecrawlError(RuntimeError):
    """Raised when Firecrawl cannot complete an operation."""


def get_api_key() -> str | None:
    """Read the standard Firecrawl key, config/api_keys.json, then the MAX OS credential vault."""
    key = os.environ.get("FIRECRAWL_API_KEY", "").strip()
    if key:
        return key
    try:
        from memory.config_manager import load_api_keys

        cfg_key = (load_api_keys().get("firecrawl_api_key") or "").strip()
        if cfg_key:
            return cfg_key
    except Exception:
        pass
    try:
        from core.max_infra.vault import Vault

        return (Vault.get_instance().get_secret("firecrawl", "api_key") or "").strip() or None
    except Exception:
        return None


class FirecrawlClient:
    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        opener: Callable[..., Any] = urlopen,
        timeout: float = 45.0,
    ) -> None:
        self.api_key = (api_key or get_api_key() or "").strip()
        self.base_url = (base_url or os.environ.get(
            "FIRECRAWL_API_URL", "https://api.firecrawl.dev/v2"
        )).rstrip("/")
        self._opener = opener
        self.timeout = timeout

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def _request(self, method: str, path: str, payload: dict | None = None) -> dict:
        if not self.configured:
            raise FirecrawlError(
                "Firecrawl is not configured. Set FIRECRAWL_API_KEY or store "
                "firecrawl/api_key in the MAX credential vault."
            )
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        request = Request(
            f"{self.base_url}{path}",
            data=body,
            method=method,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )
        parsed_base = urlsplit(self.base_url)
        if parsed_base.scheme != "https" and not (
            parsed_base.scheme == "http" and parsed_base.hostname in {"localhost", "127.0.0.1"}
        ):
            raise FirecrawlError("FIRECRAWL_API_URL must use HTTPS (HTTP is allowed only for localhost).")
        try:
            with self._opener(request, timeout=self.timeout) as response:
                raw = response.read().decode("utf-8")
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:500]
            raise FirecrawlError(f"Firecrawl HTTP {exc.code}: {detail}") from exc
        except (URLError, TimeoutError, OSError) as exc:
            raise FirecrawlError(f"Firecrawl request failed: {exc}") from exc
        try:
            result = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise FirecrawlError("Firecrawl returned invalid JSON.") from exc
        if not isinstance(result, dict):
            raise FirecrawlError("Firecrawl returned an unexpected response.")
        if result.get("success") is False or result.get("error"):
            raise FirecrawlError(str(result.get("error") or "Firecrawl request failed."))
        return result

    def start_session(self, url: str) -> tuple[str, dict]:
        if not url.strip():
            raise FirecrawlError("A URL is required to start a Firecrawl session.")
        result = self._request("POST", "/scrape", {"url": url.strip(), "formats": ["markdown"]})
        data = result.get("data") if isinstance(result.get("data"), dict) else {}
        metadata = data.get("metadata") if isinstance(data.get("metadata"), dict) else {}
        scrape_id = metadata.get("scrapeId") or metadata.get("scrape_id") or result.get("scrapeId")
        if not scrape_id:
            raise FirecrawlError("Firecrawl opened the page but returned no scrape session ID.")
        return str(scrape_id), result

    def interact(
        self,
        prompt: str,
        *,
        url: str = "",
        scrape_id: str = "",
        code: str = "",
        language: str = "node",
    ) -> tuple[str, dict]:
        if not scrape_id:
            scrape_id, _ = self.start_session(url)
        instruction = {"code": code, "language": language} if code else {"prompt": prompt}
        result = self._request(
            "POST", f"/scrape/{quote(scrape_id, safe='')}/interact", instruction
        )
        return scrape_id, result

    def stop_session(self, scrape_id: str) -> dict:
        if not scrape_id.strip():
            raise FirecrawlError("A scrape session ID is required to stop the session.")
        return self._request(
            "DELETE", f"/scrape/{quote(scrape_id.strip(), safe='')}/interact"
        )


def response_text(response: dict) -> str:
    """Return the useful, bounded user-facing part of an API response."""
    value = response.get("output") or response.get("result") or response.get("data") or response
    if isinstance(value, str):
        return value[:6000]
    return json.dumps(value, ensure_ascii=False)[:6000]


def click_once(url: str, target: str, *, api_key: str | None = None) -> str:
    """Open a page, click one requested target, verify the resulting page, close."""
    client = FirecrawlClient(api_key=api_key)
    scrape_id, _ = client.start_session(url)
    try:
        _, response = client.interact(
            f"Click only the page element matching this target: {target}. "
            "Do not submit forms, make purchases, or change account settings. "
            "After the click, report the current page URL and title.",
            scrape_id=scrape_id,
        )
        return response_text(response)
    finally:
        client.stop_session(scrape_id)
