import logging
import sys
import json
import re
from datetime import datetime, timezone
from typing import Any

class StructuredFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "level": record.levelname,
            "message": record.getMessage(),
            "module": record.module,
            "func_name": record.funcName,
            "line_no": record.lineno
        }
        
        # Add extra properties if available
        if hasattr(record, "request_id"):
            log_data["request_id"] = record.request_id
        if hasattr(record, "user_id"):
            log_data["user_id"] = record.user_id
            
        # Sensitive data redaction (SEC-010)
        msg = log_data["message"]
        
        # 1. Redact Groq / API Keys
        msg = re.sub(r"\bgsk_[a-zA-Z0-9_-]{30,90}\b", "[REDACTED_API_KEY]", msg)
        
        # 2. Redact JWT tokens
        msg = re.sub(r"\beyJ[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}\b", "[REDACTED_JWT_TOKEN]", msg)
        
        # 3. Redact database credentials in connection strings
        msg = re.sub(
            r"\b(postgres(?:ql)?|mysql|sqlite)://([^:]+):([^@]+)@([^\s/]+)",
            r"\1://\2:[REDACTED_PASSWORD]@\4",
            msg,
            flags=re.IGNORECASE
        )
        
        # 4. Redact password/secret JSON keys
        msg = re.sub(r'(?i)(["\']?password(?:_hash|_encrypted)?["\']?\s*[:=]\s*["\'])([^"\']*)(["\'])', r'\1[REDACTED]\3', msg)
        msg = re.sub(r'(?i)(["\']?secret["\']?\s*[:=]\s*["\'])([^"\']*)(["\'])', r'\1[REDACTED]\3', msg)
        msg = re.sub(r'(?i)(["\']?token["\']?\s*[:=]\s*["\'])([^"\']*)(["\'])', r'\1[REDACTED]\3', msg)
        msg = re.sub(r'(?i)(["\']?key["\']?\s*[:=]\s*["\'])([^"\']*)(["\'])', r'\1[REDACTED]\3', msg)
        msg = re.sub(r'(?i)(["\']?password_encrypted["\']?\s*[:=]\s*["\'])([^"\']*)(["\'])', r'\1[REDACTED]\3', msg)
        
        log_data["message"] = msg
        return json.dumps(log_data)

def setup_logging():
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    # Clear existing handlers
    root_logger.handlers = []
    
    # Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(StructuredFormatter())
    root_logger.addHandler(console_handler)
    
    # Silent third party loggers if too chatty
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)

logger = logging.getLogger("insightforge")
