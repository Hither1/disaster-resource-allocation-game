from __future__ import division
import numpy as np
import time
import crafter

def create_env(env_id, args, rank=-1):
    if 'MSMTC' in env_id:
        import ToM2C.MSMTC.DigitalPose2D as poseEnv
        env = poseEnv.gym.make(env_id, args)
        # adjust env steps according to args
        env.max_steps = args.env_steps
        return env
    elif 'CN' in env_id:  
        from multiagent.environment import MultiAgentEnv
        import multiagent.scenarios as scenarios
        scenario_name = args.env
        # load scenario from script
        scenario = scenarios.load(scenario_name + ".py").Scenario()
        # create world
        world = scenario.make_world(args.num_agents, args.num_targets)
        # create multiagent environment
        env = MultiAgentEnv(world, scenario.reset_world, scenario.reward, scenario.observation)
        env_wrap = env_wrapper(env, args)
        return env_wrap
    elif 'RA' in env_id:  
        from multiagent.environment import MultiAgentEnv
        import multiagent.scenarios as scenarios
        scenario = scenarios.load(args.env + ".py").Scenario()
        config, unparsed = crafter.config.get_config()
        world = scenario.make_world(config, args.num_agents, args.num_targets)
        
        env = crafter.Env(config, world, scenario.reset_world, scenario.reward, scenario.global_reward, scenario.observation)
        env = crafter.Recorder(env, config.record)
        env.reset()
        env_wrap = env_wrapper(env, args)

        return env_wrap
    else:
        raise NotImplementedError

class env_wrapper:
    # wrap for CN low level execution
    def __init__(self, env, args):
        self.env = env
        self.n = self.env.n_agents
        self.num_target = len(self.env.world.landmarks)
        self.observation_space = np.zeros([self.n, self.num_target, self.env.state_dim])
        self.action_space = np.zeros([self.n, self.num_target, 1])
        self.max_steps = args.env_steps
        self.render = args.render

    # def step(self, goals_n):
    #     goals_n = np.squeeze(goals_n)
    #     keep = 10
    #     rew_ave = 0
    #     for step in range(keep):
    #         # get low level obs
    #         act_low_n = []
    #         for i in range(self.n):
    #             goal = int(goals_n[i])
    #             land_goal = self.env.world.landmarks[goal]
    #             agent = self.env.world.agents[i]
    #             entity_pos = [(land_goal.state.p_pos - agent.state.p_pos)]
    #             obs_low = np.concatenate(entity_pos)
    #             act_low_n.append(self.env.world.rule_policy(obs_low))
            
    #         obs_n, rew, done_n, info_n = self.env.step(act_low_n)
    #         if self.render:
    #             self.env.render()
    #             time.sleep(0.1)
    #         rew_ave += rew[0]
    #     rew_all = np.array([rew_ave/keep])
    #     return obs_n, rew_all, done_n, info_n
        
    def step(self, goals_n):
        goals_n = np.squeeze(goals_n)
        keep = 1
        rew_ave = []
        for step in range(keep):
            obs_n, rew, done_n, info_n = self.env.step()

            for i in range(self.n):
                goal = int(goals_n[i])
                land_goal = self.env.world.landmarks[goal]
                agent = self.env.world.agents[i]
                agent._make_decisions_on_requests(self.decode_goal(land_goal))
            
            if done_n: self.env.reset()
            if self.render:
                self.env.render()
                time.sleep(0.1)
            rew_ave.append(rew)
        rew_all = np.mean(np.array(rew_ave), 0)

        return obs_n, rew_all, done_n, info_n
    
    def decode_goal(self, goal):
        start = 1
        pose_dim = 4
        goal_ret = {'food': goal[start], 'drink': goal[start+pose_dim], 'staff': goal[start+pose_dim*2]}
        return goal_ret
    
    # def step(self, goals_n):
    #     goals_n = np.squeeze(goals_n)

    #     for i in range(self.n):
    #         goal = int(goals_n[i])
    #         land_goal = self.env.world.landmarks[goal]
    #         agent = self.env.world.agents[i]
    #         agent._make_decisions_on_requests(land_goal)
            
    #     obs_n, rew, done_n, info_n = self.env.step()
    #     if self.render:
    #             self.env.render()
    #             time.sleep(0.1)

    #     rew_all = np.array(rew)
    #     print('obs', len(obs_n), len(obs_n[0]), rew_all.shape, done_n)
    #     return obs_n, rew_all, done_n, info_n
    
    def reset(self):
        obs_n = self.env.reset()
        return obs_n

    def seed(self, s):
        self.env.seed(s)
    
    def close(self):
        self.env.close()
