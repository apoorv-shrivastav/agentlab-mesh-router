# common/otel.py - OpenTelemetry span helpers (Placeholder)

from contextlib import contextmanager

@contextmanager
def trace_span(name: str):
    """
    Placeholder context manager for OpenTelemetry tracing.
    Fails over silently or runs standard print tracking in mock/dev mode.
    """
    print(f"[OTel Trace] Starting span: {name}")
    try:
        yield
    finally:
        print(f"[OTel Trace] Ending span: {name}")
