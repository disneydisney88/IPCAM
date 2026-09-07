from __future__ import annotations

import base64
import ctypes
import json
import os
from abc import ABC, abstractmethod
from ctypes import wintypes
from pathlib import Path
from uuid import uuid4

from app.config import settings


class CredentialStore(ABC):
    @abstractmethod
    def put(self, key: str, username: str, password: str) -> str: ...

    @abstractmethod
    def get(self, reference: str) -> tuple[str, str] | None: ...

    @abstractmethod
    def delete(self, reference: str) -> bool: ...


class DATA_BLOB(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]


def _blob(data: bytes):
    buffer = ctypes.create_string_buffer(data)
    return DATA_BLOB(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_byte))), buffer


class WindowsCredentialStore(CredentialStore):
    """Current-user DPAPI store. Only opaque references are persisted in SQLite."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = root or settings.data_dir / "credentials"
        self.root.mkdir(parents=True, exist_ok=True)

    def _protect(self, data: bytes) -> bytes:
        if os.name != "nt":
            raise RuntimeError("DPAPI credential storage requires Windows")
        source, keepalive = _blob(data)
        output = DATA_BLOB()
        if not ctypes.windll.crypt32.CryptProtectData(ctypes.byref(source), "IPCAM", None, None, None, 1, ctypes.byref(output)):
            raise ctypes.WinError()
        try:
            return ctypes.string_at(output.pbData, output.cbData)
        finally:
            ctypes.windll.kernel32.LocalFree(output.pbData)

    def _unprotect(self, data: bytes) -> bytes:
        source, keepalive = _blob(data)
        output = DATA_BLOB()
        if not ctypes.windll.crypt32.CryptUnprotectData(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(output)):
            raise ctypes.WinError()
        try:
            return ctypes.string_at(output.pbData, output.cbData)
        finally:
            ctypes.windll.kernel32.LocalFree(output.pbData)

    def put(self, key: str, username: str, password: str) -> str:
        reference = f"dpapi-{uuid4().hex}"
        payload = json.dumps({"username": username, "password": password}, ensure_ascii=False).encode("utf-8")
        encoded = base64.b64encode(self._protect(payload))
        temporary = self.root / f".{reference}.tmp"
        temporary.write_bytes(encoded)
        temporary.replace(self.root / f"{reference}.bin")
        return reference

    def get(self, reference: str) -> tuple[str, str] | None:
        if not reference.startswith("dpapi-") or any(char not in "abcdefghijklmnopqrstuvwxyz0123456789-" for char in reference):
            return None
        path = self.root / f"{reference}.bin"
        if not path.exists():
            return None
        payload = json.loads(self._unprotect(base64.b64decode(path.read_bytes())).decode("utf-8"))
        return payload["username"], payload["password"]

    def delete(self, reference: str) -> bool:
        if not reference.startswith("dpapi-"):
            return False
        path = self.root / f"{reference}.bin"
        if not path.exists(): return False
        path.unlink()
        return True


credential_store = WindowsCredentialStore()
