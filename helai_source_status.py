import json
from datetime import datetime, timezone
from pathlib import Path


STATUS_PATH = Path(__file__).with_name(
    "helai_source_status.json"
)


def utc_now_iso():
    return datetime.now(timezone.utc).isoformat()


def load_source_status():
    if not STATUS_PATH.exists():
        return {}

    try:
        return json.loads(
            STATUS_PATH.read_text(encoding="utf-8")
        )
    except Exception:
        return {}


def save_source_status(status):
    STATUS_PATH.write_text(
        json.dumps(
            status,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )


def update_source_status(source_key, values):
    status = load_source_status()
    existing = status.get(source_key, {})
    existing.update(values)
    existing["last_checked_at"] = utc_now_iso()
    status[source_key] = existing
    save_source_status(status)
