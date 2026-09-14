"""Data shapes shared by the fetcher and the renderer.

The GitHub GraphQL response is described field by field instead of being left as
dict[str, Any]. The query string and these types have to stay in step, and when
they do, a field renamed in one place is a type error instead of a KeyError on
the nightly build.
"""
from typing import TypedDict


# --- GitHub GraphQL response ---------------------------------------------

class LanguageEdgeNode(TypedDict):
    name: str
    color: str | None


class LanguageEdge(TypedDict):
    size: int
    node: LanguageEdgeNode


class LanguageConnection(TypedDict):
    edges: list[LanguageEdge]


class Repository(TypedDict):
    stargazerCount: int
    languages: LanguageConnection


class RepositoryConnection(TypedDict):
    totalCount: int
    nodes: list[Repository]


class Count(TypedDict):
    totalCount: int


class ContributionsCollection(TypedDict):
    totalCommitContributions: int


class GitHubUser(TypedDict):
    login: str
    name: str | None
    followers: Count
    following: Count
    createdAt: str
    repositories: RepositoryConnection
    contributionsCollection: ContributionsCollection


# --- aggregated stats -----------------------------------------------------

class Language(TypedDict):
    name: str
    color: str | None
    size: int


class ProfileStats(TypedDict):
    login: str
    name: str | None
    repos: int
    stars: int
    commits_12mo: int
    followers: int
    following: int
    created_at: str
    languages: list[Language]
    fetched_at: str
