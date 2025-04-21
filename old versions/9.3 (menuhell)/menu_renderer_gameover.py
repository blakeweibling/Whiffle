import cv2
from menu_renderer_base import MenuRenderer

def draw_game_over_menu(renderer, frame):
    """Draw the game over menu with the final score."""
    overlay = frame.copy()
    h, w = frame.shape[:2]

    if renderer.menu_system.menu_pos_x is None or renderer.menu_system.menu_pos_y is None:
        renderer.menu_system.menu_pos_x = w // 4
        renderer.menu_system.menu_pos_y = h // 4

    menu_x1 = renderer.menu_system.menu_pos_x
    menu_y1 = renderer.menu_system.menu_pos_y
    menu_x2 = menu_x1 + (w // 2)
    menu_y2 = menu_y1 + (h // 2)

    menu_x1 = max(0, min(menu_x1, w - (menu_x2 - menu_x1)))
    menu_y1 = max(0, min(menu_y1, h - (menu_y2 - menu_y1)))
    menu_x2 = menu_x1 + (w // 2)
    menu_y2 = menu_y1 + (h // 2)

    renderer.menu_system.menu_pos_x = menu_x1
    renderer.menu_system.menu_pos_y = menu_y1

    renderer.menu_system.menu_area = (menu_x1, menu_y1, menu_x2 - menu_x1, menu_y2 - menu_y1)

    cv2.rectangle(overlay, (menu_x1, menu_y1), (menu_x2, menu_y2), (100, 100, 100), -1)
    cv2.rectangle(overlay, (menu_x1, menu_y1), (menu_x2, menu_y2), (150, 150, 150), 2)

    header_height = 30
    cv2.rectangle(overlay, (menu_x1, menu_y1), (menu_x2, menu_y1 + header_height), (80, 80, 80), -1)
    cv2.rectangle(overlay, (menu_x1, menu_y1), (menu_x2, menu_y1 + header_height), (150, 150, 150), 1)
    renderer.menu_system.header_rect = (menu_x1, menu_y1, menu_x2 - menu_x1, header_height)

    font = cv2.FONT_HERSHEY_SIMPLEX
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

    alpha = 0.95
    cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)
    return frame