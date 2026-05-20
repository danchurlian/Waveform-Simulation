from flask import Flask, render_template, request
import numpy as np
import matplotlib.pyplot as plt
import io
import base64

app = Flask(__name__)


def sin_wave(ts: np.ndarray):
    return np.sin(2 * np.pi * 4 * ts)
    
@app.route("/")
def index():
    ts: np.ndarray = np.linspace(0, 2, 11025)
    ys = sin_wave(ts)
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