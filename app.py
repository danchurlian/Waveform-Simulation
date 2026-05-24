from flask import Flask, render_template, request
import numpy as np
import matplotlib.pyplot as plt
import io
import base64

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
    eq_original: str = "<mrow><mn>2</mn><mi>x</mi> + <mn>5</mn></mrow>"
    eq_series: str = "<mrow><mi>sin(2pifx)</mi></mrow>"
    return f"{img_tag}\n<math>{eq_original}\n{eq_series}</math>"
    
    
@app.get("/")
def index():
    return render_template("index.html")

if __name__ == "__main__":
    print("Running")
    app.run()