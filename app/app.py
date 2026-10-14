from fastapi import FastAPI, APIRouter, Form, Cookie
from fastapi.requests import Request
from fastapi.responses import Response, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

import secrets
from http.cookies import CookieError, SimpleCookie

from typing_extensions import Annotated
from pydantic import BaseModel

import app.database_manager as database_manager
from app.database_manager import AccountLoginResult, AccountCreateResult

from app.api.endpoints.signals import signal_router
from app.api.endpoints.projects import project_router


app = FastAPI()
app.mount("/static", StaticFiles(directory='static'), name='static')
templates = Jinja2Templates(directory="templates")


# routing
app.include_router(signal_router, prefix="/api/signals")
app.include_router(project_router, prefix="/api/projects")

user_router = APIRouter()
app.include_router(user_router, prefix="/api/users")


# constants ----------------------------------------
type HTMLString = str

class FrequencyForm(BaseModel):
    freq_text: list[str]
    freq_slider: int
    sig_type: str
    title: str


class LoginForm(BaseModel):
    username: str
    # this is the raw password the user enters
    password: str
    useraction: str



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



def new_session_id() -> str:
    session_id = secrets.token_hex(8)
    return session_id



@user_router.post("/login")
def on_login(login_form: Annotated[LoginForm, Form()], 
             session_id: Annotated[str | None, Cookie()] = None) -> HTMLResponse:
    result: str = "Login failed."

    login_success: bool = False
    login_valid: bool = False
    create_session_success: bool = True
    the_new_session_id: str | None = None

    user_id: int | None = None

    if login_form.useraction == "create":
        create_result, new_user_id = database_manager.create_account(login_form.username, login_form.password)

        # generate result message and do actions based on create account result
        match create_result:
            case AccountCreateResult.SUCCESS:
                login_valid = True
                user_id = new_user_id
                result = "Created account"
            case AccountCreateResult.INVALID_USERNAME:
                result = f"Cannot use this username '{login_form.username}'!"
            case AccountCreateResult.INVALID_PASSWORD:
                result = f"Cannot use this password '{login_form.password}'!"
            case AccountCreateResult.ACCOUNT_EXISTS:
                result = f"{login_form.username} already exists!"
            case _:
                result = "Could not create account."

    else:
        login_result, new_user_id = database_manager.login_existing_account(login_form.username, login_form.password)

        # generate result message and do actions based on login account result
        match login_result:
            case AccountLoginResult.SUCCESS:
                user_id = new_user_id
                login_valid = True
                result = "Login success."
            case AccountLoginResult.WRONG_PASSWORD:
                result = "Incorrect password."
            case AccountLoginResult.NO_FOUND_USERNAME:
                result = f"Could not find username '{login_form.username}'."
            case _:
                result = "Login failed."


    # attempt to store session cookies, which checks if the user is logged in already
    # from another device / client
    # login valid --> session success --> success message
    if login_valid:
        the_new_session_id = new_session_id()

        try:
            database_manager.store_session_id_to_database(
                    session_id=the_new_session_id, 
                    user_id=user_id, 
                    username=login_form.username)

        except Exception as e:
            result = f"{login_form.username} is already logged in somewhere else!"
            print(f"storing session cookie failed, {e}")
            create_session_success = False
        if create_session_success and session_id is not None:
            database_manager.delete_session_id_from_database(session_id)

    login_success = login_valid and create_session_success

    # make the response object here 
    response = HTMLResponse(content=result, status_code=200)
    if login_success and the_new_session_id is not None:
        response.set_cookie(
                "session_id", 
                the_new_session_id, 
                httponly=True, 
                secure=True, 
                )

        result += f"<div id='user-label' hx-swap-oob='true'>{login_form.username}</div>"
        response.body = result.encode("utf-8")
        response.headers["content-length"] = str(len(response.body))

    return response



@user_router.get("/logout")
def logout(session_id: Annotated[str | None, Cookie()] = None):
    if session_id is not None:
        delete_success = database_manager.delete_session_id_from_database(session_id=session_id)
        print(f"{delete_success=}")

    responseHTML: HTMLString = "<div id='user-label' hx-swap-oob='true'>Signed out</div>"
    response = HTMLResponse(content=responseHTML, status_code=200)
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
