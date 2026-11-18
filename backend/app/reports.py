from datetime import datetime, timedelta, timezone
from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import select
from .db import SessionLocal, Project, Column, Task, Report

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
