import json
from netmiko import ConnectHandler

def generate_ospf_configs(data):
    """
    Builds the CLI commands to enable OSPF on specific interfaces.
    """
    commands = []
    
    commands.append(f”router ospf {data[‘ospf’][‘process_id’]}”)
    # Iterate through the defined interfaces to enable OSPF directly
    for intf in data['ospf']['interfaces']:
        commands.append(f"interface {intf}")
        # Enable OSPFv2 (Requirement 3b) 
        commands.append(f" ip ospf {data['ospf']['process_id']} area {data['ospf']['area']}")
    
    return commands

def run_cr_automation():
    # Load the JSON data
    with open('cr_config.json') as f:
        data = json.load(f)

    # Define the device connection parameters
    device = {
        "device_type": "cisco_ios",
        "host": data["ip"],
        "username": "cisco",
        "password": "cisco",
    }

    # Generate the command set
    config_set = generate_ospf_configs(data)

    try:
        # Establish SSH connection using Netmiko [cite: 14]
        with ConnectHandler(**device) as net_connect:
            print(f"Automating OSPF configuration on {data['hostname']}...")
            output = net_connect.send_config_set(config_set)
            print(output)
            
            # Save the configuration to NVRAM
            net_connect.save_config()
            print("Successfully standardized OSPF deployment.")
            
    except Exception as e:
        print(f"Failed to automate {data['hostname']}: {e}")

if __name__ == "__main__":
    run_cr_automation()
