import os
import random
import string
from datetime import datetime, timedelta, timezone
from typing import Any, Union, Optional, List, Dict
from functools import lru_cache

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, EmailStr
from pydantic_settings import BaseSettings
from sqlalchemy import create_engine, Column, Integer, String, Boolean, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from jose import jwt, JWTError
from passlib.context import CryptContext
from dotenv import load_dotenv

# --- VAULT & CONFIG ---
load_dotenv()

class Vault:
    @staticmethod
    def get_secret(key: str, default: str = None) -> str:
        return os.getenv(key, default)

vault = Vault()

class Settings(BaseSettings):
    PROJECT_NAME: str = "Code-Realme-NonStoP"
    SECRET_KEY: str = vault.get_secret("SECRET_KEY", "CHANGEME")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    DATABASE_URL: str = vault.get_secret("DATABASE_URL", "sqlite:///./sql_app.db")

    class Config:
        env_file = ".env"

@lru_cache()
def get_settings():
    return Settings()

settings = get_settings()

# --- SECURITY ---
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def create_access_token(subject: Union[str, Any], expires_delta: timedelta = None) -> str:
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode = {"exp": expire, "sub": str(subject)}
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

# --- DATABASE ---
engine = create_engine(
    settings.DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class UserDB(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True, nullable=True)
    hashed_password = Column(String)
    social_id = Column(String, unique=True, index=True)
    full_name = Column(String, nullable=True)
    avatar_url = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    is_superuser = Column(Boolean, default=False)
    friends = Column(JSON, default=[]) # List of social_ids
    friend_requests = Column(JSON, default=[]) # List of social_ids

Base.metadata.create_all(bind=engine)

# --- SCHEMAS ---
def generate_social_id():
    suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))
    return f"CRN-{suffix}"

class UserBase(BaseModel):
    username: str
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    social_id: str = Field(default_factory=generate_social_id)
    avatar_url: Optional[str] = None

class UserCreate(UserBase):
    password: str

class User(UserBase):
    id: int
    is_active: bool = True

    class Config:
        from_attributes = True

# --- WEBSOCKET MANAGER ---
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, social_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[social_id] = websocket
        await self.broadcast_status(social_id, "online")

    def disconnect(self, social_id: str):
        if social_id in self.active_connections:
            del self.active_connections[social_id]

    async def broadcast_status(self, social_id: str, status: str):
        message = {"type": "status_update", "social_id": social_id, "status": status}
        for connection in self.active_connections.values():
            try:
                await connection.send_json(message)
            except:
                pass

    async def trigger_call(self, from_social_id: str, to_social_id: str):
        if to_social_id in self.active_connections:
            await self.active_connections[to_social_id].send_json({
                "type": "incoming_call",
                "from": from_social_id
            })
            return True
        return False

manager = ConnectionManager()

# --- APP & ROUTES ---
app = FastAPI(title=settings.PROJECT_NAME)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

@app.get("/")
async def root():
    return {"message": "Code-Realme-NonStoP Monolithic API Online"}

@app.post("/register", response_model=User)
async def register(user: UserCreate, db: Session = Depends(get_db)):
    db_user = db.query(UserDB).filter(UserDB.username == user.username).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Username already registered")

    hashed_password = get_password_hash(user.password)
    db_user = UserDB(
        username=user.username,
        email=user.email,
        full_name=user.full_name,
        hashed_password=hashed_password,
        social_id=generate_social_id(),
        avatar_url=user.avatar_url
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

@app.get("/users/me")
async def get_me(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username: str = payload.get("sub")
        user = db.query(UserDB).filter(UserDB.username == username).first()
        return user
    except:
        raise HTTPException(status_code=401)

@app.post("/friends/request/{target_social_id}")
async def send_friend_request(target_social_id: str, token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    sender_username = payload.get("sub")
    sender = db.query(UserDB).filter(UserDB.username == sender_username).first()

    target = db.query(UserDB).filter(UserDB.social_id == target_social_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    # Update target's friend requests
    requests = list(target.friend_requests or [])
    if sender.social_id not in requests:
        requests.append(sender.social_id)
        target.friend_requests = requests
        db.commit()
    return {"message": "Request sent"}

@app.post("/friends/accept/{target_social_id}")
async def accept_friend_request(target_social_id: str, token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    me_username = payload.get("sub")
    me = db.query(UserDB).filter(UserDB.username == me_username).first()

    # Remove from requests
    requests = list(me.friend_requests or [])
    if target_social_id in requests:
        requests.remove(target_social_id)
        me.friend_requests = requests

        # Add to friends for both
        my_friends = list(me.friends or [])
        if target_social_id not in my_friends:
            my_friends.append(target_social_id)
            me.friends = my_friends

        target = db.query(UserDB).filter(UserDB.social_id == target_social_id).first()
        if target:
            target_friends = list(target.friends or [])
            if me.social_id not in target_friends:
                target_friends.append(me.social_id)
                target.friends = target_friends

        db.commit()
    return {"message": "Accepted"}

@app.post("/token")
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    db_user = db.query(UserDB).filter(UserDB.username == form_data.username).first()
    if not db_user or not verify_password(form_data.password, db_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(subject=db_user.username)
    return {"access_token": access_token, "token_type": "bearer", "social_id": db_user.social_id}

@app.websocket("/ws/{social_id}")
async def websocket_endpoint(websocket: WebSocket, social_id: str, token: str = None):
    if token is None:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username: str = payload.get("sub")
        with SessionLocal() as db:
            db_user = db.query(UserDB).filter(UserDB.username == username).first()
            if not db_user or db_user.social_id != social_id:
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
                return
    except JWTError:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await manager.connect(social_id, websocket)
    try:
        while True:
            data = await websocket.receive_json()
            if data.get("type") == "force_call":
                await manager.trigger_call(social_id, data.get("to"))
            elif data.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        manager.disconnect(social_id)
        await manager.broadcast_status(social_id, "offline")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
