import contextvars

# ContextVar to hold list of self-reports for the current handling thread/task context
_self_reports = contextvars.ContextVar("self_reports", default=None)

def init_self_reports() -> list[str]:
    """Initializes a new list of self-reports in the current context."""
    reports_list = []
    _self_reports.set(reports_list)
    return reports_list

def report(reason: str) -> None:
    """
    Standard agent self-diagnostic tool called by agents.
    Logs the reason why an agent made a decision or encountered an anomaly.
    """
    reports = _self_reports.get()
    if reports is not None:
        reports.append(reason)

def get_self_reports() -> list[str]:
    """Retrieves all self-reports logged in the current context."""
    reports = _self_reports.get()
    return list(reports) if reports is not None else []
