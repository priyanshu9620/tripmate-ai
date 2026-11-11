"""Shared HTTP client for live tools: short timeout, identifying User-Agent, never raises to the caller."""

import httpx

from tripmate.config import settings

UA = "tripmate-ai/0.1 (+https://github.com/priyanshu9620/tripmate-ai)"


def get_json(url: str, params: dict | None = None, data: str | None = None) -> dict | list | None:
    try:
        with httpx.Client(timeout=settings.tools_timeout_s, headers={"User-Agent": UA}) as c:
            r = c.post(url, data={"data": data}) if data is not None else c.get(url, params=params)
            r.raise_for_status()
            return r.json()
    except (httpx.HTTPError, ValueError):
        return None


def live() -> bool:
    return settings.tools_mode == "live"
