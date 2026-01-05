# Example: Adding a New Ball Type (e.g., "blue")

This example shows the exact code changes needed to add a new ball type called "blue" to your detection system.

## Step 1: Update `detection.py`

### Change 1: Update `__init__` method

**Location:** Line 31-32

**Before:**
```python
self.model = YOLO("data/whiffle_new_best.pt")
self.class_names = ["white", "red", "half"]
```

**After:**
```python
self.model = YOLO("data/whiffle_new_best.pt")  # Or path to your new model
self.class_names = ["white", "red", "half", "blue"]  # Add your new class
```

### Change 2: Update `detect_all_balls` method signature

**Location:** Line 94-98

**Before:**
```python
) -> Tuple[
    List[Tuple[int, int, float]],  # white_balls
    List[Tuple[int, int, float]],  # red_balls
    List[Tuple[int, int, float]],  # half_balls
]:
```

**After:**
```python
) -> Tuple[
    List[Tuple[int, int, float]],  # white_balls
    List[Tuple[int, int, float]],  # red_balls
    List[Tuple[int, int, float]],  # half_balls
    List[Tuple[int, int, float]],  # blue_balls
]:
```

### Change 3: Add blue_balls list

**Location:** Line 116-119

**Before:**
```python
# Separate balls by type
white_balls = []
red_balls = []
half_balls = []
```

**After:**
```python
# Separate balls by type
white_balls = []
red_balls = []
half_balls = []
blue_balls = []
```

### Change 4: Add handling for blue balls

**Location:** Line 160-166

**Before:**
```python
# Append to respective lists (Unchanged)
if ball_type == "white":
    white_balls.append((int(x_center), int(y_center), radius))
elif ball_type == "red":
    red_balls.append((int(x_center), int(y_center), radius))
elif ball_type == "half":
    half_balls.append((int(x_center), int(y_center), radius))
```

**After:**
```python
# Append to respective lists
if ball_type == "white":
    white_balls.append((int(x_center), int(y_center), radius))
elif ball_type == "red":
    red_balls.append((int(x_center), int(y_center), radius))
elif ball_type == "half":
    half_balls.append((int(x_center), int(y_center), radius))
elif ball_type == "blue":
    blue_balls.append((int(x_center), int(y_center), radius))
```

### Change 5: Add debug visualization for blue balls

**Location:** Line 168-177

**Before:**
```python
# Debug frame drawing (Unchanged)
if debug_mode:
    debug_frame = frame.copy()
    for x, y, radius in white_balls:
        cv2.circle(debug_frame, (x, y), int(radius), (255, 255, 255), 2)
    for x, y, radius in red_balls:
        cv2.circle(debug_frame, (x, y), int(radius), (0, 0, 255), 2)
    for x, y, radius in half_balls:
        cv2.circle(debug_frame, (x, y), int(radius), (255, 0, 255), 2)
    cv2.imshow("Ball Detection", debug_frame)
```

**After:**
```python
# Debug frame drawing
if debug_mode:
    debug_frame = frame.copy()
    for x, y, radius in white_balls:
        cv2.circle(debug_frame, (x, y), int(radius), (255, 255, 255), 2)
    for x, y, radius in red_balls:
        cv2.circle(debug_frame, (x, y), int(radius), (0, 0, 255), 2)
    for x, y, radius in half_balls:
        cv2.circle(debug_frame, (x, y), int(radius), (255, 0, 255), 2)
    for x, y, radius in blue_balls:
        cv2.circle(debug_frame, (x, y), int(radius), (255, 0, 0), 2)  # Blue color
    cv2.imshow("Ball Detection", debug_frame)
```

### Change 6: Update return statement

**Location:** Line 179

**Before:**
```python
return white_balls, red_balls, half_balls
```

**After:**
```python
return white_balls, red_balls, half_balls, blue_balls
```

## Step 2: Update `tracking.py`

### Change 1: Update `track_balls` method signature

**Location:** Line 306-316

**Before:**
```python
def track_balls(
    self,
    white_balls: List[Tuple[int, int, float]],
    red_balls: List[Tuple[int, int, float]],
    half_balls: List[Tuple[int, int, float]],
    ...
```

**After:**
```python
def track_balls(
    self,
    white_balls: List[Tuple[int, int, float]],
    red_balls: List[Tuple[int, int, float]],
    half_balls: List[Tuple[int, int, float]],
    blue_balls: List[Tuple[int, int, float]],  # Add this
    ...
```

### Change 2: Add blue_balls to the combined list

**Location:** Line 344-350

**Before:**
```python
# Repackage balls with type information
white_balls_with_type = [(x, y, r, "white") for x, y, r in white_balls]
red_balls_with_type = [(x, y, r, "red") for x, y, r in red_balls]
half_balls_with_type = [(x, y, r, "half") for x, y, r in half_balls]

# Combine all balls with type information
all_balls = white_balls_with_type + red_balls_with_type + half_balls_with_type
```

**After:**
```python
# Repackage balls with type information
white_balls_with_type = [(x, y, r, "white") for x, y, r in white_balls]
red_balls_with_type = [(x, y, r, "red") for x, y, r in red_balls]
half_balls_with_type = [(x, y, r, "half") for x, y, r in half_balls]
blue_balls_with_type = [(x, y, r, "blue") for x, y, r in blue_balls]  # Add this

# Combine all balls with type information
all_balls = white_balls_with_type + red_balls_with_type + half_balls_with_type + blue_balls_with_type
```

## Step 3: Update `game_loop.py`

### Change 1: Update `detect_all_balls` call

**Location:** Line 148

**Before:**
```python
white_balls, red_balls, half_balls = game_state.detector.detect_all_balls(
    frame=frame,
    frame_count=game_state.frame_count,
    game_state=game_state,
    scoring_zones=game_state.scoring_zones,
    debug_mode=game_state.debug_mode,
)
```

**After:**
```python
white_balls, red_balls, half_balls, blue_balls = game_state.detector.detect_all_balls(
    frame=frame,
    frame_count=game_state.frame_count,
    game_state=game_state,
    scoring_zones=game_state.scoring_zones,
    debug_mode=game_state.debug_mode,
)
```

### Change 2: Add formatting for blue balls

**Location:** Line 158-160

**Before:**
```python
new_balls_white_fmt = [(int(x), int(y), float(r)) for x, y, r in white_balls]
new_balls_red_fmt = [(int(x), int(y), float(r)) for x, y, r in red_balls]
new_balls_half_fmt = [(int(x), int(y), float(r)) for x, y, r in half_balls]
```

**After:**
```python
new_balls_white_fmt = [(int(x), int(y), float(r)) for x, y, r in white_balls]
new_balls_red_fmt = [(int(x), int(y), float(r)) for x, y, r in red_balls]
new_balls_half_fmt = [(int(x), int(y), float(r)) for x, y, r in half_balls]
new_balls_blue_fmt = [(int(x), int(y), float(r)) for x, y, r in blue_balls]  # Add this
```

### Change 3: Update `track_balls` call

**Location:** Line 163-169

**Before:**
```python
tracked_detected_balls_tuples, next_id = game_state.tracker.track_balls(
    white_balls=new_balls_white_fmt,
    red_balls=new_balls_red_fmt,
    half_balls=new_balls_half_fmt,
    tracked_balls=game_state.tracked_balls,
    next_ball_id=game_state.next_ball_id,
    frame_count=game_state.frame_count,
```

**After:**
```python
tracked_detected_balls_tuples, next_id = game_state.tracker.track_balls(
    white_balls=new_balls_white_fmt,
    red_balls=new_balls_red_fmt,
    half_balls=new_balls_half_fmt,
    blue_balls=new_balls_blue_fmt,  # Add this
    tracked_balls=game_state.tracked_balls,
    next_ball_id=game_state.next_ball_id,
    frame_count=game_state.frame_count,
```

## Step 4: Update scoring (if needed)

If your new ball type has different scoring rules, update `scoring.py` or `scoring_logic.py` to handle it.

## Step 5: Update statistics (if needed)

The statistics system should automatically handle the new ball type since it uses the `ball_type` string from tracking. However, you may want to update display code in `ui.py` or `stats_calculator.py` to show the new ball type in reports.

## Quick Checklist

- [ ] Train new YOLO model with new ball type
- [ ] Update `detection.py`:
  - [ ] Add new class to `self.class_names`
  - [ ] Add new ball list (`blue_balls`)
  - [ ] Add handling in detection loop
  - [ ] Update return type and statement
  - [ ] Add debug visualization
- [ ] Update `tracking.py`:
  - [ ] Add parameter to `track_balls()`
  - [ ] Add to combined balls list
- [ ] Find and update all calls to `detect_all_balls()`
- [ ] Find and update all calls to `track_balls()`
- [ ] Test with your new model
- [ ] Update scoring logic if needed
- [ ] Update UI/statistics display if needed

## Testing

After making changes:

1. Load your new trained model
2. Run the game with debug mode enabled
3. Verify the new ball type is detected correctly
4. Check that tracking works properly
5. Verify scoring (if applicable)

