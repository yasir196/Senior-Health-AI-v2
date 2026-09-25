from __future__ import annotations
import json
from pathlib import Path
from typing import Any

_STORE_ROOT = Path("Thumbnail_Pipeline/db/receipts")

def _validate_fingerprint(value: str) -> str:
    if len(value) != 64 or any(c not in "0123456789abcdef" for c in value.lower()):
        raise ValueError("Receipt fingerprint must be a SHA-256 hex digest.")
    return value.lower()

class ReceiptStore:
    """Isolated JSON receipt store rooted under Thumbnail_Pipeline/db/receipts."""
    def __init__(self, root: str | Path = _STORE_ROOT) -> None:
        self.root = Path(root)
        normalized = self.root.as_posix()
        if normalized != _STORE_ROOT.as_posix() and not normalized.startswith(_STORE_ROOT.as_posix() + "/"):
            raise ValueError("Receipt store must stay inside Thumbnail_Pipeline/db/receipts/.")

    def save(self, receipt: dict[str, Any]) -> Path:
        fp = _validate_fingerprint(str(receipt.get("fingerprint") or ""))
        self.root.mkdir(parents=True, exist_ok=True)
        path = self.root / f"{fp}.json"
        payload = dict(receipt)
        payload["fingerprint"] = fp
        path.write_text(json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return path

    def load(self, fingerprint: str) -> dict[str, Any] | None:
        fp = _validate_fingerprint(fingerprint)
        path = self.root / f"{fp}.json"
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("fingerprint") != fp:
            raise ValueError("Stored receipt fingerprint mismatch.")
        return data

    def receipts_for(self, fingerprint: str) -> list[dict[str, Any]]:
        receipt = self.load(fingerprint)
        return [receipt] if receipt is not None else []
