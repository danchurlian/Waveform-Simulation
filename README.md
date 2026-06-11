# Waveform Simulation

**Stack:** HTMX, CSS, Javascript, Python Flask
**Dependencies:** latex2mathml, numpy, scipy, matplotlib

This a simulation where you generate signals, spectrums, and audio based on typing in a specific frequency you want to hear. The frequency you type in can range from 0Hz to 1000Hz.   

## General overview
When you enter in a chosen frequency, the website generates two plots. The first one is a signal with an abstract amplitude vs time. The second plot is the spectrum which is the real Fourier Transform of the signal.    

Along with inputting a single number for the frequency, you can also specify the shape of the signal (i.e. the waveform). By choosing different waveforms while typing in the fixed frequency, you can see that spectrum plots will be different. The spikes will follow a general pattern.  

On the left hand side you can see the equations that the backend uses to generate the signal plot. These equations are calculated using numpy, and the resulting graphs are plotted using matplotlib.   

You can also use the slider to change the frequency and see the changes in real time. By sliding left and right, you can see how the spikes of the spectrum move in relation to the changing frequency.


## The development process
I was reading a textbook called ThinkDsp by Allen B. Downey, which explored how Python can be used in order to examine signals, compute spectrums, and generate audio. I found the topic to be really interesting to me and I wanted to gain a better understanding on basic waveforms and their spectrums. As a result, I came up with this concept for the website.  

I had to make a proof of concept to see if rendering Matplotlib images to the front end was even possible. It turned out it was indeed possible but it was quite inefficient. I still have yet to find a more efficient way to generate plots of the signals.  

This was also my first time using HTMX. It worked really well with this application because much of the logic was already done in the backend, and the bulk of the webstie was just creating new HTML elements in the back end and transferring them to the front end.  

## Installation
The website is yet to be deployed. If you want to build from source, you can clone the repo first, and then run the Flask application like this.

```
source .venv/bin/activate
pip install -r requirements.txt
flask --app app.py run 
```

I plan to add more features soon. Enjoy!

## Contact
Email: chudaniel400@gmail.com
LinkedIn: https://www.linkedin.com/in/daniel-chu-13a107387/
