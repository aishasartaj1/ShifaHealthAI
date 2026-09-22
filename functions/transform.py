"""Pure mapping from a GCS `object.finalized` CloudEvent payload to an ingestion signal."""

from __future__ import annotations

from typing import Any


def build_ingestion_signal(data: dict[str, Any]) -> dict[str, Any]:
    return {
        "event_type": "RAW_FILE_ARRIVED",
        "bucket": data["bucket"],
        "object_name": data["name"],
        "content_type": data.get("contentType"),
        "size_bytes": int(data["size"]) if data.get("size") is not None else None,
        "time_created": data.get("timeCreated"),
    }
