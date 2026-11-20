"""Find out which contact channels a website offers its customers."""

__version__ = "0.1.0"

from .detect import detect, detect_html  # noqa: E402
from .models import Finding, Result  # noqa: E402
from .summary import format_summary, summarize  # noqa: E402

__all__ = [
    "Finding",
    "Result",
    "detect",
    "detect_html",
    "format_summary",
    "summarize",
    "__version__",
]
