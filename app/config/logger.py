import sys
import json as json_module
import logging
import logging.config
from typing import Dict, Any, Union, TextIO
from datetime import datetime, timezone

from pythonjsonlogger import json
from rich.logging import RichHandler
from rich.console import Console
from rich.pretty import Pretty
from rich.segment import Segment


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


class RichFormatter(logging.Formatter):
    """Rich formatter that handles extra fields beautifully"""

    def __init__(self) -> None:
        super().__init__()
        self.console = Console(file=sys.stdout, force_terminal=True)

    def format(self, record: logging.LogRecord) -> str:
        message = record.getMessage()

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
            extra_str = Pretty(extra_fields, expand_all=True).__rich_console__(
                self.console, self.console.options
            )
            extra_formatted = ""
            for segment in extra_str:
                if isinstance(segment, Segment):
                    extra_formatted += segment.text
                else:
                    # Handle other types that might be returned
                    extra_formatted += str(segment)

            return f"{message}\n{extra_formatted}" if extra_formatted else message

        return message


def setup_logging() -> None:
    """Configure logging based on environment settings."""
    from .settings import settings

    handler: Union[RichHandler, logging.StreamHandler[Union[TextIO, Any]]]
    formatter: Union[RichFormatter, JsonFormatter]

    if settings.is_development:
        handler = RichHandler(
            console=Console(file=sys.stdout, force_terminal=True),
            show_time=True,
            show_level=True,
            show_path=True,
            rich_tracebacks=True,
            tracebacks_show_locals=True,
            markup=True,
        )
        formatter = RichFormatter()
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

    # Suppress verbose logging from various libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.error").setLevel(logging.INFO)
    logging.getLogger("fastapi").setLevel(logging.INFO)
    logging.getLogger("watchdog").setLevel(logging.WARNING)
    logging.getLogger("watchdog.observers").setLevel(logging.WARNING)
    logging.getLogger("watchdog.events").setLevel(logging.WARNING)

    # Suppress any other file monitoring related logs
    for logger_name in logging.Logger.manager.loggerDict:
        if any(
            keyword in logger_name.lower()
            for keyword in ["watch", "file", "monitor", "reload"]
        ):
            logging.getLogger(logger_name).setLevel(logging.WARNING)

    logger = logging.getLogger(__name__)


__all__ = ["setup_logging"]
