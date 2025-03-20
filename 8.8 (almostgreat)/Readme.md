# Ball Tracking Game

## Overview

The Ball Tracking Game is a computer vision-based game built with Python, OpenCV, PyTorch, and Pygame. The game uses a webcam to detect and track colored balls (red, white, and half red/white) in real-time, allowing players to score points by placing balls in designated scoring zones. The game features a menu system, zone calibration, sound effects, and a CNN model for ball detection.

### Features
- **Real-time Ball Detection**: Uses a CNN model to detect red, white, and half red/white balls via a webcam.
- **Scoring Zones**: Players can define circular or rectangular zones with associated point values.
- **Zone Calibration**: Interactive UI to create, edit, and delete scoring zones.
- **Menu System**: Navigate through options to start a new game, change modes (Classic or Timed), adjust settings, and view help/about information.
- **Sound Effects**: Background music and sound effects for scoring and game events (requires Pygame).
- **Training Data Collection**: Label balls in frames to collect training data for the CNN model.

## Prerequisites

- **Python 3.8+**: Ensure Python is installed on your system.
- **Webcam**: A webcam is required for real-time ball detection.
- **Sound Files (Optional)**: Place sound files in the `sounds/` directory for background music and effects:
  - `background_music.mp3`
  - `score_effect.wav`
  - `game_over.wav`
  - `menu_click.wav`
- **Splash Image (Optional)**: Place a `splash.png` file in the project directory for the splash screen.

## Setup Instructions

1. **Clone the Repository** (if using version control):
   ```bash
   git clone <repository-url>
   cd ball-tracking-game