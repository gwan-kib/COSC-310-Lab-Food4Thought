"""Start Food4Thought on loopback with reusable demo stores and three sign-in presets.
Provision missing accounts through the normal account services before serving the app.
"""

import argparse
import os
from pathlib import Path
from secrets import token_urlsafe

import uvicorn
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from filelock import FileLock, Timeout
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.core.json_file import read_json_array, write_json_array
from app.core.storage import StorageFailure
from app.main import app
from app.repositories.customer import CustomerRepository
from app.schemas.customer import CustomerRegistration
from app.services.customer import CustomerService, DuplicateEmailError
from app.services.staff import StaffEmailTakenError, StaffProvisioningService

PROJECT_DIR = Path(__file__).resolve().parents[2]
SAMPLE_DIR = PROJECT_DIR / "data"
STORES = ("restaurants", "customers", "staff", "sessions", "carts", "orders")
DEMO_EMAILS = {
    "customer": "customer@food4thought.invalid",
    "restaurant_user": "manager@cedarbowl.invalid",
    "administrator": "admin@food4thought.invalid",
}
DEMO_RESTAURANT = "restaurant-001"


def _demo_passwords(directory: Path) -> list[str]:
    path = directory / "passwords.json"
    if not path.exists():
        write_json_array(path, [token_urlsafe(24) for _ in DEMO_EMAILS], StorageFailure)
    passwords = read_json_array(path, StorageFailure)
    if len(passwords) != len(DEMO_EMAILS) or any(
        not isinstance(password, str) or not 8 <= len(password) <= 128 for password in passwords
    ):
        raise StorageFailure("Demo passwords must be three strings of 8–128 characters.")
    return passwords


def _seed_demo_accounts(presets: dict[str, dict[str, str]]) -> None:
    customers = CustomerService(CustomerRepository())
    staff = StaffProvisioningService()
    customer = presets["customer"]
    if customers.repository.find_by_email(customer["email"]) is None:
        customers.register(CustomerRegistration(
            name="Demo Customer", delivery_address="100 Demo Lane, Kelowna", **customer,
        ))

    for role, name, restaurant_ids in (
        ("restaurant_user", "Cedar Bowl Manager", [DEMO_RESTAURANT]),
        ("administrator", "Demo Administrator", []),
    ):
        preset = presets[role]
        account = staff.staff.find_by_email(preset["email"])
        if account is None:
            staff.create_account(
                name=name, email=preset["email"], password=preset["password"],
                role=role, restaurant_ids=restaurant_ids,
            )
        elif account.role != role:
            raise StorageFailure(f"Demo account {account.email} already has a different role.")


def create_demo_app(directory: Path) -> FastAPI:
    """Select isolated storage for this process and serve presets only in demo mode."""
    directory = directory.resolve()
    if directory.is_relative_to(SAMPLE_DIR.resolve()):
        raise StorageFailure("Select a demo directory outside the sample data directory.")
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    with FileLock(directory / ".setup.lock", timeout=10):
        for store in STORES:
            filename = f"{store}.json"
            path = directory / filename
            if not path.exists():
                records = read_json_array(SAMPLE_DIR / filename, StorageFailure) if store == "restaurants" else []
                write_json_array(path, records, StorageFailure)
            os.environ[f"{store.upper()}_DATA_PATH"] = str(path)

        presets = {
            role: {"email": email, "password": password}
            for (role, email), password in zip(DEMO_EMAILS.items(), _demo_passwords(directory), strict=True)
        }
        _seed_demo_accounts(presets)
        presets["restaurant_user"]["restaurant_id"] = DEMO_RESTAURANT

    demo = FastAPI(openapi_url=None)
    demo.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost"])

    @demo.get("/demo-accounts", include_in_schema=False)
    def demo_accounts() -> JSONResponse:
        return JSONResponse(presets, headers={"Cache-Control": "no-store"})

    demo.mount("/", app)
    return demo


def main() -> None:
    parser = argparse.ArgumentParser(description="Start the local Food4Thought demo.")
    parser.add_argument("--port", type=int, default=8000, help="Local HTTP port (default: 8000)")
    args = parser.parse_args()
    try:
        demo = create_demo_app(PROJECT_DIR / ".demo-data")
    except (StorageFailure, OSError, Timeout, DuplicateEmailError, StaffEmailTakenError) as exc:
        parser.exit(1, f"Demo setup failed ({type(exc).__name__}). Check the local demo data and configuration.\n")
    uvicorn.run(demo, host="127.0.0.1", port=args.port, workers=1)


if __name__ == "__main__":
    main()
