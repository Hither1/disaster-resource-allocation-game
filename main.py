# from __future__ import print_function, division
import os
import time
import torch
import argparse
from datetime import datetime
import torch.multiprocessing as mp

from agent.tom2c.test import test
from agent.tom2c.train import train
from agent.tom2c.worker import worker
from agent.tom2c.model import build_model
from agent.tom2c.environment import create_env
from agent.tom2c.shared_optim import SharedRMSprop, SharedAdam
from utils import load_config
import hydra
from omegaconf import DictConfig, OmegaConf
os.environ["OMP_NUM_THREADS"] = "1"

# parser = argparse.ArgumentParser(description='A3C')
# num_step: 20
# max_step: 500000
# env_max_step: 100
# low-level step: 10
# training mode: -1 for worker collecting trajectories, -10 for workers waiting for training process, -20 for training, -100 for all processes end

def start(args: DictConfig):

    if args.gamma_rate == 0:
        args.gamma = 0.9
        args.env_steps *= 5
    if args.gpu_id == -1:
        torch.manual_seed(args.seed)
        args.gpu_id = [-1]
        device_share = torch.device('cpu')
        mp.set_start_method('spawn')
    else:
        torch.cuda.manual_seed(args.seed)
        mp.set_start_method('spawn', force=True)
        if len(args.gpu_id) > 1:
            raise AssertionError("Do not support multi-gpu training")
        else:
            device_share = torch.device('cuda:' + str(args.gpu_id[-1]))

    env = create_env(args.env, args)
    assert env.max_steps % args.A2C_steps == 0
    shared_model = build_model(env, args, device_share).to(device_share)
    shared_model.share_memory()
    shared_model.train()
    env.close()
    del env

    if args.load_model_dir is not None:
        saved_state = torch.load(
            args.load_model_dir,
            map_location=lambda storage, loc: storage)
        if args.load_model_dir[-3:] == 'pth':
            shared_model.load_state_dict(saved_state['model'], strict=False)
        else:
            shared_model.load_state_dict(saved_state)

    # params = shared_model.parameters()
    params = []
    params_ToM = []
    for name, param in shared_model.named_parameters():
        if 'ToM' in name or 'other' in name:
            params_ToM.append(param)
        else:
            params.append(param)
    
    if args.shared_optimizer:
        print('share memory')
        if args.optimizer == 'RMSprop':
            optimizer_Policy = SharedRMSprop(params, lr=args.lr)
            if 'ToM' in args.model:
                optimizer_ToM = SharedRMSprop(params_ToM, lr=args.lr)
            else:
                optimizer_ToM = None
        if args.optimizer == 'Adam':
            optimizer_Policy = SharedAdam(params, lr=args.lr, amsgrad=args.amsgrad)
            if 'ToM' in args.model:
                print("ToM optimizer lr * 10")
                optimizer_ToM = SharedAdam(params_ToM, lr=args.lr*10, amsgrad=args.amsgrad)
            else:
                optimizer_ToM = None
        optimizer_Policy.share_memory()
        if optimizer_ToM is not None:
            optimizer_ToM.share_memory()
    else:
        optimizer_Policy = None
        optimizer_ToM = None

    current_time = datetime.now().strftime('%b%d_%H-%M')
    args.log_dir = os.path.join(args.log_dir, args.env, current_time)

    processes = []
    manager = mp.Manager()
    train_modes = manager.list()
    n_iters = manager.list()
    curr_env_steps = manager.list()
    ToM_count = manager.list()
    ToM_history = manager.list()
    Policy_history = manager.list()
    step_history = manager.list()
    loss_history = manager.list()

    for rank in range(0, args.workers):
        p = mp.Process(target=worker, args=(rank, args, shared_model, train_modes, n_iters, curr_env_steps, ToM_count, ToM_history, Policy_history, step_history, loss_history))
        train_modes.append(args.train_mode)
        n_iters.append(0)
        curr_env_steps.append(args.env_steps)
        ToM_count.append(0)
        ToM_history.append([])
        Policy_history.append([])
        step_history.append([])
        loss_history.append([])
        p.start()
        processes.append(p)
        time.sleep(args.sleep_time)

    p = mp.Process(target=test, args=(args, shared_model, optimizer_Policy, optimizer_ToM, train_modes, n_iters))
    p.start()
    processes.append(p)
    time.sleep(args.sleep_time)

    if args.workers >= 0:
        p = mp.Process(target=train, args=(args, shared_model, optimizer_Policy, optimizer_ToM, train_modes, n_iters, curr_env_steps, ToM_count, ToM_history, Policy_history, step_history, loss_history))
        p.start()
        processes.append(p)
        time.sleep(args.sleep_time)

    for p in processes:
        time.sleep(args.sleep_time)
        p.join()


if __name__=='__main__':
    os.environ["WANDB_MODE"] = "disabled"
    model = 'sac'
    config1 = load_config("configs/model", model)
    config2 = load_config("configs/exp", "leadtimes")
    merged_config = OmegaConf.merge(config1, config2)
    start(merged_config)
