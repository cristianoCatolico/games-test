from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select
from app.database import get_db
from app.models import User, GameSession

router = APIRouter()

@router.get("/")
async def get_leaderboard(db: AsyncSession = Depends(get_db), skip: int = 0, limit: int = 10):
    subquery = (
        select(
            GameSession.user_id,
            func.count(GameSession.id).label("total_games"),
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
            subquery.c.total_games,
            subquery.c.avg_deviation,
            subquery.c.best_deviation
        )
        .join(subquery, User.id == subquery.c.user_id)
        .order_by(subquery.c.avg_deviation.asc())
        .offset(skip)
        .limit(limit)
    )

    result = await db.execute(query)
    rows = result.all()

    return [
        {
            "username": r.username,
            "total_games": r.total_games,
            "average_deviation": round(r.avg_deviation, 2),
            "best_deviation": round(r.best_deviation, 2)
        }
        for r in rows
    ]

