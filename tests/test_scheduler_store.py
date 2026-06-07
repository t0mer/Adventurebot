import json
import os
import pytest
from unittest.mock import patch


def test_load_returns_defaults_when_file_missing(tmp_path):
    from bot import scheduler_store
    with patch.object(scheduler_store, "CONFIG_PATH", str(tmp_path / "schedulers.json")):
        config = scheduler_store.load()
    assert config["checklist_reminder"]["enabled"] is False
    assert config["checklist_reminder"]["time"] == "09:00"
    assert config["checklist_reminder"]["timezone"] is None
    assert config["evening_digest"]["enabled"] is False
    assert config["evening_digest"]["time"] == "20:00"
    assert config["evening_digest"]["timezone"] is None


def test_save_and_load_roundtrip(tmp_path):
    from bot import scheduler_store
    path = str(tmp_path / "schedulers.json")
    with patch.object(scheduler_store, "CONFIG_PATH", path):
        config = scheduler_store.load()
        config["checklist_reminder"]["enabled"] = True
        config["checklist_reminder"]["time"] = "08:30"
        scheduler_store.save(config)
        loaded = scheduler_store.load()
    assert loaded["checklist_reminder"]["enabled"] is True
    assert loaded["checklist_reminder"]["time"] == "08:30"


def test_save_creates_parent_dirs(tmp_path):
    from bot import scheduler_store
    path = str(tmp_path / "nested" / "dir" / "schedulers.json")
    with patch.object(scheduler_store, "CONFIG_PATH", path):
        config = scheduler_store.load()
        scheduler_store.save(config)
    assert os.path.exists(path)


def test_get_scheduler_returns_sub_dict(tmp_path):
    from bot import scheduler_store
    with patch.object(scheduler_store, "CONFIG_PATH", str(tmp_path / "s.json")):
        config = scheduler_store.load()
        entry = scheduler_store.get_scheduler(config, "evening_digest")
    assert entry["time"] == "20:00"


def test_update_scheduler_merges_kwargs(tmp_path):
    from bot import scheduler_store
    with patch.object(scheduler_store, "CONFIG_PATH", str(tmp_path / "s.json")):
        config = scheduler_store.load()
        updated = scheduler_store.update_scheduler(config, "checklist_reminder", enabled=True, time="07:00")
    assert updated["checklist_reminder"]["enabled"] is True
    assert updated["checklist_reminder"]["time"] == "07:00"
    assert updated["checklist_reminder"]["timezone"] is None  # untouched


def test_update_scheduler_does_not_save(tmp_path):
    from bot import scheduler_store
    path = str(tmp_path / "s.json")
    with patch.object(scheduler_store, "CONFIG_PATH", path):
        config = scheduler_store.load()
        scheduler_store.update_scheduler(config, "checklist_reminder", enabled=True)
    assert not os.path.exists(path)  # save() was never called
