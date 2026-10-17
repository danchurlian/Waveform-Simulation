from pydantic import BaseModel

class FrequencyForm(BaseModel):
    freq_text: list[str]
    freq_slider: int
    sig_type: str
    title: str

type HTMLString = str
