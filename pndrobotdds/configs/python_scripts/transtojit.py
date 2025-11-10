"""_summary_"""
import os
import argparse

# from inspect import trace
# from tkinter import _TraceMode
import numpy as np
import torch
import torch.nn as nn
import time

class  actor_network(nn.Module):
    def __init__(self,  num_actor_obs,
                 num_critic_obs,
                 num_actions,
                 actor_hidden_dims=[512, 256, 256],
                 critic_hidden_dims=[512, 256, 256],
                 activation='elu',
                 init_noise_std=1.0,
                 **kwargs):
        if kwargs:
            print("ActorCritic.__init__ got unexpected arguments, which will be ignored: " + str([key for key in kwargs.keys()]))
        super(actor_network, self).__init__()

        activation = get_activation(activation)

        mlp_input_dim_a = num_actor_obs
        mlp_input_dim_c = num_critic_obs

        # Policy
        actor_layers = []
        actor_layers.append(nn.Linear(mlp_input_dim_a, actor_hidden_dims[0]))
        actor_layers.append(activation)
        for l in range(len(actor_hidden_dims)):
            if l == len(actor_hidden_dims) - 1:
                actor_layers.append(nn.Linear(actor_hidden_dims[l], num_actions))
            else:
                actor_layers.append(nn.Linear(actor_hidden_dims[l], actor_hidden_dims[l + 1]))
                actor_layers.append(activation)
        self.actor = nn.Sequential(*actor_layers)

        # Value function
        critic_layers = []
        critic_layers.append(nn.Linear(mlp_input_dim_c, critic_hidden_dims[0]))
        critic_layers.append(activation)
        for l in range(len(critic_hidden_dims)):
            if l == len(critic_hidden_dims) - 1:
                critic_layers.append(nn.Linear(critic_hidden_dims[l], 1))
            else:
                critic_layers.append(nn.Linear(critic_hidden_dims[l], critic_hidden_dims[l + 1]))
                critic_layers.append(activation)
        self.critic = nn.Sequential(*critic_layers)

        print(f"Actor MLP: {self.actor}")
        print(f"Critic MLP: {self.critic}")
        self.std = nn.Parameter(init_noise_std * torch.ones(num_actions))
    def act_inference(self, observations):
        actions_mean = self.actor(observations)
        return actions_mean
    def forward(self,obs):
        # obs_1 = torch.tensor(obs, dtype=torch.float, device='cpu', requires_grad=False)
        obs_2 = torch.clip(obs, -100.0, 100.0)

        actions = self.act_inference(obs_2.detach())
        return actions.detach()


def get_activation(act_name):
    if act_name == "elu":
        return nn.ELU()
    elif act_name == "selu":
        return nn.SELU()
    elif act_name == "relu":
        return nn.ReLU()
    elif act_name == "crelu":
        return nn.ReLU()
    elif act_name == "lrelu":
        return nn.LeakyReLU()
    elif act_name == "tanh":
        return nn.Tanh()
    elif act_name == "sigmoid":
        return nn.Sigmoid()
    else:
        print("invalid activation function!")
        return None


class SonnyPolicy():
    def __init__(self, source_pt_path, obs_number):
        self.num_actor_obs = obs_number
        self.num_critic_obs = obs_number
        self.num_actions = 23
        self.actor_hidden_dim = [512,256,256]
        self.critic_hidden_dim = [512,256,256]
        self.activation = 'elu'
        self.init_noise_std = 1.0
        self.rl_network_walk = actor_network(self.num_actor_obs,
                                             self.num_critic_obs,
                                             self.num_actions,
                                             self.actor_hidden_dim,
                                             self.critic_hidden_dim,
                                             self.activation,
                                             self.init_noise_std)
        # path = '/home/hgone/Documents/Python/ETH-ISSAC/legged_gym/logs/rough_sonny/8月19_00-12-59_/model_4000.pt'
        # path = '/home/hgone/Documents/Python/ETH-ISSAC/legged_gym/logs/rough_sonny/8月21_19-25-59_/model_1800.pt'
        # path = '/home/hgone/Documents/Python/ETH-ISSAC/legged_gym/logs/rough_sonny/8月21_22-10-09_/model_4000.pt'
        # path = '/home/hgone/Documents/Python/ETH-ISSAC/legged_gym/logs/rough_sonny/8月22_13-38-38_/model_8000.pt'#walk

        # path = '/home/hgone/Documents/Python/ETH-ISSAC/legged_gym/logs/rough_sonny/8月25_08-40-14_/model_7800.pt'
        # path_stand = './model_stand_noturn_v1.pt' #stand
        # path_walk = '/home/hgone/Documents/Python/ETH-ISSAC/legged_gym/logs/rough_sonny/8月25_22-19-39_/model_12000.pt'#walk
        # path_walk = '/home/hgone/Documents/Python/ETH-ISSAC/legged_gym/logs/rough_sonny/8月31_19-07-03_/model_16000.pt' #walk
        # path_walk = '/home/hgone/Documents/Python/ETH-ISSAC/legged_gym/logs/rough_sonny/9月01_13-12-42_/model_20000.pt' #walk_newmass
        # path_walk = '/home/hgone/Documents/Python/ETH-ISSAC/legged_gym/logs/rough_sonny/9月07_10-23-10_/model_2800.pt' #walk_newmass:humanlike
        # path_walk = './walk_amp_PRL_pndone_0116_9600.pt' #walk_newmass
        path_walk = source_pt_path
        # path_run = '/home/hgone/Documents/Python/ETH-ISSAC/legged_gym/logs/rough_sonny/Aug24_13/model_700.pt' #run
        # path_run = './model_run_turn_new.pt' #runnewmass
        # path_hop = '/home/hgone/Documents/Python/ETH-ISSAC/legged_gym/logs/rough_sonny/Aug24_23-49-56_/model_2000.pt' #hop
        # path_hop = './model_hop_noturn.pt' #hop
        print("path: ")
        # print(path_stand)
        print(path_walk)
        # print(path_run)
        # print(path_hop)
        loaded_dict_walk = torch.load(path_walk, map_location=torch.device('cpu'))
        # loaded_dict_hop = torch.load(path_hop, map_location=torch.device('cpu'))
        # loaded_dict_run = torch.load(path_run, map_location=torch.device('cpu'))
        # loaded_dict_stand = torch.load(path_stand, map_location=torch.device('cpu'))
        print(loaded_dict_walk)
        print("loaded dict ready!")
        self.rl_network_walk.load_state_dict(loaded_dict_walk['model_state_dict'])
        print(self.rl_network_walk)
        # self.rl_network_hop.load_state_dict(loaded_dict_hop['model_state_dict'])
        # self.rl_network_run.load_state_dict(loaded_dict_run['model_state_dict'])
        # self.rl_network_stand.load_state_dict(loaded_dict_stand['model_state_dict'])
        print("2!")
        self.obs_scales_lin_vel = 2.0
        self.obs_scales_ang_vel = 0.25
        self.command_scales = [self.obs_scales_lin_vel, self.obs_scales_lin_vel, self.obs_scales_ang_vel];
        self.obs_scales_dof_pos = 1.0
        self.obs_scales_dof_vel = 0.05
        self.default_dof_pos = np.zeros(23)
        self.default_dof_pos = [0.0,0.0,-0.5236,1.0472,-0.5236,-0.0,
                                -0.0,0.0,-0.5236,1.0472,-0.5236,-0.0,
                                0.0,0.0,0.0,
                                0.0,0.3,0.0,-0.3,
                                0.0,-0.3,0.0,0.3]
        self.action_last = np.zeros(23)
        self.height_scales = 5.0
        # Action noise
        # env_cfg, train_cfg = task_registry.get_cfgs(name="sonny")
        # env_cfg.env.num_envs = min(env_cfg.env.num_envs, 1)
        # env_cfg.env.num_actions = 12
        # env_cfg.env.num_observations = 169
        # env_cfg.noise.add_noise = False

        # env = task_registry.make_sonny_env(name="sonny",env_cfg=env_cfg, physics_engine=gymapi.SIM_PHYSX,sim_device='cpu')

        # train_cfg.runner.resume = True
        # train_cfg.runner.load_run = "7月25_14-06-09_"
        # train_cfg.runner.checkpoint = -1
        # ppo_runner, train_cfg = task_registry.make_alg_runner(env=env,name="sonny",train_cfg=train_cfg)
        # self.policy = ppo_runner.get_inference_policy(device="cpu")
        print("init trained PPO model")

    def transtojit(self, target_pt_path):
        #
        self.rl_network_walk.to('cpu')
        # self.rl_network_stand.to('cpu')
        # self.rl_network_hop.to('cpu')
        # self.rl_network_run.eval()
        obs = np.zeros(self.num_actor_obs)
        obs_1 = torch.tensor(obs, dtype=torch.float, device='cpu', requires_grad=False)
        traced_script_module = torch.jit.trace(self.rl_network_walk,obs_1.to("cpu"))
        # traced_script_module = torch.jit.script(self.rl_network_run)
        traced_script_module.save(target_pt_path)
        # traced_script_module.save("hop_noturn.pt")

def trans_pt_dir(pt_dir):
    for dir_path, dir_names, filenames in os.walk(pt_dir):
        for filename in filenames:
            if filename.endswith(".pt"):
                src_pt_path = os.path.join(dir_path, filename)
                target_pt_path = os.path.join(dir_path, "jit_" + filename)
                h = SonnyPolicy(source_pt_path=src_pt_path)
                h.transtojit(target_pt_path)
                

def main():
    parser = argparse.ArgumentParser(description="example: python transtojit.py -s model.pt -t source/jit_model.pt")
    parser.add_argument('-s', '--source_model_path', type=str, default=None)
    parser.add_argument('-t', '--target_model_path', type=str, default=None)
    parser.add_argument('-d', '--source_model_dir', type=str, default=None)
    parser.add_argument('-n', '--obs_number', type=int, default=91)
    args = parser.parse_args()
    if args.source_model_dir is not None:
        trans_pt_dir(args.source_model_dir)
        return
    if args.source_model_path is None:
        print("no source model path")
        return
    if args.target_model_path is None:
        print("no target model path")
        return
    
    h = SonnyPolicy(source_pt_path=args.source_model_path, obs_number=args.obs_number)
    h.transtojit(args.target_model_path)
    model = torch.jit.load(args.target_model_path)
    print(model)
    obs = np.zeros(args.obs_number)
    obs_1 = torch.tensor(obs, dtype=torch.float, device='cpu', requires_grad=False)
    print(obs_1.shape)
    a = time.time()
    output = model.forward(obs_1)
    print(f"time:{time.time()- a}")
    print(output)


if __name__ == '__main__':
    main()