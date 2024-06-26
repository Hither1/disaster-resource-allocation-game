import numpy as np
import re
from . import constants
from . import engine
from . import time_varying_demand_supply
import random
STDDEV = 1

class Person:
  def __init__(self, type, health=5):
    super().__init__()
    if type == 'injured':
      self._admitted_days = 0
    elif type == 'staff':
      pass
    self.health = health
    self._last_health = self.health

  @property
  def texture(self):
    if self.sleeping:
      return 'player-sleep'

  def update(self):
    target = (self.pos[0] + self.facing[0], self.pos[1] + self.facing[1])
    material, obj = self.world[target]

    for name, amount in self.inventory.items():
      try:
        maxmium = constants.resources[name]['max']
      except:
        maxmium = constants.items[name]['max']
      self.inventory[name] = max(0, min(amount, maxmium))


class Agency:
  """
  Base class for decision-making agency.

  Args:
    strategy (str): 'bs': base stock or 'strm': Stermann
  """
  def __init__(self, world, pos, agentNum, config, mode='bot', strategy='bs'):
    self.world = world
    self.pos = np.array(pos)
    self.random = world.random
    self.base_stock = {'food': 2, 
                  'drink': 2, 
                  'staff': 1,
                  'med_staff': 1,
                  'med_kit': 5}
    self.strategy = strategy
    self.in_requests = []
    self.out_requests = []
    self.staff_team = []
    self.gamma = 0.95
    self._communication = 0
    self.mode = mode
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
    for resource in self.inventory.keys():
      self.inventory[resource] = int(self.inventory[resource] + self.AS[resource][self.curTime]) # inventory level update
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
  
  def _make_orders(self, goal, action):
    """ 
      Using goals (indirect) or human actions (direct) to make orders 
    """
    self._communication = 0
    order = {}

    if action and self.mode == 'human': # Human player
      for key, value in action.items():
        if 'request' in key and int(value) > 0:
          order[key.replace('request-', '')] = int(value)

    elif action and isinstance(action, np.ndarray):
      action = action[self.agentNum].reshape(len(self.inventory.keys()) * 2, -1)
      action = np.argmax(action, axis=1)
      action[self.action_mask == 0] = 0
      action = action.reshape(2, -1)
      for idx, resource in enumerate(self.inventory.keys()):
        order[resource] = action[1][idx]
    

    # AI player with goal
    elif self.strategy == 'bs':
      for resource in self.inventory.keys():
        if self.config.demandDistribution == 2:
          if self.curTime and self.config.use_initial_BS <= 4:
            self.action = np.argmin(np.abs(np.array(self.config.actionListOpt)-\
								max(0, (self.int_bslBaseStock - (self.inventory[resource] + self.OO[resource] - self.AO[resource][self.curTime]))) )) 	
          else: 
            self.action = np.argmin(np.abs(np.array(self.config.actionListOpt)-\
								max(0, (self.base_stock[resource] - (self.inventory[resource] + self.OO[resource] - self.AO[resource][self.curTime]))) ))
        else:
          self.action = np.argmin(np.abs(np.array(self.config.actionListOpt)-\
							max(0, (self.base_stock[resource] - (self.inventory[resource] + self.OO[resource] - self.AO[resource][self.curTime]))) ))
          # self.action = np.argmin(np.abs(np.array(self.config.actionListOpt)-\
					# 		max(0, (goal[resource] - (self.inventory[resource] + self.OO[resource] - self.AO[resource][self.curTime]))) ))
          
        if self.action > 0: order[resource] = self.action

    elif self.strategy == 'strm':
      for resource in self.base_stock.keys():
        self.action = np.argmin(np.abs(np.array(self.config.actionListOpt) - max(0, round(self.AO[resource][self.curTime] +\
									self.alpha_b * (self.inventory[resource] - self.a_b) +\
									self.betta_b * (self.OO[resource] - self.b_b)))))
        if self.action > 0: order[resource] = self.action
    
    elif self.strategy == 'gpt-4':
      pass

    request = f'{self.name}->Warehouse: Please send '
    for resource, quantity in order.items():
      if quantity <= 0:
        next 
      elif resource in ['food', 'drink'] :
        self.OO[resource] += quantity
        request += str(quantity) + ' ' + resource + ' '
      elif resource == 'med_kit':
        self.out_requests.append(f"{self.name}->Clinic: Please send {order['staff']} med_kit")
        self._communication += 1
      elif resource == 'med_staff' and self.name != 'Station' and self.name != 'Clinic':
        coin = random.random()
        order_from = 'Station' if coin > 0.5 else 'Clinic'
        self.out_requests.append(f"{self.name}->{order_from}: Please send {order['staff']} med_staff")
        self.OO[resource] += quantity
        self._communication += 1
      elif resource == 'staff' and self.name != 'Station' and self.name != 'Volunteers':
        coin = random.random()
        order_from = 'Station' # if coin > 0.5 else 'Volunteers'
        self.out_requests.append(f"{self.name}->{order_from}: Please send {order['staff']} staff")
        self.OO['staff'] += order['staff']
        self._communication += 1

    if ('food' in order.keys() or 'drink' in order.keys()) and self.name != 'Warehouse':
      self.out_requests.append(request)
      self._communication += 1
    
    print(self, self.out_requests)
    self.cumReward = self.gamma * self.cumReward + self.curReward
    self.curTime += 1

  def resetPlayer(self, T):
    self.OO = {key: 0 for key in self.inventory.keys()}
    self.AS = {key: np.squeeze(np.zeros((1, T + max(self.config.leadRecItemUp) + max(self.config.leadRecOrderUp) + 10))) for key in self.inventory.keys()}
    self.AO = {key: np.squeeze(np.zeros((1, T + max(self.config.leadRecItemUp) + max(self.config.leadRecOrderUp) + 10))) for key in self.inventory.keys()}

    self.curReward = 0 # the reward observed at the current step
    self.cumReward = 0 # cumulative reward; reset at the begining of each episode	
    self.action= [] 
    self.hist = []
    self.hist2 = []
    self.srdqnBaseStock = []	# this holds the base stock levels that srdqn has came up with. added on Nov 8, 2017
    self.T = T
    self.nextObservation = []
    self.curTime = 0
    self.staff_team = []
    self.patients = []

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
                              self.AO[resource][t]] for resource in self.inventory])
    else:
      # curState = np.array([[-1*(self.inventory[resource]<0)*self.inventory[resource], 
      #                       1*(self.inventory[resource]>0)*self.inventory[resource], 
      #                       self.OO[resource]] for resource in self.base_stock])
      curState = np.array([[self.inventory[resource], 
                            self.OO[resource]] for resource in self.base_stock])

    if self.config.ifUseActionInD:
      a = self.config.actionList[np.argmax(self.action)]
      curState = np.concatenate((curState, np.array([a])))
    
    return curState #.flatten()

class Warehouse(Agency):
  """
  Base class for Warehouse.

  Args:
    strategy (str): 'bs': base stock or 'strm': Stermann
  """
  def __init__(self, world, pos, agentNum, name, start_inventory, config):
    super().__init__(world, pos, agentNum, config)
    self.world = world
    self.pos = np.array(pos)
    self.name = name
    self.inventory = start_inventory.copy()
    self.start_inventory = start_inventory.copy()
    self.staff_team = [Person('staff', 5) for _ in range(self.inventory['staff'])]
    self.leadtimes = constants.leadtimes[self.name]
    self._backorder = 0
    self.strategy = 'bs'

    # Warehouse action mask
    send = np.array([1 if x in ['food', 'drink'] else 0 for x in self.inventory.keys()])
    request = 1 - send
    self.action_mask = np.concatenate((send, request), axis=0)

  @property
  def texture(self):
    return 'warehouse'
  
  @property
  def reward(self):
    return self.curReward
  
  def resetPlayer(self, T):
    super().resetPlayer(T)
    self.inventory = self.start_inventory
    self.staff_team = [Person('staff', 5) for _ in range(self.inventory['staff'])]
    return 
  
  def step(self, _step, action=None):
    self.receiveItems()
    self._update_life_stats()
    self.curReward = - self._backorder - self._communication

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

  def _make_decisions_on_requests(self, goal=None, action=None):
    if action and self.mode == 'human':
      print(action)

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
        if self.inventory[resource] >= total_quantity: 
          for requester, quantity in requests_list:
            requester.AS[resource][self.curTime + self.leadtimes[resource]] += quantity
        else:
          average_quantity = total_quantity // len(requests_list)
          self.inventory[resource] -= total_quantity
          for requester, _ in requests_list:
            requester.AS[resource][self.curTime + self.leadtimes[resource]] += average_quantity

    self.in_requests = [] # Clear

    ### Step 2: 
    self._make_orders(goal, action)


class Shelter(Agency):
  def __init__(self, world, pos, agentNum, name, start_inventory, config):
    super().__init__(world, pos, agentNum, config)
    self.name = name
    self.inventory = start_inventory.copy()
    self.start_inventory = start_inventory.copy()
    num_patients = time_varying_demand_supply.demand(mean=10, std_dev=STDDEV)
    self.patients = [Person('injured', 0) for _ in range(num_patients)]
    # self.staff_team = [Person('med_staff', 5) for _ in range(self.inventory['med_staff'])]
    self.staff_team = [Person('staff', 5) for _ in range(self.inventory['staff'])]
    self.cum_death = 0

    # Shelter aciton mask: 0 for send + 1 for request
    self.action_mask = [0 for x in self.inventory.keys()] + [1 for x in self.inventory.keys()]

  @property
  def texture(self):
    return 'hospital'
  
  @property
  def reward(self):
    return self.curReward
  
  def resetPlayer(self, T):
    super().resetPlayer(T)
    self.inventory = self.start_inventory.copy()
    num_patients = time_varying_demand_supply.demand(mean=10, std_dev=STDDEV)
    self.patients = [Person('injured', 0) for _ in range(num_patients)]
    # self.staff_team = [Person('med_staff', 5) for _ in range(self.inventory['med_staff'])]
    self.staff_team = [Person('staff', 5) for _ in range(self.inventory['staff'])]
    self.base_stock = {'food': 30, 
                      'drink': 30, 
                      'staff': 15, 
                      }
  
  def step(self, _step, action=None):
    self._death = 0
    self._helped_people = 0
    self.receiveItems()

    new_arrived_injure = time_varying_demand_supply.piecewise_function(self.curTime)
    for _ in range(new_arrived_injure):
      self.patients.append(Person('injured', 0))

    self._update_patient_inventory_stats()
    self._update_staff_stats()
    
    self.curReward = - self._death - self._communication

    for name, amount in self.inventory.items():
      try:
        maxmium = constants.resources[name]['max']
      except:
        maxmium = constants.items[name]['max']
      self.inventory[name] = min(amount, maxmium)

    print('Day:', _step, [patient.health for patient in self.patients], len(self.patients), 'Staff:', len(self.staff_team), self.inventory['food'], self.inventory['drink'])
    print('      ', [patient._admitted_days for patient in self.patients])

  def _update_patient_inventory_stats(self):
    self.consumption = 0

    while self.patients and self.patients[0].health >= 5: # Dismiss an injured 
        self.patients.pop(0)
    
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
        self.cum_death += 1
        self._death += 1
    
    self.patients = [patient for patient in self.patients if patient._admitted_days < 5] # or patient.health >= 2

    # For those patients that don't have staff catering to them
    for i in range(len(self.staff_team), len(self.patients)):
      self.AO['staff'][self.curTime] += 1
      self.AO['food'][self.curTime] += 2
      self.AO['drink'][self.curTime] += 2
      self.patients[i]._admitted_days += 1
    
    if self._death>0: print('death', self._death)
    #print("AO", self.AO['staff'][self.curTime], self.AO['food'][self.curTime], self.AO['drink'][self.curTime])

  def _update_staff_stats(self):
    returning_staff = 0
    for staff in self.staff_team:
      if staff.health <= 0:
        self.staff_team.remove(staff)
        self.inventory['staff'] -= 1
        returning_staff += 1
      else:
        staff.health -= 0.5
          
    if returning_staff > 0:
      self.out_requests.append(f'{returning_staff} staff is returning to station')

  def _make_decisions_on_requests(self, goal=None, action=None):

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
    if goal and not self.patients:
      goal['food'] = 0
      goal['drink'] = 0
      goal['staff'] = 0
    self._make_orders(goal, action)


class Station(Agency):
  def __init__(self, world, pos, agentNum, name, start_inventory, config):
    super().__init__(world, pos, agentNum, config)
    self.world = world
    self.pos = np.array(pos)
    self.name = name
    self.inventory = start_inventory.copy()
    self.start_inventory = start_inventory.copy()
    self.staff_team = [Person('staff', 5) for _ in range(self.inventory['staff'])]
    self.leadtimes = constants.leadtimes[self.name]
    self._backorder = 0
    self.strategy = 'bs'

    # Station action mask
    send = np.array([1 if 'staff' in x else 0 for x in self.inventory.keys()])
    request = 1 - send
    self.action_mask = np.concatenate((send, request), axis=0)

  @property
  def texture(self):
    return 'station'
  
  @property
  def reward(self):
    return self.curReward
  
  def resetPlayer(self, T):
    super().resetPlayer(T)
    self.inventory = self.start_inventory.copy()
    self.staff_team = [Person('staff', 5) for _ in range(self.inventory['staff'])]
    return 

  def step(self, _step, action=None):
    self._backorder = 0
    self.receiveItems()
    self._update_inventory_stats()
    self.curReward = - self._backorder - self._communication

  def _update_inventory_stats(self):
    self.consumption = 0
    for _ in range(max(self.inventory['staff'] - len(self.staff_team), 0)):
      self.staff_team.append(Person('staff', 0))

    for staff in self.staff_team:
      staff.health += min(5, 1.5 + staff.health)

  def _make_decisions_on_requests(self, goal=None, action=None):
    ### Part 1: 
    if action and self.mode == 'human':
      action

    self.in_requests = self._process_requests()
    self.in_requests = sorted(self.in_requests, key=lambda x: x[0].name)
    for request in self.in_requests:
        requester, quantity, resource = request
        self.AO[resource][self.curTime] = quantity
        sending_quantity = min(self.inventory[resource], int(quantity))
        for _ in range(sending_quantity):
          if self.staff_team and self.staff_team[0].health > 4:
            self.inventory[resource] -= 1
            requester.AS[resource][self.curTime + self.leadtimes[resource]] += 1
            self.staff_team.pop(0)
          else:
            break
    
    self.in_requests = []

    ### Part 2: make orders
    self._make_orders(goal, action)

