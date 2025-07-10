from fastapi import FastAPI, WebSocket, Depends
from fastapi.middleware.cors import CORSMiddleware
from app.database import Base, engine
from app.auth.routes import router as auth_router
from app.games.routes import router as games_router
from app.leaderboard.routes import router as leaderboard_router
from app.analytics.routes import router as analytics_router
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.websockets.leaderboard import leaderboard_websocket_endpoint

app = FastAPI(title="Time It Right 🎯")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

# Incluir rutas
app.include_router(auth_router, prefix="/auth", tags=["Auth"])
app.include_router(games_router, prefix="/games", tags=["Games"])
app.include_router(leaderboard_router, prefix="/leaderboard", tags=["Leaderboard"])
app.include_router(analytics_router, prefix="/analytics", tags=["Analytics"])

#ws
@app.websocket("/ws/leaderboard")
async def ws_leaderboard(websocket: WebSocket, db: AsyncSession = Depends(get_db)):
    await leaderboard_websocket_endpoint(websocket, db)
