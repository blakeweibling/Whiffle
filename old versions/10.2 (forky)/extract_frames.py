import cv2
import os
import argparse

def extract_frames(video_path, output_dir, frame_interval=10):
    """
    Extract frames from a video at a specified interval and save them as images.

    Args:
        video_path (str): Path to the input video file.
        output_dir (str): Directory to save the extracted frames.
        frame_interval (int): Extract every nth frame (default: 10).
    """
    # Create output directory if it doesn't exist
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # Open the video file
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"Error: Could not open video file {video_path}")
        return

    # Get video properties
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    print(f"Video: {video_path}")
    print(f"Total frames: {total_frames}, FPS: {fps}")

    frame_count = 0
    saved_count = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break  # End of video

        # Extract frame at the specified interval
        if frame_count % frame_interval == 0:
            # Generate output filename
            frame_filename = os.path.join(output_dir, f"frame_{saved_count:04d}.jpg")
            # Save the frame as an image
            cv2.imwrite(frame_filename, frame)
            saved_count += 1
            print(f"Saved frame {saved_count} at {frame_filename}")

        frame_count += 1

    # Release the video capture object
    cap.release()
    print(f"Extracted {saved_count} frames from {video_path}")

if __name__ == "__main__":
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="Extract frames from a video at a specified interval.")
    parser.add_argument("video_path", help="Path to the input video file")
    parser.add_argument("output_dir", help="Directory to save the extracted frames")
    parser.add_argument("--interval", type=int, default=10, help="Extract every nth frame (default: 10)")
    args = parser.parse_args()

    # Extract frames
    extract_frames(args.video_path, args.output_dir, args.interval)