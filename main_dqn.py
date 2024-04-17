import numpy as np
import os
import random
import argparse
import pandas as pd
from MA_algorithms.model_free.tom2c.environment import create_env
from MA_algorithms.model_free.DQN.dqn_agent import Agent
import wandb
import glob
from utils import load_config
from omegaconf import DictConfig, OmegaConf

ARG_LIST = ['learning_rate', 'optimizer', 'memory_capacity', 'batch_size', 'target_frequency', 'maximum_exploration',
            'env_steps', 'first_step_memory', 'replay_steps', 'number_nodes', 'target_type', 'memory',
            'prioritization_scale', 'dueling', 'game_mode', 'reward_mode']


def get_name_brain(args, idx):

    file_name_str = '_'.join([str(args[x]) for x in ARG_LIST])

    return 'outputs/dqn/weight_files/' + file_name_str + '_' + str(idx) + '.h5'


def get_name_rewards(args):

    file_name_str = '_'.join([str(args[x]) for x in ARG_LIST])

    return './results_agents_/rewards_files/' + file_name_str + '.csv'


def get_name_timesteps(args):

    file_name_str = '_'.join([str(args[x]) for x in ARG_LIST])

    return './results_agents_/timesteps_files/' + file_name_str + '.csv'


class Environment(object):

    def __init__(self, arguments):
        current_path = os.path.dirname(__file__)  # Where your .py file is located
        self.env = create_env(args.env, args)
        self.episodes_number = arguments['episode_number']
        self.render = arguments['render']
        self.recorder = arguments['recorder']
        self.max_ts = arguments['env_steps']
        self.test = arguments['test']
        self.filling_steps = arguments['first_step_memory']
        self.steps_b_updates = arguments['replay_steps']
        self.max_random_moves = arguments['max_random_moves']
        
        self.num_agents = self.env.n
        self.num_landmarks = self.num_agents
        self.game_mode = arguments['game_mode']

        wandb.init(project="DRA", name=f"DQN-{arguments['target_type']}-{arguments['memory']}-dueling-{arguments['dueling']}")

    def run(self, agents, file1, file2):
        total_step = 0
        rewards_list = []
        timesteps_list = []
        max_score = -10000
        for episode_num in range(self.episodes_number):
            state = self.env.reset()

            random_moves = random.randint(0, self.max_random_moves)

            # create randomness in initial state
            for _ in range(random_moves):
                actions = [4 for _ in range(len(agents))]
                state, _, _ = self.env.step(actions)

            # converting list of positions to an array
            state = np.array(state)
            state = state.ravel()
            done = False
            reward_all = 0
            time_step = 0
            while not done and time_step < self.max_ts:
                actions = []
                for agent in agents:
                    actions.append(agent.greedy_actor(state))
                next_state, reward, done, info = self.env.step(actions)
                # converting list of positions to an array
                next_state = np.array(next_state)
                next_state = next_state.ravel()

                if not self.test:
                    for agent in agents:

                        agent.observe((state, actions, reward, next_state, done))
                        if total_step >= self.filling_steps:
                            agent.decay_epsilon()
                            if time_step % self.steps_b_updates == 0:
                                agent.replay()
                            agent.update_target_model()

                total_step += 1
                time_step += 1
                state = next_state
                reward_all += reward[0]


            wandb.log({"score": reward_all}, step=total_step)
            # rewards_list.append(reward_all)
            # timesteps_list.append(time_step)

            print("Episode {p}, Score: {s}, Final Step: {t}, Goal: {g}".format(p=episode_num, s=reward_all,
                                                                               t=time_step, g=done))

            # if self.recorder:
            #     os.system("ffmpeg -r 2 -i ./results_agents_landmarks/snaps/%04d.png -b:v 40000 -minrate 40000 -maxrate 4000k -bufsize 1835k -c:v mjpeg -qscale:v 0 "
            #               + "./results_agents_landmarks/videos/{a1}_{a2}_{a3}_{a4}.avi".format(a1=self.num_agents,
            #                                                                                      a2=self.num_landmarks,
            #                                                                                      a3=self.game_mode,
            #                                                                                      a4=self.grid_size))
            #     files = glob.glob('./results_agents_landmarks/snaps/*')
            #     for f in files:
            #         os.remove(f)

            if not self.test:
                if episode_num % 100 == 0:

                    if total_step >= self.filling_steps:
                        if reward_all > max_score:
                            for agent in agents:
                                agent.brain.save_model()
                            max_score = reward_all


if __name__ =="__main__":
    # os.environ["WANDB_MODE"] = "disabled"
    config1 = load_config("configs/model/model_free", "dqn")
    config2 = load_config("configs/exp", "leadtimes")
    args = OmegaConf.merge(config1, config2)

    os.environ['CUDA_VISIBLE_DEVICES'] = args['gpu_num']

    env = Environment(args)

    state_size = env.env.observation_space.shape[-2] # env.env.state_size
    state_size = state_size * env.env.n
    action_space = env.env.action_space.shape[-2]

    all_agents = []
    for b_idx in range(env.num_agents):
        brain_file = get_name_brain(args, b_idx)
        all_agents.append(Agent(state_size, action_space, b_idx, brain_file, args))

    rewards_file = get_name_rewards(args)
    timesteps_file = get_name_timesteps(args)

    env.run(all_agents, rewards_file, timesteps_file)
