from __future__ import division
import os
import time
import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np
import torch.optim as optim

import wandb
from setproctitle import setproctitle as ptitle

import json

from .model import build_model
# from .player_util import Agent
from .environment import create_env
from .shared_optim import SharedRMSprop, SharedAdam

class HLoss(nn.Module):
    def __init__(self):
        super(HLoss, self).__init__()

    def forward(self, x, prior=None):
        if prior is None:
            b = F.softmax(x, dim=1) * F.log_softmax(x, dim=1)
            b = -b.sum(1)
            b = b.mean()
        else:
            b = F.softmax(x, dim = -1)
            b = b * (F.log_softmax(x, dim = -1) - torch.log(prior).view(-1, x.size(-1)))
            b = -b.sum(-1)
            b = b.mean()
        return b
    
# def optimize_ToM(state, poses masks, available_actions, args, params, optimizer_ToM, shared_model, device_share, env):
def optimize_ToM(state, masks, available_actions, args, params, optimizer_ToM, shared_model, device_share, env):
    num_agents = env.n
    num_targets = env.num_target
    max_steps = env.max_steps
    seg_num = int(max_steps/args.A2C_steps)
    if "MSMTC" in args.env:
        batch_size, num_agents, num_both, obs_dim = state.size()
    else:
        batch_size, num_agents, obs_dim, feature_dim = state.size()
    count = int(batch_size/max_steps)
    num_resources = int(obs_dim/(num_agents + 1)) 
    if "MSMTC" in args.env:
        state = state.reshape(count, max_steps, num_agents, num_both, obs_dim)#.to(device_share)
    else:
        state = state.reshape(count, max_steps, num_agents, obs_dim, feature_dim)#.to(device_share)

    # batch_size, num_agents, num_agents, cam_dim = poses.size()
    # poses = poses.reshape(count, max_steps, num_agents, num_agents, cam_dim)#.to(device_share)
 
    masks = masks.reshape(count, max_steps, num_agents, num_agents, 1)
    h_ToM = torch.zeros(count, num_agents, num_agents, args.lstm_out).to(device_share)
    hself = torch.zeros(count, num_agents, args.lstm_out).to(device_share)
    hself_start = hself.clone().detach() # save the intial hidden state for every args.num_steps
    hToM_start = h_ToM.clone().detach()

    if args.mask_actions:
        available_actions = available_actions.reshape(count, max_steps, num_agents, num_targets, -1)

    ToM_loss_sum = torch.zeros(1).to(device_share)
    ToM_target_loss_sum = torch.zeros(1).to(device_share)
    ToM_target_acc_sum = torch.zeros(1).to(device_share)
    for seg in range(seg_num):
        for train_loop in range(args.ToM_train_loops):
            hself = hself_start.clone().detach()
            h_ToM = hToM_start.clone().detach()
            ToM_goals = None
            real_goals = None
            BCE_criterion = torch.nn.BCELoss(reduction='sum')
            mse_loss = nn.MSELoss(reduction='sum')
            ToM_target_loss = torch.zeros(1).to(device_share)
            ToM_target_acc = torch.zeros(1).to(device_share)
            for s_i in range(args.A2C_steps):
                step = seg * args.A2C_steps + s_i
                available_action = available_actions[:,step].to(device_share) if args.mask_actions else None
                
                if "RA" in args.env or "IM" in args.env:
                    value_multi, actions, entropy, log_prob, hn_self, hn_ToM, ToM_goal, edge_logits, comm_edges, probs, real_cover, ToM_target_cover =\
                        shared_model(state[:, step].to(device_share), hself, h_ToM, available_actions=available_action)
                    
                    ToM_target_cover = ToM_target_cover.squeeze(-1)
                    ToM_target_loss += mse_loss(ToM_target_cover.float(), real_cover.float())
                else:
                    value_multi, actions, entropy, log_prob, hn_self, hn_ToM, ToM_goal, edge_logits, comm_edges, probs, real_cover, ToM_target_cover =\
                        shared_model(state[:, step].to(device_share), hself, h_ToM, poses[:, step].to(device_share), masks[:,step].to(device_share), available_actions = available_action)
                    ToM_target_loss += BCE_criterion(ToM_target_cover.float(), real_cover.float())

                ToM_target_cover_discrete = (ToM_target_cover > 0.6)
                ToM_target_acc += torch.sum((ToM_target_cover_discrete == real_cover))
                
                hself = hn_self
                h_ToM = hn_ToM

                ToM_goal = ToM_goal.unsqueeze(1)
                if "MSMTC" in args.env:
                    real_goal = torch.cat((1-actions, actions), -1).detach()
                    real_goal_duplicate = real_goal.reshape(count, 1, num_agents, num_targets, -1).repeat(1, num_agents, 1, 1, 1)
                    idx = (torch.ones(num_agents, num_agents) - torch.diag(torch.ones(num_agents))).bool()
                    real_goal_duplicate = real_goal_duplicate[:, idx].reshape(count, 1, num_agents, num_agents-1, num_targets, -1)
                else:
                    real_goal = actions.reshape(count * num_agents * num_resources, 1)
                    real_goal_duplicate = torch.zeros(count * num_agents * num_resources, num_targets).to(device_share).scatter_(1, real_goal, 1)
                    real_goal_duplicate = real_goal_duplicate.reshape(count, 1, num_agents, num_targets, -1).repeat(1, num_agents, 1, 1, 1)
                    idx = (torch.ones(num_agents, num_agents) - torch.diag(torch.ones(num_agents))).bool()
                    real_goal_duplicate = real_goal_duplicate[:, idx].reshape(count, 1, num_agents, num_agents-1, num_resources, num_targets)
                if ToM_goals is None:
                    ToM_goals = ToM_goal
                    real_goals = real_goal_duplicate
                else:
                    ToM_goals = torch.cat((ToM_goals, ToM_goal),1)
                    real_goals = torch.cat((real_goals, real_goal_duplicate), 1)
            ToM_loss = torch.zeros(1).to(device_share)
            KL_criterion = torch.nn.KLDivLoss(reduction='sum')
            real_prob = real_goals.float()
            ToM_prob = ToM_goals.float()
            ToM_loss += KL_criterion(ToM_prob.log(), real_prob)
            
            loss = ToM_loss + 0.5 * ToM_target_loss
            loss = loss/(count)
            shared_model.zero_grad()
            # loss.backward()
            torch.nn.utils.clip_grad_norm_(params, 20)
            optimizer_ToM.step()
            
        # update hidden state start & loss sum
        hself_start = hself.clone().detach()
        hToM_start = h_ToM.clone().detach()
        ToM_loss_sum += ToM_loss
        ToM_target_loss_sum += ToM_target_loss
        ToM_target_acc_sum += ToM_target_acc

    print("ToM_loss =", ToM_loss_sum.sum().data)
    print("ToM Target loss=", ToM_target_loss_sum.sum().data)
    cnt_all = (num_agents * (num_agents-1) * num_targets * batch_size)
    ToM_loss_mean = ToM_loss_sum/cnt_all
    ToM_target_loss_mean = ToM_target_loss_sum/cnt_all
    ToM_target_acc_mean = ToM_target_acc_sum/cnt_all
    return ToM_loss_sum, ToM_loss_mean, ToM_target_loss_mean, ToM_target_acc_mean  

def optimize_Policy(state, real_actions, reward, masks, available_actions, args, params, optimizer_Policy, shared_model, device_share, env):
    num_agents = env.n
    num_targets = env.num_target
    max_steps = env.max_steps
    assert max_steps % args.A2C_steps == 0
    seg_num = int(max_steps/args.A2C_steps)
    if "MSMTC" in args.env:
        batch_size, num_agents, num_both, obs_dim = state.size()
    else:
        batch_size, num_agents, obs_dim, feature_dim = state.size()
    count = int(batch_size/max_steps)
    num_resources = int(obs_dim/(num_agents+1))

    if count != args.workers:
        print(count)
        
    # state, cam_state, reward, real_actions are to device only when being used
    if "MSMTC" in args.env:
        state = state.reshape(count, max_steps, num_agents, num_both, obs_dim)#.to(device_share)
        real_actions = real_actions.reshape(count, max_steps, num_agents, num_targets, 1)#.to(device_share)
    else:
        state = state.reshape(count, max_steps, num_agents, obs_dim, feature_dim)#.to(device_share)
        real_actions = real_actions.reshape(count, max_steps, num_agents, num_resources, 1)#.to(device_share)

    # batch_size, num_agents, num_agents, cam_dim = poses.size()
    # poses = poses.reshape(count, max_steps, num_agents, num_agents, cam_dim)#.to(device_share)
    batch_size, num_agents, r_dim = reward.size()
    reward = reward.reshape(count, max_steps, num_agents, r_dim)#.to(device_share)

    masks = masks.reshape(count, max_steps, num_agents, num_agents, 1)
    h_ToM = torch.zeros(count, num_agents, num_agents, args.lstm_out).to(device_share)
    
    hself = torch.zeros(count, num_agents, args.lstm_out ).to(device_share)
    hself_start = hself.clone().detach()  # save the intial hidden state for every args.num_steps
    hToM_start = h_ToM.clone().detach()
    if args.mask_actions:
        available_actions = available_actions.reshape(count, max_steps, num_agents, num_targets, -1)
    
    policy_loss_sum = torch.zeros(count, num_agents, num_targets, 1).to(device_share)
    value_loss_sum = torch.zeros(count, num_agents, 1).to(device_share)
    entropies_all = torch.zeros(1).to(device_share)
    Sparsity_loss_sum = torch.zeros(count, 1).to(device_share)

    for seg in range(seg_num): # loop for every args.A2C_steps
        for train_loop in range(args.policy_train_loops):
            hself = hself_start.clone().detach()
            h_ToM = hToM_start.clone().detach()
            values = []
            entropies = []
            log_probs = []
            rewards = []
            edge_logits = []
            for s_i in range(args.A2C_steps):
                step = s_i + seg * args.A2C_steps
                available_action = available_actions[:,step].to(device_share) if args.mask_actions else None
                
                if "ToM2C" in args.model:
                    value_multi, actions, entropy, log_prob, hn_self, hn_ToM, ToM_goal, edge_logit, comm_edges, probs, real_cover, ToM_target_cover =\
                            shared_model(state[:, step].to(device_share), hself, h_ToM, available_actions=available_action)
                    # value_multi, actions, entropy, log_prob, hn_self, hn_ToM, ToM_goal, edge_logit, comm_edges, probs, real_cover, ToM_target_cover =\
                    #         shared_model(state[:,step].to(device_share), hself, h_ToM, poses[:,step].to(device_share), masks[:,step].to(device_share), available_actions= available_action)
                    hself = hn_self
                    hToM = hn_ToM        
                
                values.append(value_multi)
                entropies.append(entropy)
                log_probs.append(torch.log(probs).gather(-1, real_actions[:,step].to(device_share)))
                rewards.append(reward[:,step].to(device_share))
                edge_logits.append(edge_logit)

            R = torch.zeros(count, num_agents, 1).to(device_share)
            if seg < seg_num -1:
                # not the last segment of the episode
                next_step = (seg+1) * args.A2C_steps
                available_action = available_actions[:,next_step].to(device_share) if args.mask_actions else None
                # value_multi, *others = shared_model(state[:,next_step].to(device_share), hself, h_ToM, poses[:,next_step].to(device_share), masks[:,next_step].to(device_share), available_actions= available_action)
                value_multi, *others = shared_model(state[:,next_step].to(device_share), hself, h_ToM, available_actions= available_action)
                R = value_multi.clone().detach()

            R = R.to(device_share)
            values.append(R)
            policy_loss = torch.zeros(count, num_agents, num_targets, 1).to(device_share)
            value_loss = torch.zeros(count, num_agents, 1).to(device_share)
            entropies_sum = torch.zeros(1).to(device_share)
            w_entropies = float(args.entropy)
            Sparsity_loss = torch.zeros(count, 1).to(device_share)
            criterionH = HLoss()
            edge_prior = torch.FloatTensor(np.array([0.7, 0.3])).to(device_share)
            gae = torch.zeros(count, num_agents, 1).to(device_share)

            for i in reversed(range(args.A2C_steps)):
                R = args.gamma * R + rewards[i]
                advantage = R - values[i]
                value_loss = value_loss + 0.5 * advantage.pow(2)
                # Generalized Advantage Estimataion
                delta_t = rewards[i] + args.gamma * values[i + 1].data - values[i].data
                gae = gae * args.gamma * args.tau + delta_t
                if "MSMTC" in args.env:
                    gae_duplicate = gae.unsqueeze(2).repeat(1,1,num_targets,1)
                    policy_loss = policy_loss - (w_entropies * entropies[i]) - (log_probs[i] * gae_duplicate)
                else:
                    gae_duplicate = gae
                    # if policy_loss.sum() == 0: policy_loss = torch.zeros(1).to(device_share)
                    policy_loss = policy_loss - (w_entropies * entropies[i].sum()) - (log_probs[i] * gae_duplicate).sum()
                
                entropies_sum += entropies[i].sum()
                edge_logit = edge_logits[i] #.reshape(count * num_agents * num_agents, -1)  # k * 2
                Sparsity_loss += -criterionH(edge_logit, edge_prior)
            
            shared_model.zero_grad()
            print(policy_loss)
            loss = policy_loss.sum() + 1e-4 * value_loss.sum() #+ 0.3 * Sparsity_loss.sum()
            loss = loss/(count * 4)
            loss.backward()

            torch.nn.utils.clip_grad_norm_(params, 5)
            optimizer_Policy.step()

        # update hself & hothers start for next segment
        hself_start = hself.clone().detach()
        hToM_start = h_ToM.clone().detach()
        # sum all the loss
        policy_loss_sum += policy_loss
        value_loss_sum += value_loss
        Sparsity_loss_sum += Sparsity_loss
        entropies_all += entropies_sum

    return policy_loss_sum, value_loss_sum, Sparsity_loss_sum, entropies_all, actions

def reduce_comm(policy_data, args, params_comm, optimizer, lr_scheduler, shared_model, ori_model, device_share, env):
    state, poses, real_actions, reward, comm_domains, available_actions = policy_data

    num_agents = env.n
    num_targets = env.num_target
    max_steps = env.max_steps
    assert max_steps % args.A2C_steps == 0

    if "MSMTC" in args.env:
        batch_size, num_agents, num_both, obs_dim = state.size()
    else:
        batch_size, num_agents, obs_dim = state.size()
    count = int(batch_size/max_steps)

    # state, cam_state, reward, real_actions are to device only when being used
    if "MSMTC" in args.env:
        state = state.reshape(count, max_steps, num_agents, num_both, obs_dim)#.to(device_share)
    else:
        state = state.reshape(count, max_steps, num_agents, obs_dim)#.to(device_share)

    batch_size, num_agents, num_agents, cam_dim = poses.size()
    poses = poses.reshape(count, max_steps, num_agents, num_agents, cam_dim)#.to(device_share)

    comm_domains = comm_domains.reshape(count, max_steps, num_agents, num_agents, 1)
    h_ToM = torch.zeros(count, num_agents, num_agents, args.lstm_out).to(device_share)
    hself = torch.zeros(count, num_agents, args.lstm_out ).to(device_share)
    if args.mask_actions:
        available_actions = available_actions.reshape(count, max_steps, num_agents, num_targets, -1)

    
    comm_loss_sum = torch.zeros(1).to(device_share)

    # sample_ids = [i for i in range(args.comm_train_loops * count)]
    # random.shuffle(sample_ids)
    # sample_ids = np.array(sample_ids) % count
    mini_batch_size = count

    #epoch_cnt = int(count * args.comm_train_loops / args.mini_batch_size)
    for epoch in range(1):
        #ids = sample_ids[epoch * mini_batch_size:(epoch+1)*mini_batch_size]
        
        h_ToM = torch.zeros(mini_batch_size, num_agents, num_agents, args.lstm_out).to(device_share)
        hself = torch.zeros(mini_batch_size, num_agents, args.lstm_out).to(device_share)

        comm_loss = torch.zeros(1).to(device_share)
        CE_criterion = nn.CrossEntropyLoss(reduction='mean')

        for step in range(max_steps):
            available_action = available_actions[:,step].to(device_share) if args.mask_actions else None

            hn_self, hn_ToM, edge_logit, curr_edges,_ , _= shared_model(state[:,step].to(device_share), hself, h_ToM,\
                 poses[:,step].to(device_share), comm_domains[:,step].to(device_share), available_actions= available_action, train_comm = args.train_comm)
            _, _, _, _, best_edges, edge_label= ori_model(state[:,step].to(device_share), hself.detach(), h_ToM.detach(),\
                 poses[:,step].to(device_share), comm_domains[:,step].to(device_share), available_actions= available_action, train_comm = args.train_comm)
            hself = hn_self
            hToM = hn_ToM        
            
            # idx = (best_edges == 1)
            # if curr_edges[idx].size()[0] > 0:
            #     print(torch.sum(1-curr_edges[idx])/curr_edges[idx].size()[0])
            # print(curr_edges.sum()/mini_batch_size)
            #print("------------")
            # print(edge_label)
            # print(edge_logit)
            #print(edge_logit.shape, edge_label.shape)
            edge_label = edge_label.detach()
            idx_0 = (edge_label == 0)
            idx_1 = (edge_label == 1)
            logit_0 = edge_logit[idx_0]
            logit_1 = edge_logit[idx_1]
            label_0 = edge_label[idx_0]
            label_1 = edge_label[idx_1]
            size_0 = label_0.size()[0]
            size_1 = label_1.size()[0]
            '''
            if size_0 > size_1:
                random_ids = [i for i in range(size_1)]
                random.shuffle(random_ids)
                random_ids = random_ids[:size_1]
                logit_0 = logit_0[random_ids]
                label_0 = label_0[random_ids]
            '''
            loss_0 = CE_criterion(logit_0, label_0.long()) if size_0 > 0 else 0
            loss_1 = CE_criterion(logit_1, label_1.long()) if size_1 > 0 else 0
            #print(CE_criterion(edge_logit,edge_label.long()), loss_0+loss_1)
            comm_loss +=  loss_0 + loss_1

        shared_model.zero_grad()
        comm_loss.backward()#retain_graph=True)
        torch.nn.utils.clip_grad_norm_(params_comm, 20)
        optimizer.step()
        lr_scheduler.step()
        comm_loss_sum += comm_loss    

    return comm_loss_sum

def load_data(args, history):
    history_list = []
    for rank in range(args.workers):
        history_list += history[rank]
    
    item_cnt = len(history_list[0])
    item_name = [item for item in history_list[0]]
    data_list = [[] for i in range(item_cnt)]

    for history in history_list:
        for i, item in enumerate(history):
            data_list[i].append(history[item])

    for i in range(item_cnt):
        data_list[i] = torch.from_numpy(np.array(data_list[i]))
        # data_list[i] = torch.stack(data_list[i])
        if 'reward' in item_name[i]:
            data_list[i] = data_list[i].unsqueeze(-1)

    return data_list

def train(args, shared_model, optimizer_Policy, optimizer_ToM, train_modes, n_iters, curr_env_steps, ToM_count, ToM_history, Policy_history, step_history, loss_history, env=None):
    rank = args.workers
    wandb.init(project='DRA', name='ToM2C-train')
    ptitle('Training')
    gpu_id = args.gpu_id[rank % len(args.gpu_id)]
    torch.manual_seed(args.seed + rank)
    env_name = args.env

    if gpu_id >= 0:
        torch.cuda.manual_seed(args.seed + rank)
        device = torch.device('cuda:' + str(gpu_id))
        if len(args.gpu_id) > 1:
            raise AssertionError("Do not support multi-gpu training")
            #device_share = torch.device('cpu')
        else:
            device_share = torch.device('cuda:' + str(args.gpu_id[-1]))
    else:
        device_share = torch.device('cpu')

    if env == None:
        env = create_env(env_name, args)

    params = []
    params_ToM = []
    params_comm = []
    for name, param in shared_model.named_parameters():
        if 'ToM' in name or 'other' in name:
            params_ToM.append(param)
        else:
            params.append(param)
        if 'graph' in name:
            params_comm.append(param)

    if args.train_comm:  # train communication in supervised way (communication reduction)
        optimizer_comm = SharedAdam(params_comm, lr=0.001, amsgrad=args.amsgrad)
        lr_scheduler = torch.optim.lr_scheduler.StepLR(optimizer_comm, step_size=20, gamma=0.1)
        ori_model = build_model(env, args, device_share)
        ori_model = ori_model.to(device_share)
        ori_state = torch.load(
            args.load_model_dir,
            map_location=lambda storage, loc: storage
        )
        ori_model.load_state_dict(ori_state['model'])
        ori_model.eval()    

    train_step_cnt = 0
    while True:  # wait for all workers to finish collecting trajectories
        t1 = time.time()
        while True:
            flag = True
            curr_time = time.time()
            if curr_time - t1 > 180:
                print("waiting too long for workers")
                print("train modes:", train_modes)
                return
            for rank in range(args.workers):
                if train_modes[rank] != -10:
                    flag = False    # some worker is still collecting trajectories
                    break
            if flag:
                break

        t2 = time.time()

        print("training start after waiting for {} seconds".format(t2-t1))
       
        if args.train_comm:
            data_list = load_data(args, Policy_history)
            comm_loss = reduce_comm(data_list, args, params_comm, optimizer_comm, lr_scheduler, shared_model, ori_model, device_share, env)
            wandb.log({'train/comm_loss': comm_loss.sum()}, step=sum(n_iters))
            print("comm_loss:", comm_loss.item())
            if comm_loss.sum() < 1:
                break
        else:
            train_step_cnt += 1
            # state, poses, real_actions, reward, masks, available_actions = load_data(args, Policy_history)
            state, real_actions, reward, masks, available_actions = load_data(args, Policy_history)

            # policy_loss, value_loss, Sparsity_loss, entropies_sum =\
            #     optimize_Policy(state, poses, real_actions, reward, masks, available_actions, args, params, optimizer_Policy, shared_model, device_share, env)
            policy_loss, value_loss, Sparsity_loss, entropies_sum, actions =\
                optimize_Policy(state, real_actions, reward, masks, available_actions, args, params, optimizer_Policy, shared_model, device_share, env)
            
            # log training information
            n_steps = sum(n_iters)  # global_steps_count
            wandb.log({'train/policy_loss_sum': policy_loss.sum()}, step=n_steps)
            wandb.log({'train/value_loss_sum': value_loss.sum()}, step=n_steps)
            wandb.log({'train/Sparsity_loss_sum': Sparsity_loss.sum()}, step=n_steps)
            wandb.log({'train/entropies_sum': entropies_sum.sum()}, step=n_steps)
            wandb.log({'train/gamma': args.gamma}, step=n_steps)
            
            print("policy loss:{}".format(policy_loss.sum().data))
            print("value loss:{}".format(value_loss.sum().data))
            print("entropies:{}".format(entropies_sum.sum().data))
            print("Policy training finished")
            print("---------------------")

            ToM_len = args.ToM_frozen * args.workers * env.max_steps
            if 'ToM2C' in args.model:
                if sum(ToM_count) >= ToM_len:
                    print("ToM training started")
                    state, masks, real_goals, available_actions = load_data(args, ToM_history)
                    print("ToM data loaded")
                    ToM_loss_sum, ToM_loss_avg, ToM_target_loss, ToM_target_acc = optimize_ToM(state, masks, available_actions, args, params_ToM, optimizer_ToM, shared_model, device_share, env)
                    print("optimized based on ToM loss")

                    wandb.log({'train/ToM_loss_sum': ToM_loss_sum.sum()}, step=n_steps)
                    wandb.log({'train/ToM_loss_avg': ToM_loss_avg.sum()}, step=n_steps)
                    wandb.log({'train/ToM_target_loss_avg': ToM_target_loss.sum()}, step=n_steps)
                    wandb.log({'train/ToM_target_acc_avg': ToM_target_acc.sum()}, step=n_steps)

                    for rank in range(args.workers):
                        ToM_history[rank] = []
                        ToM_count[rank] = 0
                    print("---------------------")

            if args.gamma_rate > 0:
                # add this one for schedule learning
                if n_steps >= args.start_eps * 20 * args.workers and args.gamma < args.gamma_final and train_step_cnt % (args.ToM_frozen) == 0:
                    if args.gamma > 0.4:
                        args.gamma = args.gamma * (1 + args.gamma_rate/2)
                    else:
                        args.gamma = args.gamma * (1 + args.gamma_rate)
                    if "MSMTC" in args.env:
                        new_env_step = int((args.gamma + 0.1)/0.2) * args.env_steps
                        env.max_steps = new_env_step
                        for rank in range(args.workers):
                            curr_env_steps[rank] = new_env_step

                print("gamma:", args.gamma)
                assert args.gamma < 0.95
        for rank in range(args.workers):
            Policy_history[rank] = []
            if train_modes[rank] == -100:
                return
            train_modes[rank] = -1

        if train_modes[0] == -100:
            env.close()
            break