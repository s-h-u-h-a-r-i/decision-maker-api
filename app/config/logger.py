import sys
import json as json_module
import logging
import logging.config
from typing import Dict, Any, Union
from datetime import datetime, timezone

from pythonjsonlogger import json


class JsonFormatter(json.JsonFormatter):
    """Custom JSON formatter"""

    def add_fields(
        self,
        log_record: Dict[str, Any],
        record: logging.LogRecord,
        message_dict: Dict[str, Any],
    ) -> None:
        from .settings import settings

        super().add_fields(log_record, record, message_dict)

        log_record["timestamp"] = datetime.fromtimestamp(
            record.created, tz=timezone.utc
        ).isoformat()

        severity_mapping = {
            "DEBUG": "DEBUG",
            "INFO": "INFO",
            "WARNING": "WARNING",
            "ERROR": "ERROR",
            "CRITICAL": "CRITICAL",
        }
        log_record["severity"] = severity_mapping.get(record.levelname, "INFO")

        log_record["sourceLocation"] = {
            "file": record.pathname,
            "line": record.lineno,
            "function": record.funcName,
            "labels": {
                "project_id": settings.gcp_project_id,
                "resource_type": settings.gcp_resource_type,
            },
        }

        log_record.pop("levelname", None)
        log_record.pop("name", None)
        log_record.pop("created", None)


class PrettyFormatter(logging.Formatter):
    """Custom pretty formatter with format: [<datetime> <level> | <file:line> | <message>]"""

    COLORS = {
        "DEBUG": "\033[36m",  # Cyan
        "INFO": "\033[32m",  # Green
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",  # Red
        "CRITICAL": "\033[35m",  # Magenta
    }

    DIM = "\033[2m"  # Dim text
    RESET = "\033[0m"  # Reset colors

    def format(self, record: logging.LogRecord) -> str:
        timestamp = datetime.fromtimestamp(record.created).strftime("%H:%M:%S.%f")[:-3]
        dimmed_timestamp = f"{self.DIM}[{timestamp}]{self.RESET}"

        level_color = self.COLORS.get(record.levelname, "")
        colored_level = f"{level_color}{record.levelname:<8}{self.RESET}"

        file_location = f"{record.filename}:{record.lineno}"
        dimmed_location = f"{self.DIM}{file_location:<22}{self.RESET}"

        message = record.getMessage()

        extra_info = ""
        if hasattr(record, "__dict__"):
            standard_fields = {
                "name",
                "msg",
                "args",
                "levelname",
                "levelno",
                "pathname",
                "filename",
                "module",
                "lineno",
                "funcName",
                "created",
                "msecs",
                "relativeCreated",
                "thread",
                "threadName",
                "processName",
                "process",
                "message",
                "exc_info",
                "exc_text",
                "stack_info",
                "getMessage",
                "taskName",
            }

            extra_fields: Dict[str, Any] = {}
            for key, value in record.__dict__.items():
                if key not in standard_fields and not key.startswith("_"):
                    extra_fields[key] = value

            if extra_fields:
                try:
                    json_str = json_module.dumps(extra_fields, indent=2, default=str)
                    formatted_json = f"{self.DIM}{json_str}{self.RESET}"
                    if "\n" in json_str:
                        extra_info = f"\n{formatted_json}"
                    else:
                        extra_info = f" {formatted_json}"
                except (TypeError, ValueError):
                    extra_str = ", ".join([f"{k}={v}" for k, v in extra_fields.items()])
                    extra_info = f" {self.DIM}[{extra_str}]{self.RESET}"

        return f"{dimmed_timestamp} {colored_level} | {dimmed_location} | {message}{extra_info}"


def setup_logging() -> None:
    """Configure logging based on environment settings."""
    from .settings import settings

    formatter: Union[PrettyFormatter, JsonFormatter]

    if settings.is_development:
        formatter = PrettyFormatter()
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(formatter)
    else:
        formatter = JsonFormatter(
            fmt="%(asctime)s %(name)s %(levelname)s %(message)s",
            rename_fields={
                "asctime": "timestamp",
                "name": "logger",
                "levelname": "level",
                "message": "message",
            },
        )

        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(formatter)

    log_level = logging.DEBUG if settings.is_development else logging.INFO

    logging.basicConfig(
        level=log_level,
        handlers=[handler],
        force=True,
    )

    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.error").setLevel(logging.INFO)
    logging.getLogger("fastapi").setLevel(logging.INFO)

    logger = logging.getLogger(__name__)
    logger.info(
        f"Logging configured",
        extra={
            "mode": settings.mode,
            "log_level": log_level,
            "gcp_project_id": settings.gcp_project_id,
        },
    )

    logger.debug(
        f"This is a debug message that will be really long in the terminal because of how long this message will be and I do not know if it will be in the proper format. I think I will haev to make this even longer becuase of how much the terminal is able to handle.",
        extra={"test": True, "debug": True},
    )


__all__ = ["setup_logging"]
