from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.sql import func
from .db import Base

class Game(Base):
    __tablename__ = "game"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    userid = Column(String, nullable=False)
    group = Column(String, nullable=False)
    role = Column(String, nullable=True)
    episode = Column(Integer, nullable=False)
    target = Column(String)
    target_pos = Column(String)
    num_step = Column(Integer)
    time_spent = Column(String)
    # actions = Column(String)
    trajectory = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# class Survey(Base):
#     __tablename__ = "survey"
#     id = Column(Integer, primary_key=True, index=True, autoincrement=True)
#     userid = Column(String, nullable=False)
#     created_at = Column(DateTime(timezone=True), server_default=func.now())