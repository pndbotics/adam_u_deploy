import json
import os


class SetPartZero():
    def __init__(self) -> None:
        self.set_zero_name = {}
        self.targat_value = {}
        self.targat_value_motor = {}
        self.pin_count = 4

    def read_targat_name(self):
        try:
            with open('encoder_name.json','r') as f:
                all_name = json.load(f)
        except FileNotFoundError:
            print("The encoder name file was not found.")
            exit(1)
        except json.JSONDecodeError:
            print("Error decoding encoder name JSON file.")
            exit(1)

        for k,v in all_name.items():
            if v['set_zero'] == 1:
                self.set_zero_name[k] = v['ip']
        print(f'"Set name {self.set_zero_name}')

        if len(self.set_zero_name) > self.pin_count:
            print(f'You are about to set up {len(self.set_zero_name)} encoders, but the maximum allowed is 4.')
            print('Please check the configuration info.')
            exit(1)
        if not self.set_zero_name:
            print(f'encoder is none')
            print('Please check the configuration info.')
            exit(1)

    def read_targat_value(self):
        try:
            with open('source/abs.json','r') as f:
                all_abs = json.load(f)
        except FileNotFoundError:
            print("The abs pos file was not found.")
            exit(1)
        except json.JSONDecodeError:
            print("Error decoding abs pos JSON file.")
            exit(1)

        for k,v in self.set_zero_name.items():
            self.targat_value[k] = all_abs[v]['radian']
            if 'motor_rotor_abs_pos' in all_abs[v]:
                self.targat_value_motor[k] = all_abs[v]['motor_rotor_abs_pos']

    def set_encoder_zero(self):
        joint_config_path_out = "/root/.adam/"
        if not os.path.exists(joint_config_path_out):
            os.makedirs(joint_config_path_out)
        joint_config_path_out += "joint_abs_config.json"
        try:
            with open(joint_config_path_out,'r') as f:
                targat_abs = json.load(f)
        except FileNotFoundError:
            print("The targat pos file was not found.")
            exit(1)
        except json.JSONDecodeError:
            print("Error decoding targat pos JSON file.")
            exit(1)
        for k,v in self.targat_value.items():
            targat_abs[k]['absolute_pos_zero'] = v
        if self.targat_value_motor:
            for k,v in self.targat_value_motor.items():
                targat_abs[k]['motor_rotor_abs_pos'] = v

        try:
            with open(joint_config_path_out, 'w') as file:
                json.dump(targat_abs, file, indent=4)
                print("Set zero sucess.") 
        except Exception as e:
            print("An error occurred while writing to the file:", e)

        
    def main(self):
        self.read_targat_name()
        self.read_targat_value()
        self.set_encoder_zero()


if __name__ == '__main__':
    set_zero = SetPartZero()
    set_zero.main()
