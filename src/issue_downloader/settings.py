import datetime
import hashlib
import json
import pathlib
from typing import Optional

# File where the settings will be saved
SETTINGS_FILE = pathlib.Path.home() / ".issue-downloader.json"


def get_settings_key(
    issue_save_path: pathlib.Path,
    url: str,
    org: Optional[str] = None,
    repos: Optional[list[str]] = None,
    include_archived: bool = False,
    include_closed: bool = True,
) -> str:
    """Create a hash of arguments that can be used as key to save settings."""

    settings_key = (
        f"{issue_save_path}:{url}:{org}:{repos}:{include_archived}:{include_closed}"
    )
    return hashlib.sha256(settings_key.encode("utf-8")).hexdigest()


def load_resume(
    issue_save_path: pathlib.Path,
    url: str,
    org: Optional[str] = None,
    repos: Optional[list[str]] = None,
    include_archived: bool = False,
    include_closed: bool = True,
) -> datetime.date | None:
    """Load the date to resume from.

    The settings are stored in JSON in SETTINGS_FILE with a key that is a hash
    of relevant arguments.
    """

    key = get_settings_key(
        issue_save_path, url, org, repos, include_archived, include_closed
    )

    try:
        with open(SETTINGS_FILE) as fh:
            settings = json.load(fh)
    except FileNotFoundError:
        return None

    try:
        return datetime.date.fromisoformat(settings[key]["date"])
    except (KeyError, ValueError):
        return None


def save_resume(
    date: datetime.date,
    url: str,
    *,
    issue_path: pathlib.Path,
    org: Optional[str] = None,
    repos: Optional[list[str]] = None,
    include_archived: bool = False,
    include_closed: bool = True,
) -> None:
    """Save the date to resume later."""

    key = get_settings_key(
        issue_path, url, org, repos, include_archived, include_closed
    )

    # Open previous settings
    try:
        with open(SETTINGS_FILE) as fh:
            settings = json.load(fh)
    except FileNotFoundError:
        settings = {}

    # Save the key in the settings
    settings.setdefault(key, {})["date"] = str(date)

    with open(SETTINGS_FILE, "w") as fh:
        json.dump(settings, fh, indent=2)
