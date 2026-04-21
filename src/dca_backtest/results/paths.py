from pathlib import Path
from .models import RunContext

def bucket_dir(root: Path, context: RunContext) -> Path:
    # Use plan name as top level bucket
    return root / context.plan.name / context.data_source

def bundle_dir(root: Path, context: RunContext, fingerprint: str) -> Path:
    return bucket_dir(root, context) / "bundles" / fingerprint

def history_file(root: Path, context: RunContext, timestamp: str) -> Path:
    return bucket_dir(root, context) / "history" / f"{timestamp}.json"

def latest_dir(root: Path, context: RunContext) -> Path:
    return bucket_dir(root, context) / "latest"
