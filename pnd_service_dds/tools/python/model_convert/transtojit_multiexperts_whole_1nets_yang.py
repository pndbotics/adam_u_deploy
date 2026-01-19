import argparse
from datetime import datetime

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
                        actor_hidden_dims=[512, 256, 128],
                        critic_hidden_dims=[512, 256, 128],
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
    
class actor_twoexperts(nn.Module): 
    def __init__(self,  walk_path):
        super(actor_twoexperts, self).__init__()
        
        self.net = actor_network(num_actor_obs=405,
                                    num_critic_obs=435, #435, 360
                                    num_actions=23,
                                    actor_hidden_dims=[512, 256, 256],
                                    critic_hidden_dims=[768, 256, 256],
                                    activation='elu',
                                    init_noise_std=1.0)
        path_walk = walk_path
        loaded_dict_walk = torch.load(path_walk, map_location=torch.device('cpu'))
        self.net.load_state_dict(loaded_dict_walk['model_state_dict'])
        
        

    def forward(self,obs):        
        obs_ = torch.clip(obs, -18.0, 18.0)
        actions = self.net.actor(obs_.detach())
        return actions      
    
  

class SonnyPolicy():
    def __init__(self, walk_path):
        
        self.rl_network = actor_twoexperts(walk_path)
        

    def transtojit(self, target_path):
        # 
        self.rl_network.to('cpu')
        obs = np.zeros(405)
        obs_1 = torch.tensor(obs, dtype=torch.float, device='cpu', requires_grad=False) 
        traced_script_module = torch.jit.trace(self.rl_network, obs_1.to("cpu"))
        traced_script_module.save(target_path)
        print ("****** target_path: ", target_path)

    
def main():
    parser = argparse.ArgumentParser(description="example: python transtojit_multiexperts_whole_1nets_yang.py -s model_stand.pt -w model_walk.pt -r model_run.pt -t adamlite")
    parser.add_argument('-w', '--source_walk_model_path', type=str, default="walk_amp_PRL_pndone_0201_8300.pt")
    parser.add_argument('-t', '--target_prefix', type=str, default="adamlite")
    args = parser.parse_args()
    
    
    if args.source_walk_model_path is None:
        print("no source walk model path")
        return
    
    now = datetime.now()
    year_last_two_digits = now.strftime("%y")
    month_day = now.strftime("%m%d")
    target_path = "source/" + args.target_prefix + "_" + year_last_two_digits + month_day + "_" + \
        args.source_walk_model_path.split(".")[0] + ".pt"
    
    h = SonnyPolicy(args.source_walk_model_path)
    h.transtojit(target_path)
    model = torch.jit.load(target_path)
    print(model)
    obs = np.zeros(405)
    obs_1 = torch.tensor(obs, dtype=torch.float, device='cpu', requires_grad=False) 
    
    print(obs_1.shape)
    a = time.time()
    output  = model.forward(obs_1)
    print(f"time:{time.time()- a}")
    print(output) 
        
        
if __name__ == '__main__':
    main()