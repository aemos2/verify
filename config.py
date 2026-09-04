import json
import os

PREFIX = "!"
CONFIG_PATH = "data/config.json"

DEFAULT_CONFIG = {
    "verify_role_id": None,
    "log_channel_id": None,

    # Executor updater
    "executor_update_channel_id": None,
    "executor_update_role_id": None,
    
    # Executor checker specific settings
    "executor_check": {
        "enabled": True,
        "check_interval_hours": 1,
        "executors_to_check": [
            "Potassium", "SirHurt", "Cosmic", "Real", "Solara", 
            "Wave", "Volt", "Velocity", "Volcano", "Synapse Z",
            "Xeno", "Seliware", "Madium", "Isaeva",  # Windows Internal
            "Photon", "Matrix Hub", "Ronin", "DX9WARE V2", 
            "Serotonin", "Lumen", "Matcha", "Severe", "Axis",  # Windows External
            "Opiumware", "MacSploit",  # Mac
            "Codex", "Delta", "Vega X",  # Android
            "Delta"  # iOS (will be differentiated by platform)
        ],
        "platform_groups": {
            "windows_internal": ["Potassium", "SirHurt", "Cosmic", "Real", "Solara", "Wave", "Volt", "Velocity", "Volcano", "Synapse Z", "Xeno", "Seliware", "Madium", "Isaeva"],
            "windows_external": ["Photon", "Matrix Hub", "Ronin", "DX9WARE V2", "Serotonin", "Lumen", "Matcha", "Severe", "Axis"],
            "mac": ["Opiumware", "MacSploit"],
            "android": ["Codex", "Delta", "Vega X"],
            "ios": ["Delta"]
        }
    },

    # Executor states (for tracking changes)
    "executor_states": {}
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

    # Add newly introduced settings to old configs
    for key, value in DEFAULT_CONFIG.items():
        if key not in data:
            data[key] = value
        elif isinstance(value, dict) and isinstance(data[key], dict):
            # Deep merge for nested dicts
            for sub_key, sub_value in value.items():
                data[key].setdefault(sub_key, sub_value)

    return data


def save_config(data):
    os.makedirs("data", exist_ok=True)

    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(
            data,
            f,
            indent=4
        )
