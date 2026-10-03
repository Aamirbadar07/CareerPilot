import logging
import re

# emails, and digit runs long enough to be a phone number
_PII = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+|\+?\d[\d\s().-]{8,}\d")


class RedactPII(logging.Filter):
    """CLAUDE.md rule 6. Over-redacts on purpose: a mangled timestamp inside a message is
    cheaper than a leaked phone number."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = _PII.sub("[redacted]", record.getMessage())
        record.args = ()
        return True


def setup_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    for handler in logging.getLogger().handlers:
        handler.addFilter(RedactPII())
