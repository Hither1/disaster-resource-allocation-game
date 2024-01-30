import numpy as np
import re
from . import constants
from . import engine
from . import time_varying_demand_supply
from agent.base_agent import Agency

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
      maxmium = constants.items[name]['max']
      self.inventory[name] = max(0, min(amount, maxmium))


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

    self.inventory = {'food': time_varying_demand_supply.demand(mean=40, std_dev=STDDEV), 
                      'drink': time_varying_demand_supply.demand(mean=40, std_dev=STDDEV), 
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
    self.inventory = {'food': time_varying_demand_supply.demand(mean=40, std_dev=STDDEV), 
                      'drink': time_varying_demand_supply.demand(mean=40, std_dev=STDDEV), 
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
    
    self.inventory = {'health': time_varying_demand_supply.demand(mean=10, std_dev=STDDEV), 
                      'food': 39, 
                      'drink': 39, 
                      'staff': time_varying_demand_supply.demand(mean=20, std_dev=STDDEV), 
                      'death': 0,
                      'wood': 0, 
                      'stone': 0, 
                      'coal': 0}
    self.patients = [Person('injured', 0) for _ in range(self.inventory['health'])]
    self.staff_team = [Person('staff', 5) for _ in range(self.inventory['staff'])]
    # self.base_stock = {'food': 30, 
    #                   'drink': 30, 
    #                   'staff': 15, 
    #                   }
    
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
    self.inventory = {'health': time_varying_demand_supply.demand(mean=10, std_dev=STDDEV), 
                      'food': 39, 
                      'drink': 39, 
                      'staff': time_varying_demand_supply.demand(mean=20, std_dev=STDDEV), 
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
                      'staff': time_varying_demand_supply.demand(mean=12, std_dev=STDDEV), 
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
                      'staff': time_varying_demand_supply.demand(mean=12, std_dev=STDDEV), 
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

