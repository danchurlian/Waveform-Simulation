from fastapi.testclient import TestClient
from .app import app


client = TestClient(app)

def test_audio():
    response = client.post("/audio", data={
        "freq_text": ["100", "400"], 
        "freq_slider": 100, 
        "sig_type": "Sine Wave",
        "title": "Test",
        })
    assert response.status_code == 200


def test_audio_nan_ints():
    response = client.post("/audio", data={
        "freq_text": ["asdb", "400"], 
        "freq_slider": 100, 
        "sig_type": "Sine Wave",
        "title": "Test"
        })
    assert response.status_code == 400


def test_audio_negative_freq():
    response = client.post("/audio", data={
        "freq_text": ["400", "-200"], 
        "freq_slider": 200, 
        "sig_type": "Sine Wave",
        "title": "Test",
        })
    assert response.status_code == 400


def test_audio_negative_freq_2():
    response = client.post("/audio", data={
        "freq_text": ["-200", "400"], 
        "freq_slider": 200, 
        "sig_type": "Sine Wave",
        "title": "Test",
        })
    assert response.status_code == 400


def test_audio_nan_ints_2():
    response = client.post("/audio", data={
        "freq_text": ["soefijsoiefjoseijfasdb"], 
        "freq_slider": 20, 
        "sig_type": "Sine Wave",
        "title": "Test",
        })
    assert response.status_code == 400


def test_audio_no_freqs():
    response = client.post("/audio", data={
        "freq_text": [], 
        "freq_slider": 200, 
        "sig_type": "Sine Wave",
        "title": "Test",
        })
    assert response.status_code != 200


def test_invalid_save():
    response = client.delete("/projects/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404



def test_login_logout():
    response = client.post("/login", data={
        "username": "dchu400",
        "password": "1234",
        "useraction": "login"
        })
    assert response.status_code == 200
    assert "Login success" in response.text

    session_id: str = response.cookies.get("session_id")
    assert session_id is not None

    response = client.get("/logout", cookies={
        "session_id": session_id})
    assert response.status_code == 200


def test_login_invalid_password():
    response = client.post("/login", data={
            "username": "dchu400",
            "password": "1234j",
            "useraction": "login",
        })
    assert response.status_code == 200
    assert "Incorrect" in response.text


def test_create_blank_username():
    response = client.post("/login", data={
            "username": "",
            "password": "1234",
            "useraction": "create",
        })
    assert response.status_code == 200
    assert "Cannot use this username" in response.text


def test_create_blank_password():
    response = client.post("/login", data={
            "username": "testuser",
            "password": "",
            "useraction": "create",
        })
    assert response.status_code == 200
    assert "Cannot use this password" in response.text


def test_login_from_2_clients():
    response1 = client.post("/login", data={
        "username": "dchu400",
        "password": "1234",
        "useraction": "login",
        })
    assert response1.status_code == 200
    session_id: str = response1.cookies.get("session_id")
    assert session_id is not None 

    response2 = client.post("/login", data={
        "username": "dchu400",
        "password": "1234",
        "useraction": "login",
        })
    assert response2.status_code == 200
    assert "already logged in " in response2.text

    logout_response = client.get("/logout", cookies={
        "session_id": session_id})

    assert logout_response.status_code == 200
