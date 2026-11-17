import socket
import time

# --- CONFIGURATION ---
KEYENCE_IP = "192.168.111.200"  # Replace with your camera's actual IP
KEYENCE_PORT = 8500           # Default Keyence TCP command port
BUFFER_SIZE = 1024            # Size of the response buffer
TIMEOUT = 3.0                 # Network timeout in seconds




def send_keyence_command(command_str: str):
    """
    Establishes a temporary TCP socket connection to send a command
    and retrieve the response from the Keyence VS camera.
    """
    # Ensure the command string ends with a Carriage Return delimiter
    if not command_str.endswith('\r'):
        command_str += '\r'
        
    print(f"Connecting to Keyence at {KEYENCE_IP}:{KEYENCE_PORT}...")
    
    try:
        # Create a standard TCP/IP socket
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client_socket:
            client_socket.settimeout(TIMEOUT)
            
            # Connect to the Keyence camera controller
            client_socket.connect((KEYENCE_IP, KEYENCE_PORT))
            
            # Send the command encoded in ASCII bytes
            print(f"Sending command: {repr(command_str)}")
            client_socket.sendall(command_str.encode('ascii'))
            
            # Receive response from the camera
            response_bytes = client_socket.recv(BUFFER_SIZE)
            response_str = response_bytes.decode('ascii').strip()
            
            print(f"Camera Response: {repr(response_str)}")
            return response_str
            
    except socket.timeout:
        print("Error: Connection timed out. Check network settings and camera IP.")
    except ConnectionRefusedError:
        print("Error: Connection refused. Check if the camera port is open and set to TCP Server.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
    return None

# --- EXAMPLES OF EXECUTION ---
if __name__ == "__main__":
    # # 1. Trigger the camera
    # print("--- Issuing Trigger Command ---")
    # send_keyence_command("T1") 
    
    # time.sleep(1) # Small delay
    
    # # 2. Change program example (Switch to program index 005)
    # print("\n--- Changing Program to 005 ---")
    # send_keyence_command("PW,1,005")


    # # Test Variant A: Split parameter
    # print("--- Testing Variant A (T1,1) ---")
    # send_keyence_command("T1,1") 
    
    # Test Variant B: Universal Trigger command
    # print("\n--- Testing Variant B (TRG) ---")
    send_keyence_command("TRG")
    # send_keyence_command("SET")
    # send_keyence_command("RUN")
    # send_keyence_command("RS")
    # send_keyence_command("PR")
    # send_keyence_command("MOR")
    # send_keyence_command("HMR")
    # send_keyence_command("TR")

    # send_keyence_command("RST")
    # send_keyence_command("PROG,0002")
    # send_keyence_command("CLRERR")
    # send_keyence_command("RECHST")
    # send_keyence_command("REBOOT")
    # send_keyence_command("HELP")
    # send_keyence_command("RESET")
    # send_keyence_command("CLR")
    # send_keyence_command("STOP")
    # send_keyence_command("T1")
    # send_keyence_command("TRG,01")


    # # Test Variant C: Strict Carriage Return check
    # # (Manually forcing only \r without any automatic additions)
    # print("\n--- Testing Variant C (Strict CR) ---")
    # send_keyence_command("T1") 