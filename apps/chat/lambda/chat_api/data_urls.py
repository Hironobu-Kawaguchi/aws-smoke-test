"""Data URL parsing helpers."""

from .constants import DATA_URL_PATTERN


def parse_data_url(data_url: str) -> tuple[str, str]:
    match = DATA_URL_PATTERN.fullmatch(data_url)
    if not match:
        raise ValueError("dataUrl must be a base64 data URL")
    return match.group("mime"), match.group("payload")
