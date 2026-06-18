#!/usr/bin/env python3
"""
Code-Realme-NonStop WebSocket Server
External Backend for Real-time Communication
Port: 8765 (configurable via PORT env var)
"""

import asyncio
import json
import uuid
import os
from datetime import datetime
from typing import Dict, Set, Optional
import websockets
from websockets.server import WebSocketServerProtocol

# Configuration
PORT = int(os.getenv('PORT', 8765))
HOST = os.getenv('HOST', '0.0.0.0')

# Active connections and data storage
active_users: Dict[str, Dict] = {}
active_calls: Dict[str, Dict] = {}
user_connections: Dict[str, WebSocketServerProtocol] = {}
chat_messages: Dict[str, list] = {}  # room_id -> [messages]

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, Set[WebSocketServerProtocol]] = {}
    
    async def connect(self, websocket: WebSocketServerProtocol, user_id: str, room_id: str):
        """Register a new connection"""
        if room_id not in self.active_connections:
            self.active_connections[room_id] = set()
        
        self.active_connections[room_id].add(websocket)
        user_connections[user_id] = websocket
        
        print(f"✓ {user_id} joined room {room_id}")
    
    async def disconnect(self, websocket: WebSocketServerProtocol, room_id: str, user_id: str):
        """Remove a connection"""
        if room_id in self.active_connections:
            self.active_connections[room_id].discard(websocket)
            if not self.active_connections[room_id]:
                del self.active_connections[room_id]
        
        if user_id in user_connections:
            del user_connections[user_id]
        
        print(f"✗ {user_id} left room {room_id}")
    
    async def broadcast(self, message: dict, room_id: str, sender_id: Optional[str] = None):
        """Broadcast message to all users in room"""
        if room_id in self.active_connections:
            for connection in self.active_connections[room_id]:
                try:
                    await connection.send(json.dumps(message))
                except Exception as e:
                    print(f"Broadcast error: {e}")
    
    async def send_to_user(self, user_id: str, message: dict):
        """Send message to specific user"""
        if user_id in user_connections:
            try:
                await user_connections[user_id].send(json.dumps(message))
            except Exception as e:
                print(f"Direct send error: {e}")

manager = ConnectionManager()

async def handle_client(websocket: WebSocketServerProtocol, path: str):
    """Handle incoming WebSocket connections"""
    user_id = None
    room_id = None
    
    try:
        async for message in websocket:
            try:
                data = json.loads(message)
                msg_type = data.get('type')
                
                # Authentication
                if msg_type == 'AUTH':
                    user_id = data.get('user_id', str(uuid.uuid4())[:8])
                    room_id = data.get('room_id', 'general')
                    
                    await manager.connect(websocket, user_id, room_id)
                    
                    # Send confirmation
                    await websocket.send(json.dumps({
                        'type': 'AUTH_SUCCESS',
                        'user_id': user_id,
                        'room_id': room_id,
                        'timestamp': datetime.now().isoformat()
                    }))
                    
                    # Notify others
                    await manager.broadcast({
                        'type': 'USER_JOINED',
                        'user_id': user_id,
                        'room_id': room_id,
                        'timestamp': datetime.now().isoformat()
                    }, room_id)
                
                # Chat messages
                elif msg_type == 'CHAT':
                    if not room_id:
                        continue
                    
                    chat_msg = {
                        'type': 'CHAT',
                        'user_id': user_id,
                        'message': data.get('message', ''),
                        'room_id': room_id,
                        'timestamp': datetime.now().isoformat()
                    }
                    
                    if room_id not in chat_messages:
                        chat_messages[room_id] = []
                    chat_messages[room_id].append(chat_msg)
                    
                    # Keep last 100 messages
                    if len(chat_messages[room_id]) > 100:
                        chat_messages[room_id].pop(0)
                    
                    await manager.broadcast(chat_msg, room_id)
                
                # Call initiation
                elif msg_type == 'CALL_REQUEST':
                    if not room_id:
                        continue
                    
                    call_id = str(uuid.uuid4())[:12]
                    target_user_id = data.get('target_user_id')
                    
                    call_data = {
                        'id': call_id,
                        'caller_id': user_id,
                        'target_user_id': target_user_id,
                        'room_id': room_id,
                        'created_at': datetime.now().isoformat()
                    }
                    active_calls[call_id] = call_data
                    
                    # Send to target user
                    await manager.send_to_user(target_user_id, {
                        'type': 'INCOMING_CALL',
                        'call_id': call_id,
                        'caller_id': user_id,
                        'caller_name': data.get('caller_name', user_id)
                    })
                    
                    # Confirm to caller
                    await websocket.send(json.dumps({
                        'type': 'CALL_REQUEST_SENT',
                        'call_id': call_id,
                        'target_user_id': target_user_id
                    }))
                
                # Call acceptance
                elif msg_type == 'CALL_ACCEPT':
                    call_id = data.get('call_id')
                    if call_id in active_calls:
                        call_data = active_calls[call_id]
                        call_data['accepted_at'] = datetime.now().isoformat()
                        call_data['status'] = 'ACTIVE'
                        
                        # Notify caller
                        await manager.send_to_user(call_data['caller_id'], {
                            'type': 'CALL_ACCEPTED',
                            'call_id': call_id,
                            'acceptor_id': user_id,
                            'acceptor_name': data.get('acceptor_name', user_id)
                        })
                
                # WebRTC Signaling
                elif msg_type == 'RTC_OFFER':
                    target_user_id = data.get('target_user_id')
                    await manager.send_to_user(target_user_id, {
                        'type': 'RTC_OFFER',
                        'from_user_id': user_id,
                        'offer': data.get('offer')
                    })
                
                elif msg_type == 'RTC_ANSWER':
                    target_user_id = data.get('target_user_id')
                    await manager.send_to_user(target_user_id, {
                        'type': 'RTC_ANSWER',
                        'from_user_id': user_id,
                        'answer': data.get('answer')
                    })
                
                elif msg_type == 'RTC_ICE_CANDIDATE':
                    target_user_id = data.get('target_user_id')
                    await manager.send_to_user(target_user_id, {
                        'type': 'RTC_ICE_CANDIDATE',
                        'from_user_id': user_id,
                        'candidate': data.get('candidate')
                    })
                
                # Call termination
                elif msg_type == 'CALL_END':
                    call_id = data.get('call_id')
                    target_user_id = data.get('target_user_id')
                    
                    if call_id in active_calls:
                        active_calls[call_id]['status'] = 'ENDED'
                        active_calls[call_id]['ended_at'] = datetime.now().isoformat()
                    
                    await manager.send_to_user(target_user_id, {
                        'type': 'CALL_ENDED',
                        'call_id': call_id,
                        'ended_by': user_id
                    })
                
                # Call rejection
                elif msg_type == 'CALL_REJECT':
                    call_id = data.get('call_id')
                    target_user_id = data.get('target_user_id')
                    
                    if call_id in active_calls:
                        active_calls[call_id]['status'] = 'REJECTED'
                    
                    await manager.send_to_user(target_user_id, {
                        'type': 'CALL_REJECTED',
                        'call_id': call_id,
                        'rejected_by': user_id
                    })
                
                # Get chat history
                elif msg_type == 'GET_CHAT_HISTORY':
                    history = chat_messages.get(room_id, [])
                    await websocket.send(json.dumps({
                        'type': 'CHAT_HISTORY',
                        'room_id': room_id,
                        'messages': history[-50:]  # Last 50 messages
                    }))
                
                # Get online users
                elif msg_type == 'GET_ONLINE_USERS':
                    if room_id in manager.active_connections:
                        # Send list of active users
                        await websocket.send(json.dumps({
                            'type': 'ONLINE_USERS',
                            'room_id': room_id,
                            'users': list(user_connections.keys())
                        }))
            
            except json.JSONDecodeError:
                await websocket.send(json.dumps({
                    'type': 'ERROR',
                    'message': 'Invalid JSON format'
                }))
            except Exception as e:
                print(f"Message handling error: {e}")
    
    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        if user_id and room_id:
            await manager.disconnect(websocket, room_id, user_id)
            await manager.broadcast({
                'type': 'USER_LEFT',
                'user_id': user_id,
                'room_id': room_id
            }, room_id)

async def main():
    print(f"🚀 Code-Realme WebSocket Server Starting...")
    print(f"📡 Listening on ws://{HOST}:{PORT}")
    print(f"Features: Chat | Calls | Real-time Sync")
    
    async with websockets.serve(handle_client, HOST, PORT):
        print(f"✓ Server running. Press Ctrl+C to stop.")
        await asyncio.Future()  # Run forever

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⊘ Server stopped.")
