import cv2
from menu_renderer_base import MenuRenderer

def draw_text_page(renderer, frame, items, title):
    """Draw a text page (e.g., Main Menu, Help, About, Mode Selection) with the given items and title."""
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
    title_font_scale = 0.7
    item_font_scale = 0.6
    thickness = 1

    # Draw title
    text_size = cv2.getTextSize(title, font, title_font_scale, thickness)[0]
    x_pos = menu_x1 + ((menu_x2 - menu_x1) - text_size[0]) // 2
    y_pos = menu_y1 + header_height // 2 + text_size[1] // 2
    cv2.putText(overlay, title, (x_pos, y_pos), font, title_font_scale, (220, 220, 220), thickness)

    back_button_height = 30
    back_button_margin = 60
    line_height = 40
    renderer.menu_system.menu_item_rects = []

    # Handle main menu and mode selection (both use a list of items)
    if title in ["Main Menu", "Select Game Mode"]:
        num_items = len(items)
        items_per_column = (num_items + 1) // 2  # Split items across two columns
        column_width = ((menu_x2 - menu_x1) - 60) // 2  # Two columns with padding
        left_column_x = menu_x1 + 20
        right_column_x = left_column_x + column_width + 20

        for idx, (item_text, _) in enumerate(items):
            if idx < items_per_column:
                x_pos = left_column_x
                col_idx = idx
            else:
                x_pos = right_column_x
                col_idx = idx - items_per_column

            y_pos = menu_y1 + header_height + 30 + col_idx * line_height
            color = (250, 206, 135) if idx == renderer.menu_system.selection else (220, 220, 220)
            text_size = cv2.getTextSize(item_text, font, item_font_scale, thickness)[0]
            rect_x = x_pos
            rect_y = y_pos - text_size[1]
            rect_w = text_size[0] + 20
            rect_h = text_size[1] + 10
            renderer.menu_system.menu_item_rects.append((rect_x, rect_y, rect_w, rect_h, idx))
            cv2.putText(overlay, item_text, (x_pos, y_pos), font, item_font_scale, color, thickness)
    # Handle help page (text is a string)
    elif title == "Help":
        text_area_height = (menu_y2 - menu_y1) - header_height - back_button_margin - back_button_height - 10
        max_lines = int(text_area_height // line_height)
        max_width = (menu_x2 - menu_x1) - 40
        wrapped_lines = renderer.wrap_text(items, font, item_font_scale, thickness, max_width)
        for i, line in enumerate(wrapped_lines[:max_lines]):
            y_pos = menu_y1 + header_height + 30 + i * 20
            cv2.putText(overlay, line, (menu_x1 + 20, y_pos), font, item_font_scale, (220, 220, 220), thickness)
    # Handle about page
    elif title == "About":
        about_text = "Whiffle Game v 9.2, Ideas by Blake Weibling coding by Grok"
        text_size = cv2.getTextSize(about_text, font, item_font_scale, thickness)[0]
        text_x = menu_x1 + ((menu_x2 - menu_x1) - text_size[0]) // 2
        text_y = menu_y1 + header_height + 30
        cv2.putText(overlay, about_text, (text_x, text_y), font, item_font_scale, (220, 220, 220), thickness)

        small_img = cv2.imread("logo.png")
        if small_img is not None:
            small_img = cv2.resize(small_img, (100, 100))
            img_h, img_w = small_img.shape[:2]
            img_x = menu_x1 + ((menu_x2 - menu_x1) - img_w) // 2
            img_y = text_y + text_size[1] + 20
            if img_y + img_h < menu_y2 - back_button_margin - back_button_height:
                overlay[img_y:img_y + img_h, img_x:img_x + img_w] = small_img
                renderer.menu_system.image_rect = (img_x, img_y, img_w, img_h)
            else:
                renderer.menu_system.image_rect = None
        else:
            print("Warning: Could not load logo.png for About page")
            renderer.menu_system.image_rect = None

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