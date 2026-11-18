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

@router.post("/api/columns/{column_id}/tasks")
async def create_task(column_id: int, data: TaskIn, db: DB, user: User = Depends(current_user)):
    project_id = project_for_column(db, column_id)
    membership(db, project_id, user.id, write=True)
    validate_assignee(db, project_id, data.assignee_id)
    task = Task(column_id=column_id, **data.model_dump())
    db.add(task)
    db.commit()
    await hub.broadcast(project_id)
    return task_dict(task)


@router.patch("/api/tasks/{task_id}")
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


@router.delete("/api/tasks/{task_id}")
async def delete_task(task_id: int, db: DB, user: User = Depends(current_user)):
    project_id = project_for_task(db, task_id)
    membership(db, project_id, user.id, write=True)
    db.query(Comment).filter(Comment.task_id == task_id).delete()
    db.delete(db.get(Task, task_id))
    db.commit()
    await hub.broadcast(project_id)
    return {"message": "Задача удалена"}
