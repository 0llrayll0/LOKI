"""Logging estruturado com structlog: JSON em produção, console legível em dev."""

import logging
import sys

import structlog

_PROD_ENVIRONMENTS = frozenset({"prod", "production"})


def configure_logging(level: str = "INFO", environment: str = "dev") -> None:
    """Configura a stdlib e o structlog com o renderer adequado ao ambiente."""
    log_level = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(stream=sys.stdout, level=log_level, format="%(message)s")

    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]
    if environment.lower() in _PROD_ENVIRONMENTS:
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer())

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        logger_factory=structlog.PrintLoggerFactory(sys.stdout),
        cache_logger_on_first_use=True,
    )
