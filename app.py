from flask import Flask, render_template, request
import numpy as np
import matplotlib.pyplot as plt
import io
import base64
import latex2mathml.converter

app = Flask(__name__)


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


def image(freq: int, sigtype: str) -> str:
    assert sigtype in JUMP_TABLE, f"The signal {sigtype} was not found in the table!"
    ts: np.ndarray = np.linspace(0, 2, 11025)
    ys: np.ndarray = JUMP_TABLE[sigtype](ts, freq=freq)

    # Convert the buffer output into a base 64 string
    buffer = io.BytesIO()

    fig, ax = plt.subplots()
    ax.plot(ts, ys)
    fig.savefig(buffer, format='png')
    data = base64.b64encode(buffer.getbuffer()).decode("ascii")

    return f"<img id='plot-image' src='data:image/png;base64,{data}'/>"


@app.post("/image")
def new_image_main() -> str:
    freq_response: str = request.form["freq"]
    # if int, cast it, else if a decimal, round it down and cast to int, else error message
    response: str = ""

    freq: int = None
    try:
        freq = int(float(freq_response))
    except ValueError:
        response = "<div>Frequency must be a number!</div>"

    if freq is not None:
        sigtype: str = request.form.get("sig-type", "NONE") 
        img_tag: str = image(freq=freq, sigtype=sigtype) 


        # math formulas, using MathML
        eq_original: str = "No object" 
        eq_series: str = "No object" 

        assert sigtype in WAVEFORM_EQS, f"Signal type {sigtype} is not known!"
        assert "eq_og"in WAVEFORM_EQS[sigtype], f"Original equations is not found for {sigtype}!"
        assert "eq_series" in WAVEFORM_EQS[sigtype], f"Fourier series expansion is not found for {sigtype}!"
        
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

        response = f"""{img_tag}
<div>
    <span>Original equation formula:</span> 
    {eq_og_template}
</div>
<div> 
    <span>Original equation:</span>
    {eq_original}
</div>
<div>
    <span>Fourier expansion formula:</span>
    {eq_series_template}
</div>
<div> 
    <span>Fourier expansion:</span>
    {eq_series}
</div>""" 

    return response
    
@app.get("/")
def index():
    return render_template("index.html")

if __name__ == "__main__":
    print("Running")
    app.run()
