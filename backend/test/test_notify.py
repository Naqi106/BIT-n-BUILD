"""
Tests for POST /alerts/notify — WhatsApp/SMS delivery to field staff.

Covers:
  1. mock fallback when Twilio credentials are absent (never send for real in CI)
  2. sms channel accepted and passed through
  3. unknown alert -> 404
  4. invalid channel -> 422 (pydantic pattern)
  5. message formatting: zone name, severity, method, confidence + graceful
     degradation when optional fields are missing

The real Twilio path is verified manually once per configuration change
(a single sandbox message); it is deliberately never exercised here so the
shared suite can't spam the field-staff number or spend money.
"""

from fastapi.testclient import TestClient

from backend.app.main import app
import backend.app.alerts.notify as notify
from backend.app.alerts.notify import format_alert_message, alert_message_variables

client = TestClient(app)

CRED_KEYS = (
    "TWILIO_ACCOUNT_SID",
    "TWILIO_AUTH_TOKEN",
    "TWILIO_WHATSAPP_FROM",
    "FIELD_STAFF_WHATSAPP_TO",
)


def _force_mock(monkeypatch):
    """Strip credentials so send_alert() takes the documented mock path."""
    for key in CRED_KEYS:
        monkeypatch.setattr(notify, key, None)


def _seed_alert_id() -> int:
    alerts = client.get("/alerts").json()
    assert alerts, "no alerts in demo DB — run: python -m backend.data.lucknow_seed"
    return alerts[0]["id"]


def test_notify_mock_fallback(monkeypatch):
    _force_mock(monkeypatch)
    alert_id = _seed_alert_id()

    res = client.post("/alerts/notify", json={"alert_id": alert_id, "channel": "whatsapp"})
    assert res.status_code == 200
    body = res.json()
    assert body["status"].startswith("mock_sent")
    assert body["alert_id"] == alert_id
    assert body["channel"] == "whatsapp"
    assert body["message"].startswith("ALTOMARE ALERT")
    assert "twilio_sid" not in body


def test_notify_sms_channel_passthrough(monkeypatch):
    _force_mock(monkeypatch)
    alert_id = _seed_alert_id()

    res = client.post("/alerts/notify", json={"alert_id": alert_id, "channel": "sms"})
    assert res.status_code == 200
    assert res.json()["channel"] == "sms"


def test_notify_unknown_alert_404(monkeypatch):
    _force_mock(monkeypatch)
    res = client.post("/alerts/notify", json={"alert_id": 999999, "channel": "whatsapp"})
    assert res.status_code == 404


def test_notify_invalid_channel_422(monkeypatch):
    _force_mock(monkeypatch)
    alert_id = _seed_alert_id()
    res = client.post("/alerts/notify", json={"alert_id": alert_id, "channel": "pigeon"})
    assert res.status_code == 422


def test_format_alert_message_full_context():
    msg = format_alert_message({
        "zone_id": "zone_9",
        "zone_name": "Hazratganj",
        "severity": "CRITICAL",
        "estimated_loss_litres": 1234567.0,
        "confidence_score": 0.98,
        "method": "water_balance,uarl",
    })
    assert "zone_9 (Hazratganj)" in msg
    assert "Severity: CRITICAL" in msg
    assert "1,234,567 litres/day" in msg
    assert "water_balance,uarl" in msg
    assert "Confidence: 98%" in msg
    assert "Dispatch field team" in msg


def test_alert_message_variables_map():
    """Template placeholders {{1}}..{{5}} must mirror the body fields."""
    vars = alert_message_variables({
        "zone_id": "zone_9",
        "zone_name": "Hazratganj",
        "severity": "CRITICAL",
        "estimated_loss_litres": 1234567.0,
        "confidence_score": 0.98,
        "method": "water_balance",
    })
    assert vars == {
        "1": "zone_9 (Hazratganj)",
        "2": "CRITICAL",
        "3": "1,234,567 litres/day",
        "4": "water_balance",
        "5": "98%",
    }


def test_format_alert_message_degrades_gracefully():
    msg = format_alert_message({"zone_id": "zone_3"})
    assert "ALTOMARE ALERT — zone_3" in msg
    assert "unknown method" in msg
    assert "an unknown volume" in msg
    assert "Confidence: unknown" in msg
    assert "Severity:" not in msg


# ---------------------------------------------------------------- twilio path
# A fake twilio.rest.Client records kwargs — verifies which send shape is
# chosen without ever touching the network (no money, no spam).

class _FakeMessages:
    def __init__(self):
        self.last_kwargs = None

    def create(self, **kwargs):
        self.last_kwargs = kwargs
        from types import SimpleNamespace
        return SimpleNamespace(sid="SM00000000000000000000000000000000")


class _FakeClient:
    last = None

    def __init__(self, sid, token):
        self.messages = _FakeMessages()
        _FakeClient.last = self


def _force_real_path(monkeypatch, content_sid=None):
    monkeypatch.setattr(notify, "TWILIO_ACCOUNT_SID", "AC_test")
    monkeypatch.setattr(notify, "TWILIO_AUTH_TOKEN", "token_test")
    monkeypatch.setattr(notify, "TWILIO_WHATSAPP_FROM", "whatsapp:+10000000000")
    monkeypatch.setattr(notify, "FIELD_STAFF_WHATSAPP_TO", "whatsapp:+910000000000")
    monkeypatch.setattr(notify, "TWILIO_CONTENT_SID", content_sid)
    import twilio.rest
    monkeypatch.setattr(twilio.rest, "Client", _FakeClient)


def test_send_uses_template_when_content_sid_set(monkeypatch):
    _force_real_path(monkeypatch, content_sid="HC_test123")
    res = notify.send_alert(
        alert_id=1,
        message="plain text body that must NOT be sent with a template",
        channel="whatsapp",
        variables={"1": "zone_2 (Aliganj)", "2": "CRITICAL"},
    )
    assert res["status"] == "sent"
    assert res["twilio_sid"].startswith("SM")
    assert res["content_sid"] == "HC_test123"
    kwargs = _FakeClient.last.messages.last_kwargs
    assert kwargs["content_sid"] == "HC_test123"
    assert kwargs["content_variables"] == '{"1": "zone_2 (Aliganj)", "2": "CRITICAL"}'
    assert "body" not in kwargs


def test_send_uses_plain_body_without_content_sid(monkeypatch):
    _force_real_path(monkeypatch, content_sid=None)
    res = notify.send_alert(alert_id=1, message="hello field team", channel="whatsapp")
    assert res["status"] == "sent"
    assert "content_sid" not in res
    kwargs = _FakeClient.last.messages.last_kwargs
    assert kwargs["body"] == "hello field team"
    assert "content_sid" not in kwargs
