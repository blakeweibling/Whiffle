import argparse
from pathlib import Path

from create_yolo_dataset import create_dataset
from extract_frames import extract_frames


def main():
    parser = argparse.ArgumentParser(
        description="Extract frames and create a YOLO dataset structure."
    )
    parser.add_argument("video", help="Path to input video (mp4)")
    parser.add_argument("output_dir", help="Output dataset directory")
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
    parser.add_argument(
        "--val-split",
        type=float,
        default=0.15,
        help="Validation split fraction (default: 0.15)",
    )
    parser.add_argument(
        "--test-split",
        type=float,
        default=0.0,
        help="Test split fraction (default: 0.0)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for shuffling (default: 42)",
    )
    parser.add_argument(
        "--mode",
        choices=["copy", "move"],
        default="copy",
        help="Copy or move images into the dataset (default: copy)",
    )
    parser.add_argument(
        "--empty-labels",
        action="store_true",
        help="Create empty label files matching each image",
    )
    parser.add_argument(
        "--classes",
        nargs="*",
        default=None,
        help="Class names to include in data.yaml (optional)",
    )
    parser.add_argument(
        "--frames-dir",
        default=None,
        help="Optional directory to store extracted frames "
        "(default: <output_dir>/raw_frames)",
    )
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    frames_dir = Path(args.frames_dir) if args.frames_dir else output_dir / "raw_frames"

    saved = extract_frames(
        video_path=Path(args.video),
        output_dir=frames_dir,
        interval_seconds=args.interval_seconds,
        start_seconds=args.start_seconds,
        end_seconds=args.end_seconds,
    )
    if saved == 0:
        raise RuntimeError("No frames were extracted.")

    create_dataset(
        input_dir=frames_dir,
        output_dir=output_dir,
        val_split=args.val_split,
        test_split=args.test_split,
        seed=args.seed,
        mode=args.mode,
        empty_labels=args.empty_labels,
        classes=args.classes,
    )


if __name__ == "__main__":
    main()
