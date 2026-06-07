import copy
import json
import os

CONFIG_PATH: str = os.environ.get("SCHEDULER_CONFIG", "data/schedulers.json")

DEFAULTS: dict = {
    "checklist_reminder": {
        "enabled": False,
        "time": "09:00",
        "timezone": None,
    },
    "evening_digest": {
        "enabled": False,
        "time": "20:00",
        "timezone": None,
    },
}


def load() -> dict:
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return copy.deepcopy(DEFAULTS)


def save(config: dict) -> None:
    os.makedirs(os.path.dirname(CONFIG_PATH) or ".", exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)


def get_scheduler(config: dict, name: str) -> dict:
    return config[name]


def update_scheduler(config: dict, name: str, **kwargs) -> dict:
    config[name] = {**config[name], **kwargs}
    return config
