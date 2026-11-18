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

@router.get("/api/tasks/{task_id}/comments")
def comments(task_id: int, db: DB, user: User = Depends(current_user)):
    membership(db, project_for_task(db, task_id), user.id)
    rows = db.execute(select(Comment, User.name).join(User, Comment.author_id == User.id).where(Comment.task_id == task_id).order_by(Comment.id)).all()
    return [{"id": c.id, "text": c.text, "author": name, "created_at": c.created_at.isoformat()} for c, name in rows]


@router.post("/api/tasks/{task_id}/comments")
async def add_comment(task_id: int, data: CommentIn, db: DB, user: User = Depends(current_user)):
    project_id = project_for_task(db, task_id)
    membership(db, project_id, user.id, write=True)
    comment = Comment(task_id=task_id, author_id=user.id, text=data.text)
    db.add(comment)
    db.commit()
    await hub.broadcast(project_id)
    return {"id": comment.id}
