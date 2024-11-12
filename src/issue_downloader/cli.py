import datetime
import logging
import pathlib
import sys
from typing import Annotated, Optional

import typer

from issue_downloader.github_utils import get_issues, save_issues
from issue_downloader.models import FileFormats
from issue_downloader.settings import load_resume, save_resume

app = typer.Typer()


@app.callback()
def callback(
    verbose: Annotated[
        bool, typer.Option("--verbose", "-v", help="Enable verbose logging")
    ] = False,
) -> None:
    """issue-downloader - Downloads issues to Markdown files"""

    level = logging.DEBUG if verbose else logging.INFO

    # Get the root module logger and set logging level
    logger = logging.getLogger("issue_downloader")
    logger.setLevel(level)


@app.command("github")
def download_github(
    token: Annotated[
        str,
        typer.Option(help="Github PAT token, can be obtained by 'gh auth token'"),
    ],
    org: Annotated[
        Optional[str],
        typer.Option(
            help=(
                "Download issues for this organisation." "Mutually exclusive to --repo."
            ),
        ),
    ] = None,
    repo: Annotated[
        Optional[list[str]],
        typer.Option(
            help="Specify repos to download form. Specified in the form org/repo",
        ),
    ] = None,
    date: Annotated[
        # click (which typer is based on) does not support datetime.date, only
        # datetime.datetime. Therefore define this as a datetime.datetime with
        # a custom format to resemble datetime.date and then convert it in the
        # function body.
        Optional[datetime.datetime],
        typer.Option(
            formats=["%Y-%m-%d"], help="Download issues updated on or after this date."
        ),
    ] = None,
    resume: Annotated[
        bool, typer.Option(help="Resume from last downloaded date.")
    ] = False,
    archived: Annotated[
        bool, typer.Option(help="Include archived repositories")
    ] = True,
    closed: Annotated[bool, typer.Option(help="Include closed issues")] = True,
    save_dir: Annotated[
        pathlib.Path, typer.Option(help="Directory to save the issues")
    ] = pathlib.Path.cwd(),
    formats: Annotated[
        Optional[list[FileFormats]],
        typer.Option(
            help="Limit formats to save. Defaults to MD & JSON formats if not set"
        ),
    ] = None,
    url: Annotated[
        str, typer.Option(help="URL to the Github api")
    ] = "https://api.github.com/",
) -> None:
    """Sync issues to local files"""
    logger = logging.getLogger(__name__)

    # If both repo and org is set, exist
    if repo and org:
        logging.error("Cannot specify both repo and org, choose one")
        sys.exit(1)

    if repo and not all("/" in r for r in repo):
        logging.error("repo should be specified as org/repo")
        sys.exit(1)

    # If `formats` is not set, set it to both MD and JSON.
    formats = [FileFormats.MD, FileFormats.JSON]

    # Convert "date" from datetime.datetime to datetime.date
    # click (which typer is based on) does not support datetime.date, only
    # datetime.datetime.
    try:
        date = getattr(date, "date")()
    except (AttributeError, TypeError):
        date = None

    # Load last date if "resume" is true
    if resume:
        if date:
            logger.info(
                (
                    "Attempting to resume from previous sync. "
                    f"--date {date} will be ignored"
                )
            )

        date = load_resume(save_dir, url, org, repo, archived, closed)  # type: ignore[assignment]
        logger.info(f"Resuming syncing from {date}")

    logger.info("Downloading issues")

    issues = get_issues(
        token=token, url=url, org=org, repos=repo, date=date, include_archived=archived
    )
    logger.info(f"{len(issues)} downloaded. Saving to files in {save_dir}")
    save_issues(issues, root_path=save_dir, formats=formats)
    logger.info("Issues saved!")

    # Save todays date as the day data was fetched
    save_resume(
        date=datetime.date.today(),
        url=url,
        issue_path=save_dir,
        org=org,
        repos=repo,
        include_archived=archived,
        include_closed=closed,
    )


def main() -> None:
    app()
