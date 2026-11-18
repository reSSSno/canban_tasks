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

@router.get("/api/projects")
def projects(db: DB, user: User = Depends(current_user)):
    rows = db.execute(select(Project, Membership.role).join(Membership).where(Membership.user_id == user.id)).all()
    return [{"id": p.id, "name": p.name, "role": role} for p, role in rows]


@router.post("/api/projects")
def create_project(data: NameIn, db: DB, user: User = Depends(current_user)):
    project = Project(name=data.name)
    db.add(project)
    db.flush()
    db.add(Membership(project_id=project.id, user_id=user.id, role="владелец"))
    for i, name in enumerate(["К выполнению", "В работе", "На проверке", "Готово"]):
        db.add(Column(project_id=project.id, name=name, position=i))
    db.commit()
    return {"id": project.id}


@router.get("/api/projects/{project_id}/board")
def board(project_id: int, db: DB, user: User = Depends(current_user)):
    member = membership(db, project_id, user.id)
    columns = db.scalars(select(Column).where(Column.project_id == project_id).order_by(Column.position)).all()
    ids = [c.id for c in columns]
    tasks = db.scalars(select(Task).where(Task.column_id.in_(ids)).order_by(Task.id)).all()
    members = db.execute(select(User, Membership.role).join(Membership).where(Membership.project_id == project_id)).all()
    return {"role": member.role, "columns": [{"id": c.id, "name": c.name, "tasks": [task_dict(t) for t in tasks if t.column_id == c.id]} for c in columns],
            "members": [{"id": u.id, "name": u.name, "email": u.email, "role": role} for u, role in members]}


@router.post("/api/projects/{project_id}/members")
def add_member(project_id: int, data: MemberIn, db: DB, user: User = Depends(current_user)):
    membership(db, project_id, user.id, owner=True)
    if data.role not in ("участник", "гость"):
        raise HTTPException(400, "Недопустимая роль")
    target = db.scalar(select(User).where(User.email == data.email.lower()))
    if not target:
        raise HTTPException(404, "Пользователь должен сначала зарегистрироваться")
    if db.get(Membership, (project_id, target.id)):
        raise HTTPException(409, "Участник уже добавлен")
    db.add(Membership(project_id=project_id, user_id=target.id, role=data.role))
    db.commit()
    return {"message": "Участник добавлен"}


@router.post("/api/projects/{project_id}/columns")
def create_column(project_id: int, data: NameIn, db: DB, user: User = Depends(current_user)):
    membership(db, project_id, user.id, write=True)
    position = db.scalar(select(func.count(Column.id)).where(Column.project_id == project_id)) or 0
    col = Column(project_id=project_id, name=data.name, position=position)
    db.add(col)
    db.commit()
    return {"id": col.id}
