from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from datetime import timedelta
from typing import List, Dict
from sqlalchemy.orm import Session

from backend.app.core.config import get_settings
from backend.app.core import security
from backend.app.core.database import engine, Base, get_db, SessionLocal
from backend.app.models import user as user_model
from backend.app.schemas.user import UserCreate, User, generate_social_id
from backend.app.websocket.manager import manager
from jose import JWTError, jwt

settings = get_settings()

# Create tables
Base.metadata.create_all(bind=engine)

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
    return {"message": "Welcome to Code-Realme-NonStoP API"}

@app.post("/register", response_model=User)
async def register(user: UserCreate, db: Session = Depends(get_db)):
    db_user = db.query(user_model.User).filter(user_model.User.username == user.username).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Username already registered")

    hashed_password = security.get_password_hash(user.password)
    social_id = generate_social_id()

    db_user = user_model.User(
        username=user.username,
        email=user.email,
        full_name=user.full_name,
        hashed_password=hashed_password,
        social_id=social_id,
        avatar_url=user.avatar_url
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

@app.post("/token")
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    db_user = db.query(user_model.User).filter(user_model.User.username == form_data.username).first()
    if not db_user or not security.verify_password(form_data.password, db_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = security.create_access_token(
        subject=db_user.username, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer", "social_id": db_user.social_id}

@app.websocket("/ws/{social_id}")
async def websocket_endpoint(websocket: WebSocket, social_id: str, token: str = None):
    # Verify JWT token
    if token is None:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

        # Check if the social_id belongs to the authenticated user
        # This prevents users from connecting as someone else
        with SessionLocal() as db:
            db_user = db.query(user_model.User).filter(user_model.User.username == username).first()
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
                target_id = data.get("to")
                await manager.trigger_call(social_id, target_id)
            elif data.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        manager.disconnect(social_id)
        await manager.broadcast_status(social_id, "offline")
