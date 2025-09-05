import re
import numpy as np
from scipy.signal import lti, step

def parse_dump(file_path):
    """
    Parses a Betaflight dump file to extract PID and filter values for the active profile.
    """
    pids = {}
    active_profile_id = -1
    in_correct_profile_block = False

    try:
        with open(file_path, 'r') as f:
            lines = f.readlines()

        # First pass: find the active profile
        for line in lines:
            line = line.strip()
            if line.startswith('profile '):
                active_profile_id = int(line.split(' ')[1])
                break

        if active_profile_id == -1:
            # Fallback for older dumps or if 'profile' command is not first
            active_profile_id = 0

        # Second pass: find the correct profile block and parse settings
        for line in lines:
            line = line.strip()
            if line == f'# profile {active_profile_id}':
                in_correct_profile_block = True
                continue

            if in_correct_profile_block:
                if line.startswith('#') or line == '':
                    # End of profile block
                    break

                match = re.match(r'set\s+([pidf]_\w+)\s+=\s+(\d+)', line)
                if match:
                    key = match.group(1)
                    value = int(match.group(2))
                    pids[key] = value

        # If the profile block method failed, fall back to global settings
        if not pids:
             for line in lines:
                line = line.strip()
                match = re.match(r'set\s+([pidf]_\w+)\s+=\s+(\d+)', line)
                if match:
                    key = match.group(1)
                    value = int(match.group(2))
                    pids[key] = value

    except FileNotFoundError:
        return None, f"Dump file not found at '{file_path}'"
    except Exception as e:
        return None, f"An error occurred while parsing: {e}"

    if not pids:
        return None, "Could not find any PID settings in the dump file."

    return pids, None


def propose_tune(pids, reduction_percent=15):
    """
    Proposes new PID settings based on a percentage reduction for D-gains.
    Returns a dictionary with the proposed new values.
    """
    new_pids = pids.copy()
    if 'd_roll' in pids:
        new_pids['d_roll'] = int(pids['d_roll'] * (1 - reduction_percent / 100))
    if 'd_pitch' in pids:
        new_pids['d_pitch'] = int(pids['d_pitch'] * (1 - reduction_percent / 100))
    return new_pids


def generate_cli(pids):
    """
    Generates Betaflight CLI commands to set the given PID values.
    """
    cli_commands = "# Paste the following commands into the Betaflight CLI:\n"
    # Assuming we are targeting the active profile, no need for `profile X` command

    if 'p_roll' in pids: cli_commands += f"set p_roll = {pids['p_roll']}\n"
    if 'i_roll' in pids: cli_commands += f"set i_roll = {pids['i_roll']}\n"
    if 'd_roll' in pids: cli_commands += f"set d_roll = {pids['d_roll']}\n"
    if 'f_roll' in pids: cli_commands += f"set f_roll = {pids['f_roll']}\n"

    if 'p_pitch' in pids: cli_commands += f"\nset p_pitch = {pids['p_pitch']}\n"
    if 'i_pitch' in pids: cli_commands += f"set i_pitch = {pids['i_pitch']}\n"
    if 'd_pitch' in pids: cli_commands += f"set d_pitch = {pids['d_pitch']}\n"
    if 'f_pitch' in pids: cli_commands += f"set f_pitch = {pids['f_pitch']}\n"

    cli_commands += "\nsave\n"
    return cli_commands


def simulate_step_response(pids, inertia=0.005, duration=0.2, time_steps=500):
    """
    Simulates the step response of a PID controller on a simplified 2nd-order system.

    Args:
        pids (dict): A dictionary containing keys like 'p_roll', 'd_roll'.
        inertia (float): An arbitrary inertia value for the system model.
        duration (float): The duration of the simulation in seconds.
        time_steps (int): The number of time steps in the simulation.

    Returns:
        A tuple (time, response) or (None, None) if PIDs are missing.
    """
    # Betaflight PID values need scaling to be used in standard PID equations.
    # These scaling factors are approximate and simplified for visualization.
    # They are not the exact factors used in Betaflight's code but serve to
    # make the simulation responsive to changes in a visually intuitive way.
    P_SCALE = 0.01
    I_SCALE = 0.005
    D_SCALE = 0.0001

    # We are simulating either roll or pitch, so we check for either
    if 'p_roll' in pids:
        Kp = pids.get('p_roll', 0) * P_SCALE
        Ki = pids.get('i_roll', 0) * I_SCALE
        Kd = pids.get('d_roll', 0) * D_SCALE
    elif 'p_pitch' in pids:
        Kp = pids.get('p_pitch', 0) * P_SCALE
        Ki = pids.get('i_pitch', 0) * I_SCALE
        Kd = pids.get('d_pitch', 0) * D_SCALE
    else:
        return None, None

    # Plant model: A simple rotating body, 1/(J*s^2)
    # This represents the physics of the quadcopter's rotation.
    plant_num = [1]
    plant_den = [inertia, 0, 0]
    plant = lti(plant_num, plant_den)

    # PID controller model: Kp + Ki/s + Kd*s
    # To implement this, we can think of it as a transfer function:
    # (Kd*s^2 + Kp*s + Ki) / s
    controller_num = [Kd, Kp, Ki]
    controller_den = [1, 0]
    controller = lti(controller_num, controller_den)

    # Closed-loop system transfer function: C*P / (1 + C*P)
    # C = controller, P = plant
    # Using the feedback formula:
    # num = C_num * P_num
    # den = (C_den * P_den) + (C_num * P_num)  -- simplified for series

    # Let's compute the open loop transfer function first: L = C * P
    open_loop_num = np.convolve(controller_num, plant_num)
    open_loop_den = np.convolve(controller_den, plant_den)

    # Now compute the closed loop transfer function: H = L / (1 + L)
    closed_loop_num = open_loop_num
    closed_loop_den = np.polyadd(open_loop_den, open_loop_num)

    system = lti(closed_loop_num, closed_loop_den)

    # Calculate the step response
    t = np.linspace(0, duration, time_steps)
    t, y = step(system, T=t)

    return t, y
