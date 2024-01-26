from typing import List
from pydantic import BaseModel


class GameBase(BaseModel):
    userid: str
    group:str
    

class GameCreate(GameBase):
    role:str
    episode: int
    target: str
    target_pos: str
    num_step: int
    time_spent: str
    # actions: str
    trajectory: str

class Game(GameBase):
    id: int
    userid: str
    group:str

    class Config:
        orm_mode = True