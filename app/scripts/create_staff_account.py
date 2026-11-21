"""Command-line provisioning for Food4Thought staff accounts (#107).
Run `python -m app.scripts.create_staff_account create ...` to add a restaurant user or
administrator, or `assign ...` to give a manager another restaurant. Passwords are read
with a hidden prompt and are never printed, logged or written anywhere but as a hash.
"""

import argparse
import getpass
import sys
from collections.abc import Callable, Sequence

from app.core.storage import StorageFailure
from app.repositories.restaurant import RestaurantDataError
from app.services.staff import (
    InvalidStaffRequestError, StaffEmailTakenError, StaffNotFoundError, StaffProvisioningService,
    UnknownRestaurantError,
)

EXPECTED_ERRORS = (InvalidStaffRequestError, StaffEmailTakenError, StaffNotFoundError,
                   UnknownRestaurantError, StorageFailure, RestaurantDataError)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m app.scripts.create_staff_account",
                                     description="Create or update Food4Thought staff accounts.")
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("create", help="Create a restaurant user or administrator")
    create.add_argument("--name", required=True)
    create.add_argument("--email", required=True)
    create.add_argument("--role", required=True, choices=["restaurant_user", "administrator"])
    create.add_argument("--restaurant", action="append", default=[], dest="restaurants",
                        help="Restaurant ID the user manages (repeat for several)")
    assign = commands.add_parser("assign", help="Give an existing restaurant user another restaurant")
    assign.add_argument("--email", required=True)
    assign.add_argument("--restaurant", required=True)
    return parser


def main(argv: Sequence[str] | None = None,
         password_prompt: Callable[[str], str] = getpass.getpass) -> int:
    args = _parser().parse_args(argv)
    service = StaffProvisioningService()
    try:
        if args.command == "create":
            password = password_prompt("Password: ")
            if password_prompt("Repeat password: ") != password:
                raise InvalidStaffRequestError("Passwords do not match")
            account = service.create_account(name=args.name, email=args.email, role=args.role,
                                             restaurant_ids=args.restaurants, password=password)
            print(f"Created {account.role} {account.email} ({account.id}); "
                  f"restaurants: {', '.join(account.restaurant_ids) or 'none'}")
        else:
            account = service.assign_restaurant(email=args.email, restaurant_id=args.restaurant)
            print(f"{account.email} now manages: {', '.join(account.restaurant_ids)}")
    except EXPECTED_ERRORS as error:
        print(f"Error: {type(error).__name__}: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
