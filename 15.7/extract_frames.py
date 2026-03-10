import argparse
import os
from pathlib import Path

import cv2


def extract_frames(video_path, output_dir, interval_seconds, start_seconds, end_seconds):
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Could not open video: {video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS)
    if fps and fps > 0:
        interval_frames = max(1, int(round(fps * interval_seconds)))
    else:
        interval_frames = None

    if start_seconds and start_seconds > 0:
        cap.set(cv2.CAP_PROP_POS_MSEC, start_seconds * 1000)

    output_dir.mkdir(parents=True, exist_ok=True)

    saved = 0
    frame_idx = 0
    next_capture_ms = (start_seconds or 0) * 1000

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        current_ms = cap.get(cv2.CAP_PROP_POS_MSEC)
        current_s = current_ms / 1000.0 if current_ms else 0.0

        if end_seconds is not None and current_s > end_seconds:
            break

        should_save = False
        if interval_frames is not None:
            if frame_idx % interval_frames == 0:
                should_save = True
        else:
            if current_ms >= next_capture_ms:
                should_save = True

        if should_save:
            filename = f"frame_{saved:06d}_t{current_s:.2f}.jpg"
            cv2.imwrite(str(output_dir / filename), frame)
            saved += 1
            if interval_frames is None:
                next_capture_ms += interval_seconds * 1000

        frame_idx += 1

    cap.release()
    return saved


def main():
    parser = argparse.ArgumentParser(
        description="Extract frames from a video at a fixed time interval."
    )
    parser.add_argument("video", help="Path to input video (mp4)")
    parser.add_argument(
        "output_dir",
        help="Directory to save frames",
    )
    parser.add_argument(
        "--interval-seconds",
        type=float,
        default=5.0,
        help="Time between frames in seconds (default: 5)",
    )
    parser.add_argument(
        "--start-seconds",
        type=float,
        default=0.0,
        help="Start time in seconds (default: 0)",
    )
    parser.add_argument(
        "--end-seconds",
        type=float,
        default=None,
        help="End time in seconds (default: until video ends)",
    )
    args = parser.parse_args()

    saved = extract_frames(
        video_path=Path(args.video),
        output_dir=Path(args.output_dir),
        interval_seconds=args.interval_seconds,
        start_seconds=args.start_seconds,
        end_seconds=args.end_seconds,
    )
    print(f"Saved {saved} frames to {args.output_dir}")


if __name__ == "__main__":
    main()
