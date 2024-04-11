"""
Scenario for inventory management.
"""

# from crafter import high_level_objects
from crafter import high_level_objects_low_obs as high_level_objects
import numpy as np
from multiagent.core import Agent, Landmark
from multiagent.scenario import BaseScenario
import random
import crafter
from crafter import engine, constants, low_level_objects
from random import randint
from crafter import time_varying_demand_supply
from utils import load_config
import torch
STDDEV = 1

class Scenario(BaseScenario):
    def make_world(self, num_agents=-1, num_targets=-1):
        config = load_config("configs/exp", 'leadtimes')
        config = crafter.config.get_config(config)
        self.config = config
        world = engine.World(config.area, constants.materials, (12, 12))
        # set any world properties first
        # world.dim_c = 0
        if num_agents == -1:
            num_agents = 3
            num_landmarks = 3
        else:
            if num_targets == -1:
                raise AssertionError("Number of targets is not assigned")
            else:
                num_landmarks = num_targets

        world.collaborative = False
        world.discrete_action = True
        self.T = 0
        self.totIterPlayed = 0

        world.landmarks = [] 
        # add agents
        shelter_inventory = {'food': 39, 
                      'drink': 39, 
                      'staff': time_varying_demand_supply.demand(mean=20, std_dev=STDDEV), 
                      }
        world.shelter = high_level_objects.Shelter(world, (28, 28), 0, "Shelter", shelter_inventory, config)

        warehouse_inventory = {'food': time_varying_demand_supply.demand(mean=40, std_dev=STDDEV), 
                      'drink': time_varying_demand_supply.demand(mean=40, std_dev=STDDEV), 
                      'staff': 9,
                      }
        world.warehouse = high_level_objects.Warehouse(world, (28, 32), 1, "Warehouse", warehouse_inventory, config)

        station_inventory = {'food': 9, 
                      'drink': 9, 
                      'staff': time_varying_demand_supply.demand(mean=12, std_dev=STDDEV), 
                      }
        world.station = high_level_objects.Station(world, (32, 28), 2, "Station", station_inventory, config)

        world.agents = [world.shelter, world.warehouse, world.station]

        world._player = low_level_objects.Player(world, (32, 32))
        world.add(world._player)
        for i, agent in enumerate(world.agents):
            world.add(agent)
            agent.collide = True
            agent.silent = False
            landmark = []
            for key, item in agent.base_stock.items():
                landmark.extend([0, item, 0])
            world.landmarks.append(landmark)
        
        # world.landmarks = [[0, 50, 0, 0, 50, 0, 0, 20, 0],
        #                    [0, 30, 0, 0, 30, 0, 0, 12, 0], 
        #                    [0, 2, 0, 0, 2, 0, 0, 1, 0]]
        # world.landmarks = [[[40, 0, 0, 0], [40, 0, 0, 0], [15, 0, 0, 0]], 
        #                    [[50, 0, 0, 0], [50, 0, 0, 0], [0, 0, 0, 0]],
        #                    [[2, 0, 0, 0],  [2, 0, 0, 0], [1, 0, 0, 0]]]

        world.landmarks = [[[40], [40], [15]], 
                           [[50], [50], [0]],
                           [[2],  [2], [1]]]
        # make initial conditions
        world = self.reset_world(world)
        
        return world, self.config

    def planHorizon(self):
		# TLow: minimum number for the planning horizon # TUp: maximum number for the planning horizon
		# output: The planning horizon which is chosen randomly.
        return randint(self.config.TLow, self.config.TUp)

    def reset_world(self, world, playType='train'):
        if playType == "train":
            self.totIterPlayed += self.T
            self.T = self.planHorizon()	
        else:
            self.T = self.config.Ttest	

        for player in world.agents:
            player.resetPlayer(self.T)

        # set random initial states
        # for agent in world.agents:
        #     agent.state.p_pos = np.random.uniform(-world.range_p, +world.range_p, world.dim_p)
        #     agent.state.c = np.zeros(world.dim_c)
        
        # # set agent goals
        # if goals is None:
        #     goals = [i for i in range(len(world.agents))]
            
        return world

    def benchmark_data(self, agent, world):
        rew = 0
        collisions = 0
        occupied_landmarks = 0
        min_dists = 0
        for l in world.landmarks:
            collision_dist = agent.size + l.size
            dists = [np.sqrt(np.sum(np.square(a.state.p_pos - l.state.p_pos))) for a in world.agents]
            min_dists += min(dists)
            rew -= min(dists)
            if min(dists) < collision_dist:
                occupied_landmarks += 1

        return (rew, collisions, min_dists, occupied_landmarks)

    def global_reward(self, world):
        """
        global reward
        """
        rew = 0
        self.comm_weight, self.cons_weight = 1., 0.5
        for agent in world.agents:
            rew += - self.comm_weight * agent._communication
            rew += - self.cons_weight * agent.consumption
        rew += -10 * world.shelter._death
        # rew += 1.2 * world.shelter._helped_people
        if len(world.shelter.patients) == 0: rew = 0
        return rew
    
    def reward(self, agent, world):
        """
        local reward
        Agents are rewarded based on minimum agent distance to each , penalized for 
        """
        rew = agent.reward

        return rew

    def observation(self, agent, world):
        agent_state_tensor = torch.tensor(agent.getCurState())
        entity_pos = []

        for entity in world.landmarks:
            entity_pos.append(torch.tensor(entity) - agent_state_tensor)

        # return np.concatenate([agent.getCurState()] + entity_pos)
        # print('obs', torch.cat([agent_state_tensor] + entity_pos).shape)
        return torch.cat([agent_state_tensor] + entity_pos)
    
    def rule_policy(self, obs):
        x_rel = obs[0]
        y_rel = obs[1]
        if max(abs(x_rel), abs(y_rel)) < 0.05:
            action = [0]
        elif abs(x_rel) > abs(y_rel):
            if x_rel > 0:
                action = [2]
            else:
                action = [1]
        else:
            if y_rel > 0:
                action = [4]
            else:
                action = [3]
        action = np.array(action)
        return action
    
    
        

        # for k in range(self.config.NoAgent):
        #     if k < self.config.NoAgent - 1:
        #         self.players[k].OO = sum(self.players[k+1].AO) + sum(self.players[k].AS)
        #     else:
        #         self.players[k].OO = sum(self.players[k].AS)

