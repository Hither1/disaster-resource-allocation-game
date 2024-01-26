from sqlalchemy.orm import Session
from . import models, schemas
from sqlalchemy import and_, or_, func

def get_episode_by_uid(db: Session, uid: str):
    query = db.query(func.count(models.Game.userid)).filter(and_(models.Game.userid == uid, models.Game.time_spent=='start'))
    return query.scalar()

def check_exist(db: Session, uid: str):
    return bool(db.query(models.Game).filter_by(userid = uid).first())

def create_game(db: Session, game: schemas.GameCreate): 
    db_game = models.Game(userid=game.userid, group=game.group, role=game.role, episode=game.episode, target=game.target, \
        target_pos=game.target_pos, num_step=game.num_step, time_spent=game.time_spent, \
        trajectory=game.trajectory)
    db.add(db_game)
    db.commit()
    db.refresh(db_game)
    return db_game