from typing import Dict, List
from fastapi import WebSocket

class ConnectionManager:
    def __init__(self):
        # active_connections: { social_id: WebSocket }
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, social_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[social_id] = websocket
        await self.broadcast_status(social_id, "online")

    def disconnect(self, social_id: str):
        if social_id in self.active_connections:
            del self.active_connections[social_id]
            # In a real app, you'd broadcast "offline" here
            # But we need to handle this carefully with async

    async def send_personal_message(self, message: dict, social_id: str):
        if social_id in self.active_connections:
            await self.active_connections[social_id].send_json(message)

    async def broadcast_status(self, social_id: str, status: str):
        message = {
            "type": "status_update",
            "social_id": social_id,
            "status": status
        }
        for connection in self.active_connections.values():
            await connection.send_json(message)

    async def trigger_call(self, from_social_id: str, to_social_id: str):
        if to_social_id in self.active_connections:
            await self.active_connections[to_social_id].send_json({
                "type": "incoming_call",
                "from": from_social_id
            })
            return True
        return False

manager = ConnectionManager()
