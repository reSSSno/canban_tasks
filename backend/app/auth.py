from datetime import datetime, timedelta, timezone
import jwt
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from .db import User, Project, Membership, Column, Task, Comment, Report
from .schemas import AuthIn, RegisterIn, NameIn, MemberIn, TaskIn, TaskPatch, CommentIn
from .dependencies import DB, current_user, membership, project_for_column, project_for_task, validate_assignee, password_hash, JWT_SECRET
from .serializers import task_dict
from .realtime import hub
router = APIRouter()

@router.post("/api/register")
def register(data: RegisterIn, db: DB):
    if db.scalar(select(User).where(User.email == data.email.lower())):
        raise HTTPException(409, "Пользователь уже существует")
    user = User(email=data.email.lower(), name=data.name, password=password_hash.hash(data.password))
    db.add(user)
    db.commit()
    return {"message": "Регистрация выполнена"}


@router.post("/api/login")
def login(data: AuthIn, db: DB):
    user = db.scalar(select(User).where(User.email == data.email.lower()))
    if not user or not password_hash.verify(data.password, user.password):
        raise HTTPException(401, "Неверный email или пароль")
    token = jwt.encode({"sub": str(user.id), "exp": datetime.now(timezone.utc) + timedelta(hours=12)}, JWT_SECRET, algorithm="HS256")
    return {"token": token, "name": user.name, "id": user.id}
