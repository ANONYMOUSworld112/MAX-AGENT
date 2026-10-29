"""Agent 24: Browser Agent.

Controls browser navigation, tab management, DOM inspection, element clicks,
and form interactions using either Firecrawl cloud sessions or local Playwright/OS sessions.
Operates at Permission Tier 1 (Safe Write).
"""

from __future__ import annotations

import logging
from typing import Any, Dict
from agents.base import BaseAgent, AgentInput, AgentOutput
from core.firecrawl_client import FirecrawlClient, FirecrawlError, response_text

logger = logging.getLogger("max.agents.browser")


class BrowserAgent(BaseAgent):
    name = "BrowserAgent"
    description = "Controls web browser tabs, navigation, interactions, and DOM inspection."
    permission_tier = 1  # Safe Write

    def _execute(self, input_data: AgentInput) -> AgentOutput:
        desc = input_data.task_description
        logger.info("BrowserAgent executing: %s", desc)

        action = input_data.parameters.get("action", "navigate")
        url = input_data.parameters.get("url", "https://google.com")
        target = (
            input_data.parameters.get("target")
            or input_data.parameters.get("description")
            or input_data.parameters.get("text", "")
        )
        browser = input_data.parameters.get("browser")
        provider = input_data.parameters.get("provider", "auto")

        if action in {"click", "smart_click"} and not target and not input_data.parameters.get("selector"):
            return AgentOutput(
                success=False,
                error="A target or selector is required for browser clicking.",
                artifacts={"action": action},
            )

        client = FirecrawlClient()
        if provider == "firecrawl" and not client.configured:
            return AgentOutput(
                success=False,
                error="Firecrawl provider requested but API key is not configured.",
                artifacts={"action": action, "provider": "firecrawl"},
            )
        if client.configured and provider != "local":
            scrape_id = str(input_data.parameters.get("scrape_id", ""))
            try:
                if action == "navigate":
                    if scrape_id:
                        scrape_id, response = client.interact(
                            f"Navigate to {url} and report the resulting page title and URL.",
                            scrape_id=scrape_id,
                        )
                        result = response_text(response)
                    else:
                        scrape_id, _ = client.start_session(str(url))
                        result = f"Firecrawl browser opened {url}."
                elif action in {"click", "smart_click"}:
                    if not target:
                        raise FirecrawlError("A target is required for browser clicking.")
                    prompt = (
                        f"Click only the page element matching this target: {target}. "
                        "Do not submit forms, make purchases, or change account settings. "
                        "Report the current page URL and title after the click."
                    )
                    scrape_id, response = client.interact(prompt, url=str(url) if not scrape_id else "", scrape_id=scrape_id)
                    result = response_text(response)
                elif action in {"interact", "type", "fill_form", "scroll", "get_text"}:
                    prompt = str(input_data.parameters.get("prompt") or desc)
                    scrape_id, response = client.interact(prompt, url=str(url) if not scrape_id else "", scrape_id=scrape_id)
                    result = response_text(response)
                elif action == "close":
                    result = response_text(client.stop_session(scrape_id))
                else:
                    raise FirecrawlError(f"Unsupported browser action: {action}")

                artifacts: Dict[str, Any] = {"action": action, "url": url, "provider": "firecrawl"}
                if scrape_id:
                    artifacts["scrape_id"] = scrape_id
                return AgentOutput(success=True, result=result, artifacts=artifacts)
            except FirecrawlError as exc:
                return AgentOutput(success=False, result=f"Firecrawl browser action failed: {exc}", artifacts={"action": action})

        # Local browser controller integration via actions/browser_control.py
        logger.info("Using local Playwright / OS browser controller for action '%s'", action)
        from actions.browser_control import browser_control

        action_map = {
            "navigate": "go_to",
            "open": "go_to",
            "go_to": "go_to",
            "click": "click",
            "smart_click": "smart_click",
            "type": "type",
            "search": "search",
            "scroll": "scroll",
            "get_text": "get_text",
            "screenshot": "screenshot",
            "close": "close",
            "list_browsers": "list_browsers",
        }
        mapped_action = action_map.get(action.lower(), action)
        control_params = {
            "action": mapped_action,
            "url": url,
            "browser": browser,
            "text": target,
            "description": target,
            "selector": input_data.parameters.get("selector"),
            "query": input_data.parameters.get("query", target),
            "direction": input_data.parameters.get("direction", "down"),
            "amount": input_data.parameters.get("amount", 500),
            "path": input_data.parameters.get("path"),
        }

        try:
            if input_data.parameters.get("dry_run") or input_data.parameters.get("simulate"):
                return AgentOutput(
                    success=True,
                    result=f"BrowserAgent (Dry Run): Verified {mapped_action} target for {url}.",
                    artifacts={"action": mapped_action, "url": url, "provider": "local_dry_run"},
                )

            res = browser_control(control_params)
            is_err = any(str(res).startswith(p) for p in [
                "Could not start browser session:",
                "Browser error",
                "Click error:",
                "Unknown browser action:",
            ])
            return AgentOutput(
                success=not is_err,
                result=str(res),
                error=str(res) if is_err else None,
                artifacts={
                    "action": mapped_action,
                    "url": url,
                    "provider": "local_playwright",
                    "raw_output": str(res),
                },
            )
        except Exception as exc:
            logger.error("BrowserAgent local execution failed: %s", exc)
            return AgentOutput(
                success=False,
                error=f"Local browser automation error: {exc}",
                artifacts={"action": mapped_action, "url": url},
            )
