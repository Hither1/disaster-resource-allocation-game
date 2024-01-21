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
