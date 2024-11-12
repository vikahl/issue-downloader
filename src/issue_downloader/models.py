import dataclasses
import datetime
import enum
from typing import Any, Literal, Optional

import pydantic


class FileFormats(enum.Enum):
    MD = "MD"
    JSON = "JSON"


class IssueType(enum.Enum):
    ISSUE = "ISSUE"
    PR = "PR"


@dataclasses.dataclass
class SearchQuery:
    issue_type: IssueType = IssueType.ISSUE
    sort: str = "created-desc"

    updated: Optional[datetime.date] = None
    repos: Optional[list[str]] = None
    user: Optional[str] = None

    include_closed: bool = True
    include_archived: bool = False

    def __str__(self) -> str:
        search_string = []

        search_string.append(f"is:{self.issue_type.value}")
        search_string.append("sort:created-asc")

        if self.updated:
            search_string.append(f"updated:>={self.updated}")
        if self.repos:
            search_string.extend(f"repo:{r}" for r in self.repos)
        if self.user:
            search_string.append(f"user:{self.user}")

        if not self.include_closed:
            search_string.append("is:open")

        if not self.include_archived:
            search_string.append("archived:false")

        return " ".join(search_string)


@dataclasses.dataclass
class GraphQLFilter:
    """Utility class for easier handling of filters.

    When calling str() on the class, the output can be directly inserted into a
    Github GraphQL filter.
    """

    first: int
    after: Optional[str] = None
    type: Optional[IssueType] = None
    query: Optional[SearchQuery] = None

    def __str__(self) -> str:
        """String suitable for GraphQL query."""
        out = [f"first:{self.first}"]

        if self.after:
            out.append(f'after:"{self.after}"')
        if self.type:
            out.append(f"type:{self.type.value}")
        if self.query:
            out.append(f'query:"{self.query}"')

        return " ".join(out)


class Repository(pydantic.BaseModel):
    id: str
    name: str
    owner: str
    is_archived: bool
    archived_at: datetime.datetime | None = None

    @pydantic.field_validator("owner", mode="before")
    def unpack_owner(cls, v: Any, _: pydantic.ValidationInfo) -> str:
        return str(v["login"])

    def __hash__(self) -> int:
        """Hashable function to identify unique objects through the Github id"""
        return hash(self.id)


REACTION_MAPPING = {
    "THUMBS_UP": "👍",
    "THUMBS_DOWN": "👎",
    "LAUGH": "😀",
    "HOORAY": "🎉",
    "CONFUSED": "😕",
    "HEART": "❤️",
    "ROCKET": "🚀",
    "EYES": "👀",
}


class Reaction(pydantic.BaseModel):
    content: str
    user: str

    @pydantic.field_validator("content", mode="before")
    def emoji_content(cls, v: Any, _: pydantic.ValidationInfo) -> str:
        return REACTION_MAPPING[v]

    def __hash__(self) -> int:
        """Hashable function to identify unique reactions"""
        return hash((self.content, self.user))


class Label(pydantic.BaseModel):
    name: str
    description: str | None = None

    def __str__(self) -> str:
        if self.description:
            return f"{self.name} ({self.description})"
        else:
            return self.name

    def __hash__(self) -> int:
        """Hashable function to identify unique labels"""
        return hash((self.name, self.description))


class Comment(pydantic.BaseModel):
    id: str
    body: str
    author: str

    created_at: datetime.datetime
    reactions: list[Reaction] | None = None

    @pydantic.field_validator("author", mode="before")
    def unpack_author(cls, v: Any, _: pydantic.ValidationInfo) -> str:
        try:
            return str(v["login"])
        except TypeError:
            return ""

    @pydantic.field_validator("reactions", mode="before")
    def parse_react(cls, v: Any, _: pydantic.ValidationInfo) -> list[Reaction]:
        return parse_reactions(v)

    @pydantic.field_validator("body", mode="before")
    def convert_line_endings(cls, v: Any, _: pydantic.ValidationInfo) -> str:
        s: str = v.encode("utf-8").replace(b"\r\n", b"\n").decode("utf-8")
        return s

    def __hash__(self) -> int:
        """Hashable function to identify unique objects through the Github id"""
        return hash(self.id)


class Issue(pydantic.BaseModel):
    author: str
    body: str
    created_at: datetime.datetime
    id: str
    number: int
    repository: Repository
    state: Literal["OPEN", "CLOSED"]
    title: str
    updated_at: datetime.datetime
    url: str

    assignees: list[str] | None = None
    closed_at: datetime.datetime | None = None
    comments: list[Comment] | None = None
    labels: list[Label] | None = None
    reactions: list[Reaction] | None = None
    state_reason: str | None = None

    @pydantic.field_validator("author", mode="before")
    def unpack_author(cls, v: Any, _: pydantic.ValidationInfo) -> str:
        try:
            return str(v["login"])
        except TypeError:
            return ""

    @pydantic.field_validator("body", mode="before")
    def convert_line_endings(cls, v: Any, _: pydantic.ValidationInfo) -> str:
        s: str = v.encode("utf-8").replace(b"\r\n", b"\n").decode("utf-8")
        return s

    def __hash__(self) -> int:
        """Hashable function to identify unique objects through the Github id"""
        return hash(self.id)

    def reactions_grouped(self) -> dict[str, list[str]]:
        """Group reaction with reaction as key and reactee as value."""
        out: dict[str, list[str]] = {}
        if self.reactions:
            for r in self.reactions:
                out.setdefault(r.content, []).append(r.user)
        return out

    def as_markdown(self) -> str:
        """Return a Markdown string for the issue."""
        out = []

        out.append(f"# {self.title}\n")

        out.append(
            (
                f"[{self.repository.owner}/{self.repository.name}#{self.number}]"
                f"({self.url})\n"
            )
        )

        # Add a note about the repository
        if self.repository.is_archived:
            out.append(f"Repository was archived at {self.repository.archived_at}\n")

        # Issue state
        if self.state == "CLOSED":
            out.append(f"Issue was closed at {self.closed_at} ({self.state_reason})\n")

        # Updated_at will always have a value, but might be the same as the
        # creation time. Only add it if it is different.
        if self.updated_at == self.created_at:
            out.append(f"{self.author} created at {self.created_at}\n")
        else:
            out.append(
                (
                    f"{self.author} created at {self.created_at}."
                    f" Updated at {self.updated_at}\n"
                )
            )

        if self.assignees:
            out.append(f"Assigned to {', '.join(self.assignees)}")

        # Add labels:
        if self.labels:
            out.append("Labels:\n")
            out.extend(f"- {label}" for label in self.labels)

        # Add reactions
        if self.reactions:
            out.append("Reactions:\n")
            out.extend(
                f"{r} ({', '.join(u)})" for r, u in self.reactions_grouped().items()
            )

        # Add the body itself
        out.append("\n\n---\n")
        out.append(self.body)
        out.append("\n---\n\n")

        # Add comments
        if self.comments:
            out.append("## Comments")
            for c in self.comments:
                out.append(f"### {c.author} (on {c.created_at})\n")

                # TODO: Fix \r\n in output
                out.append(c.body)

                out.append("\n---\n")
                if c.reactions:
                    out.extend(
                        f"{r} ({', '.join(u)})"
                        for r, u in self.reactions_grouped().items()
                    )

        return "\n".join(out)


def parse_reactions(data: dict[str, Any]) -> list[Reaction]:
    """Parse reactions from GraphQL response.

    data is the reactions object from the api response, including "edges" key.
    """

    return [
        Reaction(user=r["node"]["user"]["login"], content=r["node"]["content"])
        for r in data["edges"]
    ]
