


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

import time
import json
from netmiko import ConnectHandler, redispatch

print("--- VLAN Configuration (Automated) ---\n")

# Load VLAN and switch data from vlan_data.json
with open("vlan_data.json", "r") as f:
    vlan_data = json.load(f)

# Jump host info
jump_host = {
    "device_type": "cisco_ios",
    "host": vlan_data["branch"],
    "username": vlan_data["username"],
    "password": vlan_data["password"]
}

# Switches
switches = []
for sw_group in vlan_data["switches"]:
    for sw_name, sw_info in sw_group.items():
        svis = {svi["vlan"]: {"ip": svi["ip"], "mask": svi["mask"]} for svi in sw_info.get("svi", [])}
        switches.append({
            "host": sw_info["ip"],
            "username": sw_info["username"],
            "password": sw_info["password"],
            "vlans": sw_info["vlans"],
            "svis": svis,
            "name": sw_name
        })
print(f"Configured switches: {', '.join(sw['host'] for sw in switches)}")

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

        # Get current VLANs
        vlan_output = net_connect.send_command("show vlan-switch brief")
        vlan_lines = vlan_output.splitlines()
        current_vlans = set()
        for line in vlan_lines:
            parts = line.split()
            if len(parts) >= 2 and parts[0].isdigit():
                vlan_id = int(parts[0])
                current_vlans.add(vlan_id)


        # Remove extra VLANs (except reserved)
        reserved_vlans = {1, 1002, 1003, 1004, 1005}
        desired_vlans = set(sw["vlans"])
        vlans_to_remove = [v for v in current_vlans if v not in reserved_vlans and v not in desired_vlans]

        if vlans_to_remove:
            print(f"    Removing extra VLANs: {vlans_to_remove}")
            remove_cmds = []
            # Remove SVI interfaces for these VLANs
            for vlan_id in vlans_to_remove:
                remove_cmds.append(f"no interface vlan {vlan_id}")
            # Remove VLANs
            for vlan_id in vlans_to_remove:
                remove_cmds.append(f"no vlan {vlan_id}")
            net_connect.send_config_set(remove_cmds)
            net_connect.save_config()
        else:
            print("    No extra VLANs to remove.")

        # Add missing VLANs and SVIs
        vlans_to_add = [v for v in sw["vlans"] if v not in current_vlans]
        config_commands = []
        for vlan_id in vlans_to_add:
            config_commands.append(f"vlan {vlan_id}")
            config_commands.append(f"name VLAN_{vlan_id}")
            config_commands.append("exit")
            if vlan_id in sw["svis"]:
                svi = sw["svis"][vlan_id]
                config_commands.append(f"interface vlan {vlan_id}")
                config_commands.append(f"ip address {svi['ip']} {svi['mask']}")
                config_commands.append("no shutdown")
                config_commands.append("exit")
        if config_commands:
            print(f"    Adding/configuring VLANs and SVIs: {vlans_to_add}")
            net_connect.send_config_set(config_commands)
            net_connect.save_config()
        else:
            print("    No missing VLANs or SVIs to add.")


        # Reconnect to show final VLAN table
        net_connect = ConnectHandler(**jump_host)
        ssh_cmd = f"ssh -l {sw['username']} {sw['host']}"
        net_connect.write_channel(f"{ssh_cmd}\n")
        time.sleep(3)
        output = net_connect.read_channel()
        if "password:" in output.lower():
            net_connect.write_channel(f"{sw['password']}\n")
            time.sleep(3)
        redispatch(net_connect, device_type="cisco_ios")
        net_connect.enable()
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
        print(f"    Disconnected from {sw['host']} after final VLAN table display.\n")
    except Exception as e:
        print(f"    [!] Failure on {sw['host']}: {e}\n")

print("--- All Tasks Completed ---")