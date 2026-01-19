import numpy as np
import torch
import torch.nn as nn
import time

# Velocity Supervised Network
class VelNet(nn.Module):
    def __init__(self):
        super(VelNet, self).__init__()

        activation = nn.ELU()
        # Define a 3-layer fully connected network for velocity supervision
        vel_supervised_net = [nn.Linear(5*75, 256), activation, 
                              nn.Linear(256, 128), activation, 
                              nn.Linear(128, 3)]
        self.vel_supervised_net = nn.Sequential(*vel_supervised_net)

    def forward(self, obs):
        obs = torch.clip(obs, -100.0, 100.0)
        vel = self.vel_supervised_net(obs.detach())
        return vel

class PolicyNetwork(nn.Module):
    def __init__(self, num_actor_obs, actor_hidden_dims, num_actions, activation):
        super(PolicyNetwork, self).__init__()
        self.actor_layers = [nn.Linear(num_actor_obs, actor_hidden_dims[0]), activation]
        for l in range(len(actor_hidden_dims)):
            if l == len(actor_hidden_dims) - 1:
                self.actor_layers.append(nn.Linear(actor_hidden_dims[l], num_actions))
            else:
                self.actor_layers.append(nn.Linear(actor_hidden_dims[l], actor_hidden_dims[l + 1]))
                self.actor_layers.append(activation)
        self.actor = nn.Sequential(*self.actor_layers)

    def forward(self, obs):
        return self.actor(obs)
        
# Policy Network
class PolicyNet(nn.Module):
    def __init__(self,  num_actor_obs, num_critic_obs, num_actions,
                 actor_hidden_dims=[512, 256, 128], critic_hidden_dims=[512, 256, 128],
                 activation='elu', init_noise_std=1.0, **kwargs):
        if kwargs:
            print("Unexpected arguments in ActorCritic.__init__, which will be ignored: " + str([key for key in kwargs.keys()]))
        super(PolicyNet, self).__init__()
        
        activation = nn.ELU()

        # Velocity estimation network
        self.vel_supervised_net = VelNet()
        # Load weights
        path_vel_net = '/home/ps/workspace/Jony/202308/vel_controlnet/pnd_humanoid_robot_private_imitation/pnd_humanoid_robot/legged_gym/logs/pnd_humanoid_v3_amp/Sep02_17-23-40_/model_8000.pt'
        loaded_dict_vel_net = torch.load(path_vel_net, map_location=torch.device('cpu'))
        # Load only the required layers' parameters and ignore the rest
        model_dict = self.vel_supervised_net.state_dict()
        pretrained_dict = {}
        for k, v in loaded_dict_vel_net['model_state_dict'].items():
            print(f"Key: {k}")
            if k in model_dict:
                print(f"Key {k} is in the loaded weights.")
                pretrained_dict[k] = v
            else:
                print(f"Key {k} is not in the loaded weights.")
        model_dict.update(pretrained_dict) 
        self.vel_supervised_net.load_state_dict(model_dict)


        self.actor = PolicyNetwork(num_actor_obs, actor_hidden_dims, num_actions, activation)
        actor_model_dict = self.actor.state_dict()
        # Load weights
        path_policy_net = '/home/ps/workspace/Jony/202308/vel_controlnet/pnd_humanoid_robot_private_imitation/pnd_humanoid_robot/legged_gym/logs/pnd_humanoid_v3_amp/Sep02_17-23-40_/model_8000.pt'
        loaded_dict_policy = torch.load(path_policy_net, map_location=torch.device('cpu'))
        # Load only the required layers' parameters and ignore the rest
        actor_pretrained_dict = {}
        for k, v in loaded_dict_policy['model_state_dict'].items():
            print(f"Key: {k}")
            if k in actor_model_dict:
                print(f"Key {k} is in the loaded weights.")
                actor_pretrained_dict[k] = v
            else:
                print(f"Key {k} is not in the loaded weights.")
        actor_model_dict.update(actor_pretrained_dict) 
        self.actor.load_state_dict(actor_model_dict)

    def act_inference(self, observations, history_obs):
        # Information from the last 5 frames
        history_obs = history_obs.view(-1, 5, 91)
        # Inputs needed for velocity network estimation from the last 5 frames
        vel_input = torch.cat((history_obs[...,3:9], history_obs[...,12:81]), dim=-1)
        vel_prediction = self.vel_supervised_net(vel_input.view(history_obs.size(0), -1))
        actions = self.actor(torch.cat((vel_prediction.squeeze(0), observations[3:]), dim=0))
        return actions, vel_prediction

    def forward(self, observations, history_obs):
        observations = torch.clip(observations, -100.0, 100.0)
        history_obs = torch.clip(history_obs, -100.0, 100.0)
        actions, vel_prediction = self.act_inference(observations.detach(), history_obs.detach())
        return actions

  
policy_net_ = PolicyNet(num_actor_obs=91,
                       num_critic_obs=91,
                       num_actions=23,
                       actor_hidden_dims=[512, 256, 256],
                       critic_hidden_dims=[512, 256, 256],
                       activation='elu',
                       init_noise_std=1.0)

class TestProgram():
    def __init__(self, policy_net):
        self.policy_net = policy_net
        
    def convert_to_traced_script_module(self):
        self.policy_net.to('cpu')
        obs = torch.zeros(91)
        history_obs = torch.zeros(91*5)
        obs_1 = torch.tensor(obs, dtype=torch.float, device='cpu', requires_grad=False)
        history_obs_1 = torch.tensor(history_obs, dtype=torch.float, device='cpu', requires_grad=False)
        traced_script_module = torch.jit.trace(self.policy_net, (obs_1.to("cpu"), history_obs_1.to('cpu')))
        traced_script_module.save("./traced_script_module.pt")
        return traced_script_module

test_program = TestProgram(policy_net_)
traced_script_module = test_program.convert_to_traced_script_module()


def main():
    # Load the traced script module
    model = torch.jit.load("./traced_script_module.pt")
    print(model)

    # Create dummy inputs for the model
    obs = torch.zeros(91)
    history_obs = torch.zeros(91*5)

    # Convert inputs to tensors
    obs_1 = torch.tensor(obs, dtype=torch.float, device='cpu', requires_grad=False)
    history_obs_1 = torch.tensor(history_obs, dtype=torch.float, device='cpu', requires_grad=False)

    # Run the model with the dummy inputs
    output = model(obs_1, history_obs_1)

    # Print the output
    print(output)

if __name__ == '__main__':
    main()
