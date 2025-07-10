from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func
from app.database import get_db
from app.models import User, GameSession

router = APIRouter()

@router.get("/user/{user_id}", summary="User game statistics")
async def get_user_stats(user_id: int, db: AsyncSession = Depends(get_db)):
    user_result = await db.execute(select(User).where(User.id == user_id))
    user = user_result.scalars().first() 

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    games_result = await db.execute(
        select(GameSession).where(GameSession.user_id == user_id).order_by(GameSession.created_at.desc())
    )
    games = games_result.scalars().all()

    stats_result = await db.execute(
        select(
            func.count(GameSession.id),
            func.avg(GameSession.deviation),
            func.min(GameSession.deviation),
            func.max(GameSession.deviation)
        ).where(GameSession.user_id == user_id, GameSession.status == "stopped")
    )
    total, avg_dev, min_dev, max_dev = stats_result.one()

    return {
        "username": user.username,
        "total_games": total,
        "average_deviation_ms": round(avg_dev or 0, 2),
        "best_deviation_ms": round(min_dev or 0, 2),
        "worst_deviation_ms": round(max_dev or 0, 2),
        "history": [
            {
                "session_id": g.id,
                "started_at": g.start_time,
                "duration_ms": round(g.duration or 0, 2),
                "deviation_ms": round(g.deviation or 0, 2),
                "status": g.status
            }
            for g in games
        ]
    }
