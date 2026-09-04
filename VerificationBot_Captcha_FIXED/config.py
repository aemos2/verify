import json
import os

PREFIX = "!"
CONFIG_PATH = "data/config.json"

DEFAULT_CONFIG = {
    "verify_role_id": None,
    "log_channel_id": None
}


def load_config():
    os.makedirs("data", exist_ok=True)

    if not os.path.exists(CONFIG_PATH):
        save_config(DEFAULT_CONFIG.copy())

    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        data = DEFAULT_CONFIG.copy()

    for key, value in DEFAULT_CONFIG.items():
        data.setdefault(key, value)

    return data


def save_config(data):
    os.makedirs("data", exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)
