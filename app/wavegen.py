import numpy as np
import matplotlib
from matplotlib import pyplot as plt
import io


matplotlib.use("svg")
SAMPLING_RATE = 44100


def sin_wave(ts: np.ndarray, freq: int = 1) -> np.ndarray:
    return np.sin(2 * np.pi * freq * ts)


def sawtooth_wave(ts: np.ndarray, freq: int = 1) -> np.ndarray:
    return 2 * ((freq * ts - 1/2) - np.floor(freq * ts - 1/2) - 1/2)


def triangle_wave(ts: np.ndarray, freq: int = 1) -> np.ndarray:
    return 4 * (np.abs((freq * ts - 1/2) - np.floor(freq * ts - 1/2) - 1/2) - 1/4)


def square_wave(ts: np.ndarray, freq: int = 1) -> np.ndarray:
    return np.sign(np.sin(2 * np.pi * freq * ts))


def generate_image(ts: np.ndarray, ys: np.ndarray) -> str:
    print("generating image")
    fs: np.ndarray = np.fft.rfftfreq(ys.size, d=1/SAMPLING_RATE)
    hs: np.ndarray = np.abs(np.fft.rfft(ys))
    # Make 2 subplots, top is the signal plot, bottom is the spectrum plot
    fig, axes = plt.subplots(2)
    axes[0].plot(ts, ys)
    axes[0].set_title("Signal")
    axes[1].plot(fs, hs)
    axes[1].set_title("Spectrum")

    fig.tight_layout()

    string_buf = io.StringIO()
    fig.savefig(string_buf, format="svg")
    plt.close(fig)

    xml_string = string_buf.getvalue()
    return f"<div id='plot-image-load'>{xml_string}</div>"
