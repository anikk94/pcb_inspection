from datetime import datetime
import math
from pathlib import Path

import cv2


CAMERA_INDEX = 0  # Change this to select a different webcam.
WINDOW_NAME = "Webcam Viewer"
RECORDING_DIR = Path(__file__).resolve().parent / "recordings"
FALLBACK_FPS = 30.0  # Used if the camera does not report a valid frame rate.


def main() -> None:
    camera = cv2.VideoCapture(CAMERA_INDEX)
    writer = None
    output_path = None
    frames_written = 0
    try:
        if not camera.isOpened():
            print(f"Could not open webcam {CAMERA_INDEX}.")
            return

        cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL)
        fps = camera.get(cv2.CAP_PROP_FPS)
        if not math.isfinite(fps) or fps <= 0:
            fps = FALLBACK_FPS

        print("Drag the window edges to resize. Press Q or Esc, or close the window, to quit.")
        while True:
            success, frame = camera.read()
            if not success:
                print("Could not read a frame from the webcam.")
                break

            if writer is None:
                RECORDING_DIR.mkdir(parents=True, exist_ok=True)
                output_path = RECORDING_DIR / f"webcam_{datetime.now():%Y%m%d_%H%M%S_%f}.mp4"
                height, width = frame.shape[:2]
                writer = cv2.VideoWriter(
                    str(output_path), cv2.VideoWriter_fourcc(*"mp4v"),
                    fps, (width, height),
                )
                if not writer.isOpened():
                    print(f"Could not open video file for recording: {output_path}")
                    break
                print(f"Recording to: {output_path} ({fps:g} FPS)")

            writer.write(frame)
            frames_written += 1
            cv2.imshow(WINDOW_NAME, frame)
            key = cv2.waitKey(1) & 0xFF
            if key in (ord("q"), ord("Q"), 27):
                break
            if cv2.getWindowProperty(WINDOW_NAME, cv2.WND_PROP_VISIBLE) < 1:
                break
    except KeyboardInterrupt:
        print("\nViewer stopped.")
    finally:
        if writer is not None:
            writer.release()
        camera.release()
        cv2.destroyAllWindows()
        if frames_written:
            print(f"Saved {frames_written} frames to: {output_path}")


if __name__ == "__main__":
    main()
