from logging import Logger
from logging import getLogger
from os import environ
from pathlib import Path
from time import time
from typing import Any

import faapi
from fastapi import FastAPI
from fastapi import Request
from fastapi import status
from fastapi.exceptions import HTTPException
from fastapi.openapi.docs import get_redoc_html
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import ORJSONResponse
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from psycopg2 import connect
from uvicorn.config import LOGGING_CONFIG

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
from .models import iter_journal
from .models import iter_submission
from .models import iter_user
from .models import iter_user_partial

database_limit: int = int(environ.get("DATABASE_LIMIT", 10000))

logger: Logger = getLogger("uvicorn")
LOGGING_CONFIG["formatters"]["access"]["fmt"] = \
    '%(levelprefix)s %(asctime)s %(client_addr)s - %(request_line)s %(status_code)s %(msecs).0fms'

robots: dict[str, list[str]] = faapi.connection.get_robots()
faapi.connection.get_robots = lambda: robots
faapi.FAAPI.check_path = lambda *_: None
faapi.Submission.__iter__ = iter_submission
faapi.Journal.__iter__ = iter_journal
faapi.UserPartial.__iter__ = iter_user_partial
faapi.User.__iter__ = iter_user

tag_auth: str = "Authorization"
tag_subs: str = "Submissions"
tag_jrns: str = "Journals"
tag_usrs: str = "User"

tags: list[dict[str, Any]] = [
    {"name": tag_auth, "description": "Authorize cookies"},
    {"name": tag_subs, "description": "Get submissions"},
    {"name": tag_jrns, "description": "Get journals"},
    {"name": tag_usrs, "description": "Get user information and folders"},
]

responses: dict[int, dict[str, Any]] = {
    status.HTTP_401_UNAUTHORIZED: {"description": "Unauthorized", "model": Error},
    status.HTTP_403_FORBIDDEN: {"description": "Forbidden", "model": Error},
    status.HTTP_404_NOT_FOUND: {"description": "Not Found", "model": Error},
}

description: str = "\n".join((Path(__file__).parent.parent / "README.md").read_text().splitlines()[1:])

app: FastAPI = FastAPI(title="Fur Affinity API", servers=[{"url": "https://furaffinity-api.herokuapp.com"}],
                       version=__version__, openapi_tags=tags, description=description,
                       license_info={"name": "European Union Public Licence v. 1.2", "url": "https://eupl.eu/1.2/en"},
                       docs_url=None, redoc_url=None)
app.add_route("/docs", lambda r: get_swagger_ui_html(openapi_url="/openapi.json", title=app.title + " - Swagger UI",
                                                     swagger_favicon_url="/favicon.ico"), ["GET"])
app.add_route("/redoc", lambda r: get_redoc_html(openapi_url="/openapi.json", title=app.title + " - ReDoc",
                                                 redoc_favicon_url="/favicon.ico"), ["GET"])
app.add_route("/", lambda r: RedirectResponse("/docs"), ["GET"])
app.add_route("/license", lambda r: RedirectResponse(app.license_info["url"]), ["GET"])
app.add_route("/robots.json", lambda r: ORJSONResponse(robots), ["GET"])
app.mount("/static", StaticFiles(directory=Path(__file__).parent.parent / "static"), "static")

settings: Settings = Settings()


@app.on_event("startup")
def startup():
    app.openapi()
    app.openapi_schema["info"]["x-logo"] = {"url": "/static/logo.png"}
    logger.info(f"Using faapi {faapi.__version__}")
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


@app.get("/favicon.ico", response_class=RedirectResponse, include_in_schema=False)
async def serve_favicon():
    return RedirectResponse("/static/favicon.ico", 301)


@app.get("/icon.png", response_class=RedirectResponse, include_in_schema=False)
@app.get("/touch-icon.png", response_class=RedirectResponse, include_in_schema=False)
@app.get("/apple-touch-icon.png", response_class=RedirectResponse, include_in_schema=False)
@app.get("/apple-touch-icon-precomposed.png", response_class=RedirectResponse, include_in_schema=False)
async def serve_touch_icon():
    return RedirectResponse("/static/logo.png", 301)


@app.post("/auth/remove/", response_model=Authorization, response_class=ORJSONResponse, responses=responses,
          tags=[tag_auth])
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


@app.post("/auth/add/", response_model=Authorization, response_class=ORJSONResponse, responses=responses,
          tags=[tag_auth])
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
        if not (api := faapi.FAAPI(body.cookies_list())).login_status:
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
        api.handle_delay()
        return {"id": cookies_id, "added": True}


@app.post("/submission/{submission_id}/",
          response_model=Submission, response_class=ORJSONResponse, responses=responses, tags=[tag_subs])
async def get_submission(submission_id: int, body: Body):
    """
    Get a submission
    """
    await authorize_cookies(body)
    results = (api := faapi.FAAPI(body.cookies_list())).submission(submission_id)[0]
    api.handle_delay()
    return results


@app.post("/submission/{submission_id}/file/",
          response_class=RedirectResponse, status_code=302, responses=responses, tags=[tag_subs])
async def get_submission_file(submission_id: int, body: Body):
    """
    Redirect to a submission's file URL
    """
    await authorize_cookies(body)
    results = (api := faapi.FAAPI(body.cookies_list())).submission(submission_id)[0]
    api.handle_delay()
    return RedirectResponse(results.file_url, status.HTTP_303_SEE_OTHER)


@app.post("/journal/{journal_id}/", response_model=Journal, response_class=ORJSONResponse, responses=responses,
          tags=[tag_jrns])
async def get_journal(journal_id: int, body: Body):
    """
    Get a journal
    """
    await authorize_cookies(body)
    results = (api := faapi.FAAPI(body.cookies_list())).journal(journal_id)
    api.handle_delay()
    return results


@app.post("/me/", response_model=User, response_class=ORJSONResponse, responses=responses, tags=[tag_usrs])
async def get_login_user(body: Body):
    """
    Get the logged-in user's details, profile text, etc. The username may contain underscore (_) characters
    """
    await authorize_cookies(body)
    results = (api := faapi.FAAPI(body.cookies_list())).me()
    api.handle_delay()
    return results


@app.post("/user/{username}/", response_model=User, response_class=ORJSONResponse, responses=responses, tags=[tag_usrs])
async def get_user(username: str, body: Body):
    """
    Get a user's details, profile text, etc. The username may contain underscore (_) characters
    """
    await authorize_cookies(body)
    results = (api := faapi.FAAPI(body.cookies_list())).user(username.replace("_", ""))
    api.handle_delay()
    return results


@app.post("/user/{username}/watchlist/by/{page}/", response_model=Watchlist, response_class=ORJSONResponse,
          responses=responses, tags=[tag_usrs])
async def get_user_watchlist_by(username: str, page: int, body: Body):
    """
    Get a list of users watched by {username}
    """
    await authorize_cookies(body)
    r, n = (api := faapi.FAAPI(body.cookies_list())).watchlist_by(username.replace("_", ""), page)
    api.handle_delay()
    return {"results": r, "next": n or None}


@app.post("/user/{username}/watchlist/to/{page}/", response_model=Watchlist, response_class=ORJSONResponse,
          responses=responses, tags=[tag_usrs])
async def get_user_watchlist_to(username: str, page: int, body: Body):
    """
    Get a list of users watching {username}
    """
    await authorize_cookies(body)
    r, n = (api := faapi.FAAPI(body.cookies_list())).watchlist_to(username.replace("_", ""), page)
    api.handle_delay()
    return {"results": r, "next": n or None}


@app.post("/user/{username}/gallery/{page}/",
          response_model=SubmissionsFolder, response_class=ORJSONResponse, responses=responses,
          tags=[tag_usrs, tag_subs])
async def get_gallery(username: str, page: int, body: Body):
    """
    Get a list of submissions from the user's gallery folder.
    """
    await authorize_cookies(body)
    r, n = (api := faapi.FAAPI(body.cookies_list())).gallery(username.replace("_", ""), page)
    api.handle_delay()
    return {"results": r, "next": n or None}


@app.post("/user/{username}/scraps/{page}/",
          response_model=SubmissionsFolder, response_class=ORJSONResponse, responses=responses,
          tags=[tag_usrs, tag_subs])
async def get_scraps(username: str, page: int, body: Body):
    """
    Get a list of submissions from the user's scraps folder.
    """
    await authorize_cookies(body)
    r, n = (api := faapi.FAAPI(body.cookies_list())).scraps(username.replace("_", ""), page)
    api.handle_delay()
    return {"results": r, "next": n or None}


@app.post("/user/{username}/favorites/{page:path}",
          response_model=SubmissionsFolder, response_class=ORJSONResponse, responses=responses,
          tags=[tag_usrs, tag_subs])
async def get_favorites(username: str, page: str, body: Body):
    """
    Get a list of submissions from the user's favorites folder. Starting page should be 0 or '/'.
    """
    await authorize_cookies(body)
    r, n = (api := faapi.FAAPI(body.cookies_list())).favorites(username.replace("_", ""), page)
    api.handle_delay()
    return {"results": r, "next": n or None}


@app.post("/user/{username}/journals/{page}/",
          response_model=JournalsFolder, response_class=ORJSONResponse, responses=responses, tags=[tag_usrs, tag_jrns])
async def get_journals(username: str, page: int, body: Body):
    """
    Get a list of journals from the user's journals folder.
    """
    await authorize_cookies(body)
    r, n = (api := faapi.FAAPI(body.cookies_list())).journals(username.replace("_", ""), page)
    api.handle_delay()
    return {"results": r, "next": n or None}
