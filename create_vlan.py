


import time
from netmiko import ConnectHandler, redispatch

def ask_str(prompt, allow_empty=False):
    while True:
        val = input(prompt)
        if not allow_empty and not val:
            print("Input cannot be empty.")
            continue
        return val

def ask_list(prompt):
    val = input(prompt)
    return [v.strip() for v in val.split(',') if v.strip()]

def ask_int(prompt, minval=None, maxval=None):
    while True:
        try:
            val = int(input(prompt))
            if (minval is not None and val < minval) or (maxval is not None and val > maxval):
                print(f"Value must be between {minval} and {maxval}.")
                continue
            return val
        except ValueError:
            print("Please enter a valid integer.")

print("--- VLAN Configuration Interactive ---\n")

# Jump host info
jump_host = {
    "device_type": "cisco_ios",
    "host": ask_str("Enter jump host IP (Edge Router): "),
    "username": ask_str("Enter jump host username: "),
    "password": ask_str("Enter jump host password: ")
}
print(f"Jumped to router {jump_host['host']}")

# Switches
switch_ips = ask_list("Enter switch IPs (comma separated): ")
switches = []
for ip in switch_ips:
    username = ask_str(f"Enter username for switch {ip}: ")
    password = ask_str(f"Enter password for switch {ip}: ")
    switches.append({"host": ip, "username": username, "password": password, "svis": {}})
print(f"Configured switches: {', '.join(switch_ips)}")

# VLANs
num_vlans = ask_int("How many VLANs to add? ", 1)
vlans = []
for i in range(num_vlans):
    vlan_id = ask_int(f"Enter VLAN ID #{i+1}: ")
    vlan_name = ask_str(f"Enter VLAN name for VLAN {vlan_id} (leave blank for default): ", allow_empty=True)
    vlans.append({"id": vlan_id, "name": vlan_name if vlan_name else f"AUTO_VLAN_{vlan_id}"})
print(f"Added VLANs: {', '.join(str(v['id']) for v in vlans)}")

# SVI for each switch and VLAN
for sw in switches:
    for vlan in vlans:
        ip = ask_str(f"Enter SVI IP for VLAN {vlan['id']} on switch {sw['host']}: ")
        mask = ask_str(f"Enter subnet mask for VLAN {vlan['id']} on switch {sw['host']} (e.g. 255.255.255.0 or /24): ")
        if mask.startswith("/"):
            mask = "255.255.255.0" if mask == "/24" else mask
        sw["svis"][vlan['id']] = {"ip": ip, "mask": mask}
print("Added SVI for VLANs with masks")

# Configure and show VLANs
for sw in switches:
    print(f"\nConnecting to switch {sw['host']} via jump host...")
    try:
        net_connect = ConnectHandler(**jump_host)
        print(f"    Connected to Jump Host: {net_connect.find_prompt()}")
        ssh_cmd = f"ssh -l {sw['username']} {sw['host']}"
        print(f"    Jumping to switch: {ssh_cmd}")
        net_connect.write_channel(f"{ssh_cmd}\n")
        time.sleep(3)
        output = net_connect.read_channel()
        if "password:" in output.lower():
            net_connect.write_channel(f"{sw['password']}\n")
            time.sleep(3)
        else:
            print("    ! Did not see password prompt, check SSH config on Edge Router.")
        redispatch(net_connect, device_type="cisco_ios")
        print(f"    Successfully landed on: {net_connect.find_prompt()}")
        net_connect.enable()
        config_commands = []
        for vlan in vlans:
            config_commands.append(f"vlan {vlan['id']}")
            config_commands.append(f"name {vlan['name']}")
            config_commands.append("exit")
            config_commands.append(f"interface vlan {vlan['id']}")
            svi = sw['svis'][vlan['id']]
            config_commands.append(f"ip address {svi['ip']} {svi['mask']}")
            config_commands.append("no shutdown")
            config_commands.append("exit")
            print(f"    > Prepared VLAN {vlan['id']} (IP: {svi['ip']} Mask: {svi['mask']})")
        print("    Pushing configuration...")
        net_connect.send_config_set(config_commands)
        net_connect.save_config()
        print("    Configuration saved.")
        print("\nVLAN Table for device:")
        vlan_output = net_connect.send_command("show vlan-switch brief")
        ip_output = net_connect.send_command("show ip int brief")

        # Parse VLAN info
        vlan_lines = vlan_output.splitlines()
        vlan_table = []
        for line in vlan_lines:
            parts = line.split()
            if len(parts) >= 2 and parts[0].isdigit():
                vlan_id = int(parts[0])
                name = parts[1]
                status = parts[2] if len(parts) > 2 else ""
                ports = " ".join(parts[3:]) if len(parts) > 3 else ""
                vlan_table.append({"id": vlan_id, "name": name, "status": status, "ports": ports})

        # Parse IP info for VLANs
        ip_lines = ip_output.splitlines()
        vlan_ip_map = {}
        for line in ip_lines:
            parts = line.split()
            if len(parts) >= 6 and parts[0].startswith("Vlan"):
                try:
                    vlan_id = int(parts[0][4:])
                except:
                    continue
                ip_addr = parts[1]
                vlan_ip_map[vlan_id] = ip_addr

        # Display table
        print(f"{'VLAN':<6}{'Name':<20}{'Status':<10}{'IP':<18}{'Ports'}")
        print("-"*70)
        for entry in vlan_table:
            ip = vlan_ip_map.get(entry['id'], "-")
            print(f"{entry['id']:<6}{entry['name']:<20}{entry['status']:<10}{ip:<18}{entry['ports']}")
        net_connect.disconnect()
        print("    Disconnected.\n")
    except Exception as e:
        print(f"    [!] Failure on {sw['host']}: {e}\n")

print("--- All Tasks Completed ---")