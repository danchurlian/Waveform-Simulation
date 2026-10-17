from pydantic import BaseModel

class FrequencyForm(BaseModel):
    freq_text: list[str]
    freq_slider: int
    sig_type: str
    title: str

class LoginForm(BaseModel):
    username: str
    # this is the raw password the user enters
    password: str
    useraction: str

type HTMLString = str
