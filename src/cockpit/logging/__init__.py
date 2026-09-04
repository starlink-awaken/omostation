"""Logging and tracing substrate for Cockpit CLI."""

from .logger import CockpitLogger, get_logger, get_or_create_trace_id

__all__ = ['CockpitLogger', 'get_logger', 'get_or_create_trace_id']
