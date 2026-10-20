"""Keep all test evaluations and resets away from the application's audit DB."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from services import audit_service


@pytest.fixture(autouse=True)
def isolated_audit_database(tmp_path, monkeypatch):
    monkeypatch.setattr(audit_service, "DB_PATH", tmp_path / "incidents.db")
    audit_service.reset_counter()
    audit_service.init_db()
    yield
    audit_service.reset_counter()
