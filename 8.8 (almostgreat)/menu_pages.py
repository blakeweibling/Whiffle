# menu_pages.py
import cv2
from datetime import datetime

def draw_text_page(renderer, frame, text, title):
    """Draw a text page (e.g., Help or About) with the given text and title."""
    overlay = frame.copy()
    h, w = frame.shape[:2]

    # Use the menu position from MenuSystem, default to w//4, h//4 if not set
    if renderer.menu_system.menu_pos_x is None or renderer.menu_system.menu_pos_y is None:
        renderer.menu_system.menu_pos_x = w // 4
        renderer.menu_system.menu_pos_y = h // 4

    menu_x1 = renderer.menu_system.menu_pos_x
    menu_y1 = renderer.menu_system.menu_pos_y
    menu_x2 = menu_x1 + (w // 2)
    menu_y2 = menu_y1 + (h // 2)

    # Ensure the menu stays within the window bounds
    menu_x1 = max(0, min(menu_x1, w - (menu_x2 - menu_x1)))
    menu_y1 = max(0, min(menu_y1, h - (menu_y2 - menu_y1)))
    menu_x2 = menu_x1 + (w // 2)
    menu_y2 = menu_y1 + (h // 2)

    renderer.menu_system.menu_pos_x = menu_x1
    renderer.menu_system.menu_pos_y = menu_y1

    renderer.menu_system.menu_area = (menu_x1, menu_y1, menu_x2 - menu_x1, menu_y2 - menu_y1)

    # Draw the menu background
    cv2.rectangle(overlay, (menu_x1, menu_y1), (menu_x2, menu_y2), (100, 100, 100), -1)
    cv2.rectangle(overlay, (menu_x1, menu_y1), (menu_x2, menu_y2), (150, 150, 150), 2)

    # Draw a draggable header
    header_height = 30
    cv2.rectangle(overlay, (menu_x1, menu_y1), (menu_x2, menu_y1 + header_height), (80, 80, 80), -1)
    cv2.rectangle(overlay, (menu_x1, menu_y1), (menu_x2, menu_y1 + header_height), (150, 150, 150), 1)
    renderer.menu_system.header_rect = (menu_x1, menu_y1, menu_x2 - menu_x1, header_height)

    font = cv2.FONT_HERSHEY_DUPLEX
    font_scale = 0.5
    thickness = 1

    text_size = cv2.getTextSize(title, font, font_scale, thickness)[0]
    x_pos = menu_x1 + ((menu_x2 - menu_x1) - text_size[0]) // 2
    y_pos = menu_y1 + header_height // 2 + text_size[1] // 2
    cv2.putText(overlay, title, (x_pos, y_pos), font, font_scale, (220, 220, 220), thickness)

    # Calculate the available space for text, accounting for the "Back" button
    back_button_height = 30  # Height of the "Back" button
    back_button_margin = 60  # Margin above the bottom where the "Back" button is placed
    text_area_height = (menu_y2 - menu_y1) - header_height - back_button_margin - back_button_height - 10  # Extra 10 for padding
    line_height = 20  # Height per line of text (i * 20)
    max_lines = int(text_area_height // line_height)  # Maximum number of lines that can fit

    max_width = (menu_x2 - menu_x1) - 40
    wrapped_lines = renderer.wrap_text(text, font, font_scale, thickness, max_width)

    # Limit the number of lines to fit above the "Back" button
    for i, line in enumerate(wrapped_lines[:max_lines]):
        y_pos = menu_y1 + header_height + 30 + i * 20
        cv2.putText(overlay, line, (menu_x1 + 20, y_pos), font, font_scale, (220, 220, 220), thickness)

    close_x = menu_x2 - 40
    close_y = menu_y1 + 5
    close_w, close_h = 30, 20
    renderer.menu_system.close_button_rect = (close_x, close_y, close_w, close_h)
    cv2.rectangle(overlay, (close_x, close_y), (close_x + close_w, close_y + close_h), (0, 0, 255), -1)
    cv2.rectangle(overlay, (close_x, close_y), (close_x + close_w, close_y + close_h), (0, 0, 0), 1)
    text_size = cv2.getTextSize("X", font, 0.5, 1)[0]
    text_x = close_x + (close_w - text_size[0]) // 2
    text_y = close_y + (close_h + text_size[1]) // 2
    cv2.putText(overlay, "X", (text_x, text_y), font, 0.5, (255, 255, 255), 1)

    back_x = menu_x1 + 20
    back_y = menu_y2 - 60
    back_w, back_h = 100, 30
    renderer.menu_system.back_button_rect = (back_x, back_y, back_w, back_h)
    cv2.rectangle(overlay, (back_x, back_y), (back_x + back_w, back_y + back_h), (200, 200, 200), -1)
    cv2.rectangle(overlay, (back_x, back_y), (back_x + back_w, back_y + back_h), (0, 0, 0), 1)
    text_size = cv2.getTextSize("Back", font, 0.5, 1)[0]
    text_x = back_x + (back_w - text_size[0]) // 2
    text_y = back_y + (back_h + text_size[1]) // 2
    cv2.putText(overlay, "Back", (text_x, text_y), font, 0.5, (0, 0, 0), 1)

    # Apply semi-transparency (same as HelpWindow)
    alpha = 0.95  # Match the opacity of HelpWindow
    cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)
    return frame

def draw_leaderboard(renderer, frame):
    """Draw the leaderboard with the top scores."""
    overlay = frame.copy()
    h, w = frame.shape[:2]

    # Use the menu position from MenuSystem, default to w//4, h//4 if not set
    if renderer.menu_system.menu_pos_x is None or renderer.menu_system.menu_pos_y is None:
        renderer.menu_system.menu_pos_x = w // 4
        renderer.menu_system.menu_pos_y = h // 4

    menu_x1 = renderer.menu_system.menu_pos_x
    menu_y1 = renderer.menu_system.menu_pos_y
    menu_x2 = menu_x1 + (w // 2)
    menu_y2 = menu_y1 + (h // 2)

    # Ensure the menu stays within the window bounds
    menu_x1 = max(0, min(menu_x1, w - (menu_x2 - menu_x1)))
    menu_y1 = max(0, min(menu_y1, h - (menu_y2 - menu_y1)))
    menu_x2 = menu_x1 + (w // 2)
    menu_y2 = menu_y1 + (h // 2)

    renderer.menu_system.menu_pos_x = menu_x1
    renderer.menu_system.menu_pos_y = menu_y1

    renderer.menu_system.menu_area = (menu_x1, menu_y1, menu_x2 - menu_x1, menu_y2 - menu_y1)

    # Draw the menu background
    cv2.rectangle(overlay, (menu_x1, menu_y1), (menu_x2, menu_y2), (100, 100, 100), -1)
    cv2.rectangle(overlay, (menu_x1, menu_y1), (menu_x2, menu_y2), (150, 150, 150), 2)

    # Draw a draggable header
    header_height = 30
    cv2.rectangle(overlay, (menu_x1, menu_y1), (menu_x2, menu_y1 + header_height), (80, 80, 80), -1)
    cv2.rectangle(overlay, (menu_x1, menu_y1), (menu_x2, menu_y1 + header_height), (150, 150, 150), 1)
    renderer.menu_system.header_rect = (menu_x1, menu_y1, menu_x2 - menu_x1, header_height)

    font = cv2.FONT_HERSHEY_DUPLEX
    font_scale = 0.7
    thickness = 2

    title = f"Leaderboard ({renderer.menu_system.mode})"
    text_size = cv2.getTextSize(title, font, font_scale, thickness)[0]
    x_pos = menu_x1 + ((menu_x2 - menu_x1) - text_size[0]) // 2
    y_pos = menu_y1 + header_height // 2 + text_size[1] // 2
    cv2.putText(overlay, title, (x_pos, y_pos), font, font_scale, (220, 220, 220), thickness)

    font_scale = 0.5
    thickness = 1
    renderer.menu_system.menu_item_rects = []

    if renderer.leaderboard_loading:
        text = "Loading..."
        text_size = cv2.getTextSize(text, font, font_scale, thickness)[0]
        x_pos = menu_x1 + ((menu_x2 - menu_x1) - text_size[0]) // 2
        y_pos = menu_y1 + (menu_y2 - menu_y1) // 2
        cv2.putText(overlay, text, (x_pos, y_pos), font, font_scale, (220, 220, 220), thickness)
    elif renderer.leaderboard_error:
        text = f"Failed to load online leaderboard. Showing local scores."
        wrapped_lines = renderer.wrap_text(text, font, font_scale, thickness, menu_x2 - menu_x1 - 40)
        for i, line in enumerate(wrapped_lines):
            text_size = cv2.getTextSize(line, font, font_scale, thickness)[0]
            x_pos = menu_x1 + ((menu_x2 - menu_x1) - text_size[0]) // 2
            y_pos = menu_y1 + (menu_y2 - menu_y1) // 2 + i * 20
            cv2.putText(overlay, line, (x_pos, y_pos), font, font_scale, (220, 220, 220), thickness)
        if renderer.leaderboard_scores:
            for i, score_entry in enumerate(renderer.leaderboard_scores):
                initials = score_entry["initials"]
                score = score_entry["score"]
                created_at = datetime.fromisoformat(score_entry["created_at"].replace("Z", "+00:00")).strftime("%Y-%m-%d")
                text = f"{i+1}. {initials}: {score} ({created_at})"
                text_size = cv2.getTextSize(text, font, font_scale, thickness)[0]
                x_pos = menu_x1 + 20
                y_pos = menu_y1 + header_height + 50 + (i + len(wrapped_lines)) * 30
                cv2.putText(overlay, text, (x_pos, y_pos), font, font_scale, (220, 220, 220), thickness)
    elif not renderer.leaderboard_scores:
        text = "No scores available."
        text_size = cv2.getTextSize(text, font, font_scale, thickness)[0]
        x_pos = menu_x1 + ((menu_x2 - menu_x1) - text_size[0]) // 2
        y_pos = menu_y1 + (menu_y2 - menu_y1) // 2
        cv2.putText(overlay, text, (x_pos, y_pos), font, font_scale, (220, 220, 220), thickness)
    else:
        source_text = "Online Leaderboard" if renderer.leaderboard_is_online else "Local Leaderboard"
        text_size = cv2.getTextSize(source_text, font, font_scale, thickness)[0]
        x_pos = menu_x1 + ((menu_x2 - menu_x1) - text_size[0]) // 2
        y_pos = menu_y1 + header_height + 30
        cv2.putText(overlay, source_text, (x_pos, y_pos), font, font_scale, (220, 220, 220), thickness)
        for i, score_entry in enumerate(renderer.leaderboard_scores):
            initials = score_entry["initials"]
            score = score_entry["score"]
            created_at = datetime.fromisoformat(score_entry["created_at"].replace("Z", "+00:00")).strftime("%Y-%m-%d")
            text = f"{i+1}. {initials}: {score} ({created_at})"
            text_size = cv2.getTextSize(text, font, font_scale, thickness)[0]
            x_pos = menu_x1 + 20
            y_pos = menu_y1 + header_height + 50 + (i + 1) * 30
            cv2.putText(overlay, text, (x_pos, y_pos), font, font_scale, (220, 220, 220), thickness)

    close_x = menu_x2 - 40
    close_y = menu_y1 + 5
    close_w, close_h = 30, 20
    renderer.menu_system.close_button_rect = (close_x, close_y, close_w, close_h)
    cv2.rectangle(overlay, (close_x, close_y), (close_x + close_w, close_y + close_h), (0, 0, 255), -1)
    cv2.rectangle(overlay, (close_x, close_y), (close_x + close_w, close_y + close_h), (0, 0, 0), 1)
    text_size = cv2.getTextSize("X", font, 0.5, 1)[0]
    text_x = close_x + (close_w - text_size[0]) // 2
    text_y = close_y + (close_h + text_size[1]) // 2
    cv2.putText(overlay, "X", (text_x, text_y), font, 0.5, (255, 255, 255), 1)

    back_x = menu_x1 + 20
    back_y = menu_y2 - 60
    back_w, back_h = 100, 30
    renderer.menu_system.back_button_rect = (back_x, back_y, back_w, back_h)
    cv2.rectangle(overlay, (back_x, back_y), (back_x + back_w, back_y + back_h), (200, 200, 200), -1)
    cv2.rectangle(overlay, (back_x, back_y), (back_x + back_w, back_y + back_h), (0, 0, 0), 1)
    text_size = cv2.getTextSize("Back", font, 0.5, 1)[0]
    text_x = back_x + (back_w - text_size[0]) // 2
    text_y = back_y + (back_h + text_size[1]) // 2
    cv2.putText(overlay, "Back", (text_x, text_y), font, 0.5, (0, 0, 0), 1)

    # Apply semi-transparency (same as HelpWindow)
    alpha = 0.95  # Match the opacity of HelpWindow
    cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)
    return frame

def draw_settings_menu(renderer, frame):
    """Draw the settings menu with configurable options."""
    overlay = frame.copy()
    h, w = frame.shape[:2]

    # Use the menu position from MenuSystem, default to w//4, h//4 if not set
    if renderer.menu_system.menu_pos_x is None or renderer.menu_system.menu_pos_y is None:
        renderer.menu_system.menu_pos_x = w // 4
        renderer.menu_system.menu_pos_y = h // 4

    menu_x1 = renderer.menu_system.menu_pos_x
    menu_y1 = renderer.menu_system.menu_pos_y
    menu_x2 = menu_x1 + (w * 3 // 4)  # Increased width to 3/4 of the screen to accommodate two columns
    menu_y2 = menu_y1 + (h // 2)

    # Ensure the menu stays within the window bounds
    menu_x1 = max(0, min(menu_x1, w - (menu_x2 - menu_x1)))
    menu_y1 = max(0, min(menu_y1, h - (menu_y2 - menu_y1)))
    menu_x2 = menu_x1 + (w * 3 // 4)
    menu_y2 = menu_y1 + (h // 2)

    renderer.menu_system.menu_pos_x = menu_x1
    renderer.menu_system.menu_pos_y = menu_y1

    renderer.menu_system.menu_area = (menu_x1, menu_y1, menu_x2 - menu_x1, menu_y2 - menu_y1)

    # Draw the menu background
    cv2.rectangle(overlay, (menu_x1, menu_y1), (menu_x2, menu_y2), (100, 100, 100), -1)
    cv2.rectangle(overlay, (menu_x1, menu_y1), (menu_x2, menu_y2), (150, 150, 150), 2)

    # Draw a draggable header
    header_height = 30
    cv2.rectangle(overlay, (menu_x1, menu_y1), (menu_x2, menu_y1 + header_height), (80, 80, 80), -1)
    cv2.rectangle(overlay, (menu_x1, menu_y1), (menu_x2, menu_y1 + header_height), (150, 150, 150), 1)
    renderer.menu_system.header_rect = (menu_x1, menu_y1, menu_x2 - menu_x1, header_height)

    font = cv2.FONT_HERSHEY_DUPLEX
    font_scale = 0.7
    thickness = 2

    title = "Settings"
    text_size = cv2.getTextSize(title, font, font_scale, thickness)[0]
    x_pos = menu_x1 + ((menu_x2 - menu_x1) - text_size[0]) // 2
    y_pos = menu_y1 + header_height // 2 + text_size[1] // 2
    cv2.putText(overlay, title, (x_pos, y_pos), font, font_scale, (220, 220, 220), thickness)

    font_scale = 0.5
    thickness = 1
    renderer.menu_system.menu_item_rects = []

    # Define settings items with their labels, keys, and types
    settings_items = [
        ("White Ball Detection", "white_ball_detection", "toggle"),
        ("Red Ball Detection", "red_ball_detection", "toggle"),
        ("Game Sounds", "game_sounds", "toggle"),
        ("Background Music", "background_music", "toggle"),
        ("Confidence Threshold", "detection_confidence_threshold", "slider", 0.0, 1.0, 0.01),
        ("Radius Tolerance", "detection_radius_tolerance", "slider", 0.0, 50.0, 1.0),
        ("Area Min", "detection_area_min", "slider", 0.0, 1000.0, 10.0),
        ("Area Max", "detection_area_max", "slider", 0.0, 5000.0, 100.0),
        ("Circularity Min", "detection_circularity_min", "slider", 0.0, 1.0, 0.01),
        ("Circularity Max", "detection_circularity_max", "slider", 0.0, 2.0, 0.01),
    ]

    # Split items into toggles (left column) and sliders (right column)
    toggles = [item for item in settings_items if item[2] == "toggle"]
    sliders = [item for item in settings_items if item[2] == "slider"]

    # Calculate column positions
    column_width = (menu_x2 - menu_x1 - 60) // 2  # Two columns with 20px padding on sides and 20px between columns
    left_column_x = menu_x1 + 20
    right_column_x = left_column_x + column_width + 20

    line_height = 40

    # Draw toggles in the left column
    for idx, (label, key, item_type, *slider_args) in enumerate(toggles):
        x_pos = left_column_x
        y_pos = menu_y1 + header_height + 30 + idx * line_height
        color = (250, 206, 135) if idx == renderer.menu_system.selection else (220, 220, 220)

        value = getattr(renderer.menu_system.settings.config, key)
        display_text = f"{label}: {'On' if value else 'Off'}"
        text_size = cv2.getTextSize(display_text, font, font_scale, thickness)[0]
        toggle_x = x_pos + text_size[0] + 10
        toggle_y = y_pos - 10
        toggle_width, toggle_height = 50, 20
        renderer.draw_toggle(overlay, toggle_x, toggle_y, toggle_width, toggle_height, value)
        rect_x = toggle_x
        rect_y = toggle_y
        rect_w = toggle_width
        rect_h = toggle_height
        renderer.menu_system.menu_item_rects.append((rect_x, rect_y, rect_w, rect_h, idx))
        cv2.putText(overlay, display_text, (x_pos, y_pos), font, font_scale, color, thickness)

    # Draw sliders in the right column
    for idx, (label, key, item_type, *slider_args) in enumerate(sliders, start=len(toggles)):
        x_pos = right_column_x
        y_pos = menu_y1 + header_height + 30 + (idx - len(toggles)) * line_height
        color = (250, 206, 135) if idx == renderer.menu_system.selection else (220, 220, 220)

        min_val, max_val, step = slider_args
        value = getattr(renderer.menu_system.settings.config, key)
        display_text = f"{label}: {value:.2f}"
        text_size = cv2.getTextSize(display_text, font, font_scale, thickness)[0]
        slider_x = x_pos + text_size[0] + 10
        slider_y = y_pos - 5
        slider_width = 100
        slider_height = 10
        slider_pos = slider_x + int((value - min_val) / (max_val - min_val) * slider_width)
        cv2.rectangle(overlay, (slider_x, slider_y), (slider_x + slider_width, slider_y + slider_height), (150, 150, 150), -1)
        cv2.rectangle(overlay, (slider_x, slider_y), (slider_pos, slider_y + slider_height), (255, 255, 0), -1)
        cv2.rectangle(overlay, (slider_x, slider_y), (slider_x + slider_width, slider_y + slider_height), (200, 200, 200), 1)
        renderer.menu_system.menu_item_rects.append({
            "type": "slider",
            "rect": (slider_x, slider_y, slider_width, slider_height),
            "key": key,
            "min_val": min_val,
            "max_val": max_val,
            "step": step,
            "index": idx
        })
        cv2.putText(overlay, display_text, (x_pos, y_pos), font, font_scale, color, thickness)

    close_x = menu_x2 - 40
    close_y = menu_y1 + 5
    close_w, close_h = 30, 20
    renderer.menu_system.close_button_rect = (close_x, close_y, close_w, close_h)
    cv2.rectangle(overlay, (close_x, close_y), (close_x + close_w, close_y + close_h), (0, 0, 255), -1)
    cv2.rectangle(overlay, (close_x, close_y), (close_x + close_w, close_y + close_h), (0, 0, 0), 1)
    text_size = cv2.getTextSize("X", font, 0.5, 1)[0]
    text_x = close_x + (close_w - text_size[0]) // 2
    text_y = close_y + (close_h + text_size[1]) // 2
    cv2.putText(overlay, "X", (text_x, text_y), font, 0.5, (255, 255, 255), 1)

    # Draw the "Back" button
    back_x = menu_x1 + 20
    back_y = menu_y2 - 60
    back_w, back_h = 100, 30
    renderer.menu_system.back_button_rect = (back_x, back_y, back_w, back_h)
    cv2.rectangle(overlay, (back_x, back_y), (back_x + back_w, back_y + back_h), (200, 200, 200), -1)
    cv2.rectangle(overlay, (back_x, back_y), (back_x + back_w, back_y + back_h), (0, 0, 0), 1)
    text_size = cv2.getTextSize("Back", font, 0.5, 1)[0]
    text_x = back_x + (back_w - text_size[0]) // 2
    text_y = back_y + (back_h + text_size[1]) // 2
    cv2.putText(overlay, "Back", (text_x, text_y), font, 0.5, (0, 0, 0), 1)

    # Draw the "Reset to Defaults" button next to the "Back" button
    reset_x = back_x + back_w + 20  # Place it to the right of the "Back" button
    reset_y = menu_y2 - 60
    reset_w, reset_h = 150, 30
    renderer.menu_system.reset_button_rect = (reset_x, reset_y, reset_w, reset_h)
    cv2.rectangle(overlay, (reset_x, reset_y), (reset_x + reset_w, reset_y + reset_h), (200, 200, 200), -1)
    cv2.rectangle(overlay, (reset_x, reset_y), (reset_x + reset_w, reset_y + reset_h), (0, 0, 0), 1)
    text_size = cv2.getTextSize("Reset to Defaults", font, 0.5, 1)[0]
    text_x = reset_x + (reset_w - text_size[0]) // 2
    text_y = reset_y + (reset_h + text_size[1]) // 2
    cv2.putText(overlay, "Reset to Defaults", (text_x, text_y), font, 0.5, (0, 0, 0), 1)

    # Apply semi-transparency (same as HelpWindow)
    alpha = 0.95  # Match the opacity of HelpWindow
    cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)
    return frame

def draw_game_over_menu(renderer, frame):
    """Draw the game over menu with the final score."""
    overlay = frame.copy()
    h, w = frame.shape[:2]

    # Use the menu position from MenuSystem, default to w//4, h//4 if not set
    if renderer.menu_system.menu_pos_x is None or renderer.menu_system.menu_pos_y is None:
        renderer.menu_system.menu_pos_x = w // 4
        renderer.menu_system.menu_pos_y = h // 4

    menu_x1 = renderer.menu_system.menu_pos_x
    menu_y1 = renderer.menu_system.menu_pos_y
    menu_x2 = menu_x1 + (w // 2)
    menu_y2 = menu_y1 + (h // 2)

    # Ensure the menu stays within the window bounds
    menu_x1 = max(0, min(menu_x1, w - (menu_x2 - menu_x1)))
    menu_y1 = max(0, min(menu_y1, h - (menu_y2 - menu_y1)))
    menu_x2 = menu_x1 + (w // 2)
    menu_y2 = menu_y1 + (h // 2)

    renderer.menu_system.menu_pos_x = menu_x1
    renderer.menu_system.menu_pos_y = menu_y1

    renderer.menu_system.menu_area = (menu_x1, menu_y1, menu_x2 - menu_x1, menu_y2 - menu_y1)

    # Draw the menu background
    cv2.rectangle(overlay, (menu_x1, menu_y1), (menu_x2, menu_y2), (100, 100, 100), -1)
    cv2.rectangle(overlay, (menu_x1, menu_y1), (menu_x2, menu_y2), (150, 150, 150), 2)

    # Draw a draggable header
    header_height = 30
    cv2.rectangle(overlay, (menu_x1, menu_y1), (menu_x2, menu_y1 + header_height), (80, 80, 80), -1)
    cv2.rectangle(overlay, (menu_x1, menu_y1), (menu_x2, menu_y1 + header_height), (150, 150, 150), 1)
    renderer.menu_system.header_rect = (menu_x1, menu_y1, menu_x2 - menu_x1, header_height)

    font = cv2.FONT_HERSHEY_DUPLEX
    font_scale = 0.7
    thickness = 2
    text = f"Game Over! Final Score: {renderer.menu_system.total_score}"
    text_size = cv2.getTextSize(text, font, font_scale, thickness)[0]
    x_pos = menu_x1 + ((menu_x2 - menu_x1) - text_size[0]) // 2
    y_pos = menu_y1 + (menu_y2 - menu_y1) // 2
    cv2.putText(overlay, text, (x_pos, y_pos), font, font_scale, (220, 220, 220), thickness)

    close_x = menu_x2 - 40
    close_y = menu_y1 + 5
    close_w, close_h = 30, 20
    renderer.menu_system.close_button_rect = (close_x, close_y, close_w, close_h)
    cv2.rectangle(overlay, (close_x, close_y), (close_x + close_w, close_y + close_h), (0, 0, 255), -1)
    cv2.rectangle(overlay, (close_x, close_y), (close_x + close_w, close_y + close_h), (0, 0, 0), 1)
    text_size = cv2.getTextSize("X", font, 0.5, 1)[0]
    text_x = close_x + (close_w - text_size[0]) // 2
    text_y = close_y + (close_h + text_size[1]) // 2
    cv2.putText(overlay, "X", (text_x, text_y), font, 0.5, (255, 255, 255), 1)

    back_x = menu_x1 + 20
    back_y = menu_y2 - 60
    back_w, back_h = 100, 30
    renderer.menu_system.back_button_rect = (back_x, back_y, back_w, back_h)
    cv2.rectangle(overlay, (back_x, back_y), (back_x + back_w, back_y + back_h), (200, 200, 200), -1)
    cv2.rectangle(overlay, (back_x, back_y), (back_x + back_w, back_y + back_h), (0, 0, 0), 1)
    text_size = cv2.getTextSize("Back", font, 0.5, 1)[0]
    text_x = back_x + (back_w - text_size[0]) // 2
    text_y = back_y + (back_h + text_size[1]) // 2
    cv2.putText(overlay, "Back", (text_x, text_y), font, 0.5, (0, 0, 0), 1)

    # Apply semi-transparency (same as HelpWindow)
    alpha = 0.95  # Match the opacity of HelpWindow
    cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)
    return frame