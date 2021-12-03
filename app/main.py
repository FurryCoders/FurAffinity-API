from asyncio import sleep
from logging import Logger
from logging import getLogger

import faapi
from fastapi import FastAPI
from fastapi import Request
from fastapi.exceptions import HTTPException
from fastapi.responses import ORJSONResponse
from fastapi.responses import RedirectResponse

from .__version__ import __version__
from .exceptions import DisallowedPath
from .exceptions import NotFound
from .exceptions import Unauthorized
from .models import Body
from .models import Journal
from .models import JournalsFolder
from .models import Submission
from .models import SubmissionsFolder
from .models import User
from .models import serialise_journal
from .models import serialise_submission
from .models import serialise_user
from .models import serialise_user_partial
from .robots import robots

logger: Logger = getLogger("uvicorn")

app: FastAPI = FastAPI(title="Fur Affinity API", version=__version__, openapi_tags=[
    {"name": "submissions", "description": "Get submissions"},
    {"name": "journals", "description": "Get journals"},
    {"name": "users", "description": "Get user information and folders"},
])

app.add_route("/", lambda r: RedirectResponse("/docs"), ["GET"])

faapi.connection.get_robots = lambda: robots
faapi.Submission.__iter__ = serialise_submission
faapi.Journal.__iter__ = serialise_journal
faapi.UserPartial.__iter__ = serialise_user_partial
faapi.User.__iter__ = serialise_user


@app.exception_handler(HTTPException)
def handle_http_exception(_request: Request, err: HTTPException):
    return ORJSONResponse({"error": err.detail}, err.status_code)


@app.exception_handler(faapi.exceptions.NoticeMessage)
def handle_notice_message(_request: Request, _err: faapi.exceptions.NoticeMessage):
    return handle_http_exception(_request, Unauthorized(401))


@app.exception_handler(faapi.exceptions.ServerError)
def handle_server_error(_request: Request, _err: faapi.exceptions.ServerError):
    return handle_http_exception(_request, NotFound(404))


@app.exception_handler(faapi.exceptions.DisallowedPath)
def handle_disallowed_path(_request: Request, _err: faapi.exceptions.ServerError):
    return handle_http_exception(_request, DisallowedPath(403))


@app.post("/submission/{submission_id}/",
          response_model=Submission, response_class=ORJSONResponse, tags=["submissions"])
async def get_submission(submission_id: int, body: Body = None):
    """
    Get a submission object. Public submissions can be queried without cookies.
    """
    results = (api := faapi.FAAPI(body.cookies_list() if body else None)).get_submission(submission_id)[0]
    await sleep(api.crawl_delay)
    return results


@app.post("/journal/{journal_id}", response_model=Journal, response_class=ORJSONResponse, tags=["journals"])
async def get_journal(journal_id: int, body: Body = None):
    """
    Get a journal. Public journals can be queried without cookies.
    """
    results = (api := faapi.FAAPI(body.cookies_list() if body else None)).get_journal(journal_id)
    await sleep(api.crawl_delay)
    return results


@app.post("/user/{username}/", response_model=User, response_class=ORJSONResponse, tags=["users"])
async def get_user(username: str, body: Body = None):
    """
    Get a user's details, profile text, etc. The username may contain underscore (_) characters
    """
    results = (api := faapi.FAAPI(body.cookies_list() if body else None)).get_user(username.replace("_", ""))
    await sleep(api.crawl_delay)
    return results


@app.post("/gallery/{username}/{page}/",
          response_model=SubmissionsFolder, response_class=ORJSONResponse, tags=["users", "submissions"])
async def get_gallery(username: str, page: int, body: Body = None):
    """
    Get a list of submissions from the user's gallery folder.
    """
    r, n = (api := faapi.FAAPI(body.cookies_list() if body else None)).gallery(username.replace("_", ""), page)
    await sleep(api.crawl_delay)
    return {"results": r, "next": n or None}


@app.post("/scraps/{username}/{page}/",
          response_model=SubmissionsFolder, response_class=ORJSONResponse, tags=["users", "submissions"])
async def get_scraps(username: str, page: int, body: Body = None):
    """
    Get a list of submissions from the user's scraps folder.
    """
    r, n = (api := faapi.FAAPI(body.cookies_list() if body else None)).scraps(username.replace("_", ""), page)
    await sleep(api.crawl_delay)
    return {"results": r, "next": n or None}


@app.post("/favorites/{username}/{page}/",
          response_model=SubmissionsFolder, response_class=ORJSONResponse, tags=["users", "submissions"])
async def get_favorites(username: str, page: str, body: Body = None):
    """
    Get a list of submissions from the user's favorites folder.
    """
    r, n = (api := faapi.FAAPI(body.cookies_list() if body else None)).favorites(username.replace("_", ""), page)
    await sleep(api.crawl_delay)
    return {"results": r, "next": n or None}


@app.post("/journals/{username}/{page}/",
          response_model=JournalsFolder, response_class=ORJSONResponse, tags=["users", "journals"])
async def get_scraps(username: str, page: int, body: Body = None):
    """
    Get a list of journals from the user's journals folder.
    """
    r, n = (api := faapi.FAAPI(body.cookies_list() if body else None)).journals(username.replace("_", ""), page)
    await sleep(api.crawl_delay)
    return {"results": r, "next": n or None}
