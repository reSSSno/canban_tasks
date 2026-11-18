from typing import Annotated
import os
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pwdlib import PasswordHash
from sqlalchemy.orm import Session
from .db import User, Membership, Column, Task, get_db
JWT_SECRET = os.getenv("JWT_SECRET", "local-development-secret")
password_hash = PasswordHash.recommended()
security = HTTPBearer()
DB = Annotated[Session, Depends(get_db)]

def current_user(credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)], db: DB):
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=["HS256"])
        user = db.get(User, int(payload["sub"]))
    except (jwt.PyJWTError, ValueError, KeyError):
        user = None
    if not user:
        raise HTTPException(401, "Необходимо войти в систему")
    return user


def membership(db: Session, project_id: int, user_id: int, write=False, owner=False):
    member = db.get(Membership, (project_id, user_id))
    if not member:
        raise HTTPException(403, "Нет доступа к проекту")
    if owner and member.role != "владелец":
        raise HTTPException(403, "Требуется роль владельца")
    if write and member.role == "гость":
        raise HTTPException(403, "Гостю доступен только просмотр")
    return member


def project_for_column(db, column_id):
    col = db.get(Column, column_id)
    if not col:
        raise HTTPException(404, "Колонка не найдена")
    return col.project_id


def project_for_task(db, task_id):
    task = db.get(Task, task_id)
    if not task:
        raise HTTPException(404, "Задача не найдена")
    return project_for_column(db, task.column_id)


def validate_assignee(db, project_id, assignee_id):
    if assignee_id is not None:
        member = db.get(Membership, (project_id, assignee_id))
        if not member or member.role == "гость":
            raise HTTPException(400, "Исполнитель должен быть участником проекта")
