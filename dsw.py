import json
from netmiko import ConnectHandler

def generate_configs(switch_data):
    """
    Logic to iterate through JSON and build CLI commands dynamically.
    """
    commands = []
    
    # 1. Iterate through VLANs if they exist
    if "vlans" in switch_data:
        for vlan in switch_data["vlans"]:
            commands.append(f"vlan {vlan['id']}")
            commands.append(f" name {vlan['name']}")

    # 2. Iterate through Interface VLANs (SVIs) if they exist
    if "interface_vlans" in switch_data:
        for svi in switch_data["interface_vlans"]:
            commands.append(f"interface Vlan{svi['id']}")
            commands.append(f" ip address {svi['ip']} {svi['mask']}")
            commands.append(" no shutdown")

    # 3. Handle physical interfaces (Access or Trunk)
    if "interfaces" in switch_data:
        for intf in switch_data["interfaces"]:
            commands.append(f"interface {intf['name']}")
            if intf["type"] == "trunk":
                commands.append(" switchport trunk encapsulation dot1q")
                commands.append(" switchport mode trunk")
            elif intf["type"] == "access":
                commands.append(f" switchport mode access")
                commands.append(f" switchport access vlan {intf['vlan']}")

    # 4. Handle EtherChannels if they exist
    if "etherchannels" in switch_data:
        for ec in switch_data["etherchannels"]:
            for member in ec["members"]:
                commands.append(f"interface {member}")
                commands.append(f" channel-group {ec['group']} mode {ec['mode']}")
            commands.append(f"interface Port-channel{ec['group']}")
            commands.append(" switchport mode trunk")

   # 5. Handle OSPF if exist
   if “ospf” in switch_data:
       for ospf_entry in switch_data[“ospf”]
            commands.append(f”interface {ospf_entry[interface]}”)
            commands.append(f”ip ospf {ospf_entry[process]} area {ospf_entry[area]}”)


    return commands

def run_automation():
    with open('network_config.json') as f:
        config_data = json.load(f)

    for switch in config_data["switches"]:
        print(f"\n--- Processing {switch['hostname']} ({switch['ip']}) ---")
        
        # Generate the specific command list for THIS switch
        config_set = generate_configs(switch)
        
        if not config_set:
            print(f"No specific configuration found for {switch['hostname']}. Skipping.")
            continue

        # Establish Netmiko connection
        device_params = {
            "device_type": "cisco_ios",
            "host": switch["ip"],
            "username": "cisco",  # Standard practice for your lab
            "password": "cisco",
            "secret": "cisco"
        }

        try:
            with ConnectHandler(**device_params) as net_connect:
                net_connect.enable()
                print(f"Applying {len(config_set)} commands...")
                output = net_connect.send_config_set(config_set)
                print(output)
                print(f"Successfully configured {switch['hostname']}.")
        except Exception as e:
            print(f"Failed to connect to {switch['hostname']}: {e}")

if __name__ == "__main__":
    run_automation()



