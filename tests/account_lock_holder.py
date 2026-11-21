"""Act as a second Food4Thought process for the cross-process account-lock tests (#107).
It takes the shared account lock, signals the test, waits, then changes a store the
way a running API server or another provisioning command would, and releases it.
"""

import json
import sys
import time
from pathlib import Path

from app.core.account_lock import account_email_lock
from app.core.config import get_customers_data_path, get_staff_data_path


def _add_customer(email: str) -> None:
    path = get_customers_data_path()
    customers = json.loads(path.read_text(encoding="utf-8"))
    customers.append({**customers[0], "id": "customer-from-other-process", "email": email})
    path.write_text(json.dumps(customers), encoding="utf-8")


def _assign(email_and_restaurant: str) -> None:
    email, restaurant_id = email_and_restaurant.split("|")
    path = get_staff_data_path()
    staff = json.loads(path.read_text(encoding="utf-8"))
    account = next(a for a in staff if a["email"].casefold() == email.casefold())
    account["restaurant_ids"].append(restaurant_id)
    path.write_text(json.dumps(staff), encoding="utf-8")


def main() -> None:
    action, signal_path, argument = sys.argv[1:4]
    with account_email_lock(RuntimeError):
        Path(signal_path).write_text("held", encoding="utf-8")
        time.sleep(0.8)  # long enough for the test to try its own write meanwhile
        {"add-customer": _add_customer, "assign": _assign}[action](argument)


if __name__ == "__main__":
    main()
