from fastapi import Request, Form
from fastapi import Depends
from sqlalchemy.orm import Session

# from . import models, schemas, crud
# from .db import ENGINE, SessionLocal

# models.Base.metadata.create_all(bind=ENGINE)

from fastapi_socketio import SocketManager
from engineio.payload import Payload
Payload.max_decode_packets = 16

from utils import NumpyEncoder
import random
import os
import time
import asyncio
import numpy as np
import pandas as pd
import argparse
import sys
import glob

import json
import crafter
from collections import deque

from datetime import datetime, timedelta

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import socketio
import asyncio


#asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
app = FastAPI()

sio = socketio.AsyncServer(cors_allowed_origins='*', async_mode = 'asgi')
app.mount("/socket.io", socketio.ASGIApp(sio))
app.mount("/static", StaticFiles(directory="./static"), name="static")
templates = Jinja2Templates(directory="./templates")
sio = SocketManager(app=app)

#######################
# Database connection #
#######################

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

##################
# Global configs #
##################

# Read in global config
# CONF_PATH = os.path.join(os.getcwd(), "/config.json")
# with open(CONF_PATH, 'r') as f:
#     CONFIG = json.load(f)

# game_duration = CONFIG['game_duration']
# max_humans_per_room = int(CONFIG['max_humans_per_room'])
# max_bots_per_room = int(CONFIG['max_bots_per_room'])
# max_players_per_room = max_humans_per_room + max_bots_per_room
# map_file_list = CONFIG['map_file_list']

# map_list = []
# path = "mission/static/maps"
# for file in map_file_list:
#     map_list.append(pd.read_csv(os.path.join(path, f'{file}.csv')))

# max_episode = len(map_list)

###################
# Global trackers #
###################

USER_MAP_SESSION = {}

DATA_DIR = os.path.join(os.getcwd(),'data')
is_exist = os.path.exists(DATA_DIR)
if not is_exist:
  os.makedirs(DATA_DIR)
  print(f"The new directory {DATA_DIR} is created!")

FAILURE_SESSION = []
LOGIN_NAMES_TEMP = []
connections = {}

player_roomid = {} #list room_id corresponding to userid
roomid_event_queue = {}
roomid_game_loops = {}
roomid_players = {} #dictionary of rooms:{room1:{player1:{}, player2:{}}, room2:{player21:{'x', 'y'}, player22:{'x','y'}}}
roomid_scoreboard = {} #dictionary of scores: {room1:{green:0, yellow:0, red:0}, room2:{green:0, yellow:0, red:0}}
roomid_env = {}
roomid_start_time = {}
roomid_cur_ep_players = {}
roomid_started = {}

# Per room per episode
roomid_episode = {}
timer_recording = {} # list of timer recording each group's data
room_data = {} #room_id and values is the list of players' events
roomid_ep_keypresses = {}
roomid_ep_states = {}


key_code_dict = {87: "up", 38: "up", 65: "left", 37: "left",  68: "right", 39: "right", 83: "down", 40: "down", 13: "enter", 0: "stay"}

##########################
# Loading trained agents #
##########################

import pickle
trained_IBL = False
if trained_IBL:
    print("Current environment: ", os.getcwd())
    print("Loading pickle file")
    agents_trained = pickle.load(open('mission/MapIBL/agent-td.pickle','rb'))
    


sys.argv=['']
del sys
flags = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter, description="IBL")
flags.add_argument('--type',type=str,default='td',help='Environment.')
flags.add_argument('--episodes',type=int,default=1000,help='Number of episodes.') #ok results with 1000
FLAGS = flags.parse_args()

role_name = {0:'medic', 1:'engineer'}

###########################
# Server socket functions #
###########################

# Client connected to server
@app.sio.on('connect')
async def on_connect(sid: str, *args, **kwargs):
    print('User id (connected socketid): ', sid)
    await app.sio.emit('connect success')

# Need to work on this
# Client disconnected from server
@app.sio.on('disconnect')
async def on_disconnect(sid: str, *args, **kwargs):
    global player_roomid
    global USER_MAP_SESSION
    global roomid_players
    print('Disconnected socket id: ', sid)
    
    if sid in USER_MAP_SESSION:
        uid = USER_MAP_SESSION[sid]
        roomid = player_roomid[uid]
        if uid in roomid_players[roomid]:
            del roomid_players[roomid][uid]
        if uid in roomid_cur_ep_players[roomid]:
            roomid_cur_ep_players[roomid].remove(uid)
        app.sio.leave_room(sid, roomid)
        await app.sio.emit('leave',{'uid':uid}, room=roomid)
            
    else:
        print('Nothing in USER_MAP_SESSION')

@app.sio.on('join_room')
async def on_join(sid, *args):
    global player_roomid
    global roomid_players
    global map_list
    global roomid_ep_states
    global roomid_ep_keypresses
    global roomid_env
    global roomid_episode

    uid = args[0]['uid']
    agent_type = args[0]['agent_type']
    
    # Create mapping from session id to user id
    USER_MAP_SESSION[sid] = uid
    
    # If uid has not already appeared before
    if uid not in player_roomid:
        # Room logic
        # If no rooms exist, create a new room and put uid in that room
        if len(roomid_players) == 0:
            roomid = 0
            if agent_type == 'human':
                roomid_players[roomid] = {uid: {'human': True}}
            else:
                roomid_players[roomid] = {uid: {'human': False}}
            
            # Initialize ready player list, episode number, and data trackers upon creation of room
            roomid_cur_ep_players[roomid] = set()
            roomid_episode[roomid] = 0
            roomid_ep_keypresses[roomid] = {}
            roomid_ep_states[roomid] = {}
            roomid_started[roomid] = False
            

        # Otherwise, check for partially-filled rooms and add uid to the earliest partially-filled room
        else:
            added = False
            for i in range(len(roomid_players)):
                if agent_type == "human":
                    num_humans = 0
                    for agent, values in roomid_players[i].items():
                        if values['human'] == True:
                            num_humans += 1
                    if num_humans < max_humans_per_room:
                        roomid = i
                        roomid_players[roomid][uid] = {'human': True}
                        
                        added = True
                        break
                else:
                    num_bots = 0
                    for agent, values in roomid_players[i].items():
                        if values['human'] == False:
                            num_bots += 1
                    if num_bots < max_bots_per_room:
                        roomid = i
                        roomid_players[roomid][uid] = {'human': False}
                        
                        added = True
                        break
            if added == False:
                roomid = len(roomid_players)
                if agent_type == 'human':
                    roomid_players[roomid] = {uid: {'human': True}}
                else:
                    roomid_players[roomid] = {uid: {'human': False}}
                
        player_roomid[uid] = roomid
    else:
        roomid = player_roomid[uid]
        
    app.sio.enter_room(sid, roomid)
    print("room joined")

@app.sio.on('ready')
async def on_ready(sid, *args):
    global roomid_cur_ep_players
    global roomid_players
    global player_roomid
    global roomid_episode
    global map_list
    global roomid_ep_keypresses
    global roomid_ep_states
    global roomid_started
    global clear_rates

    uid = args[0]['uid']
    roomid = player_roomid[uid]
    episode_num = roomid_episode[roomid]

    roomid_cur_ep_players[roomid].add(uid)


    if len(roomid_cur_ep_players[roomid]) < max_players_per_room:
        if uid not in FAILURE_SESSION:
            # print(msg['uid'], 'calls waiting...')
            await app.sio.emit('waiting', {'in_game':True, 'max_size':max_players_per_room, 'status':len(roomid_cur_ep_players[roomid])}, room=roomid, to=sid) 
        else:
            await app.sio.emit('waiting', {'in_game':False, 'max_size':max_players_per_room, 'status':len(roomid_cur_ep_players[roomid])}, room=roomid, to=sid)
    
    elif len(roomid_cur_ep_players[roomid]) == max_players_per_room and roomid_started[roomid] == False:

        roomid_started[roomid] = True
        # Initialize map environment, scoreboard, and data trackers
        config, _ = crafter.config.get_config()
        roomid_env[roomid] = crafter.Env(config)
        roomid_scoreboard[roomid] = {'Food':0, 'Drink':0, 'Staff':0}
        roomid_ep_keypresses[roomid][episode_num] = []
        roomid_ep_states[roomid][episode_num] = []
            
        startGame(roomid)
        await app.sio.emit('start_game',
                           {'episode': episode_num, 'map': roomid_env[roomid].state_map, 'scoreboard': roomid_scoreboard[roomid]},
                            room=roomid)
         

def startGame(roomid):
    global roomid_env
    global roomid_players
    global roomid_event_queue
    global roomid_episode

    print("game started")
    # Pair all human players with an existing in-game human agent
    #if len(roomid_env[roomid].humans) == len(roomid_players[roomid]):
    human_i = 0
    bot_i = 0
    for uid, values in roomid_players[roomid].items():
        if values['human'] == True:
            roomid_players[roomid][uid] = {'coord':roomid_env[roomid].humans[human_i]['start_coord'], \
                                                'role':roomid_env[roomid].humans[human_i]['role'], \
                                                'keysdown': [], \
                                                'enter_start_time': 0.0, \
                                                'human': True, \
                                                'ref_int': human_i}
            human_i += 1
        else:
            roomid_players[roomid][uid] = {'coord':roomid_env[roomid].bots[bot_i]['start_coord'], \
                                                'role':roomid_env[roomid].bots[bot_i]['role'], \
                                                'keysdown': [], \
                                                'enter_start_time': 0.0, \
                                                'human': False, \
                                                'ref_int': bot_i}
            bot_i += 1
    
    # Reset environment
    roomid_env[roomid].reset()

    # Create event queue
    roomid_event_queue[roomid] = deque()

    episode = roomid_episode[roomid]

    # Start running game loop
    asyncio.create_task(gameLoop(roomid, episode))
    

@app.sio.on('request_update')
async def requestUpdate(sid, *args, **kwargs):
    global roomid_event_queue
    global player_roomid
    global roomid_players
    global game_duration
    global roomid_start_time
    global roomid_episode

    msg = args[0]
    uid = msg['uid']
    roomid = player_roomid[uid]
    timestamp = time.time() - roomid_start_time[roomid]
    time_left = game_duration - timestamp
    return({'map': roomid_env[roomid].state_map, 'scoreboard': roomid_scoreboard[roomid], \
                             'players': roomid_players[roomid], 'remaining_time': time_left})

##################
# Game tick loop #
##################

async def gameLoop(roomid, episode):
    global roomid_event_queue
    global player_roomid
    global roomid_players
    global game_duration
    global roomid_start_time
    global roomid_episode
    global roomid_ep_states
    global roomid_ep_keypresses

    start_time = time.time()
    roomid_start_time[roomid] = start_time

    yellow_removed = False
    red_removed = False

    while time.time() - start_time < game_duration:
        await asyncio.sleep(1/60)  # emit rate
        timestamp = time.time() - start_time
        time_left = game_duration - timestamp
        #state_change = False

        while len(roomid_event_queue[roomid]) > 0:
            event = roomid_event_queue[roomid].popleft()
            temp_event = event
            temp_event['process_time'] = time.time()
            roomid_ep_keypresses[roomid][episode].append(temp_event)
            #state_change = True
            #temp_event = event
            #temp_event['timestamp'] = timestamp
            #roomid_ep_keypresses[roomid][episode].append(temp_event)
            # change game state according to event
            uid, agent_coord, rescues = roomid_env[roomid].step(event)

            # update player position
            roomid_players[roomid][uid]['coord'] = agent_coord

            # update scoreboard
            for rescue in rescues:
                if rescue in ['green', 'yellow', 'red']:
                    roomid_scoreboard[roomid][rescue] += 1


            # Clear event queue for next game tick

            # Broadcast game state to all clients
            # Includes state_map and scoreboard

        if not yellow_removed and timestamp > roomid_env[roomid].death_timers['yellow']:
            roomid_env[roomid].expire("yellow")
            yellow_removed = True
            state_change = True
        
        if not red_removed and timestamp > roomid_env[roomid].death_timers['red']:
            roomid_env[roomid].expire("red")
            red_removed = True
            state_change = True

        #if state_change == True:

        #    roomid_ep_states[roomid][episode].append({'map': roomid_env[roomid].state_map, 'scoreboard': roomid_scoreboard[roomid], \
        #                                            'players': roomid_players[roomid], 'timestamp': timestamp})
        

        # To human players 
        await app.sio.emit('refresh', \
                            {'map': roomid_env[roomid].state_map, 'scoreboard': roomid_scoreboard[roomid], 
                             'players': roomid_players[roomid], 'remaining_time': time_left}, \
                            room=roomid)
        
        if sum(roomid_scoreboard[roomid].values()) >= roomid_env[roomid].goals:
            break
    
    # End episode when time runs out

    # "Unready" all players in the room
    
    print("episode ended")
    
    # Function to store data here
    # Write data to file - but need to decide the format to write

    #with open(f'{DATA_DIR}/room_{roomid}_ep_{episode}_state.json', 'w') as outfile:
    #    json.dump(roomid_ep_states[roomid][episode], outfile)

    with open(f'{DATA_DIR}/room_{roomid}_ep_{episode}_keypresses.json', 'w') as outfile:
        json.dump(roomid_ep_keypresses[roomid][episode], outfile)
    
    
    
    if episode < max_episode-1:
        await app.sio.emit('end_episode', {'episode': episode}, room=roomid)
        roomid_cur_ep_players[roomid] = set()
        roomid_episode[roomid] += 1
        roomid_started[roomid] = False
    else:
        await app.sio.emit('end_game', {}, room=roomid)
        roomid_cur_ep_players[roomid] = set()


###############
# Per episode #
###############

# Each episode needs to have a map layout
# Needs to be initialized, run, and closed
# Each episode should also have a file or two files associated with its events


##########################
# Listeners and handlers #
##########################

@app.sio.on('keyEvent')
async def keyEvent(sid, *args, **kwargs):

    global roomid_players
    global player_roomid
    global roomid_event_queue
    global roomid_episode
    global roomid_start_time
    global roomid_started
    global roomid_ep_keypresses

    msg = args[0]
    uid = msg['uid']
    event = msg['event']

    if msg['key'] in key_code_dict:
        key_name = key_code_dict[msg['key']]
        roomid = player_roomid[uid]
        episode = roomid_episode[roomid]
        if roomid_started[roomid] == True:
            cur_time = time.time()

            roomid_event_queue[roomid].append({'uid': uid, 'agent_info': roomid_players[roomid][uid], 'key': key_name, 'event': event, 'time': cur_time})

            ep_start_time = roomid_start_time[roomid]
            #ep_cur_time = cur_time - ep_start_time
            #roomid_ep_keypresses[roomid][episode].append({'timestamp': ep_cur_time, 'uid': uid, 'event': event, 'key': key_name})
    return

@app.sio.on('end')
async def handle_episode(sid, *args, **kwargs):
    global agents
    global roomid_ep_keypresses
    global roomid_ep_states
    msg = args[0]
    print('received episode info: ' + str(msg))
    game_over = msg['episode']
    print("END EPISODE: ", game_over)

    uid = msg['uid']
    if uid in player_roomid:
        if uid in roomid_players[player_roomid[msg['uid']]]:
            roomid_players[player_roomid[msg['uid']]][uid]['coord']= [msg["y"], msg["x"]]
            roomid_players[player_roomid[msg['uid']]][uid]['uid']=msg["uid"]
            roomid_players[player_roomid[msg['uid']]][uid]['timestamp']=datetime.now().timestamp()
            roomid_players[player_roomid[msg['uid']]][uid]['mission_time']=msg["mission_time"]
            roomid_players[player_roomid[msg['uid']]][uid]['event']=msg["event"]
            roomid_players[player_roomid[msg['uid']]][uid]['score']=roomid_scoreboard[player_roomid[msg['uid']]]
            
            room_data[player_roomid[msg['uid']]].append(json.dumps(roomid_players[player_roomid[msg['uid']]],cls=NumpyEncoder))
            if datetime.now() >= timer_recording[player_roomid[msg['uid']]]['start'] + timedelta(seconds=1):
                room_data[player_roomid[msg['uid']]].append(json.dumps(roomid_players[player_roomid[msg['uid']]],cls=NumpyEncoder))
                timer_recording[player_roomid[msg['uid']]]['start'] = datetime.now()
        else:
            print('End episode...', roomid_players[player_roomid[msg['uid']]])
    
    group_idx = player_roomid[msg['uid']]
    gid = msg['gid']
    with open(f'{DATA_DIR}/data_group_{gid}_episode_{game_over}.json', 'w') as outfile:
        json.dump(room_data[group_idx], outfile)
    

@app.sio.on('leave')
async def on_leave(sid, *args, **kwargs):
    user_id = USER_MAP_SESSION[sid]
    room_id=player_roomid[user_id]
    if user_id in connections[room_id]:
        del connections[room_id][connections[room_id].index(user_id)]
    FAILURE_SESSION.append(user_id)
    await app.sio.emit('end_lobby', {'uid':user_id}, room=player_roomid[user_id])

######################
# Application routes #
######################

# No need to touch these for now

@app.get("/")
async def index(request:Request):
    return {"message": "Welcome"}

@app.get("/fov/{uid}")
async def load_instructions_fov(request:Request, uid:str, session:int=1, db: Session = Depends(get_db)):
    print("Getting uid: ", uid)
    exist = crud.check_exist(db, uid)
    print("Exist: ", exist)
    if uid not in LOGIN_NAMES_TEMP:
        LOGIN_NAMES_TEMP.append(uid)
        if exist is False:
            return templates.TemplateResponse("start.html", {"request":request, "data":uid, "session":session})
        else:
            return templates.TemplateResponse("failure.html", {"request":request, "data":uid, "session":session})
    else:
        return templates.TemplateResponse("failure.html", {"request":request, "data":uid, "session":session})


@app.get("/fullmap/{uid}")
async def load_instructions_fov(request:Request, uid:str, session:int=1, db: Session = Depends(get_db)):
    print("Getting uid: ", uid)
    exist = crud.check_exist(db, uid)
    print("Exist: ", exist)
    # print('Login names: ', LOGIN_NAMES_TEMP)
    if uid not in LOGIN_NAMES_TEMP:
        LOGIN_NAMES_TEMP.append(uid)
        if exist is False:
            return templates.TemplateResponse("instructions.html", {"request":request, "data":uid, "session":session})
        else:
            return templates.TemplateResponse("failure.html", {"request":request, "data":uid, "session":session})
    else:
        return templates.TemplateResponse("failure.html", {"request":request, "data":uid, "session":session})


@app.post("/instructions")
async def load_instructions(request:Request, uid: str = Form(...), session:int = Form(...), db: Session = Depends(get_db)):
    exist = crud.check_exist(db, uid)
    # print("Exist: ", exist)
    # print('Login names: ', LOGIN_NAMES_TEMP)
    if uid not in LOGIN_NAMES_TEMP:
        LOGIN_NAMES_TEMP.append(uid)
        if exist is False:
            return templates.TemplateResponse("instructions.html", {"request":request, "data":uid, "session":session})
        else:
            return templates.TemplateResponse("failure.html", {"request":request, "data":uid, "session":session})
    else:
        return templates.TemplateResponse("failure.html", {"request":request, "data":uid, "session":session})
    

@app.post("/minimap/")
async def post_full_map(request:Request, uid: str = Form(...)):
    print("Call minimap: ", uid)
    return templates.TemplateResponse("minimap.html", {"request":request, "data":uid})


@app.post("/fullmap/")
async def post_full_map(request:Request, uid: str = Form(...)):
    print("Call minimap: ", uid)
    #asyncio.run(game_tick_timer())
    return templates.TemplateResponse("fullmap.html", {"request":request, "data":uid})


@app.get("/demo/")
async def load_map(request:Request):
    return templates.TemplateResponse("minimapdemo.html", {"request":request})


@app.get("/episode/{uid}")
async def get_episode(request:Request, uid:str, db: Session = Depends(get_db)):
    episode = crud.get_episode_by_uid(db, uid)
    print("Episode from server: ", episode)
    return episode


@app.get("/points/{uid}")
async def get_total_points(request:Request, uid:str, db: Session = Depends(get_db)):
    points = 0
    with ENGINE.connect() as con:
        query_str = "SELECT episode, target, COUNT(DISTINCT target_pos) as num FROM `game` WHERE `game`.group = (select distinct `game`.group from `game` where userid= '" + uid + "') and (target LIKE 'green%' or target LIKE 'yellow%' or target LIKE 'red%') GROUP BY episode, target"
        rs = con.execute(query_str)
        for row in rs:
            # print(row)
            if row['target']=='green_victim':
                points += row['num']*10
            elif row['target']=='yellow_victim':
                points += row['num']*30
            elif row['target']=='red_victim':
                points += row['num']*60
    return points

# @app.post("/game_play", response_model=schemas.Game)
# async def create_game(game: schemas.GameCreate, db: Session = Depends(get_db)):
#     return crud.create_game(db=db, game=game)

@app.post("/completion")
async def get_map_data():
    return {"message": "Thank you!"}
    # return RedirectResponse(url="https://cmu.ca1.qualtrics.com/jfe/form/SV_82EQelNK9y3JhNY", status_code=status.HTTP_303_SEE_OTHER)


@app.get("/survey")
async def get_survey(request:Request):
    return templates.TemplateResponse("survey.html", {"request":request})