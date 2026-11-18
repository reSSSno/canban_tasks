import jwt
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from .db import SessionLocal
from .dependencies import JWT_SECRET, membership
from .realtime import hub
router = APIRouter()

@router.websocket("/ws/projects/{project_id}")
async def websocket_board(ws: WebSocket, project_id: int, token: str):
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        with SessionLocal() as db:
            membership(db, project_id, int(payload["sub"]))
    except (jwt.PyJWTError, HTTPException, ValueError, KeyError):
        await ws.close(code=1008)
        return
    await ws.accept()
    hub.connections.setdefault(project_id, set()).add(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        hub.connections.get(project_id, set()).discard(ws)
