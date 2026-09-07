from __future__ import annotations

import hashlib
import hmac
import os
import time
from secrets import token_urlsafe

from app.database.core import session_scope
from app.models import Setting


class AdminAuth:
    SESSION_TTL_SECONDS = 900
    FAILURE_WINDOW_SECONDS = 300
    MAX_FAILURES = 5
    LOCKOUT_SECONDS = 300

    def __init__(self) -> None:
        self.tokens: dict[str, float] = {}
        self.failures: list[float] = []
        self.locked_until = 0.0

    def configured(self) -> bool:
        with session_scope() as db:
            setting = db.get(Setting, "admin_auth")
            return bool(setting and setting.value and not setting.value.get("must_change")
                        and setting.value.get("salt") and setting.value.get("hash"))

    def setup(self, password: str) -> None:
        salt = os.urandom(16)
        digest = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)
        value = {"salt": salt.hex(), "hash": digest.hex()}
        with session_scope() as db:
            setting = db.get(Setting, "admin_auth")
            if setting: setting.value = value
            else: db.add(Setting(key="admin_auth", value=value))
        self.tokens.clear()
        self.failures.clear()
        self.locked_until = 0.0

    def unlock(self, password: str) -> str:
        now = time.monotonic()
        if now < self.locked_until:
            raise ValueError("Admin unlock temporarily locked")
        with session_scope() as db:
            setting = db.get(Setting, "admin_auth")
            value = setting.value if setting else None
        if not value or value.get("must_change"):
            raise ValueError("Admin password is not configured")
        actual = hashlib.scrypt(password.encode(), salt=bytes.fromhex(value["salt"]), n=2**14, r=8, p=1).hex()
        if not hmac.compare_digest(actual, value["hash"]):
            self.failures = [item for item in self.failures if now - item < self.FAILURE_WINDOW_SECONDS] + [now]
            if len(self.failures) >= self.MAX_FAILURES: self.locked_until = now + self.LOCKOUT_SECONDS
            raise ValueError("Invalid admin password")
        self.failures.clear()
        token = token_urlsafe(32)
        self.tokens[token] = now + self.SESSION_TTL_SECONDS
        return token

    def require(self, token: str | None) -> None:
        now = time.monotonic()
        self.tokens = {key: expiry for key, expiry in self.tokens.items() if expiry >= now}
        if not token or self.tokens.get(token, 0) < now:
            raise ValueError("Admin unlock required")

    def status(self) -> dict[str, object]:
        remaining = max(0, int(self.locked_until - time.monotonic()))
        return {"configured": self.configured(), "locked": remaining > 0,
                "lockout_remaining_seconds": remaining, "session_timeout_seconds": self.SESSION_TTL_SECONDS}


admin_auth = AdminAuth()
