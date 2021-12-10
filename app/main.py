from asyncio import sleep
from logging import Logger
from logging import getLogger
from os import environ
from time import time
from typing import Any

import faapi
from bs4.element import Tag
from fastapi import FastAPI
from fastapi import Request
from fastapi import status
from fastapi.exceptions import HTTPException
from fastapi.responses import ORJSONResponse
from fastapi.responses import PlainTextResponse
from fastapi.responses import RedirectResponse
from psycopg2 import connect

from .__version__ import __version__
from .exceptions import DisallowedPath
from .exceptions import NotFound
from .exceptions import Unauthorized
from .models import Authorization
from .models import Body
from .models import Error
from .models import Journal
from .models import JournalsFolder
from .models import Settings
from .models import Submission
from .models import SubmissionsFolder
from .models import User
from .models import Watchlist
from .models import serialise_journal
from .models import serialise_submission
from .models import serialise_user
from .models import serialise_user_partial

database_limit: int = int(environ.get("DATABASE_LIMIT", 10000))

logger: Logger = getLogger("uvicorn")

robots: dict[str, list[str]] = faapi.connection.get_robots()
faapi.connection.get_robots = lambda: robots
faapi.connection.ping = lambda: None
faapi.FAAPI.handle_delay = lambda *_: None
faapi.FAAPI.check_path = lambda *_: None
faapi.Submission.__iter__ = serialise_submission
faapi.Journal.__iter__ = serialise_journal
faapi.UserPartial.__iter__ = serialise_user_partial
faapi.User.__iter__ = serialise_user

tags: list[dict[str, Any]] = [
    {"name": "authorization", "description": "Authorize cookies"},
    {"name": "submissions", "description": "Get submissions"},
    {"name": "journals", "description": "Get journals"},
    {"name": "users", "description": "Get user information and folders"},
]

responses: dict[int, dict[str, Any]] = {
    status.HTTP_401_UNAUTHORIZED: {"description": "Unauthorized", "model": Error},
    status.HTTP_403_FORBIDDEN: {"description": "Forbidden", "model": Error},
    status.HTTP_404_NOT_FOUND: {"description": "Not Found", "model": Error},
}

app: FastAPI = FastAPI(title="Fur Affinity API", servers=[{"url": "https://furaffinity-api.herokuapp.com"}],
                       version=__version__, openapi_tags=tags)
app.add_route("/", lambda r: RedirectResponse(app.docs_url), ["GET"])
app.add_route("/robots.txt",
              lambda r: PlainTextResponse("\n\n".join("\n".join(f"{k}: {v}" for v in vs) for k, vs in robots.items())))
app.add_route("/robots.json", lambda r: ORJSONResponse(robots), ["GET"])

settings: Settings = Settings()


@app.on_event("startup")
def startup():
    settings.database = connect(environ["DATABASE_URL"], sslmode="require")
    with settings.database.cursor() as cursor:
        cursor.execute("create table if not exists AUTHS (ID character(40) primary key, ADDED float)")
        settings.database.commit()


@app.exception_handler(HTTPException)
def handle_http_exception(_request: Request, err: HTTPException):
    return ORJSONResponse({"error": err.__class__.__name__, "details": err.detail}, err.status_code)


@app.exception_handler(faapi.exceptions.NoticeMessage)
def handle_notice_message(_request: Request, _err: faapi.exceptions.NoticeMessage):
    return handle_http_exception(_request, Unauthorized())


@app.exception_handler(faapi.exceptions.ServerError)
def handle_server_error(_request: Request, _err: faapi.exceptions.ServerError):
    return handle_http_exception(_request, NotFound())


@app.exception_handler(faapi.exceptions.DisallowedPath)
def handle_disallowed_path(_request: Request, _err: faapi.exceptions.ServerError):
    return handle_http_exception(_request, DisallowedPath())


@app.post("/auth/remove/", response_model=Authorization, response_class=ORJSONResponse, responses=responses,
          tags=["authorization"])
async def deauthorize_cookies(body: Body):
    """
    Manually remove a cookie ID from authorisations database.
    """
    body.raise_for_unauthorized()
    with settings.database.cursor() as cursor:
        cursor.execute("select ID from AUTHS where ID = %s", (cookies_id := body.cookies_id(),))
        if not cursor.fetchone():
            return {"id": cookies_id}
        cursor.execute("delete from AUTHS where ID = %s", (cookies_id,))
        settings.database.commit()
        logger.info(f"Deleted auth ID {cookies_id}")
        return {"id": cookies_id, "exists": True, "removed": True}


@app.post("/auth/", response_model=Authorization, response_class=ORJSONResponse, responses=responses,
          tags=["authorization"])
async def authorize_cookies(body: Body):
    """
    Manually check cookies for authorization (whether they belong to a logged-in session or not).
    A unique sha1 ID is created from the given cookies and saved in a database for future confirmation.

    Because of the limited number of rows available in the database, authorization may be checked
    again after some time.
    """
    body.raise_for_unauthorized()
    with settings.database.cursor() as cursor:
        cursor.execute("select ID from AUTHS where ID = %s", (cookies_id := body.cookies_id(),))
        if cursor.fetchone():
            return {"id": cookies_id, "exists": True, "added": False}
        avatar: Tag = faapi.FAAPI(body.cookies_list()).get_parsed("login").select_one("img.loggedin_user_avatar")
        if not avatar:
            raise Unauthorized("Not a login session")
        cursor.execute("select count(ID) from AUTHS")
        if (tot := cursor.fetchone()[0]) > database_limit:
            cursor.execute("select ID from AUTHS order by ADDED limit %s", (tot - database_limit))
            for delete_id in cursor.fetchall():
                cursor.execute("delete from AUTHS where ID = %s", (delete_id,))
                logger.info(f"Deleted auth ID {delete_id}")
        cursor.execute("insert into AUTHS (ID, ADDED) values (%s, %s)", (cookies_id, time(),))
        logger.info(f"Added auth ID {cookies_id}")
        settings.database.commit()
        return {"id": cookies_id, "added": True, "username": avatar.attrs.get("alt")}


@app.post("/submission/{submission_id}/",
          response_model=Submission, response_class=ORJSONResponse, responses=responses, tags=["submissions"])
async def get_submission(submission_id: int, body: Body):
    """
    Get a submission
    """
    await authorize_cookies(body)
    results = (api := faapi.FAAPI(body.cookies_list())).submission(submission_id)[0]
    await sleep(api.crawl_delay)
    return results


@app.post("/submission/{submission_id}/file",
          response_class=RedirectResponse, status_code=302, responses=responses, tags=["submissions"])
async def get_submission_file(submission_id: int, body: Body):
    """
    Redirect to a submission's file URL
    """
    await authorize_cookies(body)
    results = (api := faapi.FAAPI(body.cookies_list())).submission(submission_id)[0]
    await sleep(api.crawl_delay)
    return RedirectResponse(results.file_url, 302)


@app.post("/journal/{journal_id}/", response_model=Journal, response_class=ORJSONResponse, responses=responses,
          tags=["journals"])
async def get_journal(journal_id: int, body: Body):
    """
    Get a journal
    """
    await authorize_cookies(body)
    results = (api := faapi.FAAPI(body.cookies_list())).journal(journal_id)
    await sleep(api.crawl_delay)
    return results


@app.post("/user/{username}/", response_model=User, response_class=ORJSONResponse, responses=responses, tags=["users"])
async def get_user(username: str, body: Body):
    """
    Get a user's details, profile text, etc. The username may contain underscore (_) characters
    """
    await authorize_cookies(body)
    results = (api := faapi.FAAPI(body.cookies_list())).user(username.replace("_", ""))
    await sleep(api.crawl_delay)
    return results


@app.post("/user/{username}/watchlist/by/{page}/", response_model=Watchlist, response_class=ORJSONResponse,
          responses=responses, tags=["users"])
async def get_user_watchlist_by(username: str, page: int, body: Body):
    """
    Get a list of users watched by {username}
    """
    await authorize_cookies(body)
    r, n = (api := faapi.FAAPI(body.cookies_list())).watchlist_by(username.replace("_", ""), page)
    await sleep(api.crawl_delay)
    return {"results": r, "next": n or None}


@app.post("/user/{username}/watchlist/to/{page}/", response_model=Watchlist, response_class=ORJSONResponse,
          responses=responses, tags=["users"])
async def get_user_watchlist_to(username: str, page: int, body: Body):
    """
    Get a list of users watching {username}
    """
    await authorize_cookies(body)
    r, n = (api := faapi.FAAPI(body.cookies_list())).watchlist_to(username.replace("_", ""), page)
    await sleep(api.crawl_delay)
    return {"results": r, "next": n or None}


@app.post("/user/{username}/gallery/{page}/",
          response_model=SubmissionsFolder, response_class=ORJSONResponse, responses=responses,
          tags=["users", "submissions"])
async def get_gallery(username: str, page: int, body: Body):
    """
    Get a list of submissions from the user's gallery folder.
    """
    await authorize_cookies(body)
    r, n = (api := faapi.FAAPI(body.cookies_list())).gallery(username.replace("_", ""), page)
    await sleep(api.crawl_delay)
    return {"results": r, "next": n or None}


@app.post("/user/{username}/scraps/{page}/",
          response_model=SubmissionsFolder, response_class=ORJSONResponse, responses=responses,
          tags=["users", "submissions"])
async def get_scraps(username: str, page: int, body: Body):
    """
    Get a list of submissions from the user's scraps folder.
    """
    await authorize_cookies(body)
    r, n = (api := faapi.FAAPI(body.cookies_list())).scraps(username.replace("_", ""), page)
    await sleep(api.crawl_delay)
    return {"results": r, "next": n or None}


@app.post("/user/{username}/favorites/{page:path}",
          response_model=SubmissionsFolder, response_class=ORJSONResponse, responses=responses,
          tags=["users", "submissions"])
async def get_favorites(username: str, page: str, body: Body):
    """
    Get a list of submissions from the user's favorites folder. Starting page should be 0 or '/'.
    """
    await authorize_cookies(body)
    r, n = (api := faapi.FAAPI(body.cookies_list())).favorites(username.replace("_", ""), page)
    await sleep(api.crawl_delay)
    return {"results": r, "next": n or None}


@app.post("/user/{username}/journals/{page}/",
          response_model=JournalsFolder, response_class=ORJSONResponse, responses=responses, tags=["users", "journals"])
async def get_journals(username: str, page: int, body: Body):
    """
    Get a list of journals from the user's journals folder.
    """
    await authorize_cookies(body)
    r, n = (api := faapi.FAAPI(body.cookies_list())).journals(username.replace("_", ""), page)
    await sleep(api.crawl_delay)
    return {"results": r, "next": n or None}
