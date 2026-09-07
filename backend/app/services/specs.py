from __future__ import annotations

import json
import re
from typing import Any


SPECS_FILE_NAME = "camera-specs.json"


class CameraSpecEnricher:
    def __init__(self) -> None:
        self._specs: list[dict[str, Any]] = []

    def _load(self) -> list[dict[str, Any]]:
        if self._specs:
            return self._specs
        config_dir = __import__("pathlib").Path(__file__).resolve().parents[3] / "config"
        specs_file = config_dir / SPECS_FILE_NAME
        if specs_file.exists():
            with open(specs_file, "r", encoding="utf-8") as handle:
                self._specs = json.load(handle).get("models", [])
        return self._specs

    def enrich(self, brand: str | None, raw_model: str | None) -> dict[str, Any]:
        if not raw_model:
            return {"brand": brand or "Unknown", "model": "Generic Camera", "tags": []}
        for entry in self._load():
            if entry["brand"].lower() != (brand or "").lower():
                continue
            if re.fullmatch(entry["model_pattern"], raw_model, re.IGNORECASE):
                return {
                    "brand": entry["brand"],
                    "model": raw_model,
                    "resolution": entry.get("resolution_px"),
                    "resolution_mp": entry.get("resolution_mp"),
                    "night_vision": entry.get("night_vision"),
                    "codecs": entry.get("codecs", []),
                    "features": entry.get("features", []),
                    "tags": [f"{entry['resolution_mp']}MP", entry.get("night_vision_short", "IR")]
                            + entry.get("features", [])[:2],
                }
        return {"brand": brand or "Unknown", "model": raw_model, "tags": [(brand or "").upper()]}


spec_enricher = CameraSpecEnricher()
