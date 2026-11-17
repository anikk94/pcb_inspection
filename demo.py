from parker_turntable.turntable import Turntable

import socket

from datetime import datetime

import time

# --- CONFIGURATION ---
KEYENCE_IP = "192.168.111.200"
KEYENCE_PORT = 8500
BUFFER_SIZE = 1024
TIMEOUT = 3.0

ACCEPTABLE_COMMANDS = {
    "TRG",
    "SET",
    "RUN",
    "RS",
    "PR",
    "MOR",
    "HMR",
    "TR",    
}


# AUTOMATION SETTINGS
STEP_ANGLE = 15




class CognexNativeClient:
    def __init__(self, host, port=23):
        self.host = host
        self.port = port
        self.sock = None
        self.rfile = None


    def _read_until_tokens(self, tokens, timeout=10.0):
            """Accumulates bytes until any of the specified tokens appear."""
            self.sock.settimeout(timeout)
            buf = bytearray()
            start = time.time()
            while time.time() - start < timeout:
                chunk = self.sock.recv(1)
                if not chunk:
                    break
                buf.extend(chunk)
                for token in tokens:
                    if token in buf:
                        return buf
            raise TimeoutError(f"Timed out waiting for {tokens}. Received so far: {repr(buf.decode('latin1', errors='ignore'))}")


    def connect(self, user="admin", password=""):
        print(f"Connecting to {self.host}:{self.port}...")
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.settimeout(10.0)
        self.sock.connect((self.host, self.port))

        # 1. Wait for username prompt
        banner = self._read_until_tokens([b"User:", b"user:"])
        print(f"[Handshake] Banner: {repr(banner.decode('latin1', errors='ignore').strip())}")
        self.sock.sendall((user + "\r\n").encode("ascii"))

        # 2. Wait for password prompt
        pw_prompt = self._read_until_tokens([b"Password:", b"password:"])
        print(f"[Handshake] Prompt: {repr(pw_prompt.decode('latin1', errors='ignore').strip())}")
        self.sock.sendall((password + "\r\n").encode("ascii"))

        # 3. Wait for authentication response
        auth_response = self._read_until_tokens([
            b"User Logged In",
            b"Logged In",
            b"Invalid",
            b"incorrect",
            b"Access Denied"
        ])
        decoded_auth = auth_response.decode("latin1", errors="ignore")
        print(f"[Handshake] Auth result: {repr(decoded_auth.strip())}")

        if "Logged In" not in decoded_auth:
            raise ConnectionError(f"Login rejected by camera: {decoded_auth}")

        # 4. Drain any trailing prompt characters (e.g., '>' or CRLF)
        self.sock.settimeout(0.5)
        try:
            while True:
                extra = self.sock.recv(1024)
                if not extra:
                    break
        except socket.timeout:
            pass

        # Switch to high-performance buffered line reading for commands and images
        self.sock.settimeout(15.0)
        self.rfile = self.sock.makefile("rb", buffering=65536)
        print("Connected and logged in successfully.\n")


    def send_cmd(self, cmd):
        """Sends a Native Mode command and returns the status code."""
        self.sock.sendall((cmd + "\r\n").encode("ascii"))
        line = self.rfile.readline().decode("ascii", errors="ignore").strip()
        return line


    def put_online(self):
        """Puts camera Online (SO1). If already online, it still returns 1."""
        res = self.send_cmd("SO1")
        if res not in ("1", "0"):
            raise RuntimeError(f"Failed to set camera online. Response: {res}")

    def trigger(self):
        sw_res = self.send_cmd("SW8")
        if sw_res != "1":
            raise RuntimeError(
                f"Acquisition trigger failed with status '{sw_res}'. "
                "Ensure the camera is Online and Trigger mode is Network/Manual/External."
            )



    def close(self):
        if self.rfile:
            self.rfile.close()
        if self.sock:
            self.sock.close()




def send_keyence_command(client_socket: socket.socket, command_str: str) -> str:
    """Send one command and receive its response using the existing connection."""
    command_bytes = (command_str.rstrip("\r\n") + "\r").encode("ascii")
    # print(f"Sending command: {command_bytes!r}")
    client_socket.sendall(command_bytes)

    response_bytes = client_socket.recv(BUFFER_SIZE)
    if not response_bytes:
        raise ConnectionError("The camera closed the connection.")

    response_str = response_bytes.decode("ascii").strip()
    # print(f"Camera Response: {response_str!r}")
    return response_str


def main_keyence() -> None:
    """Run an interactive CLI with one socket for the entire session."""
    # print(f"Connecting to Keyence at {KEYENCE_IP}:{KEYENCE_PORT}...")

    angle = 0

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client_socket:
            client_socket.settimeout(TIMEOUT)
            client_socket.connect((KEYENCE_IP, KEYENCE_PORT))
            # print("Connected. Enter a camera command, or 'exit' to quit.")
            # print("Acceptable commands: " + "; ".join(sorted(ACCEPTABLE_COMMANDS)))


            with Turntable(port="COM6", units_per_degree=(100000*0.9375)/30, speed = 3.0, acceleration=6.0) as tt:
                print(f"UNITS PER DEGREE: {tt.units_per_degree}")
                print(f"SPEED:          : {tt.speed}")
                print(f"ACCELERATION    : {tt.acceleration}")
                tt.enable()
                tt.configure_motion()
                tt.move_relative(5)
                tt.move_relative(-5)

                print("READY!\n")

                input("ENTER TO START >> ")

                while True:

                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    print(f"[{timestamp}] Rotation: {angle} deg")

                    # command = input("keyence> ").strip().upper()
                    command = "trg".strip().upper()
                    if command == "EXIT":
                        break
                    if not command:
                        continue
                    if command not in ACCEPTABLE_COMMANDS:
                        print("Invalid command. Acceptable commands: "
                            + "; ".join(sorted(ACCEPTABLE_COMMANDS)))
                        continue

                    send_keyence_command(client_socket, command)

                    if angle >= 360:
                        break

                    tt.move_relative(STEP_ANGLE)
                    angle += STEP_ANGLE

    except (KeyboardInterrupt, EOFError):
        print("\nSession stopped.")
    except socket.timeout:
        print("Error: Connection or response timed out. Ending the session.")
    except ConnectionRefusedError:
        print("Error: Connection refused. Check the camera IP and TCP server port.")
    except (OSError, UnicodeError) as exc:
        print(f"Error: {exc}")
    finally:
        print("Session ended; socket closed.")


def main_cognex():

    CAMERA_IP = "192.168.111.202"  # Replace with your camera's IP
    CAMERA_PORT = 23             # Or 2323 if you customized it in ISVS
    USERNAME = "admin"
    PASSWORD = ""                # Default is blank ("")

    angle = 0
    # count = 0

    cam = CognexNativeClient(CAMERA_IP, CAMERA_PORT)
    try:
        cam.connect(user=USERNAME, password=PASSWORD)

        # cam.put_online()

        # while input("TRIGGER >> ").lower().strip() != "q":
        #     cam.trigger()

        with Turntable(port="COM6", units_per_degree=(100000*0.9375)/30, speed = 3.0, acceleration=6.0) as tt:
            print(f"UNITS PER DEGREE: {tt.units_per_degree}")
            print(f"SPEED:          : {tt.speed}")
            print(f"ACCELERATION    : {tt.acceleration}")
            tt.enable()
            tt.configure_motion()
            tt.move_relative(5)
            tt.move_relative(-5)

            print("READY!\n")

            input("ENTER TO START >> ")

            while True:

                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                print(f"[{timestamp}] Rotation: {angle} deg")

                cam.trigger()

                if angle >= 360:
                    break
                # count += 1
                # if count >= 3:
                #     break

                tt.move_relative(STEP_ANGLE)
                angle += STEP_ANGLE



    finally:
        cam.close()


if __name__ == "__main__":
    # main_keyence()

    main_cognex()
