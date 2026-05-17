import unittest
import uuid
from fastapi.testclient import TestClient
from main import app, Base, engine

client = TestClient(app)

class TestMonolith(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)

    def register_and_login(self, username, password):
        response = client.post(
            "/register",
            json={"username": username, "password": password}
        )
        self.assertEqual(response.status_code, 200)
        social_id = response.json()["social_id"]

        response = client.post(
            "/token",
            data={"username": username, "password": password}
        )
        self.assertEqual(response.status_code, 200)
        return response.json()["access_token"], social_id

    def test_flow(self):
        username = f"user_{uuid.uuid4().hex[:8]}"
        token, social_id = self.register_and_login(username, "pass")

        with client.websocket_connect(f"/ws/{social_id}?token={token}") as ws:
            data = ws.receive_json()
            self.assertEqual(data["type"], "status_update")

            ws.send_json({"type": "ping"})
            self.assertEqual(ws.receive_json()["type"], "pong")

if __name__ == "__main__":
    unittest.main()
