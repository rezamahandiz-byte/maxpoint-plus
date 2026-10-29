"""Secure storage wrapper for the OpenAI API key.

The underlying `flet_secure_storage.SecureStorage` is an async Service that
uses the Android Keystore on Android, the iOS Keychain on iOS, and similar
backends elsewhere. On desktop and web it may report "unavailable" — in
that case the UI shows an explicit message and refuses to store the key.

We never store the API key in source code, SQLite, or plain files. The only
copy lives in the platform keystore, and only leaves the device when the
user manually requests an AI report.

All public methods are **async** and must be called from a coroutine
scheduled via `page.run_task(...)`. Sync wrappers are provided for status
checks only (those don't touch the platform service).
"""
from __future__ import annotations

from typing import Optional

import flet as ft

try:
    from flet_secure_storage import SecureStorage as _FletSecureStorage
    _HAS_FSS = True
except ImportError:  # pragma: no cover — package is a hard dependency
    _HAS_FSS = False


API_KEY_FIELD = "openai_api_key"


class SecureKeyStore:
    """Thin async-friendly wrapper.

    Sync properties (`available`, `status_message`) are safe to call from
    event handlers. Async methods (`get_async`, `set_async`, `delete_async`)
    must be awaited from a coroutine scheduled on the Flet loop.
    """

    def __init__(self, page: ft.Page) -> None:
        self.page = page
        self._svc: Optional[_FletSecureStorage] = None
        if _HAS_FSS:
            try:
                # Constructing a Service auto-registers it with `page`.
                self._svc = _FletSecureStorage()
            except Exception:
                self._svc = None

    # ---- sync status checks (safe from event handlers) ----

    def available(self) -> bool:
        """True if the platform keystore service is wired up."""
        return self._svc is not None

    def status_message(self) -> str:
        if not _HAS_FSS:
            return "سرویس ذخیره‌سازی امن نصب نیست."
        if self._svc is None:
            return "Keystore در این دستگاه در دسترس نیست."
        return "کلید در Keystore دستگاه ذخیره شد."

    # ---- async operations (must be awaited) ----

    async def get_async(self, key: str = API_KEY_FIELD) -> Optional[str]:
        if self._svc is None:
            return None
        try:
            return await self._svc.get(key)
        except Exception:
            return None

    async def set_async(self, value: str, key: str = API_KEY_FIELD) -> bool:
        if self._svc is None or not value:
            return False
        try:
            await self._svc.set(key, value)
            return True
        except Exception:
            return False

    async def delete_async(self, key: str = API_KEY_FIELD) -> bool:
        if self._svc is None:
            return False
        try:
            await self._svc.clear()
            return True
        except Exception:
            return False

    async def contains_async(self, key: str = API_KEY_FIELD) -> bool:
        if self._svc is None:
            return False
        try:
            return bool(await self._svc.contains_key(key))
        except Exception:
            return False
