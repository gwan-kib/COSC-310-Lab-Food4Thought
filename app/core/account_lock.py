"""Serialize every Food4Thought write that can add or change an account email.
The API server and the staff provisioning command run as separate processes, so a
threading lock alone cannot keep emails unique across customers.json and staff.json.
This lock is a file next to the customer store, shared by every process that uses it.
"""

import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from filelock import FileLock, Timeout

from app.core.config import get_customers_data_path

# Long enough for any ordinary account write; a stuck holder becomes a storage error.
LOCK_TIMEOUT_SECONDS = 10
# Threads in one process queue here first; the file lock then covers other processes.
# Not reentrant on purpose: nesting this lock would wait on itself.
_thread_lock = threading.Lock()


def account_lock_path() -> Path:
    """The lock file beside the configured customer store, e.g. data/.customers.json.lock."""
    customers = get_customers_data_path()
    return customers.with_name(f".{customers.name}.lock")


@contextmanager
def account_email_lock(error: type[Exception]) -> Iterator[None]:
    """Hold the account lock across threads and processes, or raise `error` on timeout."""
    with _thread_lock:
        lock = FileLock(account_lock_path(), timeout=LOCK_TIMEOUT_SECONDS)
        try:
            lock.acquire()
        except Timeout as exc:
            raise error(f"Timed out waiting for the account lock {lock.lock_file}") from exc
        try:
            yield
        finally:
            lock.release()
