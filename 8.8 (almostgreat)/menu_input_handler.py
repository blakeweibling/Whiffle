# menu_input_handler.py
import cv2

class MenuInputHandler:
    """Handles user input for the menu system."""
    def __init__(self, menu_system):
        self.menu_system = menu_system

    def handle_input(self, key):
        """Handle keyboard input for menu navigation and actions."""
        if key == 27:  # Escape
            if self.menu_system.state == "closed":
                return False
            self.menu_system.set_state("closed")
            if self.menu_system.sound_manager:
                self.menu_system.sound_manager.update_settings()
            return True

        if self.menu_system.state == "closed":
            return False

        if key == 13:  # Enter
            if self.menu_system.state == "main_menu":
                menu_items = list(self.menu_system.current_menu.keys())
                selected_item = menu_items[self.menu_system.selection]
                action = self.menu_system.current_menu[selected_item]
                if isinstance(action, dict):
                    self.menu_system.menu_stack.append(self.menu_system.current_menu)
                    self.menu_system.current_menu = action
                    self.menu_system.selection = 0
                else:
                    action()
            elif self.menu_system.state == "settings":
                settings_items = [
                    ("White Ball Detection", "white_ball_detection"),
                    ("Red Ball Detection", "red_ball_detection"),
                    ("Game Sounds", "game_sounds"),
                    ("Background Music", "background_music"),
                    ("Confidence Threshold", "detection_confidence_threshold"),
                    ("Radius Tolerance", "detection_radius_tolerance"),
                    ("Area Min", "detection_area_min"),
                    ("Area Max", "detection_area_max"),
                    ("Circularity Min", "detection_circularity_min"),
                    ("Circularity Max", "detection_circularity_max"),
                ]
                if self.menu_system.selection < len(settings_items):
                    _, key = settings_items[self.menu_system.selection]
                    if key in ["white_ball_detection", "red_ball_detection", "game_sounds", "background_music"]:
                        self.menu_system.settings.toggle(key)
                        self.menu_system.save_settings()
            return True

        if key == ord('w') or key == 82:  # Up arrow
            self.menu_system.selection = max(0, self.menu_system.selection - 1)
            return True
        elif key == ord('s') or key == 84:  # Down arrow
            max_selection = len(self.menu_system.current_menu) - 1 if self.menu_system.state == "main_menu" else len(self.menu_system.menu_item_rects) - 1
            self.menu_system.selection = min(max_selection, self.menu_system.selection + 1)
            return True

        return False

    def mouse_callback(self, event, x, y, flags, param=None):
        """Handle mouse events for menu interaction."""
        if event == cv2.EVENT_LBUTTONDOWN:
            # Check if clicking the menu bar button
            if self.menu_system.button_rect:
                bx, by, bw, bh = self.menu_system.button_rect
                if bx <= x <= bx + bw and by <= y <= by + bh:
                    if self.menu_system.state == "closed":
                        self.menu_system.reset_menu()  # Reset menu state when opening
                        self.menu_system.set_state("main_menu")
                    else:
                        self.menu_system.set_state("closed")
                        if self.menu_system.sound_manager:
                            self.menu_system.sound_manager.update_settings()
                    print("Menu toggled via button")
                    return

            # Check if clicking the header for dragging
            if self.menu_system.header_rect and self.menu_system.state != "closed":
                hx, hy, hw, hh = self.menu_system.header_rect
                if hx <= x <= hx + hw and hy <= y <= hy + hh:
                    self.menu_system.is_dragging = True
                    self.menu_system.drag_offset_x = x - self.menu_system.menu_pos_x
                    self.menu_system.drag_offset_y = y - self.menu_system.menu_pos_y
                    return

            # Check if clicking a menu item
            for idx, item in enumerate(self.menu_system.menu_item_rects):
                if isinstance(item, dict) and item["type"] == "slider":
                    sx, sy, sw, sh = item["rect"]
                    if sx <= x <= sx + sw and sy <= y <= sy + sh:
                        self.menu_system.selection = idx
                        self.menu_system.is_dragging = True
                        self.update_slider_value(item, x)
                        return
                else:
                    # Handle both 4-tuples (main menu) and 5-tuples (settings toggles)
                    if isinstance(item, tuple):
                        if len(item) == 4:  # Main menu items
                            ix, iy, iw, ih = item
                            item_idx = idx
                        elif len(item) == 5:  # Settings toggle items
                            ix, iy, iw, ih, item_idx = item
                        else:
                            continue  # Skip malformed items
                    else:
                        continue  # Skip if item is not a tuple

                    if ix <= x <= ix + iw and iy <= y <= iy + ih:
                        self.menu_system.selection = idx
                        if self.menu_system.state == "main_menu":
                            menu_items = list(self.menu_system.current_menu.keys())
                            selected_item = menu_items[idx]
                            action = self.menu_system.current_menu[selected_item]
                            if isinstance(action, dict):
                                self.menu_system.menu_stack.append(self.menu_system.current_menu)
                                self.menu_system.current_menu = action
                                self.menu_system.selection = 0
                            else:
                                action()
                        elif self.menu_system.state == "settings":
                            settings_items = [
                                ("White Ball Detection", "white_ball_detection"),
                                ("Red Ball Detection", "red_ball_detection"),
                                ("Game Sounds", "game_sounds"),
                                ("Background Music", "background_music"),
                                ("Confidence Threshold", "detection_confidence_threshold"),
                                ("Radius Tolerance", "detection_radius_tolerance"),
                                ("Area Min", "detection_area_min"),
                                ("Area Max", "detection_area_max"),
                                ("Circularity Min", "detection_circularity_min"),
                                ("Circularity Max", "detection_circularity_max"),
                            ]
                            if idx < len(settings_items):
                                _, key = settings_items[idx]
                                if key in ["white_ball_detection", "red_ball_detection", "game_sounds", "background_music"]:
                                    self.menu_system.settings.toggle(key)
                                    self.menu_system.save_settings()
                        return

            # Check if clicking the back/close button
            if self.menu_system.back_button_rect and self.menu_system.state in ["settings", "leaderboard", "help", "about", "main_menu"]:
                bx, by, bw, bh = self.menu_system.back_button_rect
                if bx <= x <= bx + bw and by <= y <= by + bh:
                    if self.menu_system.menu_stack:
                        self.menu_system.current_menu = self.menu_system.menu_stack.pop()
                        self.menu_system.selection = 0
                        # If the stack is now empty, ensure we're in the main_menu state
                        if not self.menu_system.menu_stack:
                            self.menu_system.set_state("main_menu")
                    else:
                        self.menu_system.set_state("main_menu")
                    return
            if self.menu_system.close_button_rect and self.menu_system.state in ["main_menu", "settings", "leaderboard", "help", "about"]:
                cx, cy, cw, ch = self.menu_system.close_button_rect
                if cx <= x <= cx + cw and cy <= y <= cy + ch:
                    self.menu_system.set_state("closed")
                    if self.menu_system.sound_manager:
                        self.menu_system.sound_manager.update_settings()
                    return

        elif event == cv2.EVENT_MOUSEMOVE and self.menu_system.is_dragging:
            if self.menu_system.state != "closed":
                # Dragging the menu window
                if self.menu_system.header_rect:
                    hx, hy, hw, hh = self.menu_system.header_rect
                    if hx <= x <= hx + hw and hy <= y <= hy + hh:
                        self.menu_system.menu_pos_x = x - self.menu_system.drag_offset_x
                        self.menu_system.menu_pos_y = y - self.menu_system.drag_offset_y
                        return
                # Dragging a slider
                for idx, item in enumerate(self.menu_system.menu_item_rects):
                    if isinstance(item, dict) and item["type"] == "slider":
                        sx, sy, sw, sh = item["rect"]
                        if idx == self.menu_system.selection:
                            self.update_slider_value(item, x)
                            return

        elif event == cv2.EVENT_LBUTTONUP:
            self.menu_system.is_dragging = False

    def update_slider_value(self, item, x):
        """Update the value of a slider based on mouse position."""
        sx, sy, sw, sh = item["rect"]
        min_val = item["min_val"]
        max_val = item["max_val"]
        step = item["step"]
        key = item["key"]

        # Calculate the new value based on mouse position
        relative_x = max(0, min(sw, x - sx))
        value_range = max_val - min_val
        new_value = min_val + (relative_x / sw) * value_range

        # Round to the nearest step
        new_value = round(new_value / step) * step
        new_value = max(min_val, min(max_val, new_value))

        # Update the setting
        setattr(self.menu_system.settings.config, key, new_value)
        self.menu_system.save_settings()
        print(f"Updated {key} to {new_value}")