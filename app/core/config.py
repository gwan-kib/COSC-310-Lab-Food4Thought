# Choose the JSON restaurant-data file used by Food4Thought's repository layer.
# It honors RESTAURANTS_DATA_PATH for isolated tests or manual experiments and otherwise
# resolves the committed sample relative to the project.

import os
from pathlib import Path


def get_restaurants_data_path() -> Path:
    """Return the restaurant data file, allowing isolated test storage."""
    override = os.getenv("RESTAURANTS_DATA_PATH")
    if override:
        return Path(override)
    return Path(__file__).resolve().parents[2] / "data" / "restaurants.json"
