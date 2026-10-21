import pytest

from services import audit_service


def test_incident_sequence_starts_at_one_and_stops_at_four_digits(monkeypatch):
    assert audit_service.get_next_incident_id() == "INC-0001"
    monkeypatch.setattr(audit_service, "_incident_counter", 9998)
    assert audit_service.get_next_incident_id() == "INC-9999"
    with pytest.raises(audit_service.IncidentLimitError):
        audit_service.get_next_incident_id()
    assert audit_service._incident_counter == 9999


def test_clear_restarts_incident_sequence():
    audit_service.get_next_incident_id()
    audit_service.clear_all()
    assert audit_service.get_all_incidents() == []
    assert audit_service.get_next_incident_id() == "INC-0001"
