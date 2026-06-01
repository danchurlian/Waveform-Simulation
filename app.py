from flask import Flask, render_template, request
import io
import base64
import latex2mathml.converter

import numpy as np

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

app = Flask(__name__)
SAMPLING_RATE: int = 11025

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
    return f"<img id='plot-image' style='padding: 1rem' src='data:image/png;base64,{data}'/>"


@app.post("/image")
def new_image_main() -> str:
    freq_response: str = request.form["freq-slider"]
    # if int, cast it, else if a decimal, round it down and cast to int, else error message
    response: str = "<div>Frequency must be less than 6 digits!</div>"

    freq: int = None
    try:
        freq = int(float(freq_response))
    except ValueError:
        response = "<div>Frequency must be a number!</div>"

    if freq is not None and abs(freq) < 100000:
        sigtype: str = request.form.get("sig-type", "NONE") 

        # Calculate and sample the signal, generate plots
        ts: np.ndarray = np.linspace(0, 2, SAMPLING_RATE * 2)
        ys: np.ndarray = JUMP_TABLE[sigtype](ts, freq=freq)
        imgtag: str = image(ts, ys)

        # math formulas, using MathML
        eq_original: str = "No object" 
        eq_series: str = "No object" 

        assert sigtype in WAVEFORM_EQS, f"Signal type {sigtype} is not known!"
        assert "eq_og"in WAVEFORM_EQS[sigtype], f"Original equations is not found for {sigtype}!"
        assert "eq_series" in WAVEFORM_EQS[sigtype], f"Fourier series expansion is not found for {sigtype}!"
        
        # Format the equations
        # assign variables the strings
        eq_og_template: str = WAVEFORM_EQS[sigtype]["eq_og"]
        eq_series_template: str = WAVEFORM_EQS[sigtype]["eq_series"]

        eq_original = eq_og_template.replace(" f ", f"({freq})")
        eq_series = eq_series_template.replace(" f ", f"({freq})")

        # convert each expression to MathML
        eq_og_template = latex2mathml.converter.convert(eq_og_template)
        eq_series_template = latex2mathml.converter.convert(eq_series_template)

        eq_original = latex2mathml.converter.convert(eq_original)
        eq_series = latex2mathml.converter.convert(eq_series)

        response = f"""{imgtag}
<ul id='equation-list' hx-swap-oob='true' style='padding: 1rem 0 0 1rem'>
    <li>
        <eq-label>Chosen frequency:</eq-label> 
        {freq}
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

    return response
    
@app.get("/")
def index():
    return render_template("index.html")

if __name__ == "__main__":
    print("Running")
    app.run()
