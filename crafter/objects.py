import numpy as np
import re
from . import constants
from . import engine
from . import time_varying_demand_supply

class Object:
  def __init__(self, world, pos):
    self.world = world
    self.pos = np.array(pos)
    self.random = world.random
    self.inventory = {'health': 0}
    self.removed = False

  @property
  def texture(self):
    raise 'unknown'

  @property
  def walkable(self):
    return constants.walkable

  @property
  def health(self):
    return self.inventory['health']

  @health.setter
  def health(self, value):
    self.inventory['health'] = max(0, value)

  @property
  def all_dirs(self):
    return ((-1, 0), (+1, 0), (0, -1), (0, +1))

  def move(self, direction):
    direction = np.array(direction)
    target = self.pos + direction
    if self.is_free(target):
      self.world.move(self, target)
      return True
    return False

  def is_free(self, target, materials=None):
    materials = self.walkable if materials is None else materials
    material, obj = self.world[target]
    return obj is None and material in materials

  def distance(self, target):
    if hasattr(target, 'pos'):
      target = target.pos
    return np.abs(target - self.pos).sum()

  def toward(self, target, long_axis=True):
    if hasattr(target, 'pos'):
      target = target.pos
    offset = target - self.pos
    dists = np.abs(offset)
    if (dists[0] > dists[1] if long_axis else dists[0] <= dists[1]):
      return np.array((np.sign(offset[0]), 0))
    else:
      return np.array((0, np.sign(offset[1])))

  def random_dir(self):
    return self.all_dirs[self.random.randint(0, 4)]

class Agency:
  """
  Base class for decision-making agency.

  Args:
    strategy (str): 'bs': base stock or 'strm': Stermann
  """
  def __init__(self, world, pos, agentNum, config, strategy='bs'):
    self.world = world
    self.pos = np.array(pos)
    self.random = world.random
    self.base_stock = {'food': 2, 
                  'drink': 2, 
                  'staff': 1}
    self.removed = False
    self.strategy = strategy
    self.in_requests = []
    self.out_requests = []
    self.staff_team = []
    self.gamma = 0.95
    self._communication = 0

    # physical motor noise amount
    self.u_noise = None
    # communication noise amount
    self.c_noise = None

    self.agentNum = agentNum
    self.config = config
    self.alpha_b = self.config.alpha_b[self.agentNum] # parameters for the formula
    self.betta_b = self.config.betta_b[self.agentNum] # parameters for the formula
    if self.config.demandDistribution == 0:
      self.a_b = np.mean((self.config.demandUp[self.agentNum], self.config.demandLow[self.agentNum])) # parameters for the formula
      self.b_b = np.mean((self.config.demandUp[self.agentNum], self.config.demandLow[self.agentNum])) * (np.mean((self.config.leadRecItemLow[self.agentNum], 
			self.config.leadRecItemUp[self.agentNum])) + np.mean((self.config.leadRecOrderLow[self.agentNum], self.config.leadRecOrderUp[self.agentNum]))) # parameters for the formula

    elif self.config.demandDistribution == 1 or self.config.demandDistribution == 3 or self.config.demandDistribution == 4:
      self.a_b = self.config.demandMu # parameters for the formula
      self.b_b = self.config.demandMu*(np.mean((self.config.leadRecItemLow[self.agentNum], 
			  self.config.leadRecItemUp[self.agentNum])) + np.mean((self.config.leadRecOrderLow[self.agentNum], self.config.leadRecOrderUp[self.agentNum]))) # parameters for the formula
    elif self.config.demandDistribution == 2:
      self.a_b = 8 # parameters for the formula
      self.b_b = (3/4.)*8*(np.mean((self.config.leadRecItemLow[self.agentNum] , 
			  self.config.leadRecItemUp[self.agentNum])) + np.mean((self.config.leadRecOrderLow[self.agentNum] , self.config.leadRecOrderUp[self.agentNum]))) # parameters for the formula
    elif self.config.demandDistribution == 3:
      self.a_b = 10 # parameters for the formula
      self.b_b = 7 * (np.mean((self.config.leadRecItemLow[self.agentNum], 
			  self.config.leadRecItemUp[self.agentNum])) + np.mean((self.config.leadRecOrderLow[self.agentNum] , self.config.leadRecOrderUp[self.agentNum]))) # parameters for the formula

  @property
  def texture(self):
    raise 'unknown'
  
  # updates the IL and OO at time t, after recieving "rec" number of items 
  def receiveItems(self):
    for resource in self.base_stock.keys():
      self.inventory[resource] = int(self.inventory[resource] + self.AS[resource][self.curTime]) # inverntory level update
      if resource == 'staff':
        for _ in range(int(self.AS[resource][self.curTime])):
          self.staff_team.append(Person('staff', 5))
      self.OO[resource] = max(0, int(self.OO[resource] - self.AS[resource][self.curTime])) # invertory in transient update
    
  def _process_requests(self):
    requests = []
    for request in self.in_requests:
      destination, request = request[0], request[1]

      inventory = self.inventory.keys()
      resources = [word for word in inventory if word.lower() in request]

      quantities = re.findall(r'\d+', request)

      for quantity, resource in zip(quantities, resources):
        if int(quantity) > 0:
          requests.append([destination, quantity, resource])

    return requests
  
  def _make_orders(self, goal):
    # print(self, goal)
    self._communication = 0
    order = {}
    if self.strategy == 'bs':
      # self.players.action = np.zeros(self.config.actionListLenOpt)
      for resource in self.base_stock.keys():
        if self.config.demandDistribution == 2:
          if self.curTime and self.config.use_initial_BS <= 4:
            # self.action[np.argmin(np.abs(np.array(self.config.actionListOpt)-\
						# 		max(0, (self.int_bslBaseStock - (self.inventory[resource] + self.OO - self.AO[resource][self.curTime]))) ))]
            self.action = np.argmin(np.abs(np.array(self.config.actionListOpt)-\
								max(0, (self.int_bslBaseStock - (self.inventory[resource] + self.OO[resource] - self.AO[resource][self.curTime]))) )) 	
          else: 
            # self.action[np.argmin(np.abs(np.array(self.config.actionListOpt)-\
						# 		max(0, (self.base_stock[resource] - (self.inventory[resource] + self.OO - self.AO[self.curTime]))) ))] 
            self.action = np.argmin(np.abs(np.array(self.config.actionListOpt)-\
								max(0, (self.base_stock[resource] - (self.inventory[resource] + self.OO[resource] - self.AO[resource][self.curTime]))) ))
        else:
          # self.action[np.argmin(np.abs(np.array(self.config.actionListOpt)-\
					# 			max(0, (self.base_stock[resource] - (self.inventory[resource] + self.OO - self.AO[self.curTime]))) ))] 
          self.action = np.argmin(np.abs(np.array(self.config.actionListOpt)-\
							max(0, (self.base_stock[resource] - (self.inventory[resource] + self.OO[resource] - self.AO[resource][self.curTime]))) ))
          # self.action = np.argmin(np.abs(np.array(self.config.actionListOpt)-\
					# 		max(0, (goal[resource] - (self.inventory[resource] + self.OO[resource] - self.AO[resource][self.curTime]))) ))
          
        if self.action > 0: order[resource] = self.action

    elif self.strategy == 'strm':
      for resource in self.base_stock.keys():
        self.action = np.argmin(np.abs(np.array(self.config.actionListOpt)\
									-max(0, round(self.AO[resource][self.curTime] +\
									self.alpha_b * (self.inventory[resource] - self.a_b) +\
									self.betta_b * (self.OO[resource] - self.b_b)))))
        if self.action > 0: order[resource] = self.action
    
    elif self.strategy == 'gpt-4':
      pass

    # TODO: Change this
    if 'staff' in order.keys():
      if self.name is not 'Station':
        self.out_requests.append(f"{self.name}->Station: Please send {order['staff']} staff")
        self.OO['staff'] += order['staff']
        self._communication += 1
      del order['staff']

    request = f'{self.name}->Warehouse: Please send '
    for resource, quantity in order.items():
      if resource is not 'staff':
        self.OO[resource] += quantity
        request += str(quantity) + ' ' + resource + ' '

    if order.keys():
      self.out_requests.append(request)
      self._communication += 1
    
    self.cumReward = self.gamma * self.cumReward + self.curReward
    self.curTime += 1
    

  def resetPlayer(self, T):
    self.OO = {key: 0 for key in self.base_stock.keys()}
    # arriced shipment 
    self.AS = {key: np.squeeze(np.zeros((1, T + max(self.config.leadRecItemUp) + max(self.config.leadRecOrderUp) + 10))) for key in self.base_stock.keys()}
    # arrived order	
    self.AO = {key: np.squeeze(np.zeros((1, T + max(self.config.leadRecItemUp) + max(self.config.leadRecOrderUp) + 10))) for key in self.base_stock.keys()}

    self.curReward = 0 # the reward observed at the current step
    self.cumReward = 0 # cumulative reward; reset at the begining of each episode	
    self.action= [] 
    self.hist = []
    self.hist2 = []
    self.srdqnBaseStock = []	# this holds the base stock levels that srdqn has came up with. added on Nov 8, 2017
    self.T = T
    # self.curObservation = self.getCurState(1)  # this function gets the current state of the game
    self.nextObservation = []
    # if self.compTypeTrain == 'srdqn':
    #   self.brain.setInitState(self.curObservation) # sets the initial input of the network
    self.curTime = 0
    self.staff_team = []
    self.patients = []


  # This function returns a np.array of the current state of the agent	
  def getCurState(self, t=None):
    if t is None: t = self.curTime
    if self.config.ifUseASAO:
      if self.config.if_use_AS_t_plus_1:
        curState = np.array([[-1*(self.inventory[resource]<0)*self.inventory[resource], 
                              1*(self.inventory[resource]>0)*self.inventory[resource], 
                              self.OO[resource], 
                              self.AS[resource][t], 
                              self.AO[resource][t]] for resource in self.base_stock])
      else:
        # curState = np.array([[-1*(self.inventory[resource]<0)*self.inventory[resource], 
        #                       1*(self.inventory[resource]>0)*self.inventory[resource], 
        #                       self.OO[resource], 
        #                       self.AS[resource][t-1], 
        #                       self.AO[resource][t]] for resource in self.base_stock])
        curState = np.array([[self.inventory[resource], 
                              self.OO[resource], 
                              self.AS[resource][t-1], 
                              self.AO[resource][t]] for resource in self.base_stock])
    else:
      # curState = np.array([[-1*(self.inventory[resource]<0)*self.inventory[resource], 
      #                       1*(self.inventory[resource]>0)*self.inventory[resource], 
      #                       self.OO[resource]] for resource in self.base_stock])
      curState = np.array([[self.inventory[resource], 
                            self.OO[resource]] for resource in self.base_stock])

    if self.config.ifUseActionInD:
      a = self.config.actionList[np.argmax(self.action)]
      curState = np.concatenate((curState, np.array([a])))
    
    return curState.flatten()

  def distance(self, target):
    if hasattr(target, 'pos'):
      target = target.pos
    return np.abs(target - self.pos).sum()

  def toward(self, target, long_axis=True):
    if hasattr(target, 'pos'):
      target = target.pos
    offset = target - self.pos
    dists = np.abs(offset)
    if (dists[0] > dists[1] if long_axis else dists[0] <= dists[1]):
      return np.array((np.sign(offset[0]), 0))
    else:
      return np.array((0, np.sign(offset[1])))

  def random_dir(self):
    return self.all_dirs[self.random.randint(0, 4)]

class Player(Object):
  def __init__(self, world, pos):
    super().__init__(world, pos)
    self.facing = (0, 1)
    self.inventory = {
        name: info['initial'] for name, info in constants.items.items()}
    self.achievements = {name: 0 for name in constants.achievements}
    self.action = 'noop'
    self.sleeping = False
    self._last_health = self.health
    self._hunger = 0
    self._thirst = 0
    self._fatigue = 0
    self._recover = 0

  @property
  def texture(self):
    if self.sleeping:
      return 'player-sleep'
    return {
        (-1, 0): 'player-left',
        (+1, 0): 'player-right',
        (0, -1): 'player-up',
        (0, +1): 'player-down',
    }[tuple(self.facing)]

  @property
  def walkable(self):
    return constants.walkable + ['lava']

  def update(self):
    target = (self.pos[0] + self.facing[0], self.pos[1] + self.facing[1])
    material, obj = self.world[target]
    action = self.action
    if self.sleeping:
      if self.inventory['energy'] < constants.items['energy']['max']:
        action = 'sleep'
      else:
        self.sleeping = False
        self.achievements['wake_up'] += 1
    if action == 'noop':
      pass
    elif action.startswith('move_'):
      self._move(action[len('move_'):])
    elif action == 'do' and obj:
      self._do_object(obj)
    elif action == 'do':
      self._do_material(target, material)
    elif action == 'sleep':
      if self.inventory['energy'] < constants.items['energy']['max']:
        self.sleeping = True
    elif action.startswith('place_'):
      self._place(action[len('place_'):], target, material)
    elif action.startswith('make_'):
      self._make(action[len('make_'):])
    self._update_life_stats()
    self._degen_or_regen_health()
    for name, amount in self.inventory.items():
      maxmium = constants.items[name]['max']
      self.inventory[name] = max(0, min(amount, maxmium))
    # This needs to happen after the inventory states are clamped
    # because it involves the health water inventory count.
    self._wake_up_when_hurt()

  def _update_life_stats(self):
    self._hunger += 0.5 if self.sleeping else 1
    if self._hunger > 25:
      self._hunger = 0
      self.inventory['food'] -= 1
    self._thirst += 0.5 if self.sleeping else 1
    if self._thirst > 20:
      self._thirst = 0
      self.inventory['drink'] -= 1
    if self.sleeping:
      self._fatigue = min(self._fatigue - 1, 0)
    else:
      self._fatigue += 1
    if self._fatigue < -10:
      self._fatigue = 0
      self.inventory['energy'] += 1
    if self._fatigue > 30:
      self._fatigue = 0
      self.inventory['energy'] -= 1

  def _degen_or_regen_health(self):
    necessities = (
        self.inventory['food'] > 0,
        self.inventory['drink'] > 0,
        self.inventory['energy'] > 0 or self.sleeping)
    if all(necessities):
      self._recover += 2 if self.sleeping else 1
    else:
      self._recover -= 0.5 if self.sleeping else 1
    if self._recover > 25:
      self._recover = 0
      self.health += 1
    if self._recover < -15:
      self._recover = 0
      self.health -= 1

  def _wake_up_when_hurt(self):
    if self.health < self._last_health:
      self.sleeping = False
    self._last_health = self.health

  def _move(self, direction):
    directions = dict(left=(-1, 0), right=(+1, 0), up=(0, -1), down=(0, +1))
    self.facing = directions[direction]
    self.move(self.facing)
    if self.world[self.pos][0] == 'lava':
      self.health = 0

  def _do_object(self, obj):
    damage = max([
        1,
        self.inventory['wood_sword'] and 2,
        self.inventory['stone_sword'] and 3,
        self.inventory['iron_sword'] and 5,
    ])
    if isinstance(obj, Plant):
      if obj.ripe:
        obj.grown = 0
        self.inventory['food'] += 4
        self.achievements['eat_plant'] += 1
    if isinstance(obj, Fence):
      self.world.remove(obj)
      self.inventory['fence'] += 1
      self.achievements['collect_fence'] += 1
    if isinstance(obj, Zombie):
      obj.health -= damage
      if obj.health <= 0:
        self.achievements['defeat_zombie'] += 1
    if isinstance(obj, Skeleton):
      obj.health -= damage
      if obj.health <= 0:
        self.achievements['defeat_skeleton'] += 1
    if isinstance(obj, Cow):
      obj.health -= damage
      if obj.health <= 0:
        self.inventory['food'] += 6
        self.achievements['eat_cow'] += 1
        # TODO: Keep track of previous inventory state to do this in a more
        # general way.
        self._hunger = 0

  def _do_material(self, target, material):
    if material == 'water':
      # TODO: Keep track of previous inventory state to do this in a more
      # general way.
      self._thirst = 0
    info = constants.collect.get(material)
    if not info:
      return
    for name, amount in info['require'].items():
      if self.inventory[name] < amount:
        return
    self.world[target] = info['leaves']
    if self.random.uniform() <= info.get('probability', 1):
      for name, amount in info['receive'].items():
        self.inventory[name] += amount
        self.achievements[f'collect_{name}'] += 1

  def _place(self, name, target, material):
    if self.world[target][1]:
      return
    info = constants.place[name]
    if material not in info['where']:
      return
    if any(self.inventory[k] < v for k, v in info['uses'].items()):
      return
    for item, amount in info['uses'].items():
      self.inventory[item] -= amount
    if info['type'] == 'material':
      self.world[target] = name
    elif info['type'] == 'object':
      cls = {
          'fence': Fence,
          'plant': Plant,
      }[name]
      self.world.add(cls(self.world, target))
    self.achievements[f'place_{name}'] += 1

  def _make(self, name):
    nearby, _ = self.world.nearby(self.pos, 1)
    info = constants.make[name]
    if not all(util in nearby for util in info['nearby']):
      return
    if any(self.inventory[k] < v for k, v in info['uses'].items()):
      return
    for item, amount in info['uses'].items():
      self.inventory[item] -= amount
    self.inventory[name] += info['gives']
    self.achievements[f'make_{name}'] += 1


class Staff(Object):
  def __init__(self, world, pos):
    super().__init__(world, pos)
    self.facing = (0, 1)
    self.inventory = {
        name: info['initial'] for name, info in constants.items.items()}
    self.achievements = {name: 0 for name in constants.achievements}
    self.action = 'noop'
    self.sleeping = False
    self._last_health = self.health
    self._hunger = 0
    self._thirst = 0
    self._fatigue = 0
    self._recover = 0

  @property
  def texture(self):
    if self.sleeping:
      return 'player-sleep'
    return {
        (-1, 0): 'player-left',
        (+1, 0): 'player-right',
        (0, -1): 'player-up',
        (0, +1): 'player-down',
    }[tuple(self.facing)]

  @property
  def walkable(self):
    return constants.walkable + ['lava']

  def update(self):
    target = (self.pos[0] + self.facing[0], self.pos[1] + self.facing[1])
    material, obj = self.world[target]
    action = self.action
    if self.sleeping:
      if self.inventory['energy'] < constants.items['energy']['max']:
        action = 'sleep'
      else:
        self.sleeping = False
        self.achievements['wake_up'] += 1
    if action == 'noop':
      pass
    elif action.startswith('move_'):
      self._move(action[len('move_'):])
    elif action == 'do' and obj:
      self._do_object(obj)
    elif action == 'do':
      self._do_material(target, material)
    elif action == 'sleep':
      if self.inventory['energy'] < constants.items['energy']['max']:
        self.sleeping = True
    elif action.startswith('place_'):
      self._place(action[len('place_'):], target, material)
    elif action.startswith('make_'):
      self._make(action[len('make_'):])
    self._update_life_stats()
    self._degen_or_regen_health()
    for name, amount in self.inventory.items():
      maxmium = constants.items[name]['max']
      self.inventory[name] = max(0, min(amount, maxmium))

  def _update_life_stats(self):
    self._hunger += 0.5 if self.sleeping else 1
    if self._hunger > 25:
      self._hunger = 0
      self.inventory['food'] -= 1
    self._thirst += 0.5 if self.sleeping else 1
    if self._thirst > 20:
      self._thirst = 0
      self.inventory['drink'] -= 1
    if self.sleeping:
      self._fatigue = min(self._fatigue - 1, 0)
    else:
      self._fatigue += 1
    if self._fatigue < -10:
      self._fatigue = 0
      self.inventory['energy'] += 1
    if self._fatigue > 30:
      self._fatigue = 0
      self.inventory['energy'] -= 1

  def _degen_or_regen_health(self):
    necessities = (
        self.inventory['food'] > 0,
        self.inventory['drink'] > 0,
        self.inventory['energy'] > 0 or self.sleeping)
    if all(necessities):
      self._recover += 2 if self.sleeping else 1
    else:
      self._recover -= 0.5 if self.sleeping else 1
    if self._recover > 25:
      self._recover = 0
      self.health += 1
    if self._recover < -15:
      self._recover = 0
      self.health -= 1

  def _move(self, direction):
    directions = dict(left=(-1, 0), right=(+1, 0), up=(0, -1), down=(0, +1))
    self.facing = directions[direction]
    self.move(self.facing)
    if self.world[self.pos][0] == 'lava':
      self.health = 0

  def _do_object(self, obj):
    damage = max([
        1,
        self.inventory['wood_sword'] and 2,
        self.inventory['stone_sword'] and 3,
        self.inventory['iron_sword'] and 5,
    ])
    if isinstance(obj, Plant):
      if obj.ripe:
        obj.grown = 0
        self.inventory['food'] += 4
        self.achievements['eat_plant'] += 1
    if isinstance(obj, Fence):
      self.world.remove(obj)
      self.inventory['fence'] += 1
      self.achievements['collect_fence'] += 1
    if isinstance(obj, Zombie):
      obj.health -= damage
      if obj.health <= 0:
        self.achievements['defeat_zombie'] += 1
    if isinstance(obj, Skeleton):
      obj.health -= damage
      if obj.health <= 0:
        self.achievements['defeat_skeleton'] += 1
    if isinstance(obj, Cow):
      obj.health -= damage
      if obj.health <= 0:
        self.inventory['food'] += 6
        self.achievements['eat_cow'] += 1
        # TODO: Keep track of previous inventory state to do this in a more
        # general way.
        self._hunger = 0

  def _do_material(self, target, material):
    if material == 'water':
      # TODO: Keep track of previous inventory state to do this in a more general way.
      self._thirst = 0
    info = constants.collect.get(material)
    if not info:
      return
    for name, amount in info['require'].items():
      if self.inventory[name] < amount:
        return
    self.world[target] = info['leaves']
    if self.random.uniform() <= info.get('probability', 1):
      for name, amount in info['receive'].items():
        self.inventory[name] += amount
        self.achievements[f'collect_{name}'] += 1

  def _place(self, name, target, material):
    if self.world[target][1]:
      return
    info = constants.place[name]
    if material not in info['where']:
      return
    if any(self.inventory[k] < v for k, v in info['uses'].items()):
      return
    for item, amount in info['uses'].items():
      self.inventory[item] -= amount
    if info['type'] == 'material':
      self.world[target] = name
    elif info['type'] == 'object':
      cls = {
          'fence': Fence,
          'plant': Plant,
      }[name]
      self.world.add(cls(self.world, target))
    self.achievements[f'place_{name}'] += 1

  def _make(self, name):
    nearby, _ = self.world.nearby(self.pos, 1)
    info = constants.make[name]
    if not all(util in nearby for util in info['nearby']):
      return
    if any(self.inventory[k] < v for k, v in info['uses'].items()):
      return
    for item, amount in info['uses'].items():
      self.inventory[item] -= amount
    self.inventory[name] += info['gives']
    self.achievements[f'make_{name}'] += 1

class Person:
  def __init__(self, type, health=5):
    super().__init__()
    self.inventory = {
        name: info['initial'] for name, info in constants.items.items()}
    self.achievements = {name: 0 for name in constants.achievements}
    self.action = 'noop'
    self.sleeping = False
    self._hunger = 0
    self._thirst = 0
    self._fatigue = 0
    self._recover = 0
    if type == 'injured':
      self._admitted_days = 0

    elif type == 'staff':
      pass
      # self.health = 5
      # self.health = 0
    self.health = health
    self._last_health = self.health

  @property
  def texture(self):
    if self.sleeping:
      return 'player-sleep'

  def update(self):
    target = (self.pos[0] + self.facing[0], self.pos[1] + self.facing[1])
    material, obj = self.world[target]
    action = self.action
    if self.sleeping:
      if self.inventory['energy'] < constants.items['energy']['max']:
        action = 'sleep'
      else:
        self.sleeping = False
        self.achievements['wake_up'] += 1
    if action == 'noop':
      pass
    elif action.startswith('move_'):
      self._move(action[len('move_'):])
    elif action == 'do' and obj:
      self._do_object(obj)
    elif action == 'do':
      self._do_material(target, material)
    elif action == 'sleep':
      if self.inventory['energy'] < constants.items['energy']['max']:
        self.sleeping = True
    elif action.startswith('place_'):
      self._place(action[len('place_'):], target, material)
    elif action.startswith('make_'):
      self._make(action[len('make_'):])
    self._update_life_stats()
    self._degen_or_regen_health()
    for name, amount in self.inventory.items():
      maxmium = constants.items[name]['max']
      self.inventory[name] = max(0, min(amount, maxmium))

  def _update_life_stats(self):
    self._hunger += 0.5 if self.sleeping else 1
    if self._hunger > 25:
      self._hunger = 0
      self.inventory['food'] -= 1
    self._thirst += 0.5 if self.sleeping else 1
    if self._thirst > 20:
      self._thirst = 0
      self.inventory['drink'] -= 1
    if self.sleeping:
      self._fatigue = min(self._fatigue - 1, 0)
    else:
      self._fatigue += 1
    if self._fatigue < -10:
      self._fatigue = 0
      self.inventory['energy'] += 1
    if self._fatigue > 30:
      self._fatigue = 0
      self.inventory['energy'] -= 1

  def _degen_or_regen_health(self):
    necessities = (
        self.inventory['food'] > 0,
        self.inventory['drink'] > 0,
        self.inventory['energy'] > 0 or self.sleeping)
    if all(necessities):
      self._recover += 2 if self.sleeping else 1
    else:
      self._recover -= 0.5 if self.sleeping else 1
    if self._recover > 25:
      self._recover = 0
      self.health += 1
    if self._recover < -15:
      self._recover = 0
      self.health -= 1

  def _do_object(self, obj):
    damage = max([
        1,
        self.inventory['wood_sword'] and 2,
        self.inventory['stone_sword'] and 3,
        self.inventory['iron_sword'] and 5,
    ])
    if isinstance(obj, Plant):
      if obj.ripe:
        obj.grown = 0
        self.inventory['food'] += 4
        self.achievements['eat_plant'] += 1
    if isinstance(obj, Fence):
      self.world.remove(obj)
      self.inventory['fence'] += 1
      self.achievements['collect_fence'] += 1
    if isinstance(obj, Zombie):
      obj.health -= damage
      if obj.health <= 0:
        self.achievements['defeat_zombie'] += 1
    if isinstance(obj, Skeleton):
      obj.health -= damage
      if obj.health <= 0:
        self.achievements['defeat_skeleton'] += 1
    if isinstance(obj, Cow):
      obj.health -= damage
      if obj.health <= 0:
        self.inventory['food'] += 6
        self.achievements['eat_cow'] += 1
        # TODO: Keep track of previous inventory state to do this in a more
        # general way.
        self._hunger = 0

  def _do_material(self, target, material):
    if material == 'water':
      # TODO: Keep track of previous inventory state to do this in a more
      # general way.
      self._thirst = 0
    info = constants.collect.get(material)
    if not info:
      return
    for name, amount in info['require'].items():
      if self.inventory[name] < amount:
        return
    self.world[target] = info['leaves']
    if self.random.uniform() <= info.get('probability', 1):
      for name, amount in info['receive'].items():
        self.inventory[name] += amount
        self.achievements[f'collect_{name}'] += 1

  def _place(self, name, target, material):
    if self.world[target][1]:
      return
    info = constants.place[name]
    if material not in info['where']:
      return
    if any(self.inventory[k] < v for k, v in info['uses'].items()):
      return
    for item, amount in info['uses'].items():
      self.inventory[item] -= amount
    if info['type'] == 'material':
      self.world[target] = name
    elif info['type'] == 'object':
      cls = {
          'fence': Fence,
          'plant': Plant,
      }[name]
      self.world.add(cls(self.world, target))
    self.achievements[f'place_{name}'] += 1

  def _make(self, name):
    nearby, _ = self.world.nearby(self.pos, 1)
    info = constants.make[name]
    if not all(util in nearby for util in info['nearby']):
      return
    if any(self.inventory[k] < v for k, v in info['uses'].items()):
      return
    for item, amount in info['uses'].items():
      self.inventory[item] -= amount
    self.inventory[name] += info['gives']
    self.achievements[f'make_{name}'] += 1


class Warehouse(Agency):
  """
  Base class for Warehouse.

  Args:
    strategy (str): 'bs': base stock or 'strm': Stermann
  """
  def __init__(self, world, pos, agentNum, config):
    super().__init__(world, pos, agentNum, config)
    self.world = world
    self.pos = np.array(pos)
    self.random = world.random

    self.inventory = {'food': time_varying_demand_supply.demand(mean=40, std_dev=2), 
                      'drink': time_varying_demand_supply.demand(mean=40, std_dev=2), 
                      'staff': 9, 
                      'wood': 0, 
                      'stone': 0, 
                      'coal': 0}
    self.staff_team = [Person('staff', 5) for _ in range(self.inventory['staff'])]
    
    self.action = 'noop'
    self.sleeping = False
    self._hunger = 0
    self._fatigue = 0
    self._recover = 0
    self._backorder = 0
    self.strategy = 'bs'

  @property
  def texture(self):
    return 'warehouse'
  
  @property
  def name(self):
    return 'Warehouse'
  
  @property
  def reward(self):
    return self.curReward
  
  def resetPlayer(self, T):
    super().resetPlayer(T)
    self.inventory = {'food': time_varying_demand_supply.demand(mean=40, std_dev=2), 
                      'drink': time_varying_demand_supply.demand(mean=40, std_dev=2), 
                      'staff': 9, 
                      'wood': 0, 
                      'stone': 0, 
                      'coal': 0}
    self.staff_team = [Person('staff', 5) for _ in range(self.inventory['staff'])]
    return 
  
  def step(self, _step):
    self.receiveItems()
    self._update_life_stats()
    
    self.curReward = - self._backorder - self._communication

    for name, amount in self.inventory.items():
      maxmium = constants.items[name]['max']
      self.inventory[name] = max(0, min(amount, maxmium))

    # self.curTime += 1

  def _update_life_stats(self):
    self.consumption = 0
    # TODO: track if this request was already sent in previous 5 steps

    returning_staff = 0
    for staff in self.staff_team:
      if staff.health <= 0:
        returning_staff += 1
        self.staff_team.remove(staff)
        self.inventory['staff'] -= 1
        self.consumption += 1
        
    for staff in self.staff_team:
      self.inventory['food'] += 6
      self.inventory['drink'] += 6
      staff.health -= 1

    if returning_staff > 0:
      self.out_requests.append(f'{returning_staff} staff is returning to the station.')

  def _make_decisions_on_requests(self, goal):
    ### Step 1: 
    self.in_requests = self._process_requests()
    resource_dict = {}

    for requester, quantity, resource in self.in_requests:
        if resource not in resource_dict:
            resource_dict[resource] = []
        resource_dict[resource].append((requester, int(quantity)))

    for resource, requests_list in resource_dict.items():
        total_quantity = min(self.inventory[resource], sum(quantity for _, quantity in requests_list)) # - self.base_stock[resource]
        self.AO[resource][self.curTime] = total_quantity
        # if self.inventory[resource] - self.base_stock[resource] >= total_quantity: 
        if self.inventory[resource] >= total_quantity: 
          for requester, quantity in requests_list:
            requester.AS[resource][self.curTime + 1] += quantity
        else:
          average_quantity = total_quantity // len(requests_list)
          self.inventory[resource] -= total_quantity
          for requester, _ in requests_list:
            requester.AS[resource][self.curTime + 1] += average_quantity

    self.in_requests = [] # Clear

    ### Step 2: 
    self._make_orders(goal)


class Shelter(Agency):
  def __init__(self, world, pos, agentNum, config):
    super().__init__(world, pos, agentNum, config)
    # self.inventory = {name: info['initial'] for name, info in constants.items.items()}
    
    self.inventory = {'health': time_varying_demand_supply.demand(mean=10, std_dev = 2), 
                      'food': 39, 
                      'drink': 39, 
                      'staff': time_varying_demand_supply.demand(mean=20, std_dev=2), 
                      'death': 0,
                      'wood': 0, 
                      'stone': 0, 
                      'coal': 0}
    self.patients = [Person('injured', 0) for _ in range(self.inventory['health'])]
    self.staff_team = [Person('staff', 5) for _ in range(self.inventory['staff'])]
    self.base_stock = {'food': 30, 
                      'drink': 30, 
                      'staff': 15, 
                      }
    
    self.achievements = {name: 0 for name in constants.achievements}
    self.action = 'noop'
    # self._last_health = self.health
    self._inventory = 0
    self._injured = []
    self._death = 0

  @property
  def texture(self):
    return 'hospital'

  @property
  def name(self):
    return 'Shelter'
  
  @property
  def reward(self):
    return self.curReward
  
  def resetPlayer(self, T):
    super().resetPlayer(T)
    self.inventory = {'health': time_varying_demand_supply.demand(mean=10, std_dev=2), 
                      'food': 39, 
                      'drink': 39, 
                      'staff': time_varying_demand_supply.demand(mean=20, std_dev=2), 
                      'death': 0,
                      'wood': 0, 
                      'stone': 0, 
                      'coal': 0}
    self.patients = [Person('injured', 0) for _ in range(self.inventory['health'])]
    self.staff_team = [Person('staff', 5) for _ in range(self.inventory['staff'])]
    self.base_stock = {'food': 30, 
                      'drink': 30, 
                      'staff': 15, 
                      }
  
  def step(self, _step):
    self._death = 0
    self._helped_people = 0
    self.receiveItems()

    new_arrived_injure = time_varying_demand_supply.piecewise_function(self.curTime)

    self.inventory['health'] += new_arrived_injure
    for _ in range(new_arrived_injure):
      self.patients.append(Person('injured', 0))

    self._update_patient_inventory_stats()
    self._update_staff_stats()
    
    self.curReward = - self._death - self._communication

    for name, amount in self.inventory.items():
      maxmium = constants.items[name]['max']
      # self.inventory[name] = max(0, min(amount, maxmium))
      self.inventory[name] = min(amount, maxmium)

    print('Day:', _step, [patient.health for patient in self.patients], self.inventory['health'], len(self.staff_team), self.inventory['food'], self.inventory['drink'])
    print([patient._admitted_days for patient in self.patients])

  def _update_patient_inventory_stats(self):
    self.consumption = 0

    while self.patients and self.patients[0].health >= 5: # Dismiss an injured 
        self.patients.pop(0)
        self.inventory['health'] -= 1
    
    for i in range(min(len(self.patients), len(self.staff_team))):
      patient, staff = self.patients[i], self.staff_team[i]
      if patient.health < 5:
        staff.health -= 1
        self.AO['staff'][self.curTime] += 1
        self.AO['food'][self.curTime] += 2
        self.AO['drink'][self.curTime] += 2
        # Consume food
        if self.inventory['food'] > 0:
          self.inventory['food'] -= 1
          patient.health += 0.5
          self.consumption += 1
          self._helped_people += 1

        # Consume water
        if self.inventory['drink'] > 0:
          self.inventory['drink'] -= 1
          patient.health += 0.5
          self.consumption += 1
          self._helped_people += 1

    for i in range(len(self.patients)):
      if self.patients[i]._admitted_days >= 5 and self.patients[i].health < 2:
        self.inventory['death'] += 1
        self._death += 1
        self.inventory['health'] -= 1

    
    self.patients = [patient for patient in self.patients if patient._admitted_days < 5] # or patient.health >= 2

    # For those patients that don't have staff catering to them
    for i in range(len(self.staff_team), len(self.patients)):
      self.AO['staff'][self.curTime] += 1
      self.AO['food'][self.curTime] += 2
      self.AO['drink'][self.curTime] += 2
      self.patients[i]._admitted_days += 1

    print('death', self._death, self.AO['staff'][self.curTime], self.AO['food'][self.curTime], self.AO['drink'][self.curTime])
    

  def _update_staff_stats(self):
    # for _ in range(max(0, self.inventory['staff'] - len(self.staff_team))):
    #   self.staff_team.append(Person('staff', 5))
    
    returning_staff = 0
    for staff in self.staff_team:
      if staff.health <= 0:
        self.staff_team.remove(staff)
        self.inventory['staff'] -= 1
        returning_staff += 1
      else:
        staff.health -= 0.5
        # # Update food
        # if self.inventory['food'] > 0:
        #   self.inventory['food'] -= 1
        #   staff.health += 0.5
        # else:
        #   food_request += 1

        # # Update water
        # if self.inventory['drink'] > 0:
        #   self.inventory['drink'] -= 1
        #   staff.health += 0.5
        # else:
        #   drink_request += 1
          
    if returning_staff > 0:
      self.out_requests.append(f'{returning_staff} staff is returning to station')

  def _make_decisions_on_requests(self, goal):
    ### Step 1: 
    self.in_requests = self._process_requests()
    for requester, resource, quantity in self.in_requests:
      if self.inventory[resource] >= quantity:
        self.inventory[resource] -= 1
        requester.inventory[resource] += 1 

      elif self.inventory[resource] > 0:
        self.inventory[resource] -= 1
        requester.inventory[resource] += 1

    # Clear TODO: do not clear requests that were not satisfied during the current (and past) steps
    self.in_requests = [] 

    ### Step 2: 
    self._make_orders(goal)


class Station(Agency):
  def __init__(self, world, pos, agentNum, config):
    super().__init__(world, pos, agentNum, config)
    self.world = world
    self.pos = np.array(pos)
    self.random = world.random
    
    self.inventory = {'food': 9, 
                      'drink': 9, 
                      'staff': time_varying_demand_supply.demand(mean=12, std_dev=2), 
                      'wood': 0, 
                      'stone': 0, 
                      'coal': 0}
    self.staff_team = [Person('staff', 5) for _ in range(self.inventory['staff'])]

    self.achievements = {name: 0 for name in constants.achievements}
    self.action = 'noop'
    self.sleeping = False
    self._hunger = 0
    self._thirst = 0
    self._recover = 0
    self._backorder = 0
    self.strategy = 'bs'

  @property
  def texture(self):
    return 'station'
  
  @property
  def name(self):
    return 'Station'
  
  @property
  def reward(self):
    return self.curReward
  
  def resetPlayer(self, T):
    super().resetPlayer(T)
    
    self.inventory = {'food': 9, 
                      'drink': 9, 
                      'staff': time_varying_demand_supply.demand(mean=12, std_dev=2), 
                      'wood': 0, 
                      'stone': 0, 
                      'coal': 0}
    self.staff_team = [Person('staff', 5) for _ in range(self.inventory['staff'])]
    return 

  def step(self, _step):
    self._backorder = 0
    self.receiveItems()
    self._update_inventory_stats()
    self.curReward = - self._backorder - self._communication

    for name, amount in self.inventory.items():
      maxmium = constants.items[name]['max']
      # self.inventory[name] = max(0, min(amount, maxmium))
      self.inventory[name] = min(amount, maxmium)
    
    # self.curTime += 1

  def _update_inventory_stats(self):
    self.consumption = 0
    for _ in range(max(self.inventory['staff'] - len(self.staff_team), 0)):
      self.staff_team.append(Person('staff', 0))

    for staff in self.staff_team:
      staff.health += min(5, 1.5 + staff.health)

  def _make_decisions_on_requests(self, goal):
    ### Part 1: 
    self.in_requests = self._process_requests()
    self.in_requests = sorted(self.in_requests, key=lambda x: x[0].name)
    for request in self.in_requests:
        requester, quantity, resource = request
        self.AO[resource][self.curTime] = quantity
        # for _ in quantity:
        #   if self.inventory[resource] < int(quantity):
        #     self._backorder += int(quantity) - self.inventory[resource]
        sending_quantity = min(self.inventory[resource], int(quantity))
        for _ in range(sending_quantity):
          if self.staff_team and self.staff_team[0].health > 4:
            self.inventory[resource] -= 1
            requester.AS[resource][self.curTime + 1] += 1
            self.staff_team.pop(0)
          else:
            break
    
    self.in_requests = []

    ### Part 2: make orders
    self._make_orders(goal)



class Cow(Object):

  def __init__(self, world, pos):
    super().__init__(world, pos)
    self.health = 3

  @property
  def texture(self):
    return 'cow'

  def update(self):
    if self.health <= 0:
      self.world.remove(self)
    if self.random.uniform() < 0.5:
      direction = self.random_dir()
      self.move(direction)


class Skeleton(Object):
  def __init__(self, world, pos, player):
    super().__init__(world, pos)
    self.player = player
    self.health = 3
    self.reload = 0

  @property
  def texture(self):
    return 'skeleton'

  def update(self):
    if self.health <= 0:
      self.world.remove(self)
    self.reload = max(0, self.reload - 1)
    dist = self.distance(self.player.pos)
    if dist <= 3:
      moved = self.move(-self.toward(self.player, self.random.uniform() < 0.6))
      if moved:
        return
    if dist <= 5 and self.random.uniform() < 0.5:
      self._shoot(self.toward(self.player))
    elif dist <= 8 and self.random.uniform() < 0.3:
      self.move(self.toward(self.player, self.random.uniform() < 0.6))
    elif self.random.uniform() < 0.2:
      self.move(self.random_dir())

  def _shoot(self, direction):
    if self.reload > 0:
      return
    if direction[0] == 0 and direction[1] == 0:
      return
    pos = self.pos + direction
    if self.is_free(pos, Arrow.walkable):
      self.world.add(Arrow(self.world, pos, direction))
      self.reload = 4


class Arrow(Object):

  def __init__(self, world, pos, facing):
    super().__init__(world, pos)
    self.facing = facing

  @property
  def texture(self):
    return {
        (-1, 0): 'arrow-left',
        (+1, 0): 'arrow-right',
        (0, -1): 'arrow-up',
        (0, +1): 'arrow-down',
    }[tuple(self.facing)]

  @engine.staticproperty
  def walkable():
    return constants.walkable + ['water', 'lava']

  def update(self):
    target = self.pos + self.facing
    material, obj = self.world[target]
    if obj:
      obj.health -= 2
      self.world.remove(self)
    elif material not in self.walkable:
      self.world.remove(self)
      if material in ['table', 'furnace']:
        self.world[target] = 'path'
    else:
      self.move(self.facing)


class Plant(Object):

  def __init__(self, world, pos):
    super().__init__(world, pos)
    self.health = 1
    self.grown = 0

  @property
  def texture(self):
    if self.ripe:
      return 'plant-ripe'
    else:
      return 'plant'

  @property
  def ripe(self):
    return self.grown > 300

  def update(self):
    self.grown += 1
    objs = [self.world[self.pos + dir_][1] for dir_ in self.all_dirs]
    if any(isinstance(obj, (Zombie, Skeleton, Cow)) for obj in objs):
      self.health -= 1
    if self.health <= 0:
      self.world.remove(self)


class Fence(Object):

  def __init__(self, world, pos):
    super().__init__(world, pos)

  @property
  def texture(self):
    return 'fence'

  def update(self):
    pass
