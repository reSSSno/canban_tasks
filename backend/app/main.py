from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Annotated

import jwt
from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import Depends, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, EmailStr, Field
from pwdlib import PasswordHash
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, create_engine, func, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./kanban.db")
JWT_SECRET = os.getenv("JWT_SECRET", "local-development-secret")
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine)
password_hash = PasswordHash.recommended()
security = HTTPBearer()


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100))
    password: Mapped[str] = mapped_column(String(255))


class Project(Base):
    __tablename__ = "projects"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(150))


class Membership(Base):
    __tablename__ = "memberships"
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    role: Mapped[str] = mapped_column(String(20))


class Column(Base):
    __tablename__ = "columns"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    name: Mapped[str] = mapped_column(String(100))
    position: Mapped[int] = mapped_column(Integer)


class Task(Base):
    __tablename__ = "tasks"
    id: Mapped[int] = mapped_column(primary_key=True)
    column_id: Mapped[int] = mapped_column(ForeignKey("columns.id"))
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    assignee_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    priority: Mapped[str] = mapped_column(String(20), default="Обычный")
    due_date: Mapped[str | None] = mapped_column(String(10), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Comment(Base):
    __tablename__ = "comments"
    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id"))
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class Report(Base):
    __tablename__ = "reports"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    completed: Mapped[int] = mapped_column(Integer)
    total: Mapped[int] = mapped_column(Integer)


class AuthIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)


class RegisterIn(AuthIn):
    name: str = Field(min_length=1, max_length=100)


class NameIn(BaseModel):
    name: str = Field(min_length=1, max_length=150)


class MemberIn(BaseModel):
    email: EmailStr
    role: str


class TaskIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = ""
    priority: str = "Обычный"
    due_date: str | None = None
    assignee_id: int | None = None


class TaskPatch(BaseModel):
    title: str | None = None
    description: str | None = None
    priority: str | None = None
    due_date: str | None = None
    assignee_id: int | None = None
    column_id: int | None = None


class CommentIn(BaseModel):
    text: str = Field(min_length=1, max_length=5000)


def get_db():
    with SessionLocal() as db:
        yield db


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


def task_dict(task):
    return {"id": task.id, "column_id": task.column_id, "title": task.title,
            "description": task.description, "priority": task.priority,
            "due_date": task.due_date, "assignee_id": task.assignee_id}


class Hub:
    def __init__(self):
        self.connections: dict[int, set[WebSocket]] = {}

    async def broadcast(self, project_id: int):
        for ws in list(self.connections.get(project_id, set())):
            try:
                await ws.send_json({"type": "board_changed"})
            except Exception:
                self.connections[project_id].discard(ws)


hub = Hub()


def weekly_reports():
    with SessionLocal() as db:
        since = datetime.now(timezone.utc) - timedelta(days=7)
        for project in db.scalars(select(Project)).all():
            column_ids = list(db.scalars(select(Column.id).where(Column.project_id == project.id)))
            tasks = db.scalars(select(Task).where(Task.column_id.in_(column_ids))).all()
            completed = sum(bool(t.completed_at and t.completed_at.replace(tzinfo=timezone.utc) >= since) for t in tasks)
            db.add(Report(project_id=project.id, completed=completed, total=len(tasks)))
        db.commit()


scheduler = BackgroundScheduler(timezone="UTC")


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(engine)
    scheduler.add_job(weekly_reports, "cron", day_of_week="mon", hour=8, id="weekly_report", replace_existing=True)
    scheduler.start()
    yield
    scheduler.shutdown(wait=False)


app = FastAPI(title="Командная доска задач", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:5173").split(","), allow_methods=["*"], allow_headers=["*"])


@app.post("/api/register")
def register(data: RegisterIn, db: DB):
    if db.scalar(select(User).where(User.email == data.email.lower())):
        raise HTTPException(409, "Пользователь уже существует")
    user = User(email=data.email.lower(), name=data.name, password=password_hash.hash(data.password))
    db.add(user)
    db.commit()
    return {"message": "Регистрация выполнена"}


@app.post("/api/login")
def login(data: AuthIn, db: DB):
    user = db.scalar(select(User).where(User.email == data.email.lower()))
    if not user or not password_hash.verify(data.password, user.password):
        raise HTTPException(401, "Неверный email или пароль")
    token = jwt.encode({"sub": str(user.id), "exp": datetime.now(timezone.utc) + timedelta(hours=12)}, JWT_SECRET, algorithm="HS256")
    return {"token": token, "name": user.name, "id": user.id}


@app.get("/api/projects")
def projects(db: DB, user: User = Depends(current_user)):
    rows = db.execute(select(Project, Membership.role).join(Membership).where(Membership.user_id == user.id)).all()
    return [{"id": p.id, "name": p.name, "role": role} for p, role in rows]


@app.post("/api/projects")
def create_project(data: NameIn, db: DB, user: User = Depends(current_user)):
    project = Project(name=data.name)
    db.add(project)
    db.flush()
    db.add(Membership(project_id=project.id, user_id=user.id, role="владелец"))
    for i, name in enumerate(["К выполнению", "В работе", "На проверке", "Готово"]):
        db.add(Column(project_id=project.id, name=name, position=i))
    db.commit()
    return {"id": project.id}


@app.get("/api/projects/{project_id}/board")
def board(project_id: int, db: DB, user: User = Depends(current_user)):
    member = membership(db, project_id, user.id)
    columns = db.scalars(select(Column).where(Column.project_id == project_id).order_by(Column.position)).all()
    ids = [c.id for c in columns]
    tasks = db.scalars(select(Task).where(Task.column_id.in_(ids)).order_by(Task.id)).all()
    members = db.execute(select(User, Membership.role).join(Membership).where(Membership.project_id == project_id)).all()
    return {"role": member.role, "columns": [{"id": c.id, "name": c.name, "tasks": [task_dict(t) for t in tasks if t.column_id == c.id]} for c in columns],
            "members": [{"id": u.id, "name": u.name, "email": u.email, "role": role} for u, role in members]}


@app.post("/api/projects/{project_id}/members")
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


@app.post("/api/projects/{project_id}/columns")
def create_column(project_id: int, data: NameIn, db: DB, user: User = Depends(current_user)):
    membership(db, project_id, user.id, write=True)
    position = db.scalar(select(func.count(Column.id)).where(Column.project_id == project_id)) or 0
    col = Column(project_id=project_id, name=data.name, position=position)
    db.add(col)
    db.commit()
    return {"id": col.id}


@app.post("/api/columns/{column_id}/tasks")
async def create_task(column_id: int, data: TaskIn, db: DB, user: User = Depends(current_user)):
    project_id = project_for_column(db, column_id)
    membership(db, project_id, user.id, write=True)
    validate_assignee(db, project_id, data.assignee_id)
    task = Task(column_id=column_id, **data.model_dump())
    db.add(task)
    db.commit()
    await hub.broadcast(project_id)
    return task_dict(task)


@app.patch("/api/tasks/{task_id}")
async def edit_task(task_id: int, data: TaskPatch, db: DB, user: User = Depends(current_user)):
    project_id = project_for_task(db, task_id)
    membership(db, project_id, user.id, write=True)
    task = db.get(Task, task_id)
    changes = data.model_dump(exclude_unset=True)
    if "column_id" in changes:
        new_column = db.get(Column, changes["column_id"])
        if not new_column or new_column.project_id != project_id:
            raise HTTPException(400, "Нельзя переместить задачу в другой проект")
        if new_column.name == "Готово" and not task.completed_at:
            task.completed_at = datetime.now(timezone.utc)
        elif new_column.name != "Готово":
            task.completed_at = None
    if "assignee_id" in changes:
        validate_assignee(db, project_id, changes["assignee_id"])
    for key, value in changes.items():
        setattr(task, key, value)
    db.commit()
    await hub.broadcast(project_id)
    return task_dict(task)


@app.delete("/api/tasks/{task_id}")
async def delete_task(task_id: int, db: DB, user: User = Depends(current_user)):
    project_id = project_for_task(db, task_id)
    membership(db, project_id, user.id, write=True)
    db.query(Comment).filter(Comment.task_id == task_id).delete()
    db.delete(db.get(Task, task_id))
    db.commit()
    await hub.broadcast(project_id)
    return {"message": "Задача удалена"}


@app.get("/api/tasks/{task_id}/comments")
def comments(task_id: int, db: DB, user: User = Depends(current_user)):
    membership(db, project_for_task(db, task_id), user.id)
    rows = db.execute(select(Comment, User.name).join(User, Comment.author_id == User.id).where(Comment.task_id == task_id).order_by(Comment.id)).all()
    return [{"id": c.id, "text": c.text, "author": name, "created_at": c.created_at.isoformat()} for c, name in rows]


@app.post("/api/tasks/{task_id}/comments")
async def add_comment(task_id: int, data: CommentIn, db: DB, user: User = Depends(current_user)):
    project_id = project_for_task(db, task_id)
    membership(db, project_id, user.id, write=True)
    comment = Comment(task_id=task_id, author_id=user.id, text=data.text)
    db.add(comment)
    db.commit()
    await hub.broadcast(project_id)
    return {"id": comment.id}


@app.get("/api/projects/{project_id}/reports")
def reports(project_id: int, db: DB, user: User = Depends(current_user)):
    membership(db, project_id, user.id)
    rows = db.scalars(select(Report).where(Report.project_id == project_id).order_by(Report.generated_at.desc()).limit(20)).all()
    return [{"date": r.generated_at.isoformat(), "completed": r.completed, "total": r.total} for r in rows]


@app.websocket("/ws/projects/{project_id}")
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
