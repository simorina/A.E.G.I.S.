import re
import logging
from typing import Optional

log = logging.getLogger(__name__)

# Sensitive Patterns to Redact
BEARER_TOKEN_REGEX = re.compile(r"(?:bearer\s+|token=)(SESSION_[A-Za-z0-9_\-\.]+)", re.IGNORECASE)
SECRET_KEY_REGEX = re.compile(r"(?:password|access_key)\s*[:=]\s*['\"]?([A-Za-z0-9_\-]+)['\"]?", re.IGNORECASE)
CLASSIFIED_COORD_REGEX = re.compile(r"CLASSIFIED_SECTOR\s*[:=]?\s*\(?(-?\d+\.\d+),\s*(-?\d+\.\d+)\)?", re.IGNORECASE)

def redact_text(text: Optional[str]) -> Optional[str]:
    """
    OPSEC Redaction Guardrail.
    Scans briefing output or log messages and masks sensitive keys, session tokens,
    or classified coordinate strings.
    """
    if text is None:
        return None

    s = text
    s = BEARER_TOKEN_REGEX.sub("token=[REDACTED_TOKEN]", s)
    s = SECRET_KEY_REGEX.sub("access_key=[REDACTED_KEY]", s)
    s = CLASSIFIED_COORD_REGEX.sub("CLASSIFIED_SECTOR: [REDACTED_COORDINATES]", s)
    return s

class OpsecLoggingFilter(logging.Filter):
    """
    Logging Filter that redacts sensitive operational information from Python logging handlers.
    """
    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = redact_text(record.msg)
        if record.args:
            if isinstance(record.args, tuple):
                record.args = tuple(redact_text(str(arg)) if isinstance(arg, str) else arg for arg in record.args)
            elif isinstance(record.args, dict):
                record.args = {k: redact_text(str(v)) if isinstance(v, str) else v for k, v in record.args.items()}
        return True
