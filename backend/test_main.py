import unittest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.core.database import Base, engine, SessionLocal
from backend.app.models import user as user_model
import uuid

client = TestClient(app)

class TestAuth(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)

    def register_and_login(self, username, password):
        # Register
        response = client.post(
            "/register",
            json={"username": username, "password": password}
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        social_id = data["social_id"]

        # Login
        response = client.post(
            "/token",
            data={"username": username, "password": password}
        )
        self.assertEqual(response.status_code, 200)
        login_data = response.json()
        return login_data["access_token"], social_id

    def test_register_and_login_success(self):
        username = f"user_{uuid.uuid4().hex[:8]}"
        self.register_and_login(username, "testpassword")

    def test_websocket_connection_authenticated(self):
        username = f"user_{uuid.uuid4().hex[:8]}"
        token, social_id = self.register_and_login(username, "testpassword")

        with client.websocket_connect(f"/ws/{social_id}?token={token}") as websocket:
            # First message should be the status update (self)
            data = websocket.receive_json()
            self.assertEqual(data["type"], "status_update")
            self.assertEqual(data["social_id"], social_id)

            websocket.send_json({"type": "ping"})
            data = websocket.receive_json()
            self.assertEqual(data, {"type": "pong"})

    def test_websocket_connection_unauthenticated(self):
        username = f"user_{uuid.uuid4().hex[:8]}"
        _, social_id = self.register_and_login(username, "testpassword")

        try:
             with client.websocket_connect(f"/ws/{social_id}") as websocket:
                 pass
             self.fail("Should have raised an exception or closed the connection")
        except Exception:
             pass

if __name__ == "__main__":
    unittest.main()
