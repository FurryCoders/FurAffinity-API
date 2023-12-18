from functools import cache
from pathlib import Path
from typing import Any
from typing import Callable
from typing import Coroutine
from urllib.robotparser import RobotFileParser

import faapi
import requests
from fastapi import FastAPI
from fastapi import Request
from fastapi import Response
from fastapi import status
from fastapi.exceptions import HTTPException
from fastapi.responses import HTMLResponse
from fastapi.responses import ORJSONResponse
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from requests import Session

from .__version__ import __version__
from .description import description
from .exceptions import DisallowedPath
from .exceptions import NotFound
from .exceptions import ParsingError
from .exceptions import Unauthorized
from .models import Body
from .models import Error
from .models import Journal
from .models import JournalsFolder
from .models import Submission
from .models import SubmissionPartial
from .models import SubmissionsFolder
from .models import User
from .models import Watchlist
from .models import serialise_object

root_folder: Path = Path(__file__).parent.parent
static_folder: Path = root_folder / "static"

robots: RobotFileParser = faapi.connection.get_robots(faapi.connection.make_session(
    [{"name": "a", "value": "0"}],
    Session
))
robots_serialised: dict = serialise_object(robots)
faapi.connection.get_robots = lambda *_: robots

tag_subs: str = "Submissions"
tag_jrns: str = "Journals"
tag_usrs: str = "User"

tags: list[dict[str, Any]] = [
    {"name": tag_subs, "description": "Get submissions"},
    {"name": tag_jrns, "description": "Get journals"},
    {"name": tag_usrs, "description": "Get user information and folders"},
]

responses: dict[int | str, dict[str, Any]] = {
    status.HTTP_401_UNAUTHORIZED: {"description": "Unauthorized", "model": Error},
    status.HTTP_403_FORBIDDEN: {"description": "Forbidden", "model": Error},
    status.HTTP_404_NOT_FOUND: {"description": "Not Found", "model": Error},
    status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "Server Error", "model": Error},
}

badge: dict[str, str | int] = {
    "schemaVersion": 1,
    "label": "furaffinity-api",
    "message": __version__,
    "color": "#FAAF3A",
    "logoSvg": (static_folder / "logo.svg").read_text()
}

documentation_swagger: str = (root_folder / "docs" / "swagger.html").read_text()
documentation_redoc: str = (root_folder / "docs" / "redoc.html").read_text()

app: FastAPI = FastAPI(title="Fur Affinity API")
app.mount("/static", StaticFiles(directory=static_folder), "static")


@cache
def get_badge(endpoint: str, query_params: str) -> Response:
    res: requests.Response = requests.request("GET", f"https://img.shields.io/endpoint?url={endpoint}&{query_params}")
    return Response(
        res.content,
        res.status_code,
        media_type=res.headers.get("Content-Type", None)
    )


@app.on_event("startup")
def startup():
    app.openapi()
    app.openapi_schema["info"]["x-logo"] = {"url": "/static/logo.png"}


@app.exception_handler(HTTPException)
def handle_http_exception(_request: Request, err: HTTPException):
    return ORJSONResponse({"detail": err.detail}, err.status_code)


# noinspection PyTypeChecker
@app.exception_handler(faapi.exceptions.Unauthorized)
@app.exception_handler(faapi.exceptions.NoticeMessage)
def handle_notice_message(_request: Request, err: Exception | faapi.exceptions.ParsingError):
    return handle_http_exception(_request, Unauthorized(err.args[0] if err.args else None))


# noinspection PyTypeChecker
@app.exception_handler(faapi.exceptions.ServerError)
@app.exception_handler(faapi.exceptions.DisabledAccount)
def handle_server_error(_request: Request, err: faapi.exceptions.ParsingError):
    return handle_http_exception(_request, NotFound([err.__class__.__name__, *err.args[0:1]]))


# noinspection PyTypeChecker
@app.exception_handler(faapi.exceptions.NoTitle)
@app.exception_handler(faapi.exceptions.NonePage)
def handle_parsing_errors(_request: Request, err: faapi.exceptions.ParsingError):
    return handle_http_exception(_request, ParsingError([err.__class__.__name__, *err.args[0:1]]))


# noinspection PyTypeChecker
@app.exception_handler(faapi.exceptions.DisallowedPath)
def handle_disallowed_path(_request: Request, err: faapi.exceptions.DisallowedPath):
    return handle_http_exception(_request, DisallowedPath(err.args[0] if err.args else None))


@app.get("/badge/json", response_class=ORJSONResponse, include_in_schema=False)
def badge_json():
    return badge


@app.get("/badge/svg", response_class=Response, include_in_schema=False)
def badge_svg(request: Request):
    return get_badge("https://furaffinity-api.herokuapp.com" + app.url_path_for(badge_json.__name__),
                     str(request.query_params))


@app.get("/favicon.ico", response_class=RedirectResponse, include_in_schema=False)
async def serve_favicon():
    return RedirectResponse("/static/favicon.ico", 301)


@app.get("/icon.png", response_class=RedirectResponse, include_in_schema=False)
@app.get("/touch-icon.png", response_class=RedirectResponse, include_in_schema=False)
@app.get("/apple-touch-icon.png", response_class=RedirectResponse, include_in_schema=False)
@app.get("/apple-touch-icon-precomposed.png", response_class=RedirectResponse, include_in_schema=False)
async def serve_touch_icon():
    return RedirectResponse("/static/logo.png", 301)


@app.post("/frontpage/", response_model=list[SubmissionPartial], response_class=ORJSONResponse, responses=responses,
          tags=[tag_subs])
async def get_frontpage(body: Body):
    """
    Get the most recent submissions.
    """
    results = (api := faapi.FAAPI(body.cookies_list())).frontpage()
    api.handle_delay()
    return [dict(r) for r in results]


@app.post("/submission/{submission_id}/",
          response_model=Submission, response_class=ORJSONResponse, responses=responses, tags=[tag_subs])
async def get_submission(submission_id: int, body: Body):
    """
    Get a submission
    """
    results = (api := faapi.FAAPI(body.cookies_list())).submission(submission_id)[0]
    if body.bbcode:
        results.description = results.description_bbcode
    api.handle_delay()
    return dict(results)


@app.post("/submission/{submission_id}/file/",
          response_class=RedirectResponse, status_code=302, responses=responses, tags=[tag_subs])
async def get_submission_file(submission_id: int, body: Body):
    """
    Redirect to a submission's file URL
    """
    results = (api := faapi.FAAPI(body.cookies_list())).submission(submission_id)[0]
    api.handle_delay()
    return RedirectResponse(results.file_url, status.HTTP_303_SEE_OTHER)


@app.post("/journal/{journal_id}/", response_model=Journal, response_class=ORJSONResponse, responses=responses,
          tags=[tag_jrns])
async def get_journal(journal_id: int, body: Body):
    """
    Get a journal
    """
    results = (api := faapi.FAAPI(body.cookies_list())).journal(journal_id)
    api.handle_delay()
    if body.bbcode:
        results.content = results.content_bbcode
        results.header = results.header_bbcode
        results.footer = results.footer_bbcode
    return dict(results)


@app.post("/me/", response_model=User, response_class=ORJSONResponse, responses=responses, tags=[tag_usrs])
async def get_login_user(body: Body):
    """
    Get the logged-in user's details, profile text, etc. The username may contain underscore (_) characters
    """
    results = (api := faapi.FAAPI(body.cookies_list())).me()
    if body.bbcode:
        results.profile = results.profile_bbcode
    api.handle_delay()
    return dict(results)


@app.post("/user/{username}/", response_model=User, response_class=ORJSONResponse, responses=responses, tags=[tag_usrs])
async def get_user(username: str, body: Body):
    """
    Get a user's details, profile text, etc. The username may contain underscore (_) characters
    """
    results = (api := faapi.FAAPI(body.cookies_list())).user(username.replace("_", ""))
    if body.bbcode:
        results.profile = results.profile_bbcode
    api.handle_delay()
    return dict(results)


@app.post("/user/{username}/watchlist/by/{page}/", response_model=Watchlist, response_class=ORJSONResponse,
          responses=responses, tags=[tag_usrs])
async def get_user_watchlist_by(username: str, page: int, body: Body):
    """
    Get a list of users watched by {username}
    """
    r, n = (api := faapi.FAAPI(body.cookies_list())).watchlist_by(username.replace("_", ""), page)
    api.handle_delay()
    return {"results": [dict(u) for u in r], "next": n or None}


@app.post("/user/{username}/watchlist/to/{page}/", response_model=Watchlist, response_class=ORJSONResponse,
          responses=responses, tags=[tag_usrs])
async def get_user_watchlist_to(username: str, page: int, body: Body):
    """
    Get a list of users watching {username}
    """
    r, n = (api := faapi.FAAPI(body.cookies_list())).watchlist_to(username.replace("_", ""), page)
    api.handle_delay()
    return {"results": [dict(u) for u in r], "next": n or None}


@app.post("/user/{username}/gallery/{page}/",
          response_model=SubmissionsFolder, response_class=ORJSONResponse, responses=responses,
          tags=[tag_usrs, tag_subs])
async def get_gallery(username: str, page: int, body: Body):
    """
    Get a list of submissions from the user's gallery folder.
    """
    r, n = (api := faapi.FAAPI(body.cookies_list())).gallery(username.replace("_", ""), page)
    api.handle_delay()
    return {"results": [dict(s) for s in r], "next": n or None}


@app.post("/user/{username}/scraps/{page}/",
          response_model=SubmissionsFolder, response_class=ORJSONResponse, responses=responses,
          tags=[tag_usrs, tag_subs])
async def get_scraps(username: str, page: int, body: Body):
    """
    Get a list of submissions from the user's scraps folder.
    """
    r, n = (api := faapi.FAAPI(body.cookies_list())).scraps(username.replace("_", ""), page)
    api.handle_delay()
    return {"results": [dict(s) for s in r], "next": n or None}


@app.post("/user/{username}/favorites/{page:path}",
          response_model=SubmissionsFolder, response_class=ORJSONResponse, responses=responses,
          tags=[tag_usrs, tag_subs])
async def get_favorites(username: str, page: str, body: Body):
    """
    Get a list of submissions from the user's favorites folder. Starting page should be 0 or '/'.
    """
    r, n = (api := faapi.FAAPI(body.cookies_list())).favorites(username.replace("_", ""), page)
    api.handle_delay()
    return {"results": [dict(s) for s in r], "next": n or None}


@app.post("/user/{username}/journals/{page}/",
          response_model=JournalsFolder, response_class=ORJSONResponse, responses=responses, tags=[tag_usrs, tag_jrns])
async def get_journals(username: str, page: int, body: Body):
    """
    Get a list of journals from the user's journals folder.
    """
    rs, n = (api := faapi.FAAPI(body.cookies_list())).journals(username.replace("_", ""), page)
    if body.bbcode:
        for r in rs:
            r.content = r.content_bbcode
    api.handle_delay()
    return {"results": [dict(j) for j in rs], "next": n or None}
