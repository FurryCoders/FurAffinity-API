from __future__ import annotations
from datetime import datetime
from hashlib import sha1
from typing import Any

from pydantic import BaseModel
from pydantic import Field

from .exceptions import Unauthorized


class Cookie(BaseModel):
    """
    Container for the cookies used to connect to Fur Affinity
    """
    name: str = Field(description="The name of the cookie (a, b, etc.)")
    value: str = Field(description="The value of the cookie (e.g. 5dabd975-436f-4af7-b949-f5d0f1e803a0)")

    def to_dict(self) -> dict[str, str]:
        return {"name": self.name, "value": self.value}


class Body(BaseModel):
    """
    Request body with authentication fields
    """
    cookies: list[Cookie] = Field(description="A list of cookies to use to authenticate the request")

    def cookies_list(self) -> list[dict[str, str]]:
        return [c.to_dict() for c in self.cookies]

    def cookies_id(self) -> str:
        return sha1("".join(f"{c.name}={c.value}" for c in self.cookies).encode()).hexdigest()

    def raise_for_unauthorized(self) -> None:
        if not self.cookies:
            raise Unauthorized("Missing cookies")


class Error(BaseModel):
    """
    Error response
    """
    detail: str | list[str] | None = Field(description="details of the error")


class UserStats(BaseModel):
    """
    User statistics
    """
    views: int = Field(description="Number of views")
    submissions: int = Field(description="Number of submissions")
    favorites: int = Field(description="Number of favorites")
    comments_earned: int = Field(description="Number of comments earned")
    comments_made: int = Field(description="Number of comments made")
    journals: int = Field(description="Number of journals")


class UserPartial(BaseModel):
    """
    Simplified user information
    """
    name: str = Field(description="User's name (as it appears on their page)")
    status: str | None = Field(description="User's status (~, !, etc.)")
    title: str = Field(description="User's title")
    avatar_url: str = Field(description="URL to user's icon")
    join_date: datetime | None = Field(description="User's join date")


class User(BaseModel):
    """
    User information from their personal page
    """
    name: str = Field(description="User's name (as it appears on their page)")
    status: str = Field(description="User's status (~, !, etc.)")
    title: str = Field(description="User's title")
    join_date: datetime | None = Field(description="User's join date")
    profile: str = Field(description="User's profile text in HTML format")
    stats: UserStats = Field(description="User's statistics")
    info: dict[str, str] = Field(description="User's info (e.g. Accepting Commissions, Favorite Music, etc.)")
    contacts: dict[str, str] = Field(description="User's contacts (e.g. Twitter, Telegram, etc.)")
    avatar_url: str = Field(description="URL to user's icon")
    banner_url: str | None = Field(description="URL to user's banner (if present)")
    watched: bool = Field(description="Watch status of the user")
    watched_toggle_link: str | None = Field(description="Link to toggle watch status of the user")
    blocked: bool = Field(description="Block status of the user")
    blocked_toggle_link: str | None = Field(description="Link to toggle block status of the user")


# noinspection PyRedeclaration
class Comment(BaseModel):
    """
    Comment information and text
    """
    id: int = Field(description="Comment's ID")
    author: UserPartial
    date: datetime = Field(description="Comment's post date")
    text: str = Field(description="Comment's content")
    replies: list[Comment] = Field(description="Replies to the comment")
    reply_to: int | None = Field(description="ID of the parent comment, if any")
    edited: bool = Field(description="Whether the comment was edited")
    hidden: bool = Field(description="Whether the comment is hidden")


Comment.update_forward_refs()


class SubmissionStats(BaseModel):
    """
    Submission statistics
    """
    views: int = Field(description="Number of views")
    comments: int = Field(description="Number of comments")
    favorites: int = Field(description="Number of favorites")


class SubmissionUserFolder(BaseModel):
    name: str = Field(description="Folder name")
    url: str = Field(description="URL to folder")
    group: str = Field(description="Folder group (if any)")


class SubmissionPartial(BaseModel):
    """
    Simplified submission information
    """
    id: int = Field(description="Submission's ID")
    title: str = Field(description="Submission's title")
    author: UserPartial
    rating: str = Field(description="Submission's rating (e.g. general, mature, etc.)")
    type: str = Field(description="Submission's type (i.e. image, text, music)")
    thumbnail_url: str = Field(description="URL to submission's thumbnail")


class Submission(BaseModel):
    """
    Submission information as it appears on the submission's page
    """
    id: int = Field(description="Submission's ID")
    title: str = Field(description="Submission's title")
    author: UserPartial
    date: datetime = Field(description="Submission's upload date")
    tags: list[str] = Field(description="Submission's tags")
    category: str = Field(description="Submission's category (e.g. Artwork)")
    species: str = Field(description="Submission's species")
    gender: str = Field(description="Submission's gender")
    rating: str = Field(description="Submission's rating (e.g. general, mature, etc.)")
    type: str = Field(description="Submission's type (i.e. image, text, music)")
    stats: SubmissionStats
    description: str = Field(description="Submission's description")
    footer: str = Field(description="Submission's footer")
    mentions: list[str] = Field(description="Submission's mentions (users mentioned with FA links in the description)")
    folder: str = Field(description="Submission's folder (i.e. gallery or scraps)")
    user_folders: list[SubmissionUserFolder] = Field(description="User-defined folder(s)")
    file_url: str = Field(description="URL to submission's file")
    thumbnail_url: str = Field(description="URL to submission's thumbnail")
    comments: list[Comment] = Field(description="Submission's comments")
    prev: int | None = Field(description="ID of previous submission")
    next: int | None = Field(description="ID of previous submission")
    favorite: bool = Field(description="Favorite status of the submission")
    favorite_toggle_link: str = Field(description="Link to toggle favorite status of the submission")


class JournalStats(BaseModel):
    """
    Journal statistics
    """
    comments: int = Field(description="Number of comments")


class JournalPartial(BaseModel):
    """
    Journal information without comments as it appears in the journals' page
    """
    id: int = Field(description="Journal's ID")
    title: str = Field(description="Journal's title")
    author: UserPartial
    stats: JournalStats
    date: datetime = Field(description="Journal's upload date")
    content: str = Field(description="Journal's content")
    mentions: list[str] = Field(description="Journal's mentions (users mentioned with FA links in the content)")


class Journal(BaseModel):
    """
    Journal information as it appears in the journal's page
    """
    id: int = Field(description="Journal's ID")
    title: str = Field(description="Journal's title")
    author: UserPartial
    stats: JournalStats
    date: datetime = Field(description="Journal's upload date")
    header: str = Field(description="Journal's header")
    footer: str = Field(description="Journal's footer")
    content: str = Field(description="Journal's content")
    mentions: list[str] = Field(description="Journal's mentions (users mentioned with FA links in the content)")
    comments: list[Comment] = Field(description="Journal's comments")


class SubmissionsFolder(BaseModel):
    """
    Submissions appearing in a submissions page (e.g. gallery page)
    """
    results: list[SubmissionPartial] = Field(description="List of submissions found in the page")
    next: int | str | None = Field(description="Number of the next page, null if last page")


class JournalsFolder(BaseModel):
    """
    Journals appearing in a journals page
    """
    results: list[JournalPartial] = Field(description="List of journals found in the page")
    next: int | None = Field(description="Number of the next page, null if last page")


class Watchlist(BaseModel):
    """
    Users appearing in a user's watchlist
    """
    results: list[UserPartial] = Field(description="List of users found in the page")
    next: int | None = Field(description="Number of the next page, null if last page")


def serialise_object(obj: object) -> Any:
    if obj is None:
        return obj
    elif isinstance(obj, (str, int, float, bool)):
        return obj
    elif isinstance(obj, (tuple, list)):
        return list(map(serialise_object, obj))
    elif isinstance(obj, dict):
        return {k: serialise_object(v) for k, v in obj.items()}
    elif hasattr(obj, "__dict__"):
        return {k: serialise_object(v) for k, v in obj.__dict__.items()}
    elif hasattr(obj, "__str__"):
        return str(obj)
    else:
        return repr(obj)
