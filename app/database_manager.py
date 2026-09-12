import sqlalchemy
import dotenv
import os
import datetime as dt
import uuid
import bcrypt

from dataclasses import dataclass
from enum import Enum, auto

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

sql_metadata = sqlalchemy.MetaData()
user_db_table = sqlalchemy.Table("user_table", sql_metadata, autoload_with=sql_engine)
project_db_table = sqlalchemy.Table("project", sql_metadata, autoload_with=sql_engine)
session_db_table = sqlalchemy.Table("session", sql_metadata, autoload_with=sql_engine)

SESSION_INACTIVITY_TIMEOUT = dt.timedelta(minutes = 30)
SESSION_CLEANUP_INTERVAL_MINS: float = 10 * 1 / 60


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


@dataclass(frozen=True)
class SessionInfo:
    username: str
    user_id: int

    def __str__(self) -> str:
        return f"<ProjectInfo '{self.title}' {self.waveform} {self.frequencies}>"


class AccountCreateResult(Enum):
    SUCCESS = auto()
    INVALID_USERNAME = auto()
    INVALID_PASSWORD = auto()
    ACCOUNT_EXISTS = auto()
    GENERAL_FAIL = auto()


class AccountLoginResult(Enum):
    SUCCESS = auto()
    WRONG_PASSWORD = auto()
    NO_FOUND_USERNAME = auto()
    GENERAL_FAIL = auto()


# -----------------------------------------------------------------------------


def get_project_info_from_database(user_id: int | None) -> list[ProjectInfo]:
    print("getting project info from new module")
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
    print("saving in new module")
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


def delete_project_from_database(project_id: str) -> bool:
    print(f"deleting {project_id=} from new module")

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

    return can_delete



# -----------------------------------------------------------------------------


def session_cleanup_old() -> None: 
    print('calling inside database_manager module')
    now_time = dt.datetime.now(dt.timezone.utc)
    base_time = now_time - SESSION_INACTIVITY_TIMEOUT

    with sql_engine.begin() as conn:
        result = conn.execute(
                sqlalchemy.delete(session_db_table)
                .where(session_db_table.c.last_interacted < base_time)
                )
        if result.rowcount > 0:
            print("deleted an old session")



def get_session_info_from_database(user_id: int | None = None, 
                                   session_id: str | None = None) -> SessionInfo | None:
    print("getting session info from new module")
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
    print("storing session info from new module")

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
    print("deleting session id from new module")
    success: bool = False
    with sql_engine.begin() as conn:
        result = conn.execute(
                sqlalchemy.delete(session_db_table)
                .where(session_db_table.c.session_id == session_id)
                )
        success = result.rowcount > 0

    return success




# -----------------------------------------------------------------------------


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


def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    hashed: bytes = bcrypt.hashpw(password.encode("utf-8"), salt)
    new_hashed_pw: str = hashed.decode("utf-8")
    return new_hashed_pw


def create_account(new_username: str, new_pw: str) -> tuple[AccountCreateResult, int | None]:
    res = AccountCreateResult.GENERAL_FAIL
    user_id: int | None = None

    if not is_valid_username(new_username):
        res = AccountCreateResult.INVALID_USERNAME
    elif not is_valid_password(new_pw):
        res = AccountCreateResult.INVALID_PASSWORD
    else:
        new_hashed_pw: str = hash_password(new_pw)

        with sql_engine.begin() as conn:
            # enter the password for the user
            existing_user_row = conn.execute(
                sqlalchemy.select(user_db_table)
                .where(user_db_table.c.username == new_username)
                ).first()

            if existing_user_row is None:
                # create the account
                insert_result = conn.execute(
                    sqlalchemy.insert(user_db_table)
                    .values(username=new_username, password=new_hashed_pw)
                )
                user_id = insert_result.inserted_primary_key[0]
                res = AccountCreateResult.SUCCESS
            else:
                res = AccountCreateResult.ACCOUNT_EXISTS

    return res, user_id


def login_existing_account(username: str, password: str) -> tuple[AccountLoginResult, int | None]:
    # compare in database
    user_id: int | None = None
    res = AccountLoginResult.GENERAL_FAIL
 
    with sql_engine.begin() as conn:
        user_search_stmt = (
                sqlalchemy.select(user_db_table)
                .where(user_db_table.c.username == username)
                )
        user_row = conn.execute(user_search_stmt).first()
        if user_row is not None:
            if bcrypt.checkpw(password.encode("utf-8"), user_row.password.encode("utf-8")):
                res = AccountLoginResult.SUCCESS
                user_id = user_row.user_id
            else:
                res = AccountLoginResult.WRONG_PASSWORD
        else:
            res = AccountLoginResult.NO_FOUND_USERNAME

    return res, user_id
