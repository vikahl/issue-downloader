"""Collection of utils to fetch issues from the Github api."""

import copy
import datetime
import json
import logging
import pathlib
from typing import Any, Optional

import httpx
import pydantic

from issue_downloader.github_api_query import get_query
from issue_downloader.models import (
    Comment,
    FileFormats,
    GraphQLFilter,
    Issue,
    IssueType,
    Label,
    Repository,
    SearchQuery,
    parse_reactions,
)

logger = logging.getLogger(__name__)


def get_client(token: str, base_url: str) -> httpx.Client:
    """Create a client ready for the Github API.

    Using a client makes the requests slightly faster and its a convenient way
    to set headers.
    """
    c = httpx.Client(base_url=base_url)
    c.headers.update(
        {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        }
    )

    return c


def make_request(client: httpx.Client, query: str) -> dict[str, Any]:
    """Make a request, return data, handle errors."""

    r = client.post("graphql", json={"query": query})

    r.raise_for_status()

    if "errors" in r.json():
        logger.debug(f"Error, response was {r.text}")
        raise RuntimeError(f"Error from Github api: {r.json()['errors']}")

    try:
        data: dict[str, Any] = r.json()["data"]["search"]
        return data
    except json.JSONDecodeError as e:
        logging.debug(
            f"Error decoding api response: {r.status_code}: {r.text}", exc_info=True
        )
        raise RuntimeError(
            "Something went wrong. Could not decode response from Github API"
        ) from e


def get_issues(
    token: str,
    url: str,
    *,
    date: Optional[datetime.date] = None,
    issue_type: IssueType = IssueType.ISSUE,
    org: Optional[str] = None,
    repos: Optional[list[str]] = None,
    include_archived: bool = False,
    include_closed: bool = True,
) -> list[Issue]:
    """Get issues from the Github API

    If "repo" and "org" is set, result will include issues for both repo _and_
    org.

    About pagination:

    The GraphQL query/response gives a pagination cursor on every step
    pagination can happens and the next page will only be fetched for this
    token. If e.g., labels get paginatated on an issue, the pagination token
    will only get the next page of labels _on that issues_. All other objects
    will still be returned from the start issue.

    This creates a deduplication issue. To get around this, the cursor from the
    previous item is extracted and only fetch one item after that. This means
    if comments get paginated we will only extract 1 issue and then page the
    comments as many times as needed.

    About max nodes:

    To protect from expensive queries where e.g., millions of objects are
    selected Github's api has a max node count. If 10 search results (issues)
    are selected and in these issues 100 comments are selected and then in the
    comments 10 reactions are selected the result will be 10·100·10 nodes. The
    filters has been set to select fewer nodes, but if we get to a pagination
    and only select 1 issue it is possible to increase the number of e.g.,
    comments.

    About max search results:

    Github search returns a maximum of 1000 results, which will be a problem
    for large organisations. The "issueCount" key in the result gives the total
    number of matched issues.

    To circumvent the 1000 result limitation, if the "issueCount" is over 1000,
    the request will continue, without pagination but with the updated_date set
    to the last issue.
    """
    # Get the client used to get the requests
    client = get_client(token, url)

    query = SearchQuery(
        issue_type=issue_type,
        updated=date,
        repos=repos,
        user=org,
        include_closed=include_closed,
        include_archived=include_archived,
    )
    search_filter = GraphQLFilter(first=100, type=issue_type, query=query)
    labels_filter = GraphQLFilter(first=10)
    comments_filter = GraphQLFilter(first=10)

    issues, search_issue_count = _get_paginated_issues(
        client,
        search_filter=search_filter,
        labels_filter=labels_filter,
        comments_filter=comments_filter,
    )

    # Search returns max 1000 results. If there are more than 1000 issues, make
    # a new search for issues created after the latest issue fetched. The
    # search is ordered in ascending creation order.

    while search_issue_count > 1000 and len(issues) % 1000 == 0:
        logger.debug(f"Found {search_issue_count} issues. Have fetched {len(issues)}")

        latest_date = issues[-1].created_at.date()

        logger.debug(
            (
                f"Will search for more issues after {latest_date} "
                f"(latest issue {issues[-1].title})"
            )
        )

        new_search_filter = copy.copy(search_filter)
        new_search_filter.after = None
        new_search_filter.query.updated = latest_date  # type: ignore[union-attr]

        next_issue_batch, search_issue_count = _get_paginated_issues(
            client, new_search_filter, labels_filter, comments_filter
        )
        logger.debug(
            (
                f"Next batch has {len(next_issue_batch)},"
                f" total search count {search_issue_count}"
            )
        )

        issues.extend(next_issue_batch)

    # Deduplicate the list before returning it
    return list(set(issues))


def _get_paginated_labels(
    client: httpx.Client,
    search_filter: GraphQLFilter,
    labels_filter: GraphQLFilter,
    comments_filter: GraphQLFilter,
    issue_data: dict[str, Any],
) -> list[Label]:
    labels = []

    labels.extend(
        pydantic.TypeAdapter(list[Label]).validate_python(
            [edge["node"] for edge in issue_data["labels"]["edges"]],
        )
    )

    if issue_data["labels"]["pageInfo"]["hasNextPage"]:
        labels_filter_next = copy.copy(labels_filter)

        labels_filter_next.first = 100
        labels_filter_next.after = issue_data["labels"]["pageInfo"]["endCursor"]

        inner_query = get_query(search_filter, labels_filter_next, comments_filter)
        inner_response = make_request(client, inner_query)

        # Only one issue in this response due search_filter, so can use indexing below
        inner_issue_data = inner_response["edges"][0]["node"]

        labels.extend(
            _get_paginated_labels(
                client,
                search_filter,
                labels_filter_next,
                comments_filter,
                inner_issue_data,
            )
        )

    return labels


def _get_paginated_comments(
    client: httpx.Client,
    search_filter: GraphQLFilter,
    labels_filter: GraphQLFilter,
    comments_filter: GraphQLFilter,
    issue_data: dict[str, Any],
) -> list[Comment]:
    comments = []

    comments.extend(
        pydantic.TypeAdapter(list[Comment]).validate_python(
            [edge["node"] for edge in issue_data["comments"]["edges"]],
        )
    )

    if issue_data["comments"]["pageInfo"]["hasNextPage"]:
        comments_filter_next = copy.copy(comments_filter)

        # When only one is requested, the subnodes can be increased
        comments_filter_next.first = 100
        comments_filter_next.after = issue_data["comments"]["pageInfo"]["endCursor"]

        inner_query = get_query(search_filter, labels_filter, comments_filter_next)
        inner_response = make_request(client, inner_query)

        # Only one issue in this response due search_filter, so can use indexing below
        inner_issue_data = inner_response["edges"][0]["node"]

        comments.extend(
            _get_paginated_comments(
                client,
                search_filter,
                labels_filter,
                comments_filter_next,
                inner_issue_data,
            )
        )

    return comments


def _get_paginated_issues(
    client: httpx.Client,
    search_filter: GraphQLFilter,
    labels_filter: GraphQLFilter,
    comments_filter: GraphQLFilter,
) -> tuple[list[Issue], int]:
    """Helper function that gets issues, resolve pagination and return a full result.

    Search results returns max 1000 issues, so this function also returns the
    total issue count so the parent function can initiating more searches.
    """

    issues = []

    query = get_query(search_filter, labels_filter, comments_filter)
    search_result = make_request(client, query)

    for index, issue_edge in enumerate(search_result["edges"]):
        # Prepare the search_filter for labels and comments by getting the
        # previous cursor and requesting only one item. This is used if there
        # is pagination in the labels response.
        search_filter_single_issue = copy.copy(search_filter)
        search_filter_single_issue.first = 1
        search_filter_single_issue.after = search_result["edges"][index - 1]["cursor"]

        # Get all labels (recursively)
        labels = _get_paginated_labels(
            client,
            search_filter_single_issue,
            labels_filter,
            comments_filter,
            issue_edge["node"],
        )

        # Get all comments (recursively)
        comments = _get_paginated_comments(
            client,
            search_filter_single_issue,
            labels_filter,
            comments_filter,
            issue_edge["node"],
        )

        data = {
            **issue_edge["node"],
            "repository": Repository(**issue_edge["node"]["repository"]),
            "assignees": [
                a["node"]["login"] for a in issue_edge["node"]["assignees"]["edges"]
            ],
            "comments": comments,
            "labels": labels,
            "reactions": parse_reactions(issue_edge["node"]["reactions"]),
        }

        issue = Issue(**data)
        issues.append(issue)

    if search_result["pageInfo"]["hasNextPage"]:
        logger.debug(
            (
                "Fetching next page of issues"
                f" (after {search_result['pageInfo']['endCursor']})"
            )
        )
        search_filter.after = search_result["pageInfo"]["endCursor"]

        inner_issues, _ = _get_paginated_issues(
            client, search_filter, labels_filter, comments_filter
        )

        issues.extend(inner_issues)

    return issues, search_result["issueCount"]


def save_issues(
    issues: list[Issue],
    formats: list[FileFormats],
    root_path: pathlib.Path = pathlib.Path("."),
) -> None:
    for issue in issues:
        path_dir = root_path / issue.repository.owner / issue.repository.name
        path_dir.mkdir(parents=True, exist_ok=True)

        # TODO: Create a nice filename from the issue title. Perhaps there is
        # a "url-friendly" name in the api?

        # Save markdown
        if FileFormats.MD in formats:
            path_file = path_dir / f"{issue.number}.md"
            path_file.write_text(issue.as_markdown())

        # Save JSON
        if FileFormats.JSON in formats:
            path_file = path_dir / f"{issue.number}.json"
            path_file.write_text(issue.model_dump_json())
