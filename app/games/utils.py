from sqlalchemy import select, func
from app.models import GameSession, User

async def get_leaderboard_data(db):
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
