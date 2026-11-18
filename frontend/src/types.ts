export type Task = { id: number; column_id: number; title: string; description: string; priority: string; due_date: string | null; assignee_id: number | null };
export type Member = { id: number; name: string; email: string; role: string };
export type Board = { role: string; columns: { id: number; name: string; tasks: Task[] }[]; members: Member[] };
export type Project = { id: number; name: string; role: string };
