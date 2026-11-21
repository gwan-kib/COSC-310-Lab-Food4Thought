"""Check Food4Thought's shared JSON-array store helper (#96).
Every account and cart repository reads and atomically replaces its file through
app/core/json_file.py, so these guarantees hold for all of them at once.
"""

import pytest

from app.core import json_file
from app.core.json_file import read_json_array, write_json_array


class StoreError(Exception):
    pass


def _temporaries(path):
    return list(path.parent.glob(f".{path.name}.*.tmp"))


def test_integers_past_the_text_limit_round_trip_exactly(tmp_path):
    path = tmp_path / "store.json"
    huge = 10**5000 + 7

    write_json_array(path, [{"quantity": huge, "name": "Café"}], StoreError)

    assert read_json_array(path, StoreError) == [{"quantity": huge, "name": "Café"}]


@pytest.mark.parametrize("content", ["{oops", "{}", '"text"', ""])
def test_corrupt_or_non_array_files_are_the_stores_error(tmp_path, content):
    path = tmp_path / "store.json"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(StoreError):
        read_json_array(path, StoreError)


def test_missing_file_is_the_stores_error(tmp_path):
    with pytest.raises(StoreError):
        read_json_array(tmp_path / "absent.json", StoreError)


def test_unserializable_records_keep_the_old_file_and_leave_no_temporary(tmp_path):
    path = tmp_path / "store.json"
    path.write_text("[]\n", encoding="utf-8")

    with pytest.raises(StoreError):
        write_json_array(path, [{"value": object()}], StoreError)

    assert path.read_text(encoding="utf-8") == "[]\n"
    assert _temporaries(path) == []


def test_failed_replace_keeps_the_old_file_and_leaves_no_temporary(tmp_path, monkeypatch):
    path = tmp_path / "store.json"
    path.write_text("[]\n", encoding="utf-8")
    monkeypatch.setattr(json_file.os, "replace", lambda *_: (_ for _ in ()).throw(OSError("disk full")))

    with pytest.raises(StoreError):
        write_json_array(path, [{"a": 1}], StoreError)

    assert path.read_text(encoding="utf-8") == "[]\n"
    assert _temporaries(path) == []


# --- PR #116 review (gwan-kib) --------------------------------------------------------------

@pytest.mark.parametrize("encoding", ["utf-16", "utf-32"])
def test_a_store_not_encoded_as_utf8_is_the_stores_error(tmp_path, encoding):
    path = tmp_path / "store.json"
    path.write_bytes('[{"id": "x"}]'.encode(encoding))

    with pytest.raises(StoreError):
        read_json_array(path, StoreError)


def test_exact_reader_rejects_bytes_that_are_not_utf8():
    # The order repository passes raw bytes to loads_exact.
    with pytest.raises(ValueError):
        json_file.loads_exact('[{"id": "x"}]'.encode("utf-16"))


def test_failed_cleanup_after_a_failed_replace_is_still_the_stores_error(tmp_path, monkeypatch):
    path = tmp_path / "store.json"
    path.write_text("[]\n", encoding="utf-8")
    monkeypatch.setattr(json_file.os, "replace", lambda *_: (_ for _ in ()).throw(OSError("disk full")))
    monkeypatch.setattr(json_file.Path, "unlink",
                        lambda *_a, **_k: (_ for _ in ()).throw(PermissionError("cannot delete")))

    with pytest.raises(StoreError, match="disk full"):
        write_json_array(path, [{"a": 1}], StoreError)

    assert path.read_text(encoding="utf-8") == "[]\n"
