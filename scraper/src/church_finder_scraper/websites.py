"""Validation of website links from external sources."""

from urllib.parse import urlsplit


def website_url(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip()
    if not value or any(char.isspace() or char in ";,\\<>" for char in value):
        return None
    if "://" not in value:
        value = "https://" + value
    try:
        parsed = urlsplit(value)
        if (
            parsed.scheme.lower() in {"http", "https"}
            and parsed.hostname
            and "." in parsed.hostname
            and parsed.username is None
            and parsed.password is None
            and parsed.port != 0
        ):
            return value
    except ValueError:
        return None
    return None
