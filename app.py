from fastapi import FastAPI, Form
from fastapi.requests import Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

import io
import base64
import latex2mathml.converter

from typing_extensions import Annotated
from pydantic import BaseModel

import numpy as np
from scipy.io import wavfile

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

app = FastAPI()
app.mount("/static", StaticFiles(directory='static'), name='static')
templates = Jinja2Templates(directory="templates")

# constants ----------------------------------------
SAMPLING_RATE: int = 44100
MAX_FREQUENCY_INPUT: int = 1000


class FrequencyForm(BaseModel):
    freq_text: int | None
    freq_slider: int
    sig_type: str


# waveform formulas --------------------------------
def sin_wave(ts: np.ndarray, freq: int = 1):
    return np.sin(2 * np.pi * freq * ts)


def sawtooth_wave(ts: np.ndarray, freq: int = 1):
    return 2 * ((freq * ts - 1/2) - np.floor(freq * ts - 1/2) - 1/2)


def triangle_wave(ts: np.ndarray, freq: int = 1):
    return 4 * (np.abs((freq * ts - 1/2) - np.floor(freq * ts - 1/2) - 1/2) - 1/4)


def square_wave(ts: np.ndarray, freq: int = 1):
    return np.sign(np.sin(2 * np.pi * freq * ts))


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


def get_numpy_data(freq: int, waveform: str):
    ts: np.ndarray = np.linspace(0, 2, SAMPLING_RATE * 2)
    ys: np.ndarray = JUMP_TABLE[waveform](ts, freq=freq)
    return ts, ys


@app.post("/audio")
def new_audio_main():
    # get request arguments
    freq_text_input: str = request.form.get("freq")
    freqdata = request.form.get("freq-slider")
    waveform: str = request.form.get("sig-type")

    # get ts, ys
    freq = int(freqdata)
    try:
        freq = int(freq_text_input)
    except ValueError:
        pass

    __, ys = get_numpy_data(freq=freq, waveform=waveform)

    # convert ys to another data type such as 32 ints
    ys = (32767 * ys).astype('int16')
    # use scipy to write to an io.BytesIO
    stream: io.BytesIO = io.BytesIO()
    wavfile.write(stream, SAMPLING_RATE, ys)
    # write an audio tag and use the data type attribute and base64 encoding
    datastr: str = base64.b64encode(stream.getbuffer()).decode("ascii")
    return f"""<audio id='audio-output' controls type='audio/wav' src='data:audio/wav;base64,{datastr}' />"""



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

    freq: int = data.freq_text if data.freq_text is not None else data.freq_slider

    # if int, cast it, else if a decimal, round it down and cast to int, else error message
    """
    try:
        freq_int = int(float(freq)) \
            if freq != "" \
                else int(float(freq_slider))
    except ValueError:
        error_msg = "Frequency must be a number!"
"""

    # setup error message div and setup result variable
    error_msg_div: str = f"<div id='error-message' hx-swap-oob='true'>{error_msg}</div>"

    response: str = error_msg_div + "\n<img id='plot-image-load' style='display: none' src='data:image/png;base64,'/>"


    if freq is not None and abs(freq) <= MAX_FREQUENCY_INPUT:

        # Calculate and sample the signal, generate plots
        ts: np.ndarray = np.linspace(0, 2, SAMPLING_RATE * 2)
        ys: np.ndarray = JUMP_TABLE[data.sig_type](ts, freq=freq)
        imgtag: str = image(ts, ys)

        # math formulas, using MathML
        eq_original: str = "No object" 
        eq_series: str = "No object" 

        assert data.sig_type in WAVEFORM_EQS, f"Signal type {data.sig_type} is not known!"
        assert "eq_og"in WAVEFORM_EQS[data.sig_type], f"Original equations is not found for {data.sig_type}!"
        assert "eq_series" in WAVEFORM_EQS[data.sig_type], f"Fourier series expansion is not found for {data.sig_type}!"
        
        # Format the equations
        # assign variables the strings
        eq_og_template: str = WAVEFORM_EQS[data.sig_type]["eq_og"]
        eq_series_template: str = WAVEFORM_EQS[data.sig_type]["eq_series"]

        eq_original = eq_og_template.replace(" f ", f"({freq})")
        eq_series = eq_series_template.replace(" f ", f"({freq})")

        # convert each expression to MathML
        eq_og_template = latex2mathml.converter.convert(eq_og_template)
        eq_series_template = latex2mathml.converter.convert(eq_series_template)

        eq_original = latex2mathml.converter.convert(eq_original)
        eq_series = latex2mathml.converter.convert(eq_series)

        response = f""" 
<div id='error-message' hx-swap-oob='true'></div> 

{imgtag}

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

    return HTMLResponse(content=response, status_code=200)
    
@app.get("/")
def index(request: Request):
    return templates.TemplateResponse(request=request, name='index.html')
