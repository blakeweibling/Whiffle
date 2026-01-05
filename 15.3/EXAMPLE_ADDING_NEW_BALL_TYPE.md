# Current Ball Type Implementation: Silver and Gold

This document describes the current ball detection system implementation, which supports **silver** and **gold** balls.

## `detection.py`

### `__init__` method

**Location:** Line 31-32

```python
self.model = YOLO("data/whiffle_new_best.pt")
self.class_names = ["silver", "gold"]
```

### `detect_all_balls` method signature

**Location:** Line 94-98

```python
) -> Tuple[
    List[Tuple[int, int, float]],  # silver_balls
    List[Tuple[int, int, float]],  # gold_balls
]:
```

### Ball type lists

**Location:** Line 116-119

```python
# Separate balls by type
silver_balls = []
gold_balls = []
```

### Ball type handling

**Location:** Line 160-166

```python
# Append to respective lists
if ball_type == "silver":
    silver_balls.append((int(x_center), int(y_center), radius))
elif ball_type == "gold":
    gold_balls.append((int(x_center), int(y_center), radius))
```

### Debug visualization

**Location:** Line 168-177

```python
# Debug frame drawing
if debug_mode:
    debug_frame = frame.copy()
    for x, y, radius in silver_balls:
        cv2.circle(debug_frame, (x, y), int(radius), (192, 192, 192), 2)  # Silver color
    for x, y, radius in gold_balls:
        cv2.circle(debug_frame, (x, y), int(radius), (0, 215, 255), 2)  # Gold color
    cv2.imshow("Ball Detection", debug_frame)
```

### Return statement

**Location:** Line 179

```python
return silver_balls, gold_balls
```

## `tracking.py`

### `track_balls` method signature

**Location:** Line 306-316

```python
def track_balls(
    self,
    silver_balls: List[Tuple[int, int, float]],
    gold_balls: List[Tuple[int, int, float]],
    tracked_balls: List[Tuple[int, int, float, int, int, str]],
    next_ball_id: int,
    frame_count: int,
    scored_positions: Dict[Tuple[int, int], int],
    debug_mode: bool,
) -> Tuple[List[Tuple[int, int, float, int, str]], int]:
```

### Combined balls list

**Location:** Line 344-350

```python
# Repackage balls with type information
silver_balls_with_type = [(x, y, r, "silver") for x, y, r in silver_balls]
gold_balls_with_type = [(x, y, r, "gold") for x, y, r in gold_balls]

# Combine all balls with type information
all_balls = silver_balls_with_type + gold_balls_with_type
```

## `game_loop.py`

### `detect_all_balls` call

**Location:** Line 148

```python
silver_balls, gold_balls = game_state.detector.detect_all_balls(
    frame=frame,
    frame_count=game_state.frame_count,
    game_state=game_state,
    scoring_zones=game_state.scoring_zones,
    debug_mode=game_state.debug_mode,
)
```

### Ball formatting

**Location:** Line 158-160

```python
new_balls_silver_fmt = [(int(x), int(y), float(r)) for x, y, r in silver_balls]
new_balls_gold_fmt = [(int(x), int(y), float(r)) for x, y, r in gold_balls]
```

### `track_balls` call

**Location:** Line 163-169

```python
tracked_detected_balls_tuples, next_id = game_state.tracker.track_balls(
    silver_balls=new_balls_silver_fmt,
    gold_balls=new_balls_gold_fmt,
    tracked_balls=game_state.tracked_balls,
    next_ball_id=game_state.next_ball_id,
    frame_count=game_state.frame_count,
    scored_positions=game_state.scored_positions,
    debug_mode=game_state.debug_mode,
)
```

## `ui_elements.py`

### BALL_COLORS dictionary

```python
BALL_COLORS = {
    "silver": (192, 192, 192),  # Silver color in BGR
    "gold": (0, 215, 255),  # Gold color in BGR
}
```

## `scoring_logic.py`

### Score multiplier logic

```python
score_multiplier = 1.0
if b_type == "gold":
    score_multiplier = 2.0
elif b_type == "silver":
    score_multiplier = 1.0
```

## `ui.py`

### Statistics display type order

**Location:** type_order list

```python
type_order = ["silver", "gold"]
```

6. Check that the new ball type appears in statistics
