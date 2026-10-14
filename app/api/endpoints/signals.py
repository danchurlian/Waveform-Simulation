from fastapi import APIRouter, Form
from fastapi.responses import HTMLResponse

from typing_extensions import Annotated
import app.wavegen as wavegen

from pydantic import BaseModel


# ------------------------------------------------------------------------------


signal_router = APIRouter()
type HTMLString = str


class FrequencyForm(BaseModel):
    freq_text: list[str]
    freq_slider: int
    sig_type: str
    title: str


MAX_FREQUENCY_INPUT: int = 1000


# ------------------------------------------------------------------------------


def get_audio_tag(freqs: list[int], signal_type: str) -> HTMLString:
    datastr: str = wavegen.get_audio_from_freqs(freqs, signal_type)
    return f"<audio id='audio-output' controls type='audio/wav' src='data:audio/wav;base64,{datastr}' />"



@signal_router.post("/audio", response_class=HTMLResponse)
def new_audio_main(data: Annotated[FrequencyForm, Form()]):
    # TODO: check if this is the right error handling strategy for HTMX
    freqs = []
    try:
        freqs = [int(freq) for freq in data.freq_text]
    except ValueError:
        print("something went wrong")
        return HTMLResponse(content="One of the frequencies is not an integer!",
                            status_code=400)

    # Check for negative numbers
    for freq in freqs:
        if freq < 0:
            return HTMLResponse(content = f"The frequency {freq} cannot be negative!",
                                status_code=400)

    return HTMLResponse(
            content=get_audio_tag(freqs, data.sig_type), 
            status_code=200)



@signal_router.post("/graphs", response_class=HTMLResponse)
def new_image_main(data: Annotated[FrequencyForm, Form()]):
    # setup error message div and setup result variable
    error_msg: str = f"Frequency must be <= {MAX_FREQUENCY_INPUT}!"
    error_msg_div: HTMLString = f"<div id='error-message' hx-swap-oob='true'>{error_msg}</div>"
    response: HTMLString = error_msg_div + "\n<img id='plot-image-load' style='display: none' src='data:image/png;base64,'/>"

    freq: int = data.freq_slider
    # TODO: add some error handling to this
    freqs: list[int] = [int(freq) for freq in data.freq_text]

    if freq is not None and abs(freq) <= MAX_FREQUENCY_INPUT:
        # if there is only one frequency, display equation information.
        # if there is a list of frequencies, do not display equation information.
        plot_image_html = f"<div id='plot-image-load'>{wavegen.get_image_svg_from_freqs(freqs, data.sig_type)}</div>"
        equation_list_html = wavegen.generate_equation_list_html(freqs, data.sig_type)

        # final response HTML that is returned
        response = f""" 
<div id='error-message' hx-swap-oob='true'></div> 
{plot_image_html}
{equation_list_html}
""" 
    return HTMLResponse(content=response, status_code=200)
