# from inspect import trace
# from tkinter import _TraceMode
import numpy as np
import torch
import torch.nn as nn
import time

STAND_PT_PATH = "pndnew_stand_10000.pt"
WALK_PT_PATH = "pndnew_walk_7700.pt"
TARGET_PT_PATH = "source/adam_2net_stand_walk_libtorch_20240222.pt"

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
    def __init__(self):
        super(actor_twoexperts, self).__init__()
        self.net1 = actor_network(num_actor_obs=91,
                                    num_critic_obs=91,
                                    num_actions=23,
                                    actor_hidden_dims=[512, 256, 256],
                                    critic_hidden_dims=[512, 256, 256],
                                    activation='elu',
                                    init_noise_std=1.0)
        path_stand = STAND_PT_PATH
        loaded_dict_stand = torch.load(path_stand, map_location=torch.device('cpu'))
        self.net1.load_state_dict(loaded_dict_stand['model_state_dict'])
        self.net2 = actor_network(num_actor_obs=91,
                                    num_critic_obs=91,
                                    num_actions=23,
                                    actor_hidden_dims=[512, 256, 256],
                                    critic_hidden_dims=[512, 256, 256],
                                    activation='elu',
                                    init_noise_std=1.0)
        path_standrecover = WALK_PT_PATH
        loaded_dict_standrecover = torch.load(path_standrecover, map_location=torch.device('cpu'))
        self.net2.load_state_dict(loaded_dict_standrecover['model_state_dict'])
        
        

    def forward(self,obs):
        # obs_1 = torch.tensor(obs, dtype=torch.float, device='cpu', requires_grad=False)
        
        obs_2 = torch.clip(obs, -100.0, 100.0)
        obs_1 = torch.clip(obs, -100.0, 100.0)
        
        actions1 = self.net1.actor(obs_1.detach())
        actions2 = self.net2.actor(obs_2.detach())
       
        return torch.cat((actions1, actions2),dim=0)      
    
  

class SonnyPolicy():
    def __init__(self):
        
        self.rl_network = actor_twoexperts()
        

    def transtojit(self):
        # 
        self.rl_network.to('cpu')
        # self.rl_network_stand.to('cpu')
        # self.rl_network_hop.to('cpu')
        # self.rl_network_run.eval()
        obs = np.zeros(91)
        obs_1 = torch.tensor(obs, dtype=torch.float, device='cpu', requires_grad=False)   
        traced_script_module = torch.jit.trace(self.rl_network,obs_1.to("cpu"))
        # traced_script_module = torch.jit.script(self.rl_network_run)
        traced_script_module.save(TARGET_PT_PATH)
        # traced_script_module.save("hop_noturn.pt")

    
def main():
    h = SonnyPolicy()
    h.transtojit()
    # model = torch.jit.load("./run.pt")
    model = torch.jit.load(TARGET_PT_PATH)
    print(model)
    obs = np.zeros(91)
    obs_1 = torch.tensor(obs, dtype=torch.float, device='cpu', requires_grad=False) 
    print(obs_1.shape)
    a = time.time()
    output  = model.forward(obs_1)
    print(f"time:{time.time()- a}")
    print(output) 
    # print(output2) 

    # output2 = model.net2.forward(obs_1)
    # print(f"time:{time.time()- a}")
    # print(output2)  
        
        
if __name__ == '__main__':
    main()