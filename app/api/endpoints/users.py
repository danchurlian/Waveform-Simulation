from fastapi import APIRouter, Form, Cookie
from fastapi.responses import HTMLResponse

from app.models import LoginForm, HTMLString, LoginUserAction

import app.database_manager as database_manager
from app.database_manager import AccountCreateResult, AccountLoginResult

import secrets

from typing_extensions import Annotated

user_router = APIRouter()



# -----------------------------------------------------------------------------



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

    if login_form.useraction == LoginUserAction.CREATE:
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

