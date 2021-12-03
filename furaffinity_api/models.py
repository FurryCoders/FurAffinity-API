from datetime import datetime
from typing import Optional
from typing import Union

import faapi
from pydantic import BaseModel


class Cookie(BaseModel):
    name: str
    value: str

    def to_dict(self) -> dict[str, str]:
        return {"name": self.name, "value": self.value}


class Cookies(BaseModel):
    cookies: list[Cookie] = []

    def to_list(self) -> list[dict[str, str]]:
        return [c.to_dict() for c in self.cookies]


class UserStats(BaseModel):
    views: int
    submissions: int
    favs: int
    comments_earned: int
    comments_made: int
    journals: int


class UserPartial(BaseModel):
    name: str
    status: Optional[str]
    title: str
    user_icon_url: str
    join_date: Optional[datetime]


class User(BaseModel):
    name: str
    status: str
    title: str
    join_date: datetime
    profile: str
    stats: UserStats
    info: dict[str, str]
    contacts: dict[str, str]
    user_icon_url: str


class SubmissionPartial(BaseModel):
    id: int
    title: str
    author: UserPartial
    rating: str
    type: str
    thumbnail_url: str


class Submission(BaseModel):
    id: int
    title: str
    author: UserPartial
    date: datetime
    tags: list[str]
    category: str
    species: str
    gender: str
    rating: str
    type: str
    description: str
    mentions: list[str]
    folder: str
    file_url: str
    thumbnail_url: str


class Journal(BaseModel):
    id: int
    title: str
    date: datetime
    author: UserPartial
    content: str
    mentions: list[str]


class SubmissionsFolder(BaseModel):
    results: list[SubmissionPartial]
    next: Union[int, str]


class JournalsFolder(BaseModel):
    results: list[Journal]
    next: int


def serialise_journal(jrn: faapi.Journal):
    yield "id", jrn.id
    yield "title", jrn.title
    yield "date", jrn.date
    yield "author", jrn.author
    yield "content", jrn.content
    yield "mentions", jrn.mentions


def serialise_submission(sub: faapi.Submission):
    yield "id", sub.id
    yield "title", sub.title
    yield "author", sub.author
    yield "date", sub.date
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


def serialise_user(usr: faapi.User):
    yield "name", usr.name
    yield "status", usr.status
    yield "title", usr.title
    yield "join_date", usr.join_date
    yield "profile", usr.profile
    # noinspection PyProtectedMember
    yield "stats", usr.stats._asdict()
    yield "info", usr.info
    yield "contacts", usr.contacts
    yield "user_icon_url", usr.user_icon_url


def serialise_user_partial(usr: faapi.UserPartial):
    yield "name", usr.name
    yield "status", usr.status if usr.status else None
    yield "title", usr.title
    yield "join_date", usr.join_date if usr.join_date.timestamp() > 0 else None
    yield "user_icon_url", usr.user_icon_url
