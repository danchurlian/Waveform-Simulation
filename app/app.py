from fastapi import FastAPI, Form 
from fastapi.requests import Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

import sqlalchemy
import dotenv

import io
import base64
import json
import latex2mathml.converter

from typing_extensions import Annotated
from pydantic import BaseModel

import numpy as np
from scipy.io import wavfile

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


env_values = dotenv.dotenv_values(".env")
engine = sqlalchemy.create_engine(env_values["DATABASE_URL"])

app = FastAPI()
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


class ProjectInfo:
    frequencies: list[int]
    waveform: str
    title: str

    def __init__(self, frequencies: list[int] = [],
                 waveform: str = "",
                 title: str = "Unnamed"):
        self.frequencies = frequencies
        self.waveform = waveform
        self.title = title
        


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




# waveform formulas --------------------------------
def sin_wave(ts: np.ndarray, freq: int = 1):
    return np.sin(2 * np.pi * freq * ts)


def sawtooth_wave(ts: np.ndarray, freq: int = 1):
    return 2 * ((freq * ts - 1/2) - np.floor(freq * ts - 1/2) - 1/2)


def triangle_wave(ts: np.ndarray, freq: int = 1):
    return 4 * (np.abs((freq * ts - 1/2) - np.floor(freq * ts - 1/2) - 1/2) - 1/4)


def square_wave(ts: np.ndarray, freq: int = 1):
    return np.sign(np.sin(2 * np.pi * freq * ts))


# ---------------------------------------------------------------

JUMP_TABLE: dict = {
    "Sine Wave": sin_wave,
    "Triangle Wave": triangle_wave,
    "Sawtooth Wave": sawtooth_wave,  
    "Square Wave": square_wave,
}

WAVEFORM_EQS: dict = {
    "Sine Wave": {
        "eq_og": "\\sin({2 \\pi f t})",
        "eq_series": "\\sin({2 \\pi f t})",
    },

    "Sawtooth Wave": {
        "eq_og": "2( f t - \\lfloor f t \\rfloor - \\frac{1}{2})",
        "eq_series": "\\sin({2\\pi f t}) - \\frac{1}{2}\\sin({2\\pi 2 f t}) + \\frac{1}{3}\\sin({2\\pi 3 f t}) + ...",
    },

    "Triangle Wave": {
        "eq_og": "4(| f t - \\lfloor f t \\rfloor - \\frac{1}{2}| - \\frac{1}{4})",
        "eq_series": "\\sin({2\\pi f t}) - \\frac{1}{9}sin({2\\pi 3 f t}) + \\frac{1}{25}sin({2\\pi 5 f t}) + ...",
    },
    "Square Wave": {
        "eq_og": "\\text{sgn}({\\sin({2\\pi f t})})",
        "eq_series": "\\sin(2\\pi f t) + \\frac{1}{3}sin(2\\pi 3 f t) + \\frac{1}{5}\\sin(2\\pi 5 f t) + ..."
    },
}


# ---------------------------------------------------------------


def get_project_info_from_database(user_id: int) -> list[ProjectInfo]:
    assert user_id is not None, "user id is not given!"
    res = []

    with engine.begin() as conn:
        query_result = conn.execute(sqlalchemy.text("SELECT frequencies, project_name, waveform FROM project WHERE user_id=1;"))
        print(query_result)
        for row in query_result:
            res.append(ProjectInfo(frequencies=row.frequencies, waveform=row.waveform, title=row.project_name))

    return res


def load_project_info(project_info: ProjectInfo) -> HTMLString:
    content: HTMLString = f"""<div>
    <span></span>
    <span>"{project_info.title}": {str(project_info.frequencies)}</span>
    <button 
        commandfor="load-projects-dialog" 
        command="close"
        data-title="{project_info.title}"
        data-waveform="{project_info.waveform}"
        data-freqs="{json.dumps(project_info.frequencies)}"
        onclick="loadProject(event.target)"
        >
        Load
    </button>
    </div>"""
    return content


@app.get("/projects", response_class=HTMLResponse)
def get_project_list() -> HTMLResponse:
    project_list: list[ProjectInfo] = get_project_info_from_database(1)
    test_project = ProjectInfo(
            frequencies=[440, 554, 660, 880],
            title="A Major Chord",
            waveform="Sawtooth Wave"
            )
    project_list.append(test_project)
    print(project_list)
    content: HTMLString = ""

    for proj in project_list:
        content = "".join([content, load_project_info(proj)])

    return HTMLResponse(content=content, status_code=200)


# ---------------------------------------------------------------


def get_numpy_data(freq: int, waveform: str):
    ts: np.ndarray = np.linspace(0, 2, SAMPLING_RATE * 2)
    ys: np.ndarray = JUMP_TABLE[waveform](ts, freq=freq)
    return ts, ys


def chord(freq_list: list[int], waveform: str) -> np.ndarray:
    final_ys: np.ndarray = np.zeros(SAMPLING_RATE * 2)
    for freq in freq_list:
        __, ys = get_numpy_data(freq, waveform)
        final_ys += ys

    ys_max = np.max(final_ys)
    ys_min = np.min(final_ys)

    return 2 * ((final_ys - ys_min) / (ys_max - ys_min))  - 1




def get_audio_tag(ys: np.ndarray) -> HTMLString:
    ys = (32767 * ys).astype('int16')
    # use scipy to write to an io.BytesIO
    stream: io.BytesIO = io.BytesIO()
    wavfile.write(stream, SAMPLING_RATE, ys)
    # write an audio tag and use the data type attribute and base64 encoding
    datastr: str = base64.b64encode(stream.getbuffer()).decode("ascii")
    return f"<audio id='audio-output' controls type='audio/wav' src='data:audio/wav;base64,{datastr}' />"



@app.get("/test-chord", response_class=HTMLResponse)
def test_chord():
    freq_list: list = [220, 440, 523, 659, 880]
    ys = chord(freq_list, "Square Wave")
    return HTMLResponse(content=get_audio_tag(ys), status_code=200)




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

    ys = chord(freqs, waveform=data.sig_type)
    return HTMLResponse(content=get_audio_tag(ys), status_code=200)




def image(ts: np.ndarray, ys: np.ndarray):
    fs: np.ndarray = np.fft.rfftfreq(ys.size, d=1/SAMPLING_RATE)
    hs: np.ndarray = np.abs(np.fft.rfft(ys))
    # Make 2 subplots, top is the signal plot, bottom is the spectrum plot
    fig, axes = plt.subplots(2)
    axes[0].plot(ts, ys)
    axes[0].set_title("Signal")
    axes[1].plot(fs, hs)
    axes[1].set_title("Spectrum")

    fig.tight_layout()

    buffer = io.BytesIO()
    # Save IO and into base64
    fig.savefig(buffer, format='png')
    plt.close(fig)
    # Then return the data as an image tag
    data: str = base64.b64encode(buffer.getbuffer()).decode('ascii')
    return f"<img id='plot-image-load' style='display: none' src='data:image/png;base64,{data}'/>"




@app.post("/image", response_class=HTMLResponse)
def new_image_main(data: Annotated[FrequencyForm, Form()]):
    error_msg: str = f"Frequency must be <= {MAX_FREQUENCY_INPUT}!"

    freq: int = data.freq_slider
    # add some error handling to this
    freqs: list[int] = [int(freq) for freq in data.freq_text]

    # for text input only
    # if int, cast it, else if a decimal, round it down and cast to int, else error message
    """
    try:
        freq = int(float(data.freq_text))
    except ValueError:
        error_msg = "Frequency must be a number!"
    """


    # setup error message div and setup result variable
    error_msg_div: str = f"<div id='error-message' hx-swap-oob='true'>{error_msg}</div>"

    response: str = error_msg_div + "\n<img id='plot-image-load' style='display: none' src='data:image/png;base64,'/>"


    if freq is not None and abs(freq) <= MAX_FREQUENCY_INPUT:

        # Calculate and sample the signal, generate plots
        ts: np.ndarray = np.linspace(0, 2, SAMPLING_RATE * 2)
        ys: np.ndarray = chord(freqs, data.sig_type)
        # ys: np.ndarray = JUMP_TABLE[data.sig_type](ts, freq=freq)
        imgtag: str = image(ts, ys)

        # math formulas, using MathML
        eq_original: str = "No object" 
        eq_series: str = "No object" 

        assert data.sig_type in WAVEFORM_EQS, f"Signal type {data.sig_type} is not known!"
        assert "eq_og"in WAVEFORM_EQS[data.sig_type], f"Original equations is not found for {data.sig_type}!"
        assert "eq_series" in WAVEFORM_EQS[data.sig_type], f"Fourier series expansion is not found for {data.sig_type}!"



        # if there is only one frequency, display equation information.
        # if there is a list of frequencies, do not display equation information.
        equation_list_html: HTMLString = "<ul id='equation-list' hx-swap-oob='true' style='display: none; padding: 1rem 0 0 1rem'>"

        if (len(freqs) == 1):
            # Format the equations
            # assign variables the strings
            eq_og_template: str = WAVEFORM_EQS[data.sig_type]["eq_og"]
            eq_series_template: str = WAVEFORM_EQS[data.sig_type]["eq_series"]

            eq_original: str = eq_og_template.replace(" f ", f"({freq})")
            eq_series: str = eq_series_template.replace(" f ", f"({freq})")

            # convert each expression to MathML
            eq_og_template = latex2mathml.converter.convert(eq_og_template)
            eq_series_template = latex2mathml.converter.convert(eq_series_template)

            eq_original = latex2mathml.converter.convert(eq_original)
            eq_series = latex2mathml.converter.convert(eq_series)

            # assembly the HTML content
            equation_list_html = f"""
<ul id='equation-list' hx-swap-oob='true' style='padding: 1rem 0 0 1rem'>
    <li>
        <eq-label id='freq-label'>Chosen frequency:</eq-label> 
        {freq} Hz
    </li>
    <li>
        <eq-label>Original equation formula:</eq-label> 
        {eq_og_template}
    </li>
    <li> 
        <eq-label>Original equation:</eq-label>
        {eq_original}
    </li>
    <li>
        <eq-label>Fourier expansion formula:</eq-label>
        {eq_series_template}
    </li>
    <li> 
        <eq-label>Fourier expansion:</eq-label>
        {eq_series}
    </li>
</ul>
"""

        # final response HTML that is returned
        response = f""" 
<div id='error-message' hx-swap-oob='true'></div> 
{imgtag}
{equation_list_html}
""" 

    return HTMLResponse(content=response, status_code=200)
    


@app.get("/")
def index(request: Request):
    return templates.TemplateResponse(request=request, name='index.html')
