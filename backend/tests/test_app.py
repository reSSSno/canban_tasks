import os
import tempfile

path = tempfile.mktemp(suffix=".db")
os.environ["DATABASE_URL"] = "sqlite:///" + path
os.environ["JWT_SECRET"] = "test-secret"

from fastapi.testclient import TestClient
from app.main import app


def test_project_and_guest_permissions():
    with TestClient(app) as client:
        for name in ("owner", "guest"):
            response = client.post("/api/register", json={"name": name, "email": name + "@example.com", "password": "password123"})
            assert response.status_code == 200
        owner = client.post("/api/login", json={"email": "owner@example.com", "password": "password123"}).json()["token"]
        guest = client.post("/api/login", json={"email": "guest@example.com", "password": "password123"}).json()["token"]
        owner_headers = {"Authorization": "Bearer " + owner}
        guest_headers = {"Authorization": "Bearer " + guest}
        project = client.post("/api/projects", json={"name": "Учебный проект"}, headers=owner_headers)
        assert project.status_code == 200
        project_id = project.json()["id"]
        board = client.get(f"/api/projects/{project_id}/board", headers=owner_headers).json()
        assert len(board["columns"]) == 4
        column_id = board["columns"][0]["id"]
        assert client.post(f"/api/projects/{project_id}/members", json={"email": "guest@example.com", "role": "гость"}, headers=owner_headers).status_code == 200
        assert client.get(f"/api/projects/{project_id}/board", headers=guest_headers).status_code == 200
        assert client.post(f"/api/columns/{column_id}/tasks", json={"title": "Нельзя изменять"}, headers=guest_headers).status_code == 403
        task = client.post(f"/api/columns/{column_id}/tasks", json={"title": "Новая задача"}, headers=owner_headers)
        assert task.status_code == 200
        task_id = task.json()["id"]
        assert client.post(f"/api/tasks/{task_id}/comments", json={"text": "Тест"}, headers=guest_headers).status_code == 403
        assert client.post(f"/api/tasks/{task_id}/comments", json={"text": "Тест"}, headers=owner_headers).status_code == 200
        assert len(client.get(f"/api/tasks/{task_id}/comments", headers=guest_headers).json()) == 1
