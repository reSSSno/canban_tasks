from pydantic import BaseModel, EmailStr, Field

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
