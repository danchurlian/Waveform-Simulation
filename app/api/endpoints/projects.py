from fastapi import APIRouter, Cookie, Form
from fastapi.responses import HTMLResponse

from app.models import FrequencyForm, HTMLString

import app.database_manager as database_manager
from app.database_manager import ProjectInfo

from typing_extensions import Annotated
import json

project_router = APIRouter()


# -----------------------------------------------------------------------------


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
            hx-delete="/api/projects/{project_info.project_id}"
            hx-target="closest .project-list-item"
            hx-swap="outerHTML"
        >Delete</button>
    </div>"""
    return content



@project_router.get("/", response_class=HTMLResponse)
def get_project_list(session_id: Annotated[str | None, Cookie()] = None) -> HTMLResponse:
    if session_id is None:
        return HTMLResponse(
                content="To load your previously saved projects, please <strong>login.</strong>", 
                status_code=200)

    session_info = database_manager.get_session_info_from_database(session_id=session_id)
    user_id = session_info.user_id if session_info is not None else None

    project_list: list[ProjectInfo] = database_manager.get_project_info_from_database(user_id)
    content: HTMLString = "You have no projects!"

    if len(project_list) > 0:
        content = ""
        for proj in project_list:
            content = "".join([content, load_project_info(proj)])

    return HTMLResponse(content=content, status_code=200)



@project_router.post("/", response_class=HTMLResponse)
def on_save(form: Annotated[FrequencyForm, Form()], 
            session_id: Annotated[str | None, Cookie()] = None) -> HTMLResponse:
    freq_list = []
    try:
        freq_list = [int(freq_str) for freq_str in form.freq_text]
    except ValueError:
        return HTMLResponse(content="Frequencies must be integers!", status_code=200)

    session_info = database_manager.get_session_info_from_database(session_id=session_id)
    user_id: int | None = session_info.user_id if session_info is not None else None
    if user_id is None:
        return HTMLResponse(content="Please login to save.", status_code=200)

    project_info = ProjectInfo(frequencies=freq_list, 
                               waveform=form.sig_type, 
                               title=form.title)

    save_success: bool = database_manager.save_project_info_to_database(user_id, project_info)
    if not save_success:
        return HTMLResponse(content="Save failed!", status_code=200)
    
    return HTMLResponse(content="Saved!", status_code=200)



@project_router.delete("/{project_id}")
def delete_project(project_id: str) -> HTMLResponse:
    delete_success = database_manager.delete_project_from_database(project_id)

    return HTMLResponse(content="", status_code=200) if delete_success \
            else HTMLResponse(content="delete failed", status_code=404)

