import pytest
from fastapi.testclient import TestClient
from app.main import app
from asgi_lifespan import LifespanManager
from httpx import AsyncClient
from app.database import get_db
from app.models import GameSession
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch, Mock, MagicMock
from fastapi import HTTPException
from app.dependencies import get_current_user 
from sqlalchemy.future import select
from jose import JWTError
from collections import namedtuple
from app.analytics.routes import get_user_stats
from app.games.routes import get_leaderboard
from app.games.routes import start_game

client = TestClient(app)

def register_user(email: str, username: str, password: str = "test123"):
    return client.post("/auth/register", json={
        "username": username,
        "email": email,
        "password": password
    })

def login_user(email: str, password: str = "test123"):
    return client.post("/auth/login", json={
        "email": email,
        "password": password
    })

def test_double_login():
    email = "doublelogin@example.com"
    username = "doublelogin"
    register_user(email, username)
    res1 = login_user(email)
    res2 = login_user(email)
    assert res1.status_code == 200
    assert res2.status_code == 200

def test_duplicate_user_registration():
    email = "duplicate@example.com"
    username = "duplicateuser"
    register_user(email, username)
    res = register_user(email, username)
    assert res.status_code == 400 or res.status_code == 409

def start_game_token(token: str):
    return client.post("/games/start", headers={"Authorization": f"Bearer {token}"})

def stop_game(session_id: int, token: str):
    return client.post(f"/games/{session_id}/stop", headers={"Authorization": f"Bearer {token}"})

@pytest.mark.parametrize("email,username", [
    ("test22222@example.com", "user22222"),
    ("test33333@example.com", "user33333")
])

def test_game_flow(email, username):
    # Register
    res = register_user(email, username)
    assert res.status_code == 200

    # Login
    res = login_user(email)
    assert res.status_code == 200
    token = res.json()["access_token"]

    # Start Game
    res = start_game_token(token)
    assert res.status_code == 200
    session_id = res.json()["session_id"]

    # Stop Game
    res = stop_game(session_id, token)
    assert res.status_code == 200
    data = res.json()
    assert "duration_ms" in data
    assert "deviation_ms" in data
    assert 0 <= data["deviation_ms"] > 60

def test_stop_without_start():
    # Intentar detener sin iniciar sesión
    res = stop_game(999, "invalidtoken")
    assert res.status_code == 401

def test_start_without_token():
    res = client.post("/games/start")
    assert res.status_code == 401

def auth_token(email="test100@example.com", username="user100"):
    client.post("/auth/register", json={
        "email": email, "username": username, "password": "test123"
    })
    res = client.post("/auth/login", json={
        "email": email, "password": "test123"
    })
    return res.json()["access_token"]

def test_start_and_stop_game():
    token = auth_token()

    # Inicia juego
    res = client.post("/games/start", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    session_id = res.json()["session_id"]

    # Detiene juego
    res = client.post(f"/games/{session_id}/stop", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()
    assert "duration_ms" in data
    assert "deviation_ms" in data

def test_start_twice_should_fail():
    token = auth_token("test101@example.com", "user101")

    client.post("/games/start", headers={"Authorization": f"Bearer {token}"})
    res = client.post("/games/start", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 400
    assert "Existing session" in res.text

@pytest.mark.asyncio
async def test_stop_expired_game():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        # Registro y login
        await ac.post("/auth/register", json={
            "username": "stats_user2",
            "email": "expired@example.com",
            "password": "test123"
        })
        res = await ac.post("/auth/login", json={
            "email": "expired@example.com",
            "password": "test123"
        })
        token = res.json()["access_token"]

        # Inicia juego
        res = await ac.post("/games/start", headers={"Authorization": f"Bearer {token}"})
        session_id = res.json()["session_id"]
 
        async for db in get_db():
            result = await db.execute(
                select(GameSession).where(GameSession.id == session_id)
            )
            session = result.scalars().first()
            session.start_time = datetime.utcnow() - timedelta(minutes=31)
            await db.commit()
            break 

        # Intenta detenerlo
        res = await ac.post(f"/games/{session_id}/stop", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 400
        assert "Session expired" in res.text

def test_get_leaderboard():
    res = client.get("/games/")
    assert res.status_code == 200
    assert isinstance(res.json(), list)

@pytest.mark.asyncio
async def test_get_user_stats_not_found():
    async with LifespanManager(app):
        async with AsyncClient(app=app, base_url="http://test") as ac:
            res = await ac.get("/analytics/user/999999")  # ID no existente
            assert res.status_code == 404
            assert "User not found" in res.text

@pytest.mark.asyncio
async def test_leaderboard_empty():
    async with LifespanManager(app):
        async with AsyncClient(app=app, base_url="http://test") as ac:
            res = await ac.get("/leaderboard/")
            assert res.status_code == 200
            assert isinstance(res.json(), list)

@pytest.mark.asyncio
async def test_leaderboard_endpoint():
    async with LifespanManager(app):
        async with AsyncClient(app=app, base_url="http://test") as ac:
            # 1. Registro de usuario
            await ac.post("/auth/register", json={
                "username": "leader_player1",
                "email": "leader@example.com",
                "password": "test123"
            })

            # 2. Login
            res = await ac.post("/auth/login", json={
                "email": "leader@example.com",
                "password": "test123"
            })
            token = res.json()["access_token"]

            # 3. Iniciar y detener juego
            start_res = await ac.post("/games/start", headers={"Authorization": f"Bearer {token}"})
            session_id = start_res.json()["session_id"]

            stop_res = await ac.post(f"/games/{session_id}/stop", headers={"Authorization": f"Bearer {token}"})
            assert stop_res.status_code == 200

            # 4. Consultar leaderboard
            lb_res = await ac.get("/leaderboard/")
            assert lb_res.status_code == 200

            leaderboard = lb_res.json()
            assert any(player["username"] == "leader_player1" for player in leaderboard)
 
@pytest.mark.asyncio
async def test_user_stats_not_found():
    async with LifespanManager(app):
        async with AsyncClient(app=app, base_url="http://test") as ac:
            res = await ac.get("/analytics/user/999999")  # id que no existe
            assert res.status_code == 404
            assert res.json()["detail"] == "User not found"

@pytest.mark.asyncio
async def test_get_user_stats_route(monkeypatch):
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.get("/user/1")
        assert response.status_code in (200, 404)

@pytest.mark.asyncio
async def test_get_user_stats_user_not_found():
    mock_db = AsyncMock()
    mock_scalars = Mock()
    mock_scalars.first.return_value = None

    mock_result = Mock()
    mock_result.scalars.return_value = mock_scalars

    mock_db.execute.return_value = mock_result

    with pytest.raises(HTTPException) as exc:
        await get_user_stats(user_id=999, db=mock_db)

    assert exc.value.status_code == 404
    assert exc.value.detail == "User not found"

# Simulaciones 
UserMock = namedtuple("User", ["username"])
GameMock = namedtuple("GameSession", ["id", "start_time", "duration", "deviation", "status"])

@pytest.mark.asyncio
async def test_get_user_stats_success():
    mock_db = AsyncMock()

    # --- Mock usuario ---
    user = UserMock(username="testuser")
    mock_user_scalars = Mock()
    mock_user_scalars.first.return_value = user

    user_result = Mock()
    user_result.scalars.return_value = mock_user_scalars

    # --- Mock juegos ---
    games = [
        GameMock(1, "2024-01-01T10:00:00Z", 9000.0, 1000.0, "stopped"),
        GameMock(2, "2024-01-02T10:00:00Z", None, None, "stopped")
    ]
    mock_games_scalars = Mock()
    mock_games_scalars.all.return_value = games

    games_result = Mock()
    games_result.scalars.return_value = mock_games_scalars

    # --- Mock estadísticas ---
    stats_result = Mock()
    stats_result.one.return_value = (2, 1000.0, 1000.0, 1000.0)

    # Encadena los 3 resultados para cada llamado a `db.execute`
    mock_db.execute.side_effect = [user_result, games_result, stats_result]

    # Ejecutar la función
    result = await get_user_stats(user_id=1, db=mock_db)

    # Verificar resultados
    assert result["username"] == "testuser"
    assert result["total_games"] == 2
    assert result["average_deviation_ms"] == 1000.0
    assert result["best_deviation_ms"] == 1000.0
    assert result["worst_deviation_ms"] == 1000.0
    assert len(result["history"]) == 2
    assert result["history"][0]["deviation_ms"] == 1000.0
    assert result["history"][1]["duration_ms"] == 0.0  # None convertido a 0.0

@pytest.mark.asyncio
async def test_get_leaderboard_success():
    mock_db = AsyncMock()

    # Simulamos resultados del query
    RowMock = lambda username, games, avg, best: type(
        "Row",
        (),
        {
            "username": username,
            "games_played": games,
            "avg_deviation": avg,
            "best_deviation": best
        },
    )

    rows = [
        RowMock("alice", 10, 200.456, 100.123),
        RowMock("bob", 8, 250.0, 150.0)
    ]

    result_mock = Mock()
    result_mock.all.return_value = rows
    mock_db.execute.return_value = result_mock

    # Ejecutar función
    response = await get_leaderboard(db=mock_db, skip=0, limit=10)

    assert len(response) == 2
    assert response[0]["username"] == "alice"
    assert response[1]["total_games"] == 8
    assert response[0]["average_deviation_ms"] == 200.46  # redondeo
    assert response[0]["best_deviation_ms"] == 100.12
 
@patch("app.dependencies.jwt.decode")
@pytest.mark.asyncio
async def test_get_current_user_missing_sub(mock_decode):
    mock_decode.return_value = {}

    mock_db = AsyncMock()

    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(token="token-sin-sub", db=mock_db)

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Could not validate credentials"
    mock_decode.assert_called_once()

@patch("app.dependencies.jwt.decode", side_effect=JWTError("Invalid token"))
@pytest.mark.asyncio
async def test_get_current_user_invalid_token(mock_decode):
    mock_db = AsyncMock()
    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(token="invalid-token", db=mock_db)

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Could not validate credentials"
    mock_decode.assert_called_once()


@patch("app.auth.auth_dependencies.jwt.decode")
@pytest.mark.asyncio
async def test_get_current_user_success(mock_decode):
    mock_decode.return_value = {"sub": "1"}

    mock_db = AsyncMock()

    # Simula un usuario válido
    mock_user = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.first.return_value = mock_user

    mock_result = MagicMock()
    mock_result.scalars.return_value = mock_scalars

    mock_db.execute.return_value = mock_result

    user = await get_current_user(token="token-valido", db=mock_db)

    assert user == mock_user
    mock_decode.assert_called_once()

@patch("app.auth.auth_dependencies.jwt.decode")
@pytest.mark.asyncio
async def test_get_current_user_user_not_found(mock_decode):
    mock_decode.return_value = {"sub": "1"}  # Simula user_id = 1

    mock_db = AsyncMock()
 
    mock_scalars = MagicMock()
    mock_scalars.first.return_value = None

    mock_result = MagicMock()
    mock_result.scalars.return_value = mock_scalars

    mock_db.execute.return_value = mock_result

    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(token="valido-pero-user-no-existe", db=mock_db)

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Could not validate credentials"


def test_websocket_leaderboard():
    with client.websocket_connect("/ws/leaderboard") as websocket:
        response = websocket.receive_json()
        assert "leaderboard" in response
        assert isinstance(response["leaderboard"], list)
        assert all("username" in user for user in response["leaderboard"])