import socket
import time

# Camera network configuration
CAMERA_IP = "192.168.111.200"  # Update to your VS-L320CX IP address
PORT = 8500                   # Standard Keyence TCP command port (verify in VS-Creator)

def trigger_camera():
    # Create a TCP/IP socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(3.0) # 3 second timeout
        try:
            print(f"Connecting to camera at {CAMERA_IP}:{PORT}...")
            s.connect((CAMERA_IP, PORT))
            
            # Keyence command syntax typically requires a command + delimiter (CR+LF)
            # 'TGR' or 'TRG' is commonly used to execute an external trigger command
            command = b"TGR\r\n" 
            # command = b"PRG\r\n" 
            # command = b"RST\r\n" 
            
            print("Sending trigger command...")
            s.sendall(command)
            
            # Receive response from camera (e.g., judgment result, error code, or completion)
            response = s.recv(1024)
            print(f"Camera Response: {response.decode('ascii', errors='ignore').strip()}")
            
        except socket.timeout:
            print("Connection timed out. Check IP address and wiring.")
        except ConnectionRefusedError:
            print("Connection refused. Ensure the camera is in Run Mode and network settings match.")

# Example loop to capture every 500ms (2 Hz) via Python
if __name__ == "__main__":
    print("Starting python trigger loop (Ctrl+C to stop)...")
    try:
        trigger_camera()
        # while True:
        #     trigger_camera()
        #     time.sleep(0.5) # Wait 500 ms between triggers
    except KeyboardInterrupt:
        print("Stopped by user.")