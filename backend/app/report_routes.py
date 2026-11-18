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

@router.get("/api/projects/{project_id}/reports")
def reports(project_id: int, db: DB, user: User = Depends(current_user)):
    membership(db, project_id, user.id)
    rows = db.scalars(select(Report).where(Report.project_id == project_id).order_by(Report.generated_at.desc()).limit(20)).all()
    return [{"date": r.generated_at.isoformat(), "completed": r.completed, "total": r.total} for r in rows]
