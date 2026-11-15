from fastapi import FastAPI, Cookie
from fastapi.requests import Request
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from http.cookies import CookieError, SimpleCookie

from typing_extensions import Annotated

import app.database_manager as database_manager

from app.api.endpoints.signals import signal_router
from app.api.endpoints.projects import project_router
from app.api.endpoints.users import user_router

app = FastAPI()
app.mount("/static", StaticFiles(directory='static'), name='static')
templates = Jinja2Templates(directory="templates")


# routing
app.include_router(signal_router, prefix="/api/signals")
app.include_router(project_router, prefix="/api/projects")
app.include_router(user_router, prefix="/api/users")


# -----------------------------------------------------------------------------



@app.middleware("http")
async def check_session_cookie_on_http_request(request: Request, callback) -> Response:
    """
    Let E = expired, S = set_cookie_enabled, G = set_cookie_good
    Let the lowercase letters be the negated versions of these variables


    expired or not + has set session cookie + is in database -> do nothing
    expired or not + has set session cookie + NOT in database -> delete the set cookie
    no set_cookie but expired session cookie from check -> delete the session cookie
    no set_cookie and no expired -> do nothing


    Truth table
    E S G
    1 1 1 0
    1 1 0 1
    1 0 1 1
    1 0 0 1
    0 1 1 0
    0 1 0 1
    0 0 1 0
    0 0 0 0
    """
    
    # boolean algebra
    # esg + esG + eSG + ESG
    # es + eSG + ESG
    # es + SG
    # negate
    # (E + S)(s + g)
    # Es + Eg + Ss + Sg
    # Es + Eg + Sg final answer for deletion

    expired: bool = False
    set_cookie_enabled: bool = False
    set_cookie_good: bool = False

    should_delete_cookie: bool = False
    session_id: str | None = request.cookies.get("session_id")
    session_info = database_manager.get_session_info_from_database(session_id=session_id)

    # the session cookie is not stored in the session database
    # so we simply mark the cookie as expired
    if session_info is None:
        # delete the cookie
        request.cookies.pop("session_id", None)
        expired = True

    response: Response = await callback(request)
    
    cookie = SimpleCookie()
    try:
        set_cookie_header = response.headers.get("set-cookie")

        if set_cookie_header is not None:
            cookie.load(set_cookie_header)
            response_session_id: str | None = (
                    cookie["session_id"].value if "session_id" in cookie
                    else None
                    )

            response_session_info = database_manager.get_session_info_from_database(session_id=response_session_id)

            if response_session_id is not None:
                set_cookie_enabled = True

            if response_session_info is not None:
                set_cookie_good = True

    except CookieError as e:
        print("cookie error", e)


    # Es + Eg + Sg final answer for deletion
    should_delete_cookie = expired and not set_cookie_enabled \
            or expired and not set_cookie_good \
            or set_cookie_enabled and not set_cookie_good

    # print(f"{expired=} {set_cookie_enabled=} {set_cookie_good=} {should_delete_cookie=}")

    if should_delete_cookie:
        print("timed out")
        response.delete_cookie("session_id")

    return response



# -----------------------------------------------------------------------------



@app.get("/")
def index(request: Request, session_id: Annotated[str | None, Cookie()] = None):
    # display the user's name at the top of the website
    username: str = "Signed out"

    if session_id is not None:
        session_info = database_manager.get_session_info_from_database(session_id=session_id)
        if session_info is not None:
            username = session_info.username

    return templates.TemplateResponse(
            request=request, 
            name='index.html', 
            context={"username": username})
