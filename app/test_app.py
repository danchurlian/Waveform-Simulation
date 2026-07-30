from fastapi.testclient import TestClient
from .app import app


client = TestClient(app)

def test_audio():
    response = client.post("/audio", data={
        "freq_text": ["100", "400"], 
        "freq_slider": 100, 
        "sig_type": "Sine Wave"
        })
    assert response.status_code == 200


def test_audio_nan_ints():
    response = client.post("/audio", data={
        "freq_text": ["asdb", "400"], 
        "freq_slider": 100, 
        "sig_type": "Sine Wave"
        })
    assert response.status_code == 400


def test_audio_negative_freq():
    response = client.post("/audio", data={
        "freq_text": ["400", "-200"], 
        "freq_slider": 200, 
        "sig_type": "Sine Wave"
        })
    assert response.status_code == 400


def test_audio_negative_freq_2():
    response = client.post("/audio", data={
        "freq_text": ["-200", "400"], 
        "freq_slider": 200, 
        "sig_type": "Sine Wave"
        })
    assert response.status_code == 400


def test_audio_nan_ints_2():
    response = client.post("/audio", data={
        "freq_text": ["soefijsoiefjoseijfasdb"], 
        "freq_slider": 20, 
        "sig_type": "Sine Wave"
        })
    assert response.status_code == 400


def test_audio_no_freqs():
    response = client.post("/audio", data={
        "freq_text": [], 
        "freq_slider": 200, 
        "sig_type": "Sine Wave"
        })
    assert response.status_code != 200


def test_invalid_save():
    response = client.delete("/projects/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404
