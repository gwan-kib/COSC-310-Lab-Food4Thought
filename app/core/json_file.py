"""Read and atomically replace Food4Thought's JSON-array store files.
Repositories pass their own error type, so a missing, corrupt or unwritable file is
reported as that store's data failure and a failed write leaves the old file intact.
"""

import json
import os
import tempfile
from pathlib import Path
from typing import Any


def read_json_array(path: Path, error: type[Exception]) -> list[Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise error(f"Could not read {path}: {exc}") from exc
    if not isinstance(data, list):
        raise error(f"{path} must contain a JSON array")
    return data


def write_json_array(path: Path, records: list[Any], error: type[Exception]) -> None:
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", newline="\n", dir=path.parent,
            prefix=f".{path.name}.", suffix=".tmp", delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
            json.dump(records, temporary_file, ensure_ascii=False, indent=2)
            temporary_file.write("\n")
        os.replace(temporary_path, path)
    except (OSError, UnicodeError, TypeError, ValueError) as exc:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
        raise error(f"Could not save {path}: {exc}") from exc
