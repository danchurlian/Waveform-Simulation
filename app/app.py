from contextlib import asynccontextmanager
from types import NoneType

from fastapi import FastAPI, Form, Cookie
from fastapi.requests import Request
from fastapi.responses import Response, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

import sqlalchemy
from sqlalchemy.ext.asyncio import create_async_engine \
        as create_async_sql_engine
import dotenv
import bcrypt

import asyncio
import io
import os
import base64
import secrets
import uuid
import json
import datetime as dt
from http.cookies import CookieError, SimpleCookie

from typing_extensions import Annotated
from pydantic import BaseModel
from dataclasses import dataclass

import numpy as np
from scipy.io import wavfile

import matplotlib
matplotlib.use("Agg")


import app.wavegen as wavegen


# load the database
dotenv.load_dotenv()
DB_USER: str = os.getenv("POSTGRES_USER")
DB_PASSWORD: str = os.getenv("POSTGRES_PASSWORD")
DB_HOST: str = os.getenv("POSTGRES_HOST")
DB_PORT: str = os.getenv("POSTGRES_PORT")
DB_NAME: str = os.getenv("DB_NAME")

sql_engine = sqlalchemy.create_engine(
        os.getenv("DATABASE_URL"),
        poolclass=sqlalchemy.NullPool,
        )

async_sql_engine = create_async_sql_engine(
        f"postgresql+asyncpg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}",
        poolclass=sqlalchemy.NullPool,
        connect_args={"command_timeout": 5}
        )

sql_metadata = sqlalchemy.MetaData()
user_db_table = sqlalchemy.Table("user_table", sql_metadata, autoload_with=sql_engine)
project_db_table = sqlalchemy.Table("project", sql_metadata, autoload_with=sql_engine)
session_db_table = sqlalchemy.Table("session", sql_metadata, autoload_with=sql_engine)


@asynccontextmanager
async def lifespan(app: FastAPI):
    session_cleanup_task = asyncio.create_task(session_cleanup_loop())

    yield

    session_cleanup_task.cancel()


app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory='static'), name='static')
templates = Jinja2Templates(directory="templates")

# constants ----------------------------------------
SAMPLING_RATE: int = 44100
MAX_FREQUENCY_INPUT: int = 1000

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


class ProjectInfo:
    frequencies: list[int]
    waveform: str
    title: str
    project_id: uuid.UUID

    def __init__(self, frequencies: list[int] = [],
                 waveform: str = "",
                 title: str = "Unnamed",
                 project_id: uuid.UUID = uuid.uuid4()):
        self.frequencies = frequencies
        self.waveform = waveform
        self.title = title
        self.project_id = project_id


    def __str__(self) -> str:
        return f"<ProjectInfo '{self.title}' {self.waveform} {self.frequencies}>"
        

# -----------------------------------------------------------------------------

@dataclass(frozen=True)
class SessionInfo:
    username: str
    user_id: int

SESSION_INACTIVITY_TIMEOUT = dt.timedelta(minutes = 30)
SESSION_CLEANUP_INTERVAL_MINS: float = 10 * 1 / 60


# -----------------------------------------------------------------------------

# Audio generation exception when clicking the listen button with
# invalid data
class AudioGenerationException(Exception):
    def __init__(self, detail: str):
        self.detail = detail
        super().__init__(detail)
        pass

@app.exception_handler(AudioGenerationException)
async def audio_exception_handler(_request, exc):
    return HTMLResponse(content=f"<div id='audio-output'>{exc.detail}</div>", status_code=400) 


# waveform formulas -----------------------------------------------------------
def sin_wave(ts: np.ndarray, freq: int = 1):
    return np.sin(2 * np.pi * freq * ts)


def sawtooth_wave(ts: np.ndarray, freq: int = 1):
    return 2 * ((freq * ts - 1/2) - np.floor(freq * ts - 1/2) - 1/2)


def triangle_wave(ts: np.ndarray, freq: int = 1):
    return 4 * (np.abs((freq * ts - 1/2) - np.floor(freq * ts - 1/2) - 1/2) - 1/4)


def square_wave(ts: np.ndarray, freq: int = 1):
    return np.sign(np.sin(2 * np.pi * freq * ts))


# -----------------------------------------------------------------------------


def get_project_info_from_database(user_id: int | None) -> list[ProjectInfo]:
    res = []
    if user_id is not None:
        with sql_engine.begin() as conn:
            stmt = (
                    sqlalchemy.select(project_db_table)
                    .where(project_db_table.c.user_id == user_id)
                    )

            query_result = conn.execute(stmt)
            res = [ProjectInfo(frequencies=row.frequencies, 
                                       waveform=row.waveform,
                                       title=row.project_name,
                                       project_id=row.project_id)

                   for row in query_result]

    return res


def save_project_info_to_database(user_id: int, project_info: ProjectInfo) -> bool:
    res: bool = True

    with sql_engine.begin() as conn:
        user_row = conn.execute(
                    sqlalchemy.select(user_db_table)
                    .where(user_db_table.c.user_id == user_id)
                ).first()

        if user_row is None:
            return False

        # check if the project already exists
        existing_project_row = conn.execute(
                sqlalchemy.select(project_db_table.c.project_name, project_db_table.c.project_id) \
                        .where(project_db_table.c.project_name == project_info.title \
                                and project_db_table.c.user_id == user_id
                               )
                ).first()

        existing_id: int | NoneType = None
        if existing_project_row is not None:
            existing_id = existing_project_row.project_id

        if existing_id is None:
            # create a new entry 
            stmt = sqlalchemy.insert(project_db_table) \
                    .values(
                        project_name=project_info.title,
                        frequencies=project_info.frequencies,
                        waveform=project_info.waveform,
                        user_id=user_id
                    )
            conn.execute(stmt)

        elif existing_id:
            # update the existing entry
            stmt = sqlalchemy.update(project_db_table) \
                    .where(project_db_table.c.project_id == existing_id) \
                    .values(
                        project_name=project_info.title,
                        frequencies=project_info.frequencies,
                        waveform=project_info.waveform,
                        user_id=user_id
                    )
            conn.execute(stmt)

        else:
            # saving failed for some reason
            print("Saving error")
            res = False

    return res


@app.post("/save", response_class=HTMLResponse)
def on_save(form: Annotated[FrequencyForm, Form()], session_id: Annotated[str | None, Cookie()] = None) -> HTMLResponse:
    freq_list: list[int] = []
    try:
        freq_list = [int(freq_str) for freq_str in form.freq_text]
    except ValueError:
        return HTMLResponse(content="Frequencies must be integers!", status_code=200)

    session_info = get_session_info_from_database(session_id=session_id)
    user_id: int | None = session_info.user_id if session_info is not None else None
    if user_id is None:
        return HTMLResponse(content="Please login to save.", status_code=200)

    project_info = ProjectInfo(frequencies=freq_list, 
                               waveform=form.sig_type, 
                               title=form.title)

    save_success: bool = save_project_info_to_database(user_id, project_info)
    if not save_success:
        return HTMLResponse(content="Save failed!", status_code=200)
    
    return HTMLResponse(content="Saved!", status_code=200)


def load_project_info(project_info: ProjectInfo) -> HTMLString:
    content: HTMLString = f"""
    <div class="project-list-item">
        <span class="project-list-item-info">
            "{project_info.title}": {str(project_info.frequencies)}
        </span>
        <button 
            class="project-list-item-load"
            commandfor="load-projects-dialog" 
            command="close"
            data-title="{project_info.title}"
            data-waveform="{project_info.waveform}"
            data-project-id="{project_info.project_id}"
            data-freqs="{json.dumps(project_info.frequencies)}"
            onclick="loadProject(event.target)"
            >
            Load
        </button>

        <button class="project-list-item-delete"
            hx-delete="/projects/{project_info.project_id}"
            hx-target="closest .project-list-item"
            hx-swap="outerHTML"
        >Delete</button>
    </div>"""
    return content



@app.get("/projects", response_class=HTMLResponse)
def get_project_list(session_id: Annotated[str | None, Cookie()] = None) -> HTMLResponse:
    if session_id is None:
        return HTMLResponse(content="To load your previously saved projects, please <strong>login.</strong>", status_code=200)

    session_info = get_session_info_from_database(session_id=session_id)
    user_id = session_info.user_id if session_info is not None else None

    project_list: list[ProjectInfo] = get_project_info_from_database(user_id)
    content: HTMLString = "You have no projects!"

    if len(project_list) > 0:
        content = ""
        for proj in project_list:
            content = "".join([content, load_project_info(proj)])

    return HTMLResponse(content=content, status_code=200)



@app.delete("/projects/{project_id}")
def delete_project(project_id: str) -> HTMLResponse:
    where_clause = project_db_table.c.project_id == uuid.UUID(project_id)
    can_delete: bool = True

    with sql_engine.connect() as conn:
        # test out the delete statement first before committing
        delete_stmt = (
                sqlalchemy.delete(project_db_table)
                .where(where_clause)
        )
        delete_result = conn.execute(delete_stmt)

        if delete_result.rowcount != 1:
            can_delete = False
            if delete_result.rowcount > 1:
                print(f"deleting {project_id} will result in too many entries being removed.")
            else:
                print(f"{project_id} not found!")

        if can_delete:
            conn.commit()
            

    return HTMLResponse(content="", status_code=200) if can_delete \
            else HTMLResponse(content="delete failed", status_code=404)


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
    session_info = get_session_info_from_database(session_id=session_id)

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

            response_session_info = get_session_info_from_database(session_id=response_session_id)

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


async def session_cleanup_old() -> None: 
    now_time = dt.datetime.now(dt.timezone.utc)
    base_time = now_time - SESSION_INACTIVITY_TIMEOUT

    try:
        async with async_sql_engine.begin() as conn:
            result = await conn.execute(
                    sqlalchemy.delete(session_db_table)
                    .where(session_db_table.c.last_interacted < base_time)
                    )
            if result.rowcount > 0:
                print("deleted an old session")

    except asyncio.CancelledError as e:
        print(e)
       

# must be called by a lifespan function defined by FastAPI
async def session_cleanup_loop():
    # we will have to use async version of sqlalchemy
    print("cleanup loop")
    while True:
        await asyncio.sleep(SESSION_CLEANUP_INTERVAL_MINS * 60)
        await session_cleanup_old()


def get_session_info_from_database(user_id: int | None = None, 
                                   session_id: str | None = None) -> SessionInfo | None:
    session_info = None
    if user_id is not None or session_id is not None:
        with sql_engine.begin() as conn:
            result = conn.execute(
                    sqlalchemy.select(session_db_table)
                    .where(sqlalchemy.or_(
                        session_db_table.c.user_id == user_id,
                        session_db_table.c.session_id == session_id
                        )
                    )
                    ).first()

            if result is not None:
                session_info = SessionInfo(user_id=result.user_id, username=result.username)
    return session_info


def store_session_id_to_database(session_id: str, user_id: int, username: str) -> bool:
    # create time here
    create_time = dt.datetime.now(dt.timezone.utc)
    # store it in database, seems like in database it stores the time and not the date

    success: bool = False
    with sql_engine.begin() as conn:
        result = conn.execute(
                sqlalchemy.insert(session_db_table)
                .values(session_id=session_id, user_id=user_id, username=username,
                        created=create_time, last_interacted=create_time)
                )
        success = result.rowcount > 0

    return success


def delete_session_id_from_database(session_id: str) -> bool:
    success: bool = False
    with sql_engine.begin() as conn:
        result = conn.execute(
                sqlalchemy.delete(session_db_table)
                .where(session_db_table.c.session_id == session_id)
                )
        success = result.rowcount > 0

    return success


# does not determine if username already exists
def is_valid_username(username: str) -> bool:
    if " " in username:
        return False

    BLACKLISTED_USERNAMES: set = {""}
    if username in BLACKLISTED_USERNAMES:
        return False

    return True


def is_valid_password(password: str) -> bool:
    if len(password) == 0:
        return False

    if " " in password:
        return False

    return True


@app.post("/login")
def on_login(login_form: Annotated[LoginForm, Form()], session_id: Annotated[str | None, Cookie()] = None) -> HTMLResponse:
    result: str = "Login failed."

    login_success: bool = False
    login_valid: bool = False
    create_session_success: bool = True
    the_new_session_id: str | None = None

    user_id: int | None = None

    if login_form.useraction == "create":
        if not is_valid_username(login_form.username):
            result = f"Cannot use this username '{login_form.username}'!"
        elif not is_valid_password(login_form.password):
            result = f"Cannot use this password '{login_form.password}'!"
        else:
            # store the hashed password into the database
            salt = bcrypt.gensalt()
            hashed: bytes = bcrypt.hashpw(login_form.password.encode("utf-8"), salt)
            hashed_pw: str = hashed.decode("utf-8")
            
            result = "Failed to create account"

            with sql_engine.begin() as conn:
                # enter the password for the user
                existing_user_row = conn.execute(
                    sqlalchemy.select(user_db_table)
                    .where(user_db_table.c.username == login_form.username)
                    ).first()

                if existing_user_row is None:
                    # create the account
                    insert_result = conn.execute(
                        sqlalchemy.insert(user_db_table)
                        .values(username=login_form.username, password=hashed_pw)
                    )
                    user_id = insert_result.inserted_primary_key[0]
                    result = "created account"
                    login_valid = True
                else:
                    result = f"{login_form.username} already exists!"

    else:
        # compare in database
        with sql_engine.begin() as conn:
            user_search_stmt = (
                    sqlalchemy.select(user_db_table)
                    .where(user_db_table.c.username == login_form.username)
                    )
            user_row = conn.execute(user_search_stmt).first()
            if user_row is not None:
                if bcrypt.checkpw(login_form.password.encode("utf-8"), user_row.password.encode("utf-8")):
                    result = "Login success."
                    user_id = user_row.user_id
                    login_valid = True
                else:
                    result = "Incorrect password."
            else:
                result = "Username does not exist."


    # attempt to store session cookies, which checks if the user is logged in already
    # from another device / client
    # login valid --> session success --> success message
    if login_valid:
        the_new_session_id = new_session_id()

        try:
            store_session_id_to_database(session_id=the_new_session_id, user_id=user_id, username=login_form.username)
        except Exception as e:
            result = f"{login_form.username} is already logged in somewhere else!"
            print(f"storing session cookie failed, {e}")
            create_session_success = False

        if create_session_success and session_id is not None:
            delete_session_id_from_database(session_id)

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



@app.get("/logout")
def logout(session_id: Annotated[str | None, Cookie()] = None):
    if session_id is not None:
        delete_success = delete_session_id_from_database(session_id=session_id)
        print(f"{delete_success=}")

    responseHTML: HTMLString = "<div id='user-label' hx-swap-oob='true'>Signed out</div>"
    response = HTMLResponse(content=responseHTML, status_code=200)
    response.delete_cookie("session_id")
    return response


# -----------------------------------------------------------------------------


def get_audio_tag(ys: np.ndarray) -> HTMLString:
    ys = (32767 * ys).astype('int16')
    # use scipy to write to an io.BytesIO
    stream: io.BytesIO = io.BytesIO()
    wavfile.write(stream, SAMPLING_RATE, ys)
    # write an audio tag and use the data type attribute and base64 encoding
    datastr: str = base64.b64encode(stream.getbuffer()).decode("ascii")
    return f"<audio id='audio-output' controls type='audio/wav' src='data:audio/wav;base64,{datastr}' />"



@app.post("/audio", response_class=HTMLResponse)
def new_audio_main(data: Annotated[FrequencyForm, Form()]):
    try:
        freqs: list[int] = [int(freq) for freq in data.freq_text]
    except ValueError:
        raise AudioGenerationException(detail="One of the frequencies is not an integer!")

    # Check for negative numbers
    for freq in freqs:
        if freq < 0:
            raise AudioGenerationException(detail=f"The frequency {freq} cannot be negative!")

    ys = wavegen.get_total_signal_data(freqs, waveform=data.sig_type)
    return HTMLResponse(content=get_audio_tag(ys), status_code=200)



@app.post("/image", response_class=HTMLResponse)
def new_image_main(data: Annotated[FrequencyForm, Form()]):
    # setup error message div and setup result variable
    error_msg: str = f"Frequency must be <= {MAX_FREQUENCY_INPUT}!"
    error_msg_div: str = f"<div id='error-message' hx-swap-oob='true'>{error_msg}</div>"
    response: str = error_msg_div + "\n<img id='plot-image-load' style='display: none' src='data:image/png;base64,'/>"

    freq: int = data.freq_slider
    # add some error handling to this
    freqs: list[int] = [int(freq) for freq in data.freq_text]

    if freq is not None and abs(freq) <= MAX_FREQUENCY_INPUT:
        # Calculate and sample the signal, generate plots
        ts: np.ndarray = np.linspace(0, 2, SAMPLING_RATE * 2)
        ys: np.ndarray = wavegen.get_total_signal_data(freqs, data.sig_type)

        imgtag: str = wavegen.generate_image(ts, ys)

        # if there is only one frequency, display equation information.
        # if there is a list of frequencies, do not display equation information.
        equation_list_html = wavegen.generate_equation_list_html(freqs, data.sig_type)

        # final response HTML that is returned
        response = f""" 
<div id='error-message' hx-swap-oob='true'></div> 
{imgtag}
{equation_list_html}
""" 
    return HTMLResponse(content=response, status_code=200)
    

@app.get("/")
def index(request: Request, session_id: Annotated[str | None, Cookie()] = None):
    # display the user's name at the top of the website
    username: str = "Signed out"

    if session_id is not None:
        session_info = get_session_info_from_database(session_id=session_id)
        if session_info is not None:
            username = session_info.username

    return templates.TemplateResponse(
            request=request, 
            name='index.html', 
            context={"username": username})
