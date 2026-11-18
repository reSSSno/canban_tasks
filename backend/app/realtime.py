from fastapi import WebSocket

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
