from .env import Env
from .recorder import Recorder
from .config import get_config, update_config

try:
  import gym
  gym.envs.register(
      id='CrafterReward-v1',
      entry_point='crafter:Env',
      max_episode_steps=10000,
      kwargs={'reward': True})
  gym.envs.register(
      id='CrafterNoReward-v1',
      entry_point='crafter:Env',
      max_episode_steps=10000,
      kwargs={'reward': False})
except ImportError:
  pass


from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import socketio
import asyncio


#asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
app = FastAPI()

sio = socketio.AsyncServer(cors_allowed_origins='*', async_mode = 'asgi')
app.mount("/socket.io", socketio.ASGIApp(sio))

app.mount("/static", StaticFiles(directory="./crafter/static"), name="static")
templates = Jinja2Templates(directory="./crafter/templates")

from crafter import main