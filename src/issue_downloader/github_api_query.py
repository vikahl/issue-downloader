"""GraphQL query for the Github api."""

from issue_downloader.models import GraphQLFilter


def get_query(
    search_filter: GraphQLFilter,
    labels_filter: GraphQLFilter,
    comments_filter: GraphQLFilter,
) -> str:
    """Return a GraphQL query to get issues through search.


    The filters are injected with f-strings because they will differ from
    first query (first: 100) to subsequent queries when there will be a cursor
    (after: CURSOR). If using variables, the query fails with an empty cursor.
    """
    return (
        " {"
        " search("
        f" {search_filter}"
        " ) {"
        "   issueCount"
        "   pageInfo {"
        "    hasNextPage"
        "    endCursor"
        "   }"
        "   edges {"
        "     cursor"
        "     node {"
        "       ... on Issue {"
        "         id"
        "         number"
        "         title"
        "         url"
        "         author {"
        "           login"
        "         }"
        "         repository {"
        "           id"
        "           name"
        "           owner {"
        "             login"
        "           }"
        "           name_with_owner: nameWithOwner"
        "           archived_at: archivedAt"
        "           is_archived: isArchived"
        " }"
        " state"
        " state_reason: stateReason"
        " closed_at: closedAt"
        " created_at: createdAt"
        " updated_at: updatedAt"
        " body"
        " reactions(first: 10) {"
        "   edges {"
        "     node {"
        "       ... on Reaction {"
        "         content"
        "         user {"
        "           login"
        "         }"
        "       }"
        "     }"
        "   }"
        " }"
        " assignees(first: 10) {"
        "   edges {"
        "     node {"
        "       id"
        "       login"
        "     }"
        "   }"
        " }"
        " labels("
        f" {labels_filter}"
        " ) {"
        "  pageInfo {"
        "    hasNextPage"
        "    endCursor"
        "  }"
        "  edges {"
        "    cursor"
        "    node {"
        "      id"
        "      name"
        "      description"
        "    }"
        "  }"
        " }"
        " comments("
        f" {comments_filter}"
        " ) {"
        "  pageInfo {"
        "    hasNextPage"
        "    endCursor"
        "  }"
        "  edges {"
        "    cursor"
        "    node {"
        "      id"
        "      body"
        "      created_at: createdAt"
        "      author {"
        "        login"
        "      }"
        "      reactions(first: 10) {"
        "        edges {"
        "          node {"
        "            ... on Reaction {"
        "              content"
        "              user {"
        "                login"
        "              }"
        "            }"
        "          }"
        "        }"
        "      }"
        "    }"
        "  }"
        " }"
        " }"
        " }"
        " }"
        " }"
        " }"
    )