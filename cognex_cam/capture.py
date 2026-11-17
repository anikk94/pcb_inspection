import io
import socket
import time
from PIL import Image

CAMERA_IP = "192.168.111.202"  # Replace with your camera's IP
CAMERA_PORT = 23             # Or 2323 if you customized it in ISVS
USERNAME = "admin"
PASSWORD = ""                # Default is blank ("")


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

    def trigger_and_capture(self):
        """
        SW8: Triggers acquisition & execution, then waits for completion.
        RB:  Reads the current frame as an ASCII-hex encoded BMP.
        """
        print("Triggering acquisition (SW8)...")
        sw_res = self.send_cmd("SW8")
        if sw_res != "1":
            raise RuntimeError(
                f"Acquisition trigger failed with status '{sw_res}'. "
                "Ensure the camera is Online and Trigger mode is Network/Manual/External."
            )

        print("Requesting image data (RB)...")
        self.sock.sendall(b"RB\r\n")

        # Line 1: Status code (1 = Success)
        status = self.rfile.readline().decode("ascii", errors="ignore").strip()
        if status != "1":
            raise RuntimeError(f"RB command failed with status: {status}")

        # Line 2: Size of binary BMP in bytes
        size_str = self.rfile.readline().decode("ascii", errors="ignore").strip()
        expected_size = int(size_str)
        print(f"Receiving {expected_size:,} bytes of image data...")

        # Subsequent lines: 80 hex characters per line (40 binary bytes)
        raw_chunks = []
        bytes_received = 0

        while bytes_received < expected_size:
            line = self.rfile.readline().strip()
            if not line:
                break
            
            # The final 4 characters in the stream are a checksum line (e.g. 611E)
            if len(line) == 4 and bytes_received >= expected_size:
                break

            try:
                chunk = bytes.fromhex(line.decode("ascii"))
                raw_chunks.append(chunk)
                bytes_received += len(chunk)
            except ValueError:
                # Reached end-of-payload checksum or non-hex terminator
                break

        # Consume any trailing checksum line if not already consumed
        raw_bmp_bytes = b"".join(raw_chunks)
        return raw_bmp_bytes

    def close(self):
        if self.rfile:
            self.rfile.close()
        if self.sock:
            self.sock.close()


if __name__ == "__main__":
    cam = CognexNativeClient(CAMERA_IP, CAMERA_PORT)
    try:
        cam.connect(user=USERNAME, password=PASSWORD)
        cam.put_online()

        # bmp_data = cam.trigger_and_capture()

        # # Save to disk
        # filename = "cognex_capture.bmp"
        # with open(filename, "wb") as f:
        #     f.write(bmp_data)
        # print(f"Image successfully saved to '{filename}' ({len(bmp_data):,} bytes)")

        # # Verify image with Pillow
        # img = Image.open(io.BytesIO(bmp_data))
        # print(f"Captured Image: {img.size[0]}x{img.size[1]} pixels, {img.format} format")

    finally:
        cam.close()