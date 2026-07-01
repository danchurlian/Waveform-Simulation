from fastapi.testclient import TestClient
from .app import app

client = TestClient(app)

def testing():
    print("First test")
    assert (1 + 1) == 3
