"""
Collector API client for user dashboard data.
"""

from __future__ import annotations

from typing import Any

import httpx
from telegram import User

from bot.core.exceptions import CollectorAPIError
from bot.core.logging import get_logger

logger = get_logger(__name__)


class CollectorApiClient:
    """HTTP client for Collector API."""

    def __init__(self, base_url: str | None, api_key: str | None, timeout: float = 10.0) -> None:
        if not base_url:
            raise CollectorAPIError("SITE_API_BASE_URL is not configured")
        if not api_key:
            raise CollectorAPIError("SITE_API_KEY is not configured")
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._timeout = timeout

    async def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{self._base_url}{path}"
        headers = {"X-API-Key": self._api_key}

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text
            logger.error("Collector API error %s: %s", exc.response.status_code, detail)
            raise CollectorAPIError(f"Collector API error: {exc.response.status_code}") from exc
        except httpx.RequestError as exc:
            logger.error("Collector API request failed: %s", exc)
            raise CollectorAPIError("Collector API request failed") from exc

        try:
            data = response.json()
        except ValueError as exc:
            raise CollectorAPIError("Collector API returned invalid JSON") from exc

        if not isinstance(data, dict):
            raise CollectorAPIError("Collector API returned unexpected payload")

        return data

    async def get_lk_payload(self, user: User) -> dict[str, Any]:
        """Fetch LK payload for the Telegram user."""
        payload = {
            "telegram_id": str(user.id),
            "username": user.username or "",
            "first_name": user.first_name or "",
            "last_name": user.last_name or "",
        }
        return await self._post("/api/lk", payload)

    async def get_lk_transactions(
        self,
        user: User,
        *,
        page: int = 1,
        page_size: int = 10,
    ) -> dict[str, Any]:
        """Fetch LK transaction history for the Telegram user."""
        payload = {
            "telegram_id": str(user.id),
            "username": user.username or "",
            "first_name": user.first_name or "",
            "last_name": user.last_name or "",
            "page": page,
            "page_size": page_size,
        }
        return await self._post("/api/lk/transactions", payload)

    async def confirm_payment(self, payment_id: int, admin_telegram_id: int) -> dict[str, Any]:
        payload = {
            "payment_id": payment_id,
            "admin_telegram_id": str(admin_telegram_id),
        }
        return await self._post("/api/lk/payments/confirm", payload)

    async def decline_payment(self, payment_id: int, admin_telegram_id: int) -> dict[str, Any]:
        payload = {
            "payment_id": payment_id,
            "admin_telegram_id": str(admin_telegram_id),
        }
        return await self._post("/api/lk/payments/decline", payload)
