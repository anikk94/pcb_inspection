import socket

# --- CONFIGURATION ---
KEYENCE_IP = "192.168.111.200"
KEYENCE_PORT = 8500
BUFFER_SIZE = 1024
TIMEOUT = 3.0

# Edit this allowlist to match the commands you want to permit.
# Entries come from the examples previously in this file; camera support varies.
# Commands with parameters must match a complete entry, including parameters.
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


def send_keyence_command(client_socket: socket.socket, command_str: str) -> str:
    """Send one command and receive its response using the existing connection."""
    command_bytes = (command_str.rstrip("\r\n") + "\r").encode("ascii")
    print(f"Sending command: {command_bytes!r}")
    client_socket.sendall(command_bytes)

    response_bytes = client_socket.recv(BUFFER_SIZE)
    if not response_bytes:
        raise ConnectionError("The camera closed the connection.")

    response_str = response_bytes.decode("ascii").strip()
    print(f"Camera Response: {response_str!r}")
    return response_str


def main() -> None:
    """Run an interactive CLI with one socket for the entire session."""
    print(f"Connecting to Keyence at {KEYENCE_IP}:{KEYENCE_PORT}...")
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client_socket:
            client_socket.settimeout(TIMEOUT)
            client_socket.connect((KEYENCE_IP, KEYENCE_PORT))
            print("Connected. Enter a camera command, or 'exit' to quit.")
            print("Acceptable commands: " + "; ".join(sorted(ACCEPTABLE_COMMANDS)))

            while True:
                command = input("keyence> ").strip().upper()
                if command == "EXIT":
                    break
                if not command:
                    continue
                if command not in ACCEPTABLE_COMMANDS:
                    print("Invalid command. Acceptable commands: "
                          + "; ".join(sorted(ACCEPTABLE_COMMANDS)))
                    continue

                send_keyence_command(client_socket, command)
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


if __name__ == "__main__":
    main()
