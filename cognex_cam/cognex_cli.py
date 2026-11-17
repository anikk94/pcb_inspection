import argparse
import cmd
import io
import os
import select
import socket
import sys
import time
from PIL import Image

NATIVE_STATUS_CODES = {
    "1": "Success",
    "0": "Unrecognized / Invalid command",
    "-1": "Invalid parameter / argument value",
    "-2": "Camera Offline / Execution not allowed in current state",
    "-3": "Job load or operation failed",
    "-4": "Sensor is busy",
    "-6": "Insufficient user permissions (Check User Access in ISVS)",
    "-7": "Sensor execution timeout",
}


class CognexNativeClient:
    def __init__(self, host: str, port: int = 23):
        self.host = host
        self.port = port
        self.sock = None

    def _read_until_tokens(self, tokens, timeout=10.0):
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
        raise TimeoutError(f"Timed out waiting for handshake. Received: {buf.decode('latin1', errors='ignore')}")

    def connect(self, user="admin", password=""):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.settimeout(10.0)
        self.sock.connect((self.host, self.port))

        # 1. Username handshake
        self._read_until_tokens([b"User:", b"user:"])
        self.sock.sendall((user + "\r\n").encode("ascii"))

        # 2. Password handshake
        self._read_until_tokens([b"Password:", b"password:"])
        self.sock.sendall((password + "\r\n").encode("ascii"))

        # 3. Auth verification
        auth_response = self._read_until_tokens([
            b"User Logged In", b"Logged In", b"Invalid", b"Access Denied"
        ])
        decoded = auth_response.decode("latin1", errors="ignore")
        if "Logged In" not in decoded:
            raise ConnectionError(f"Login failed: {decoded.strip()}")

        # Drain any residual banner bytes
        self.sock.settimeout(0.3)
        try:
            while True:
                if not self.sock.recv(1024):
                    break
        except socket.timeout:
            pass

    def _read_line(self, timeout=5.0):
        self.sock.settimeout(timeout)
        buf = bytearray()
        while True:
            chunk = self.sock.recv(1)
            if not chunk:
                break
            buf.extend(chunk)
            if buf.endswith(b"\r\n"):
                return buf[:-2].decode("ascii", errors="ignore")
            if buf.endswith(b"\n"):
                return buf[:-1].decode("ascii", errors="ignore")
        return buf.decode("ascii", errors="ignore")

    def send_raw(self, cmd_text: str):
        """Sends arbitrary Native Mode command and collects all returned response lines."""
        self.sock.sendall((cmd_text + "\r\n").encode("ascii"))
        lines = []

        # Read the mandatory primary response line
        primary = self._read_line(timeout=5.0)
        lines.append(primary)

        # Check if secondary lines (payload) are waiting on the socket
        while True:
            rlist, _, _ = select.select([self.sock], [], [], 0.15)
            if not rlist:
                break
            extra_line = self._read_line(timeout=0.5)
            if extra_line:
                lines.append(extra_line)
            else:
                break
        return lines

    def capture_image(self, save_path: str):
        """Triggers execution (SW8) and transfers BMP image data (RB)."""
        # Step 1: Trigger and wait
        self.sock.sendall(b"SW8\r\n")
        sw_res = self._read_line(timeout=10.0)
        if sw_res != "1":
            desc = NATIVE_STATUS_CODES.get(sw_res, "Unknown Error")
            raise RuntimeError(f"SW8 failed: Status {sw_res} ({desc}). Is the camera Online?")

        # Step 2: Request BMP bytes
        self.sock.sendall(b"RB\r\n")
        status = self._read_line(timeout=5.0)
        if status != "1":
            desc = NATIVE_STATUS_CODES.get(status, "Unknown Error")
            raise RuntimeError(f"RB failed: Status {status} ({desc})")

        size_line = self._read_line(timeout=5.0)
        expected_size = int(size_line)
        print(f"Downloading {expected_size:,} bytes over TCP...")

        raw_chunks = []
        bytes_received = 0

        # High-performance buffered read for hex payload
        rfile = self.sock.makefile("rb", buffering=65536)
        while bytes_received < expected_size:
            line = rfile.readline().strip()
            if not line:
                break
            # Skip checksum line if encountered at the end
            if len(line) == 4 and bytes_received >= expected_size:
                break
            try:
                chunk = bytes.fromhex(line.decode("ascii"))
                raw_chunks.append(chunk)
                bytes_received += len(chunk)
            except ValueError:
                break

        bmp_data = b"".join(raw_chunks)
        with open(save_path, "wb") as f:
            f.write(bmp_data)

        # Confirm valid image using Pillow
        img = Image.open(io.BytesIO(bmp_data))
        return img.size, img.format, len(bmp_data)

    def close(self):
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass


class CognexCLI(cmd.Cmd):
    intro = (
        "\n======================================================\n"
        " Cognex In-Sight Native Mode Interactive CLI\n"
        " Type 'help' or '?' for macros, or enter any raw Native\n"
        " command (e.g. SW8, SO1, SO0, GF, GV...). 'exit' to quit.\n"
        "======================================================\n"
    )

    def __init__(self, client: CognexNativeClient):
        super().__init__()
        self.cam = client
        self.prompt = f"cognex ({self.cam.host})> "

    def do_capture(self, arg):
        """capture [filename.bmp] - Trigger camera (SW8) and download image to disk."""
        filename = arg.strip() if arg.strip() else f"capture_{int(time.time())}.bmp"
        try:
            dims, fmt, size = self.cam.capture_image(filename)
            print(f"[SUCCESS] Saved to '{filename}' | Resolution: {dims[0]}x{dims[1]} | Format: {fmt} | Size: {size:,} bytes")
        except Exception as e:
            print(f"[ERROR] Capture failed: {e}")

    def do_trigger(self, _):
        """trigger - Issue SW8 (Set Event and Wait) without downloading the image."""
        res = self.cam.send_raw("SW8")
        status = res[0] if res else "?"
        desc = NATIVE_STATUS_CODES.get(status, "Unknown")
        print(f"Trigger status: {status} ({desc})")

    def do_online(self, _):
        """online - Put the camera Online (SO1)."""
        res = self.cam.send_raw("SO1")
        status = res[0] if res else "?"
        print(f"Online status: {status} ({NATIVE_STATUS_CODES.get(status, 'Unknown')})")

    def do_offline(self, _):
        """offline - Put the camera Offline (SO0)."""
        res = self.cam.send_raw("SO0")
        status = res[0] if res else "?"
        print(f"Offline status: {status} ({NATIVE_STATUS_CODES.get(status, 'Unknown')})")

    def do_job(self, _):
        """job - Get the currently active job file name (GF)."""
        lines = self.cam.send_raw("GF")
        if lines and lines[0] == "1" and len(lines) > 1:
            print(f"Active Job: {lines[1]}")
        else:
            print(f"Response: {lines}")

    def default(self, line):
        """Pass any unrecognized input directly to the camera as a raw Native Mode command."""
        cmd_clean = line.strip()
        if not cmd_clean:
            return
        try:
            responses = self.cam.send_raw(cmd_clean)
            if not responses:
                print("<No response from camera>")
                return

            primary = responses[0]
            desc = NATIVE_STATUS_CODES.get(primary, "")
            status_desc = f" ({desc})" if desc else ""
            print(f"Status: {primary}{status_desc}")

            # Print payload lines if any
            for extra in responses[1:]:
                print(f"  {extra}")
        except Exception as e:
            print(f"[ERROR] Communication error: {e}")

    def do_exit(self, _):
        """exit - Disconnect and terminate the session."""
        print("Closing camera connection...")
        self.cam.close()
        return True

    def do_quit(self, arg):
        """quit - Alias for exit."""
        return self.do_exit(arg)

    def do_EOF(self, _):
        """Handle Ctrl+D / Ctrl+Z cleanly."""
        print()
        return self.do_exit(_)


def main():
    parser = argparse.ArgumentParser(description="Cognex In-Sight 2800 Series Interactive CLI")
    parser.add_argument("--ip", required=True, help="Camera IP address (e.g. 192.168.1.100)")
    parser.add_argument("--port", type=int, default=23, help="Telnet/Native Mode Port (default: 23)")
    parser.add_argument("--user", default="admin", help="Username (default: admin)")
    parser.add_argument("--password", default="", help="Password (default: empty)")

    args = parser.parse_args()

    # print(args)

    client = CognexNativeClient(args.ip, args.port)
    try:
        print(f"Connecting to {args.ip}:{args.port} as '{args.user}'...")
        client.connect(args.user, args.password)
        print("Connected.")
    except Exception as e:
        print(f"Connection failed: {e}")
        sys.exit(1)

    try:
        cli = CognexCLI(client)
        cli.cmdloop()
    except KeyboardInterrupt:
        print("\nSession aborted by user.")
    finally:
        client.close()


if __name__ == "__main__":
    main()