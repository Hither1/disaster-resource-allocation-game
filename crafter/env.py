import collections
# from crafter import high_level_objects
from crafter import high_level_objects_low_obs as high_level_objects

import numpy as np
import torch
import cv2
import re

from gym import spaces

from multiagent.multi_discrete import MultiDiscrete
from . import constants
from . import engine
from . import low_level_objects
from . import worldgen

try:
  import gym
  DiscreteSpace = gym.spaces.Discrete
  BoxSpace = gym.spaces.Box
  DictSpace = gym.spaces.Dict
  BaseClass = gym.Env
except ImportError:
  DiscreteSpace = collections.namedtuple('DiscreteSpace', 'n')
  BoxSpace = collections.namedtuple('BoxSpace', 'low, high, shape, dtype')
  DictSpace = collections.namedtuple('DictSpace', 'spaces')
  BaseClass = object


def draw_text(image, text):
  pil_image = cv2.UMat(np.array(image).transpose((1, 0, 2)))
  cv2.putText(pil_image, text, (30, 35), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
  return cv2.UMat.get(pil_image).transpose((1, 0, 2))

class Env(BaseClass):
  def __init__(self, config, world, userRole=None, reset_callback=None, reward_callback=None, global_reward_callback=None,
                observation_callback=None, info_callback=None,
                done_callback=None):
    self.config = config
    view = np.array(config.view if hasattr(config.view, '__len__') else (config.view, config.view))
    size = np.array(config.size if hasattr(config.size, '__len__') else (config.size, config.size))
    seed = np.random.randint(0, 2**31 - 1) if config.seed is None else config.seed
    self._area = config.area
    self._view = view
    self._size = size
    self._reward = config.reward
    self._length = config.length
    self._seed = seed
    self._episode = 0
    self.world = world
    self._textures = engine.Textures(constants.root / 'assets')
    item_rows = int(np.ceil(len(constants.items) / view[0]))
    self._local_view = engine.LocalView(
        self.world, self._textures, [view[0], view[1] - 3 * item_rows])
    self._item_view_shelter = engine.ItemView(
        self._textures, [view[0], item_rows])
    self._item_view_station = engine.ItemView(
        self._textures, [view[0], item_rows])
    self._item_view_warehouse = engine.ItemView(
        self._textures, [view[0], item_rows])
    self._chat_view = engine.ChatView([view[0], view[1]])  
    self._sem_view = engine.SemanticView(self.world, [
        low_level_objects.Player, high_level_objects.Station, high_level_objects.Shelter, high_level_objects.Warehouse])
    self._step = None
    self._player = None
    self._unlocked = None
    # Some libraries expect these attributes to be set.
    self.reward_range = None
    self.metadata = None
    
    self.agents = self.world.agents
    self.n_agents = len(self.agents)
    self.n = self.n_agents
    self.num_target = len(self.agents)

    self.reset_callback = reset_callback
    self.reward_callback = reward_callback
    self.global_reward_callback = global_reward_callback
    self.observation_callback = observation_callback
    if config.ifUseASAO:
      self.state_dim = 4
    else:
      self.state_dim = 2
    if config.ifUseActionInD:
      self.state_dim += 1

    self.state_dim = (len(self.agents[0].inventory.keys()), self.state_dim)
    self.state_dim = (len(self.agents[0].inventory.keys()), 1)
    # self.state_dim *= len(self.agents[0].inventory.keys())
    self.shared_reward = True # world.collaborative if hasattr(world, 'collaborative') else False

    # configure spaces
    self.action_space = []
    self.observation_space = []
    for agent in self.agents:
      total_action_space = []
      # resource allocation action space
      # Send
      num_actions = len(agent.inventory.keys())
      u_action_space = [spaces.Discrete(1) for i in range(num_actions)] 
      total_action_space.extend(u_action_space)

      # Request: communication action space
      c_action_space = [spaces.Discrete(1) for i in range(num_actions)]
      total_action_space.extend(c_action_space)

      # total action space
      if len(total_action_space) > 1:
        # all action spaces are discrete, so simplify to MultiDiscrete action space
        if all([isinstance(act_space, spaces.Discrete) for act_space in total_action_space]):
          act_space = MultiDiscrete([[0, act_space.n - 1] for act_space in total_action_space])
        else:
          act_space = spaces.Tuple(total_action_space)
        # self.action_space.append(act_space)
        self.action_space.append(MultiDiscrete([[0, 41], [0, 41], [0, 41], [0, 41], [0, 41], [0, 41]]))
      
      # observation space
      # obs_dim = len(observation_callback(agent, self.world))
      obs_dim = observation_callback(agent, self.world).shape
      self.observation_space.append(spaces.Box(low=-np.inf, high=+np.inf, shape=obs_dim, dtype=np.float32))
      # agent.action.c = np.zeros(self.world.dim_c)

    self.humans = []
    self.bots = []

    if userRole and userRole == "Shelter":
        self.user = self.world.shelter
        self.world.shelter.mode = "human"
    elif userRole and userRole == "Warehouse": 
        self.user = self.world.warehouse
        self.world.warehouse.mode = "human"
    elif userRole and userRole == "Station":
        self.user = self.world.station
        self.world.station.mode = "human"
    self.user_communication_history = []

    for agent in self.world.agents:
      if agent.mode == "human":
        self.humans.append(agent)
      else:
        self.bots.append(agent)

    self.user_name = userRole
    

  @property
  def action_names(self):
    return constants.actions

  def reset(self):
    self._episode += 1
    self._step = 0
    self.world.reset(seed=hash((self._seed, self._episode)) % (2 ** 31 - 1))
    self.reset_callback(self.world)
    self._update_time()

    self._unlocked = set()
    worldgen.generate_world(self.world, self.agents)

    obs_n = []
    for agent in self.agents:
      obs_n.append(self._get_obs(agent))

    self.world.update_OO()
    return torch.stack(obs_n)
  
  def game_reset(self):
    self._episode += 1
    self._step = 0
    self.world.reset(seed=hash((self._seed, self._episode)) % (2 ** 31 - 1))
    self.reset_callback(self.world)
    self._update_time()

    self._unlocked = set()
    worldgen.generate_world(self.world, self.agents)

    obs_n = []
    for agent in self.agents:
      obs_n.append(self._get_obs(agent))

    self.world.update_OO()

    user_state = self.user.inventory.copy()
    user_state['death'] = 10 # self.death
    user_state['injured'] = len(self.user.patients)
    user_state['reward'] = 0

    return user_state
  
  def _get_state(self):
    return
  
  # get reward for a particular agent
  def _get_reward(self, agent):
    if self.reward_callback is None:
      return 0.0

    if self.shared_reward:
      return self.global_reward_callback(self.world)
    else:
      return self.reward_callback(agent, self.world)
  
  # get observation for a particular agent
  def _get_obs(self, agent):
    if self.observation_callback is None:
        return np.zeros(0)
    return self.observation_callback(agent, self.world)
  
  def update_agent_state(self, agent):
    # set communication state (directly for now)
    if agent.silent:
        agent.state.c = np.zeros(self.dim_c)
    else:
        noise = np.random.randn(*agent.action.c.shape) * agent.c_noise if agent.c_noise else 0.0
        # agent.state.c = agent.action.c + noise      
    
  def step(self, action=None):
    self._step += 1
    obs_n = []
    reward_n = []
    done_n = []
    info_n = {'n': []}
    self._update_time()
            
    for agent in self.agents:
      agent.step(self._step)
      self.update_agent_state(agent)

    # used in model-based, TODO: standardize the env_wrapper interface
    # for agent in self.agents:
    #   agent._make_decisions_on_requests(action=action)

    communications = []
    for requester in self.agents:
      if requester.out_requests:
        print('out_requests', requester.out_requests)
        # TODO: make this more efficient and less hard-coding
        for request in requester.out_requests:
          communications.extend(requester.out_requests)

          if 'return' in request:
            self.world.station.inventory['staff'] += int(re.findall(r'\d+', request)[0])

          else:
            self._chat_view.info.append(request)
            requestee = request.split('->')[1].split(':')[0]
            for agent in self.world.agents:
              if agent.name == requestee:
                agent.in_requests.append([requester, request.split(': ')[1]])

      requester.out_requests = []

    for obj in self.world.objects:
      if self._player.distance(obj) < 2 * max(self._view) and obj not in self.agents:
        obj.update()

    if self._step % 10 == 0:
      for chunk, objs in self.world.chunks.items():
        self._balance_chunk(chunk, objs)

    # record observation for each agent
    for agent in self.agents:
      obs_n.append(self._get_obs(agent))
      r = self._get_reward(agent)
      reward_n.append(r)
      # done_n.append(self._get_done(agent))
      # info_n['n'].append(self._get_info(agent))

    # all agents get total reward in cooperative case
    # done = self._length and (self._step >= self._length)
    done = self._step >= 20
    info = {
        'inventory': self.world._player.inventory.copy(),
        'semantic': self._sem_view(),
        'player_pos': self.world._player.pos,
        'reward': reward_n,
    }
    return torch.stack(obs_n), reward_n, done, info
  
  def game_step(self, event):
    '''
		Change environment state based on events
		'''
		# event = {'agent_info': roomid_players[roomid][pid], }
		# agent_info = {'': , '': , 'role': , 'enter_start_time': , 'human': }
    agent_info = event['agent_info']
    uid = event['uid']
    event = event['event']
    self._step += 1
    obs_n = []

    for agent in self.agents:
      agent.step(self._step, event)
      self.update_agent_state(agent)

    for agent in self.agents:
      agent._make_decisions_on_requests(action=event)

    communications = []
    for requester in self.agents:
      if requester.out_requests:
        # TODO: make this more efficient and less hard-coding
        for request in requester.out_requests:
          communications.extend(requester.out_requests)

          if requester == self.user:
            self.user_communication_history.extend(requester.out_requests)

          if 'return' in request:
            self.world.station.inventory['staff'] += int(re.findall(r'\d+', request)[0])
          else:
            self._chat_view.info.append(request)
            requestee = request.split('->')[1].split(':')[0]

            if requestee == self.user:
              self.user_communication_history.extend(request)

            for agent in self.world.agents:
              if agent.name == requestee:
                agent.in_requests.append([requester, request.split(': ')[1]])

      requester.out_requests = []

    # record observation for each agent
    for agent in self.agents:
      obs_n.append(self._get_obs(agent))
      r = self._get_reward(agent)
		
    user_state = self.user.inventory.copy()
    user_state['death'] = 10 # self.death
    user_state['injured'] = len(self.user.patients)
    user_state['reward'] = r
    print('user_communication_history', self.user_communication_history)
    user_state['requests'] = self.user_communication_history[:-9]

    return uid, user_state

  def render(self, size=None):
    size = size or self._size
    unit = size // self._view
    canvas = np.zeros(tuple((int(size[0] * 2), size[1])) + (3,), np.uint8)
    local_view = self._local_view(self._player, unit)

    item_view_station = self._item_view_station(self.station.inventory, unit)
    item_view_shelter = self._item_view_shelter(self.shelter.inventory, unit)
    item_view_warehouse = self._item_view_warehouse(self.warehouse.inventory, unit)

    item_view_station = draw_text(item_view_station, 'Station')
    item_view_shelter = draw_text(item_view_shelter, 'Shelter')
    item_view_warehouse = draw_text(item_view_warehouse, 'Warehouse')

    chat_view = self._chat_view(unit)

    view = np.concatenate([local_view, item_view_station, item_view_shelter, item_view_warehouse], 1)
    view = np.concatenate([view, chat_view], 0)

    border = (size - (size // self._view) * self._view) // 2
    (x, y), (w, h) = border, view.shape[:2]
    canvas[x: x + w, y: y + h] = view
    return canvas.transpose((1, 0, 2))

  def _update_time(self):
    # https://www.desmos.com/calculator/grfbc6rs3h
    progress = (self._step / 300) % 1 + 0.3
    daylight = 1 - np.abs(np.cos(np.pi * progress)) ** 3
    self.world.daylight = daylight

  def _balance_chunk(self, chunk, objs):
    light = self.world.daylight
    self._balance_object(
        chunk, objs, low_level_objects.Zombie, 'grass', 6, 0, 0.3, 0.4,
        lambda pos: low_level_objects.Zombie(self.world, pos, self._player),
        lambda num, space: (
            0 if space < 50 else 3.5 - 3 * light, 3.5 - 3 * light))
    self._balance_object(
        chunk, objs, low_level_objects.Skeleton, 'path', 7, 7, 0.1, 0.1,
        lambda pos: low_level_objects.Skeleton(self.world, pos, self._player),
        lambda num, space: (0 if space < 6 else 1, 2))
    self._balance_object(
        chunk, objs, low_level_objects.Cow, 'grass', 5, 5, 0.01, 0.1,
        lambda pos: low_level_objects.Cow(self.world, pos),
        lambda num, space: (0 if space < 30 else 1, 1.5 + light))

  def _balance_object(
      self, chunk, objs, cls, material, span_dist, despan_dist,
      spawn_prob, despawn_prob, ctor, target_fn):
    xmin, xmax, ymin, ymax = chunk
    random = self._world.random
    creatures = [obj for obj in objs if isinstance(obj, cls)]
    mask = self._world.mask(*chunk, material)
    target_min, target_max = target_fn(len(creatures), mask.sum())
    if len(creatures) < int(target_min) and random.uniform() < spawn_prob:
      xs = np.tile(np.arange(xmin, xmax)[:, None], [1, ymax - ymin])
      ys = np.tile(np.arange(ymin, ymax)[None, :], [xmax - xmin, 1])
      xs, ys = xs[mask], ys[mask]
      i = random.randint(0, len(xs))
      pos = np.array((xs[i], ys[i]))
      empty = self._world[pos][1] is None
      away = self._player.distance(pos) >= span_dist
      if empty and away:
        self._world.add(ctor(pos))
    elif len(creatures) > int(target_max) and random.uniform() < despawn_prob:
      obj = creatures[random.randint(0, len(creatures))]
      away = self._player.distance(obj.pos) >= despan_dist
      if away:
        self._world.remove(obj)

  def seed(self, para):
    pass
