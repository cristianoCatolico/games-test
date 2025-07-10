from fastapi import APIRouter, Depends, HTTPException, status,Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from datetime import datetime, timedelta
from app.database import get_db
from app.auth.auth_dependencies import get_current_user
from app import models
from app.models import User, GameSession
from sqlalchemy import func, select
from datetime import UTC

router = APIRouter()

@router.get("/", summary="Top 10 players by average deviation")
async def get_leaderboard(
    db: AsyncSession = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(10, le=100)
):
    subquery = (
        select(
            GameSession.user_id,
            func.count(GameSession.id).label("games_played"),
            func.avg(GameSession.deviation).label("avg_deviation"),
            func.min(GameSession.deviation).label("best_deviation")
        )
        .where(GameSession.status == "stopped")
        .group_by(GameSession.user_id)
        .subquery()
    )

    query = (
        select(
            User.username,
            subquery.c.games_played,
            subquery.c.avg_deviation,
            subquery.c.best_deviation
        )
        .join(subquery, User.id == subquery.c.user_id)
        .order_by(subquery.c.avg_deviation.asc())
        .offset(skip)
        .limit(limit)
    )

    result = await db.execute(query)
    leaderboard = result.all()

    return [
        {
            "username": row.username,
            "total_games": row.games_played,
            "average_deviation_ms": round(row.avg_deviation, 2),
            "best_deviation_ms": round(row.best_deviation, 2)
        }
        for row in leaderboard
    ]


@router.post("/start")
async def start_game(db: AsyncSession = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    # Check for existing active session
    result = await db.execute(
        select(models.GameSession).where(
            models.GameSession.user_id == current_user.id,
            models.GameSession.status == "started"
        )
    )
    existing_session = result.scalars().first()
    if existing_session:
        raise HTTPException(status_code=400, detail="Existing session already in progress")

    new_session = models.GameSession(
        user_id=current_user.id,
        start_time=datetime.utcnow(),
        status="started"
    )
    db.add(new_session)
    await db.commit()
    await db.refresh(new_session)
    return {"session_id": new_session.id, "message": "Timer started"}

@router.post("/{session_id}/stop")
async def stop_game(session_id: int, db: AsyncSession = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    result = await db.execute(
        select(models.GameSession).where(
            models.GameSession.id == session_id,
            models.GameSession.user_id == current_user.id
        )
    )
    session = result.scalars().first()

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.status != "started":
        raise HTTPException(status_code=400, detail="Session already stopped or expired")

    now = datetime.utcnow()
    if now - session.start_time > timedelta(minutes=30):
        session.status = "expired"
        await db.commit()
        raise HTTPException(status_code=400, detail="Session expired")

    session.stop_time = now
    duration = (session.stop_time - session.start_time).total_seconds() * 1000  # in ms
    deviation = abs(duration - 10000)
    session.duration = duration
    session.deviation = deviation
    session.status = "stopped"
    await db.commit()

    return {
        "message": "Timer stopped",
        "duration_ms": round(duration, 2),
        "deviation_ms": round(deviation, 2)
    }
