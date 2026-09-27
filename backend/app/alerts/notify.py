"""
ALERTS — WhatsApp Business API / Twilio SMS alert delivery.

FALLBACK BEHAVIOUR: if Twilio credentials aren't set in .env yet
(TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN / TWILIO_WHATSAPP_FROM), send_alert()
does NOT crash — it logs what would have been sent and returns a "mock_sent"
status. This means the demo still works end-to-end even before Twilio is
configured. Once real credentials are added to .env, delivery becomes real
automatically, no code change needed. Same fallback pattern is reused for
Groq in agent.py.

TWILIO_CONTENT_SID (optional): a WhatsApp content template SID (HC...).
Outside a 24-hour free-form session WhatsApp only accepts approved template
messages — Twilio rejects free-form with "ContentSid Required". When the SID
is set, send_alert() sends the template with {{1}}..{{5}} variables built
from the same fields as the plain-text message. When it isn't set, the
plain-text body is used (works inside a sandbox session).
"""

import json
import os
from dotenv import load_dotenv

load_dotenv()

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_WHATSAPP_FROM = os.getenv("TWILIO_WHATSAPP_FROM")       # e.g. "whatsapp:+14155238886"
FIELD_STAFF_WHATSAPP_TO = os.getenv("FIELD_STAFF_WHATSAPP_TO") # e.g. "whatsapp:+91XXXXXXXXXX"
TWILIO_CONTENT_SID = os.getenv("TWILIO_CONTENT_SID")           # optional, e.g. "HCxxxxxxxx"


def _format_fields(alert: dict) -> dict:
    """Shared field formatting for both the plain-text body and the
    template variables, so the two can never disagree."""
    zone_id = alert.get("zone_id", "unknown zone")
    zone_name = alert.get("zone_name")
    loss = alert.get("estimated_loss_litres")
    confidence = alert.get("confidence_score")

    return {
        "zone": f"{zone_id} ({zone_name})" if zone_name else zone_id,
        "severity": alert.get("severity") or "",
        "loss": f"{loss:,.0f} litres/day" if loss is not None else "an unknown volume",
        "method": alert.get("method") or alert.get("detection_methods") or "unknown method",
        "confidence": f"{confidence * 100:.0f}%" if confidence is not None else "unknown",
    }


def format_alert_message(alert: dict) -> str:
    """
    Turns a leak_alerts row into a clear, human-readable field message.
    All keys optional — unknown fields degrade to honest placeholders.
    """
    f = _format_fields(alert)
    severity_line = f"Severity: {f['severity']}\n" if f["severity"] else ""

    return (
        f"ALTOMARE ALERT — {f['zone']}\n"
        f"{severity_line}"
        f"Estimated loss: {f['loss']}\n"
        f"Detection method: {f['method']}\n"
        f"Confidence: {f['confidence']}\n"
        f"Action: Dispatch field team to inspect {f['zone']} for leak/tampering."
    )


def alert_message_variables(alert: dict) -> dict:
    """1-based placeholder map for the WhatsApp content template:

        *ALTOMARE ALERT — {{1}}*
        Severity: {{2}}
        Estimated loss: {{3}}
        Detection method: {{4}}
        Confidence: {{5}}
    """
    f = _format_fields(alert)
    return {
        "1": f["zone"],
        "2": f["severity"] or "—",
        "3": f["loss"],
        "4": f["method"],
        "5": f["confidence"],
    }


def send_alert(alert_id: int, message: str, channel: str = "whatsapp", variables: dict | None = None) -> dict:
    """
    Sends via Twilio WhatsApp/SMS if credentials are configured.
    Falls back to a safe no-crash mock response otherwise.

    WhatsApp: uses TWILIO_CONTENT_SID template (with `variables`) when set,
    plain-text body otherwise (session messages only).
    """
    if not (TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN and TWILIO_WHATSAPP_FROM and FIELD_STAFF_WHATSAPP_TO):
        print(f"[MOCK ALERT — Twilio not configured] Would send via {channel}:\n{message}")
        return {
            "status": "mock_sent (Twilio not configured yet)",
            "alert_id": alert_id,
            "channel": channel,
            "message": message,
        }

    try:
        from twilio.rest import Client
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

        kwargs = {
            "from_": TWILIO_WHATSAPP_FROM,
            "to": FIELD_STAFF_WHATSAPP_TO,
        }
        used_template = channel == "whatsapp" and bool(TWILIO_CONTENT_SID)
        if used_template:
            kwargs["content_sid"] = TWILIO_CONTENT_SID
            kwargs["content_variables"] = json.dumps(variables or {})
        else:
            kwargs["body"] = message

        sent = client.messages.create(**kwargs)
        result = {
            "status": "sent",
            "alert_id": alert_id,
            "channel": channel,
            "message": message,
            "twilio_sid": sent.sid,
        }
        if used_template:
            result["content_sid"] = TWILIO_CONTENT_SID
        return result
    except Exception as e:
        # Don't crash the whole request if Twilio errors — degrade gracefully.
        print(f"[ALERT SEND FAILED] {e}")
        return {
            "status": f"failed ({str(e)})",
            "alert_id": alert_id,
            "channel": channel,
            "message": message,
        }
