// For rendering the final image from the buffer
document.addEventListener("DOMContentLoaded", () => {
  const finalImageTag = document.getElementById("plot-image");
  const graphDataDiv = document.getElementById("graph-data");
  const form = document.getElementById("signal-form");

  // logic loading the graph pictures from the server
  form.addEventListener("htmx:afterRequest", () => {
    const loadImageTag = document.getElementById("plot-image-load");
    if (loadImageTag) {
      finalImageTag.appendChild(loadImageTag.closeNode(true));
    }
  });


  // add logic for showing "save successful" message before going away
  const saveResultDiv = document.getElementById("save-result");
  const SAVE_DISPLAY_TIME_MS = 1500;
  let saveResultDebounce = false;
  saveResultDiv.addEventListener("htmx:afterSettle", () => {
    if (!saveResultDebounce) {
      saveResultDebounce = true;
      setTimeout(() => {
        saveResultDiv.textContent = "";
        saveResultDebounce = false;
      }, SAVE_DISPLAY_TIME_MS);
    }
  })
});


// fired when the user clicks on "add wave", generates a new waveform slider input
const addWave = (form, frequency) => {
  const parser = new DOMParser();
  const newTextField = `<input 
                class="freq-text-field"
                name="freq_text" 
                type="number" 
                autofocus="true" 
                autocomplete="off"  
                placeholder="Frequency (Hz)"
                required="true"
                />`;

  const fieldElement = parser.parseFromString(newTextField, "text/html").body.firstElementChild;

  const newSliderField = `<input 
                class="freq-slider"
                name="freq_slider" 
                type="range" 
                min="0" 
                max="1000" 
                step="10"
                oninput="event.target.parentElement.querySelector('.freq-text-field').value = this.value;"
                />`;
  const sliderElement = parser.parseFromString(newSliderField, "text/html").body.firstElementChild;

  if (frequency) {
    fieldElement.value = frequency;
    sliderElement.value = frequency;
  }

  // create a delete button for the item
  const deleteButton = document.createElement("button");
  deleteButton.className = "waveform-item-delete";
  deleteButton.textContent = "Delete";
  deleteButton.type = "button";

  // when you click on the delete button, 
  // remove that specific button from the array
  deleteButton.addEventListener("click", (event) => {
    const currentItem = event.target.parentElement;
    currentItem.remove();
  });

  // Create the wave object
  const waveFormObj = document.createElement("div");
  waveFormObj.classList.add("wave-form-item");
  waveFormObj.appendChild(fieldElement);
  waveFormObj.appendChild(sliderElement);
  waveFormObj.appendChild(deleteButton);

  console.log(typeof form);
  form.appendChild(waveFormObj);
}

// when clicking on the "add wave button", fire the event
document.getElementById("add-wave-button").addEventListener("click", (event) => {
  addWave(document.getElementById("signal-form"), 440);
})


// ----------------------------------------------------------------------------


// fires when the user wants to load the project
// loads up all the waveforms and the name, the genreal procedure
const loadProject = (target) => {
  const freqList = JSON.parse(target.dataset.freqs);
  const titleStr = target.dataset.title;
  const waveformStr = target.dataset.waveform;

  const form = document.getElementById("signal-form");
  const waveformSelect = document.getElementById("sig-type-select");
  const listenButton = document.getElementById("listen-button");
  const titleInput = document.getElementById("project-name-input")

  // delete the old extra waveform items from the previous project
  waveformItems = document.querySelectorAll(".wave-form-item");
  waveformItems.forEach((item) => {
    if (item.id != "wave-form-item")
      item.remove();
  })

  // add the new waveform inputs that correspond to the new loading project
  for (let i = 0; i < freqList.length; i++) {
    const freq = freqList[i];
    if (i == 0) {
      const firstFreqText = document.getElementById("freq-text");
      const firstFreqSlider = document.getElementById("freq-slider");

      firstFreqText.value = freq;
      firstFreqSlider.value = freq;
    } else {
      addWave(form, freq);
    }
  }

  // update workspace to new project matadata, such as the signal type 
  // and the project title
  waveformSelect.value = waveformStr;
  titleInput.value = titleStr;

  // submit to the server to run the simulation instantly
  form.dispatchEvent(new Event('projectLoad'));
  listenButton.dispatchEvent(new Event('projectLoad'));
}
