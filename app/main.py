from logging import Logger
from logging import getLogger
from pathlib import Path
from typing import Any
from typing import Callable
from typing import Coroutine
from urllib.parse import quote
from urllib.robotparser import RobotFileParser

import faapi
from fastapi import FastAPI
from fastapi import Request
from fastapi import Response
from fastapi import status
from fastapi.exceptions import HTTPException
from fastapi.responses import HTMLResponse
from fastapi.responses import ORJSONResponse
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from uvicorn.config import LOGGING_CONFIG

from .__version__ import __version__
from .exceptions import DisallowedPath
from .exceptions import NotFound
from .exceptions import ParsingError
from .exceptions import Unauthorized
from .models import Body
from .models import Error
from .models import Journal
from .models import JournalsFolder
from .models import Submission
from .models import SubmissionsFolder
from .models import User
from .models import Watchlist
from .models import iter_journal
from .models import iter_submission
from .models import iter_user
from .models import iter_user_partial

root_folder: Path = Path(__file__).parent.parent
static_folder: Path = root_folder / "static"

logger: Logger = getLogger("uvicorn")
LOGGING_CONFIG["formatters"]["access"]["fmt"] = \
    '%(levelprefix)s %(asctime)s %(client_addr)s - %(request_line)s %(status_code)s %(msecs).0fms'

robots: RobotFileParser = faapi.connection.get_robots(faapi.connection.make_session([]))
faapi.connection.get_robots = lambda *_: robots
faapi.Submission.__iter__ = iter_submission
faapi.Journal.__iter__ = iter_journal
faapi.UserPartial.__iter__ = iter_user_partial
faapi.User.__iter__ = iter_user

tag_subs: str = "Submissions"
tag_jrns: str = "Journals"
tag_usrs: str = "User"

tags: list[dict[str, Any]] = [
    {"name": tag_subs, "description": "Get submissions"},
    {"name": tag_jrns, "description": "Get journals"},
    {"name": tag_usrs, "description": "Get user information and folders"},
]

responses: dict[int, dict[str, Any]] = {
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

description: str = "\n".join((root_folder / "README.md").read_text().splitlines()[1:])
documentation_swagger: str = (root_folder / "docs" / "swagger.html").read_text()
documentation_redoc: str = (root_folder / "docs" / "redoc.html").read_text()

app: FastAPI = FastAPI(title="Fur Affinity API", servers=[{"url": "https://furaffinity-api.herokuapp.com"}],
                       version=__version__, openapi_tags=tags, description=description,
                       license_info={"name": "European Union Public Licence v. 1.2", "url": "https://eupl.eu/1.2/en"},
                       docs_url=None, redoc_url=None)
app.add_route("/docs", lambda r: HTMLResponse(documentation_swagger), ["GET"])
app.add_route("/redoc", lambda r: HTMLResponse(documentation_redoc), ["GET"])
app.add_route("/", lambda r: RedirectResponse("/docs"), ["GET"])
app.add_route("/license", lambda r: RedirectResponse(app.license_info["url"]), ["GET"])
app.add_route("/robots.json", lambda r: ORJSONResponse(robots), ["GET"])
app.mount("/static", StaticFiles(directory=static_folder), "static")


@app.on_event("startup")
def startup():
    app.openapi()
    app.openapi_schema["info"]["x-logo"] = {"url": "/static/logo.png"}
    logger.info(f"Using faapi {faapi.__version__}")


@app.exception_handler(HTTPException)
def handle_http_exception(_request: Request, err: HTTPException):
    return ORJSONResponse({"detail": err.detail}, err.status_code)


@app.exception_handler(faapi.exceptions.Unauthorized)
@app.exception_handler(faapi.exceptions.NoticeMessage)
def handle_notice_message(_request: Request, err: Exception | faapi.exceptions.ParsingError):
    return handle_http_exception(_request, Unauthorized(err.args[0] if err.args else None))


@app.exception_handler(faapi.exceptions.ServerError)
@app.exception_handler(faapi.exceptions.DisabledAccount)
def handle_server_error(_request: Request, err: faapi.exceptions.ParsingError):
    return handle_http_exception(_request, NotFound([err.__class__.__name__, *err.args[0:1]]))


@app.exception_handler(faapi.exceptions.NoTitle)
@app.exception_handler(faapi.exceptions.NonePage)
def handle_parsing_errors(_request: Request, err: faapi.exceptions.ParsingError):
    return handle_http_exception(_request, ParsingError([err.__class__.__name__, *err.args[0:1]]))


@app.exception_handler(faapi.exceptions.DisallowedPath)
def handle_disallowed_path(_request: Request, err: faapi.exceptions.DisallowedPath):
    return handle_http_exception(_request, DisallowedPath(err.args[0] if err.args else None))


@app.middleware("http")
async def redirect_https(request: Request, call_next: Callable[[Request], Coroutine[Any, Any, Response]]):
    if request.url.scheme.lower() == "http":
        return RedirectResponse("https" + str(request.url).removeprefix("http"))
    else:
        return await call_next(request)


@app.get("/badge/json", response_class=ORJSONResponse, include_in_schema=False)
def badge_json():
    return badge


@app.get("/badge/svg", response_class=RedirectResponse, include_in_schema=False)
def badge_svg():
    badge_url: str = quote(app.servers[0]["url"] + app.url_path_for(badge_json.__name__))
    return RedirectResponse(f"https://img.shields.io/endpoint?url={badge_url}")


@app.get("/favicon.ico", response_class=RedirectResponse, include_in_schema=False)
async def serve_favicon():
    return RedirectResponse("/static/favicon.ico", 301)


@app.get("/icon.png", response_class=RedirectResponse, include_in_schema=False)
@app.get("/touch-icon.png", response_class=RedirectResponse, include_in_schema=False)
@app.get("/apple-touch-icon.png", response_class=RedirectResponse, include_in_schema=False)
@app.get("/apple-touch-icon-precomposed.png", response_class=RedirectResponse, include_in_schema=False)
async def serve_touch_icon():
    return RedirectResponse("/static/logo.png", 301)


@app.post("/submission/{submission_id}/",
          response_model=Submission, response_class=ORJSONResponse, responses=responses, tags=[tag_subs])
async def get_submission(submission_id: int, body: Body):
    """
    Get a submission
    """
    results = (api := faapi.FAAPI(body.cookies_list())).submission(submission_id)[0]
    api.handle_delay()
    return results


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
    return results


@app.post("/me/", response_model=User, response_class=ORJSONResponse, responses=responses, tags=[tag_usrs])
async def get_login_user(body: Body):
    """
    Get the logged-in user's details, profile text, etc. The username may contain underscore (_) characters
    """
    results = (api := faapi.FAAPI(body.cookies_list())).me()
    api.handle_delay()
    return results


@app.post("/user/{username}/", response_model=User, response_class=ORJSONResponse, responses=responses, tags=[tag_usrs])
async def get_user(username: str, body: Body):
    """
    Get a user's details, profile text, etc. The username may contain underscore (_) characters
    """
    results = (api := faapi.FAAPI(body.cookies_list())).user(username.replace("_", ""))
    api.handle_delay()
    return results


@app.post("/user/{username}/watchlist/by/{page}/", response_model=Watchlist, response_class=ORJSONResponse,
          responses=responses, tags=[tag_usrs])
async def get_user_watchlist_by(username: str, page: int, body: Body):
    """
    Get a list of users watched by {username}
    """
    r, n = (api := faapi.FAAPI(body.cookies_list())).watchlist_by(username.replace("_", ""), page)
    api.handle_delay()
    return {"results": r, "next": n or None}


@app.post("/user/{username}/watchlist/to/{page}/", response_model=Watchlist, response_class=ORJSONResponse,
          responses=responses, tags=[tag_usrs])
async def get_user_watchlist_to(username: str, page: int, body: Body):
    """
    Get a list of users watching {username}
    """
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
    r, n = (api := faapi.FAAPI(body.cookies_list())).favorites(username.replace("_", ""), page)
    api.handle_delay()
    return {"results": r, "next": n or None}


@app.post("/user/{username}/journals/{page}/",
          response_model=JournalsFolder, response_class=ORJSONResponse, responses=responses, tags=[tag_usrs, tag_jrns])
async def get_journals(username: str, page: int, body: Body):
    """
    Get a list of journals from the user's journals folder.
    """
    r, n = (api := faapi.FAAPI(body.cookies_list())).journals(username.replace("_", ""), page)
    api.handle_delay()
    return {"results": r, "next": n or None}
