from __future__ import annotations
import hashlib
import json
from .models import RunContext

def build_bundle_fingerprint(context: RunContext, payload: dict) -> str:
    # Handle non-serializable objects in payload for fingerprinting
    def serialize_val(obj):
        if hasattr(obj, 'isoformat'):
            return obj.isoformat()
        if isinstance(obj, dict):
            return {k: serialize_val(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [serialize_val(x) for x in obj]
        return obj

    fingerprint_payload = {
        "context": {
            "plan_name": context.plan.name,
            "symbols": sorted(context.symbols),
            "data_source": context.data_source,
            "date_range": context.date_range,
            "commit_hash": context.commit_hash,
            "contribution": context.plan.contribution_amount,
            "frequency": context.plan.frequency,
        },
        "payload": serialize_val(payload),
    }
    encoded = json.dumps(fingerprint_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:16]
