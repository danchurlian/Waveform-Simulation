import numpy as np
import matplotlib
from matplotlib import pyplot as plt
import io

import latex2mathml.converter


matplotlib.use("svg")
SAMPLING_RATE = 44100


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


# -----------------------------------------------------------------------------


def sin_wave(ts: np.ndarray, freq: int = 1) -> np.ndarray:
    return np.sin(2 * np.pi * freq * ts)


def sawtooth_wave(ts: np.ndarray, freq: int = 1) -> np.ndarray:
    return 2 * ((freq * ts - 1/2) - np.floor(freq * ts - 1/2) - 1/2)


def triangle_wave(ts: np.ndarray, freq: int = 1) -> np.ndarray:
    return 4 * (np.abs((freq * ts - 1/2) - np.floor(freq * ts - 1/2) - 1/2) - 1/4)


def square_wave(ts: np.ndarray, freq: int = 1) -> np.ndarray:
    return np.sign(np.sin(2 * np.pi * freq * ts))


# -----------------------------------------------------------------------------

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



def generate_equation_list_html(freq_list: list[int], signal_type: str) -> str:
    assert signal_type in WAVEFORM_EQS, f"Signal type {signal_type} is not known!"
    assert "eq_og"in WAVEFORM_EQS[signal_type], f"Original equations is not found for {signal_type}!"
    assert "eq_series" in WAVEFORM_EQS[signal_type], f"Fourier series expansion is not found for {signal_type}!"


    equation_list_html: str = "<ul id='equation-list' hx-swap-oob='true' style='display: none; padding: 1rem 0 0 1rem'>"

    if len(freq_list) == 1:
        frequency = freq_list[0]

        # Format the equations
        # assign variables the strings
        eq_og_template: str = WAVEFORM_EQS[signal_type]["eq_og"]
        eq_series_template: str = WAVEFORM_EQS[signal_type]["eq_series"]

        eq_original: str = eq_og_template.replace(" f ", f"({frequency})")
        eq_series: str = eq_series_template.replace(" f ", f"({frequency})")

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
        {frequency} Hz
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
    return equation_list_html
