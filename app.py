from flask import Flask, render_template, request
import numpy as np
import matplotlib.pyplot as plt
import io
import base64

app = Flask(__name__)


def sin_wave(ts: np.ndarray, freq: int = 1):
    return np.sin(2 * np.pi * freq * ts)
    
@app.route("/", methods=["GET", "POST"])
def index():
    ts: np.ndarray = np.linspace(0, 2, 11025)
    
    freq: int = 1
    if request.method == "POST":
        freq = int(request.form["freq"])
        print(f"Got frequency {freq}")
    else:
        try:
            freq: int = int(request.args.get("freq", "1"))
        except ValueError:
            pass

    ys = sin_wave(ts, freq)
    fig, ax = plt.subplots()
    ax.plot(ts, ys)

    # Convert the buffer output into a base 64 string
    buffer = io.BytesIO()
    fig.savefig(buffer, format='png')
    data = base64.b64encode(buffer.getbuffer()).decode("ascii")
    print(buffer.getbuffer())
    
    figure_html: str = f"<img src='data:image/png;base64,{data}'/>"
    return render_template("index.html", figure_html=figure_html)

if __name__ == "__main__":
    print("Running")
    app.run()