from logging import Logger
from logging import getLogger
from time import sleep
from time import time
from typing import Optional

import faapi
from fastapi import FastAPI
from fastapi import Request
from fastapi.exceptions import HTTPException
from fastapi.responses import ORJSONResponse, RedirectResponse
from pydantic import BaseModel

from .__version__ import __version__
from .exceptions import DisallowedPath
from .exceptions import NotFound
from .exceptions import Unauthorized
from .models import Cookies
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


class IPList(BaseModel):
    ips: dict[str, float] = {}


logger: Logger = getLogger("uvicorn")

# noinspection PyUnresolvedReferences
faapi.connection.get_robots = lambda: robots
app: FastAPI = FastAPI(title="Fur Affinity API", version=__version__, openapi_tags=[
    {"name": "submissions", "description": "Get submissions"},
    {"name": "journals", "description": "Get journals"},
    {"name": "users", "description": "Get user information and folders"},
])
ip_list = IPList()

app.add_route("/", lambda r: RedirectResponse("/docs"), ["GET"])

faapi.Submission.__iter__ = serialise_submission
faapi.Journal.__iter__ = serialise_journal
faapi.UserPartial.__iter__ = serialise_user_partial
faapi.User.__iter__ = serialise_user


@app.exception_handler(HTTPException)
def handle_http_exception(_request: Request, err: HTTPException):
    return ORJSONResponse({"error": err.detail}, err.status_code)


@app.exception_handler(faapi.exceptions.NoticeMessage)
def handle_notice_message(_request: Request, err: faapi.exceptions.NoticeMessage):
    return handle_http_exception(_request, Unauthorized(401))


# noinspection PyUnresolvedReferences
@app.exception_handler(faapi.exceptions.ServerError)
def handle_server_error(_request: Request, _err: faapi.exceptions.ServerError):
    return handle_http_exception(_request, NotFound(404))


# noinspection PyUnresolvedReferences
@app.exception_handler(faapi.exceptions.DisallowedPath)
def handle_disallowed_path(_request: Request, _err: faapi.exceptions.ServerError):
    return handle_http_exception(_request, DisallowedPath(403))


def wait_ip(request: Request):
    t: float = time()
    d: Optional[float] = None
    if (last := ip_list.ips.get(ip := request.client.host, None)) and (d := t - last) < 1:
        sleep(d)
    ip_list.ips[ip] = time()
    logger.info(f"{ip} {t:.07f} {d}")


# noinspection GrazieInspection
@app.post("/submission/{submission_id}/",
          response_model=Submission, response_class=ORJSONResponse, tags=["submissions"])
def get_submission(request: Request, submission_id: int, cookies: Cookies):
    wait_ip(request)
    """
    Get a submission object. Public submissions can be queried without cookies.
    """
    return faapi.FAAPI(cookies.to_list() if cookies else None).get_submission(submission_id)[0]


@app.post("/journal/{journal_id}", response_model=Journal, response_class=ORJSONResponse, tags=["journals"])
def get_journal(request: Request, journal_id: int, cookies: Cookies):
    wait_ip(request)
    """
    Get a journal. Public journals can be queried without cookies.
    """
    return faapi.FAAPI(cookies.to_list() if cookies else None).get_journal(journal_id)


@app.post("/user/{username}/", response_model=User, response_class=ORJSONResponse, tags=["users"])
def get_user(request: Request, username: str, cookies: Cookies):
    wait_ip(request)
    """
    Get a username details, profile text, etc. The username may contain underscore (_) characters
    """
    return faapi.FAAPI(cookies.to_list() if cookies else None).get_user(username.replace("_", ""))


@app.post("/gallery/{username}/{page}/",
          response_model=SubmissionsFolder, response_class=ORJSONResponse, tags=["users", "submissions"])
def get_gallery(request: Request, username: str, page: int, cookies: Cookies):
    """
    Get a list of submissions from the user's gallery folder.
    """
    wait_ip(request)
    r, n = faapi.FAAPI(cookies.to_list() if cookies else None).gallery(username.replace("_", ""), page)
    return {"results": r, "next": n}


@app.post("/scraps/{username}/{page}/",
          response_model=SubmissionsFolder, response_class=ORJSONResponse, tags=["users", "submissions"])
def get_scraps(request: Request, username: str, page: int, cookies: Cookies):
    """
    Get a list of submissions from the user's scraps folder.
    """
    wait_ip(request)
    r, n = faapi.FAAPI(cookies.to_list() if cookies else None).scraps(username.replace("_", ""), page)
    return {"results": r, "next": n}


@app.post("/favorites/{username}/{page}/",
          response_model=SubmissionsFolder, response_class=ORJSONResponse, tags=["users", "submissions"])
def get_favorites(request: Request, username: str, page: str, cookies: Cookies):
    """
    Get a list of submissions from the user's favorites folder.
    """
    wait_ip(request)
    r, n = faapi.FAAPI(cookies.to_list() if cookies else None).favorites(username.replace("_", ""), page)
    return {"results": r, "next": n}


@app.post("/journals/{username}/{page}/",
          response_model=JournalsFolder, response_class=ORJSONResponse, tags=["users", "journals"])
def get_scraps(request: Request, username: str, page: int, cookies: Cookies):
    """
    Get a list of journals from the user's journals folder.
    """
    wait_ip(request)
    r, n = faapi.FAAPI(cookies.to_list() if cookies else None).journals(username.replace("_", ""), page)
    return {"results": r, "next": n}
