import cv2
import numpy as np
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
    items = [
        (f"White Ball Detection: {'On' if renderer.menu_system.settings.config.white_ball_detection else 'Off'}",
         lambda: renderer.menu_system.settings.toggle('white_ball_detection')),
        (f"Red Ball Detection: {'On' if renderer.menu_system.settings.config.red_ball_detection else 'Off'}",
         lambda: renderer.menu_system.settings.toggle('red_ball_detection')),
        (f"Game Sounds: {'On' if renderer.menu_system.settings.config.game_sounds else 'Off'}",
         lambda: renderer.menu_system.settings.toggle('game_sounds')),
        (f"Background Music: {'On' if renderer.menu_system.settings.config.background_music else 'Off'}",
         lambda: renderer.menu_system.settings.toggle('background_music'))
    ]
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

    title = "Settings"
    text_size = cv2.getTextSize(title, font, font_scale, thickness)[0]
    x_pos = menu_x1 + ((menu_x2 - menu_x1) - text_size[0]) // 2
    y_pos = menu_y1 + header_height // 2 + text_size[1] // 2
    cv2.putText(overlay, title, (x_pos, y_pos), font, font_scale, (220, 220, 220), thickness)

    renderer.menu_system.menu_item_rects = []
    toggle_width, toggle_height = 50, 20
    for i, (label, action) in enumerate(items):
        x_pos = menu_x1 + 20
        y_pos = menu_y1 + header_height + 30 + i * 40
        color = (250, 206, 135) if i == renderer.menu_system.selection else (220, 220, 220)

        text_size = cv2.getTextSize(label, font, font_scale, thickness)[0]
        toggle_x = x_pos + text_size[0] + 10
        toggle_y = y_pos - toggle_height // 2
        state = "On" in label
        renderer.draw_toggle(overlay, toggle_x, toggle_y, toggle_width, toggle_height, state)
        rect_x = toggle_x
        rect_y = toggle_y
        rect_w = toggle_width
        rect_h = toggle_height
        renderer.menu_system.menu_item_rects.append((rect_x, rect_y, rect_w, rect_h, i))

        cv2.putText(overlay, label, (x_pos, y_pos), font, font_scale, color, thickness)

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