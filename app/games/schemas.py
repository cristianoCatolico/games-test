from pydantic import BaseModel
from datetime import datetime
from typing import Optional
from pydantic import BaseModel
from pydantic.config import ConfigDict

class GameStartResponse(BaseModel):
    session_id: int
    start_time: datetime

    class Config:
        model_config = ConfigDict(from_attributes=True)

class GameStopResponse(BaseModel):
    session_id: int
    stop_time: datetime
    duration_ms: float
    deviation_ms: float
    message: str

    class Config:
        model_config = ConfigDict(from_attributes=True)
