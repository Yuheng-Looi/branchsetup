import json
from netmiko import ConnectHandler

def generate_er_configs(data):
    commands = []
    
    # 1. Infrastructure Protection ACL (G3/0 IN) - Requirement 3c
    commands.append("ip access-list extended EDGE_INBOUND")
    commands.append(" remark Anti-Spoofing & RFC 1918 Protection")
    commands.append(" deny ip host 0.0.0.0 any")
    commands.append(" deny ip 127.0.0.0 0.255.255.255 any")
    commands.append(" deny ip 192.168.0.0 0.0.255.255 any")
    commands.append(" remark Permit VPN Traffic (ISAKMP & ESP)")
    commands.append(" permit udp any any eq 500")
    commands.append(" permit esp any any")
    commands.append(" remark Permit Operational Traffic")
    commands.append(" permit icmp any any echo-reply")
    commands.append(" permit tcp any any established")
    commands.append(" deny ip any any")

    # 2. NAT/PAT Configuration - Requirement 19
    commands.append("ip access-list extended NAT_ACL")
    for net in data['nat']['source_networks']:
        commands.append(f" permit ip {net} any")
    
    # Static global IP PAT (Requirement 19)
    commands.append(f"ip nat inside source list NAT_ACL interface {data['nat']['outside_interface']} overload")
    
    # 3. Apply ACL and NAT to Interfaces
    commands.append(f"interface {data['nat']['outside_interface']}")
    commands.append(" ip nat outside")
    commands.append(" ip access-group EDGE_INBOUND in")
    
    commands.append(f"interface {data['nat']['inside_interface']}")
    commands.append(" ip nat inside")

    # 4. OSPF Interface-Level Configuration - Requirement 17
    for intf in data['ospf']['interfaces']:
        commands.append(f"interface {intf}")
        commands.append(f" ip ospf {data['ospf']['process_id']} area {data['ospf']['area']}")

    return commands

def run_er_automation():
    with open('er_config.json') as f:
        data = json.load(f)

    device = {
        "device_type": "cisco_ios",
        "host": data["ip"],
        "username": "cisco",
        "password": "cisco",
    }

    config_set = generate_er_configs(data)

    try:
        with ConnectHandler(**device) as net_connect:
            print(f"Applying ACL, NAT, and OSPF to {data['hostname']}...")
            output = net_connect.send_config_set(config_set)
            print(output)
            net_connect.save_config()
            print("Configuration complete.")
    except Exception as e:
        print(f"Connection error: {e}")

if __name__ == "__main__":
    run_er_automation()
