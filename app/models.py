from datetime import datetime
from hashlib import sha1
from typing import Any
from typing import ForwardRef
from typing import Optional
from typing import Union

import faapi  # type:ignore
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
    detail: Optional[Union[str, list[str]]] = Field(description="details of the error")


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
    status: Optional[str] = Field(description="User's status (~, !, etc.)")
    title: str = Field(description="User's title")
    user_icon_url: str = Field(description="URL to user's icon")
    join_date: Optional[datetime] = Field(description="User's join date")


class User(BaseModel):
    """
    User information from their personal page
    """
    name: str = Field(description="User's name (as it appears on their page)")
    status: str = Field(description="User's status (~, !, etc.)")
    title: str = Field(description="User's title")
    join_date: Optional[datetime] = Field(description="User's join date")
    profile: str = Field(description="User's profile text in HTML format")
    stats: UserStats = Field(description="User's statistics")
    info: dict[str, str] = Field(description="User's info (e.g. Accepting Commissions, Favorite Music, etc.)")
    contacts: dict[str, str] = Field(description="User's contacts (e.g. Twitter, Telegram, etc.)")
    user_icon_url: str = Field(description="URL to user's icon")


Comment = ForwardRef("Comment")


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
    mentions: list[str] = Field(description="Submission's mentions (users mentioned with FA links in the description)")
    folder: str = Field(description="Submission's folder (i.e. gallery or scraps)")
    file_url: str = Field(description="URL to submission's file")
    thumbnail_url: str = Field(description="URL to submission's thumbnail")
    comments: list[Comment] = Field(description="Submission's comments")


class JournalStats(BaseModel):
    """
    Journal statistics
    """
    comments: int = Field(description="Number of comments")


class Journal(BaseModel):
    """
    Journal information as it appears in the journals' page
    """
    id: int = Field(description="Journal's ID")
    title: str = Field(description="Journal's title")
    author: UserPartial
    stats: JournalStats
    date: datetime = Field(description="Journal's upload date")
    content: str = Field(description="Journal's content")
    mentions: list[str] = Field(description="Journal's mentions (users mentioned with FA links in the content)")
    comments: list[Comment] = Field(description="Journal's comments")


class SubmissionsFolder(BaseModel):
    """
    Submissions appearing in a submissions page (e.g. gallery page)
    """
    results: list[SubmissionPartial] = Field(description="List of submissions found in the page")
    next: Optional[Union[int, str]] = Field(description="Number of the next page, null if last page")


class JournalsFolder(BaseModel):
    """
    Journals appearing in a journals page
    """
    results: list[Journal] = Field(description="List of journals found in the page")
    next: Optional[int] = Field(description="Number of the next page, null if last page")


class Watchlist(BaseModel):
    """
    Users appearing in a user's watchlist
    """
    results: list[UserPartial] = Field(description="List of users found in the page")
    next: Optional[int] = Field(description="Number of the next page, null if last page")


def iter_journal(jrn: faapi.Journal):
    yield "id", jrn.id
    yield "title", jrn.title
    yield "author", jrn.author
    yield "date", jrn.date
    # noinspection PyProtectedMember
    yield "stats", jrn.stats._asdict()
    yield "content", jrn.content
    yield "mentions", jrn.mentions
    yield "comments", jrn.comments


def iter_submission(sub: faapi.Submission):
    yield "id", sub.id
    yield "title", sub.title
    yield "author", sub.author
    yield "date", sub.date
    # noinspection PyProtectedMember
    yield "stats", sub.stats._asdict()
    yield "tags", sub.tags
    yield "category", sub.category
    yield "species", sub.species
    yield "gender", sub.gender
    yield "rating", sub.rating
    yield "type", sub.type
    yield "description", sub.description
    yield "mentions", sub.mentions
    yield "folder", sub.folder
    yield "file_url", sub.file_url
    yield "thumbnail_url", sub.thumbnail_url
    yield "comments", sub.comments


def iter_user(usr: faapi.User):
    yield "name", usr.name
    yield "status", usr.status
    yield "title", usr.title
    yield "join_date", usr.join_date if usr.join_date.timestamp() > 0 else None
    yield "profile", usr.profile
    # noinspection PyProtectedMember
    yield "stats", usr.stats._asdict()
    yield "info", usr.info
    yield "contacts", usr.contacts
    yield "user_icon_url", usr.user_icon_url


def iter_user_partial(usr: faapi.UserPartial):
    yield "name", usr.name
    yield "status", usr.status if usr.status else None
    yield "title", usr.title
    yield "join_date", usr.join_date if usr.join_date.timestamp() > 0 else None
    yield "user_icon_url", usr.user_icon_url


def iter_comment(comment: faapi.Comment):
    yield "id", comment.id
    yield "author", dict(comment.author)
    yield "date", comment.date
    yield "text", comment.text
    yield "replies", [dict(r) for r in comment.replies]
    yield "reply_to", comment.reply_to.id if comment.reply_to else None
    yield "edited", comment.edited
    yield "hidden", comment.hidden


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
