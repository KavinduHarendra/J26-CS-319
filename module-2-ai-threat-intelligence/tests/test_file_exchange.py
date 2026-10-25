import json
from pathlib import Path

from src.file_exchange import exchange_filename, sanitize_observation_id, write_json_atomic


def test_atomic_write_exposes_only_complete_destination(tmp_path, monkeypatch):
    destination = tmp_path / "capture.json"
    observed = []
    original_replace = __import__("os").replace

    def inspect_then_replace(source, target):
        observed.append(Path(source).read_text(encoding="utf-8"))
        assert not Path(target).exists()
        original_replace(source, target)

    monkeypatch.setattr("src.file_exchange.os.replace", inspect_then_replace)
    write_json_atomic(destination, {"complete": True})

    assert json.loads(observed[0]) == {"complete": True}
    assert json.loads(destination.read_text(encoding="utf-8")) == {"complete": True}
    assert not list(tmp_path.glob("*.tmp"))


def test_filename_is_built_only_from_validated_values():
    assert sanitize_observation_id("safe/../id") == "safe____id"
    assert exchange_filename(7, "safe/../id", threat=True) == "000007_safe____id_threat.json"
