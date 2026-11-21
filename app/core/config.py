# Select the JSON data path when Food4Thought creates a repository, keeping storage
# configuration out of routes and services. Per-store overrides let tests and
# manual experiments use disposable files; otherwise the path resolves to the
# project's representative data.

import os
from pathlib import Path


def get_restaurants_data_path() -> Path:
    """Return the restaurant data file, allowing isolated test storage."""
    override = os.getenv("RESTAURANTS_DATA_PATH")
    if override:
        return Path(override)
    return Path(__file__).resolve().parents[2] / "data" / "restaurants.json"


def get_orders_data_path() -> Path:
    """Resolve order storage when constructing the repository."""
    override = os.getenv("ORDERS_DATA_PATH")
    if override:
        return Path(override)
    return Path(__file__).resolve().parents[2] / "data" / "orders.json"


def get_customers_data_path() -> Path:
    """Resolve customer account storage when constructing the repository."""
    override = os.getenv("CUSTOMERS_DATA_PATH")
    if override:
        return Path(override)
    return Path(__file__).resolve().parents[2] / "data" / "customers.json"


def get_sessions_data_path() -> Path:
    """Resolve sign-in session storage when constructing the repository."""
    override = os.getenv("SESSIONS_DATA_PATH")
    if override:
        return Path(override)
    return Path(__file__).resolve().parents[2] / "data" / "sessions.json"


def get_staff_data_path() -> Path:
    """Resolve provisioned staff-account storage (#107) when resolving staff sessions."""
    override = os.getenv("STAFF_DATA_PATH")
    if override:
        return Path(override)
    return Path(__file__).resolve().parents[2] / "data" / "staff.json"


def get_carts_data_path() -> Path:
    """Resolve cart storage when constructing the repository."""
    override = os.getenv("CARTS_DATA_PATH")
    if override:
        return Path(override)
    return Path(__file__).resolve().parents[2] / "data" / "carts.json"
