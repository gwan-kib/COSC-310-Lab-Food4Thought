"""Read and atomically replace Food4Thought's JSON-array store files in one place.
Account, session, staff and cart repositories share these guarantees: integers of any
length round-trip exactly, files must be UTF-8, a missing or corrupt file is the store's
own error, and a failed write leaves the previous file intact and removes its temporary file
(unless the filesystem refuses even that deletion, which is reported with the failure).
"""

import json
import os
import tempfile
from decimal import Decimal
from pathlib import Path
from typing import Any

from pydantic_core import to_json


def _exact_int(text: str) -> int:
    # Python refuses int<->text conversion past 4300 digits; Decimal has no such limit.
    return int(Decimal(text))


def loads_exact(data: bytes | str) -> Any:
    """Parse JSON with exact integers of any length (cart quantities can be huge).

    Bytes must be UTF-8: json.loads would otherwise auto-detect UTF-16/32 and silently
    accept a wrongly encoded store. A decoding failure is a ValueError (UnicodeDecodeError).
    """
    if isinstance(data, (bytes, bytearray)):
        data = bytes(data).decode("utf-8")
    return json.loads(data, parse_int=_exact_int)


def read_json_array(path: Path, error: type[Exception]) -> list[Any]:
    try:
        data = loads_exact(path.read_bytes())
    except (OSError, UnicodeError, ValueError) as exc:
        raise error(f"Could not read {path}: {exc}") from exc
    if not isinstance(data, list):
        raise error(f"{path} must contain a JSON array")
    return data


def write_json_array(path: Path, records: list[Any], error: type[Exception]) -> None:
    temporary_path: Path | None = None
    try:
        # Pydantic's serializer writes integers of any length, unlike the json module.
        content = to_json(records, indent=2) + b"\n"
        with tempfile.NamedTemporaryFile(
            mode="wb", dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
            temporary_file.write(content)
        os.replace(temporary_path, path)
    except Exception as exc:  # any failure: keep the old file and remove our temporary
        message = f"Could not save {path}: {exc}"
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError as cleanup_exc:
                # The store's error must still win; say the temporary file may remain.
                message += f" (temporary file {temporary_path} may remain: {cleanup_exc})"
        raise error(message) from exc
