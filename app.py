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
        "eq_og": "2(ft - \\lfloor ft \\rfloor - \\frac{1}{2})",
        "eq_series": "\\sin({2\\pi ft}) - \\frac{1}{2}\\sin({2\\pi 2ft}) + \\frac{1}{3}\\sin({2\\pi 3ft}) + ...",
    },

    "Triangle Wave": {
        "eq_og": """
<mn>4</mn>
<mo>(</mo>
    <mi>abs</mi>
    <mo>(</mo>
        <mi>f</mi>
        <mi>t</mi>

        <mo>-</mo>

        <mi>floor</mi>
        <mo>(</mo>
            <mi>f</mi>
            <mi>t</mi>
        <mo>)</mo>

        <mo>-</mo>

        <mfrac>
            <mn>1</mn>
            <mn>2</mn>
        </mfrac>

    <mo>)</mo>
    <mo>-</mo>
    <mfrac>
        <mn>1</mn>
        <mn>4</mn>
    </mfrac>
<mo>)</mo>
""",
    },
    "Square Wave": {
        "eq_og": """
<mrow>
    <mi>sign</mi>
    <mo>(</mo>
        <mi>sin</mi>
        <mo>(</mo>
            <mn>2</mn>
            <mi>&pi;</mi>
            <mi>f</mi>
            <mi>t</mi>
        <mo>)</mo>
    <mo>)</mo>
""",
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
def new_image_main():
    freq: int = int(request.form["freq"])
    sigtype: str = request.form.get("sig-type", "NONE") 
    img_tag: str = image(freq=freq, sigtype=sigtype) 

    # math formulas, using MathML
    eq_original: str = "No object" 
    eq_series: str = "No object" 

    if sigtype in WAVEFORM_EQS:
        eq_original = WAVEFORM_EQS[sigtype].get("eq_og", "<mrow><mn>2</mn><mi>x</mi> + <mn>5</mn></mrow>")

        eq_series = WAVEFORM_EQS[sigtype].get("eq_series", "<mrow><mi>sin(2pifx)</mi></mrow>")

        eq_original = latex2mathml.converter.convert(eq_original)
        eq_series = latex2mathml.converter.convert(eq_series)
        print(eq_original)
        print(eq_series)

    return f"""{img_tag}
<div> 
    <span>Original equation:</span>
    {eq_original}
</div>
<div> 
    <span>Fourier expansion:</span>
    {eq_series}
</div>""" 
    
@app.get("/")
def index():
    return render_template("index.html")

if __name__ == "__main__":
    print("Running")
    app.run()