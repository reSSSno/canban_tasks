"""FastAPI application and lifecycle configuration."""
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .db import Base, engine
from .reports import scheduler, weekly_reports
from . import auth, projects, tasks, comments, report_routes, ws

@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(engine)
    scheduler.add_job(weekly_reports, "cron", day_of_week="mon", hour=8, id="weekly_report", replace_existing=True)
    scheduler.start()
    try:
        yield
    finally:
        scheduler.shutdown(wait=False)

app = FastAPI(title="Командная доска задач", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:5173").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)
for router in (auth.router, projects.router, tasks.router, comments.router, report_routes.router, ws.router):
    app.include_router(router)
