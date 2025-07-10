import asyncio
from fastapi import WebSocket, WebSocketDisconnect
from typing import List
from app.leaderboard.routes import get_leaderboard 
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.database import SessionLocal


class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            await connection.send_json(message)

manager = ConnectionManager()

async def leaderboard_websocket_endpoint(websocket: WebSocket, db: AsyncSession):
    await manager.connect(websocket)
    try:
        while True:
            leaderboard = await get_leaderboard(db=db, skip=0, limit=10)
            await manager.broadcast({"leaderboard": leaderboard})
            await asyncio.sleep(3)
    except WebSocketDisconnect:
        manager.disconnect(websocket)