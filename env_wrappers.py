"""
Modified from Stable-baselines3 code to work with multi-agent envs
"""
from __future__ import division
from typing import List, Optional
import numpy as np
from multiprocessing import Process, Pipe
from stable_baselines3.common.vec_env.base_vec_env import VecEnv, CloudpickleWrapper
import torch
import time
import crafter

def worker(remote, parent_remote, env_fn_wrapper: CloudpickleWrapper):
    parent_remote.close()
    env = env_fn_wrapper.var()
    while True:
        cmd, data = remote.recv()
        if cmd == "step":
            ob, reward, done, info = env.step(data)
            # if all(done):
            if done:
                ob = env.reset()
            remote.send((ob, reward, done, info))
        elif cmd == "reset":
            ob = env.reset()
            remote.send(ob)
        elif cmd == "reset_task":
            ob = env.reset_task()
            remote.send(ob)
        elif cmd == "close":
            remote.close()
            break
        elif cmd == "get_spaces":
            remote.send((env.observation_space, env.action_space))
        elif cmd == "get_agent_types":
            if all([hasattr(a, "adversary") for a in env.env.agents]):
                remote.send(
                    ["adversary" if a.adversary else "agent" for a in env.agents]
                )
            else:
                remote.send(["agent" for _ in env.env.agents])
        else:
            raise NotImplementedError


def create_env(env_id, args, rank=-1):
    if 'RA' or 'IM' in env_id:  
        import multiagent.scenarios as scenarios
        scenario = scenarios.load(args.env + ".py").Scenario()
        world, config = scenario.make_world()
        env = crafter.Env(config, world, None, scenario.reset_world, scenario.reward, scenario.global_reward, scenario.observation)
        env = crafter.Recorder(env, config.record, save_stats=True)
        env.reset()
        env_wrap = env_wrapper(env, args)
        return env_wrap
    else:
        raise NotImplementedError

class env_wrapper:
    # wrap for CN low level execution
    def __init__(self, env):
        self.env = env
        self.n = self.env.n_agents
        self.num_target = len(self.env.world.landmarks)
        # self.observation_space = np.zeros([self.n, self.num_target, *self.env.state_dim])
        # self.action_space = np.zeros([self.n, self.num_target, 1])
        self.observation_space = self.env.observation_space
        self.action_space = self.env.action_space

    # def step(self, goals_n):
    #     goals_n = np.squeeze(goals_n)
    #     keep = 10
    #     rew_ave = 0
    #     for step in range(keep):
    #         # get low level obs
    #         act_low_n = []
    #         for i in range(self.n):
    #         rew_ave += rew[0]
    #     rew_all = np.array([rew_ave/keep])
    #     return obs_n, rew_all, done_n, info_n
        
    def step(self, goals_n):
        goals_n = np.squeeze(goals_n)
        # goals_n = [[action.reshape(3, -1).argmax(-1) for action in thread] for thread in goals_n]
        keep = 1
        rew_ave = []
        for step in range(keep):
            obs_n, rew, done_n, info_n = self.env.step()

            for i in range(self.n):
                # goal = int(goals_n[i])
                goals = goals_n[i].reshape(3, -1).argmax(-1)
                bs_goal = [self.env.world.landmarks[int(goal)] for goal in goals]
                # bs_goal = self.env.world.landmarks[int(goals_n[i])]
                agent = self.env.world.agents[i]
                agent._make_decisions_on_requests(self.decode_goal(bs_goal))
            
            if done_n: self.env.reset()
            # if self.render:
            #     self.env.render()
            #     time.sleep(0.1)
            rew_ave.append(rew)
        rew_all = np.mean(np.array(rew_ave), 0)

        return obs_n, rew_all, done_n, info_n
    
    def decode_goal(self, goal):
        start = 1
        pose_dim = 4
        goal_ret = {'food': goal[0][0][0], 
                    'drink': goal[0][1][0], 
                    'staff': goal[0][2][0]}
        # goal_ret = {'food': goal[0][0][0], 
        #             'drink': goal[1][1][0], 
        #             'staff': goal[2][2][0]}
        return goal_ret

    
    def reset(self):
        obs_n = self.env.reset()
        return obs_n

    def seed(self, s):
        self.env.seed(s)
    
    def close(self):
        self.env.close()


class SubprocVecEnv(VecEnv):
    def __init__(self, env_fns, spaces=None):
        """
        envs: list of gym environments to run in subprocesses
        """
        self.waiting = False
        self.closed = False
        nenvs = len(env_fns)
        self.remotes, self.work_remotes = zip(*[Pipe() for _ in range(nenvs)])
        self.ps = [
            Process(
                target=worker, args=(work_remote, remote, CloudpickleWrapper(env_fn))
            )
            for (work_remote, remote, env_fn) in zip(
                self.work_remotes, self.remotes, env_fns
            )
        ]
        for p in self.ps:
            p.daemon = (
                True  # if the main process crashes, we should not cause things to hang
            )
            p.start()
        for remote in self.work_remotes:
            remote.close()

        self.remotes[0].send(("get_spaces", None))
        observation_space, action_space = self.remotes[0].recv()
        self.remotes[0].send(("get_agent_types", None))
        self.agent_types = self.remotes[0].recv()
        self.n = len(self.agent_types)
        print(len(env_fns), 'len(env_fns)')
        VecEnv.__init__(self, len(env_fns), observation_space, action_space)

    def step_async(self, actions):
        for remote, action in zip(self.remotes, actions):
            remote.send(("step", action))
        self.waiting = True

    def step_wait(self):
        results = [remote.recv() for remote in self.remotes]
        self.waiting = False
        obs, rews, dones, infos = zip(*results)
        return torch.stack(obs), np.stack(rews), np.stack(dones), infos

    def reset(self):
        for remote in self.remotes:
            remote.send(("reset", None))
        return torch.stack([remote.recv() for remote in self.remotes])

    def reset_task(self):
        for remote in self.remotes:
            remote.send(("reset_task", None))
        return np.stack([remote.recv() for remote in self.remotes])

    def close(self):
        if self.closed:
            return
        if self.waiting:
            for remote in self.remotes:
                remote.recv()
        for remote in self.remotes:
            remote.send(("close", None))
        for p in self.ps:
            p.join()
        self.closed = True

    def env_is_wrapped(self, wrapper_class, indices) -> List[bool]:
        pass

    def env_method(self, method_name: str, *method_args, indices, **method_kwargs):
        pass

    def get_attr(self, attr_name: str, indice = None):
        pass

    def set_attr(self, attr_name: str, value, indices) -> None:
        pass

    def seed(self, seed: Optional[int] = None):
        pass


class DummyVecEnv(VecEnv):
    def __init__(self, env_fns):
        self.envs = [fn() for fn in env_fns]
        env = self.envs[0]
        VecEnv.__init__(self, len(env_fns), env.observation_space, env.action_space)
        if all([hasattr(a, "adversary") for a in env.env.agents]):
            self.agent_types = [
                "adversary" if a.adversary else "agent" for a in env.agents
            ]
        else:
            self.agent_types = ["agent" for _ in env.agents]
        self.ts = np.zeros(len(self.envs), dtype="int")
        self.actions = None

    def step_async(self, actions):
        self.actions = actions

    def step_wait(self):
        results = [env.step(a) for (a, env) in zip(self.actions, self.envs)]
        obs, rews, dones, infos = map(np.array, zip(*results))
        self.ts += 1
        for (i, done) in enumerate(dones):
            if all(done):
                obs[i] = self.envs[i].reset()
                self.ts[i] = 0
        self.actions = None
        return np.array(obs), np.array(rews), np.array(dones), infos

    def reset(self):
        results = [env.reset() for env in self.envs]
        return np.array(results)

    def close(self):
        return
