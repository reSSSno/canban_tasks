def task_dict(task):
    return {"id": task.id, "column_id": task.column_id, "title": task.title,
            "description": task.description, "priority": task.priority,
            "due_date": task.due_date, "assignee_id": task.assignee_id}
