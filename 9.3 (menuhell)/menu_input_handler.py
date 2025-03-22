import cv2

class MenuInputHandler:
    """Handles user input for the MenuSystem, including keyboard and mouse events."""
    def __init__(self, menu_system):
        self.menu_system = menu_system

    def handle_input(self, key):
        """Handle keyboard input for the menu system."""
        if key == 27:  # Esc key
            if self.menu_system.state in ["main_menu", "settings", "leaderboard", "help", "about", "mode_selection", "game_over"]:
                if self.menu_system.menu_stack:
                    self.menu_system.current_menu = self.menu_system.menu_stack.pop()
                    self.menu_system.selection = 0
                    if not self.menu_system.menu_stack:
                        self.menu_system.set_state("main_menu")
                else:
                    self.menu_system.set_state("closed")
                    if self.menu_system.sound_manager:
                        self.menu_system.sound_manager.update_settings()
            return True

        if self.menu_system.state in ["main_menu", "mode_selection"]:
            menu = self.menu_system.get_current_menu()
            num_items = len(menu["items"]) if menu else 0

            if key in [ord('w'), 82]:  # W or Up arrow
                self.menu_system.selection = max(0, self.menu_system.selection - 1)
                return True
            elif key in [ord('s'), 84]:  # S or Down arrow
                self.menu_system.selection = min(num_items - 1, self.menu_system.selection + 1)
                return True
            elif key == 13:  # Enter
                if 0 <= self.menu_system.selection < num_items:
                    _, action = menu["items"][self.menu_system.selection]
                    action()
                return True

        elif self.menu_system.state == "help":
            if key in [ord('w'), 82]:  # W or Up arrow
                self.menu_system.scroll_offset = max(0, self.menu_system.scroll_offset - 1)
                return True
            elif key in [ord('s'), 84]:  # S or Down arrow
                self.menu_system.scroll_offset += 1
                return True

        elif self.menu_system.state == "settings":
            if key in [ord('w'), 82]:  # W or Up arrow
                self.menu_system.selection = max(0, self.menu_system.selection - 1)
                return True
            elif key in [ord('s'), 84]:  # S or Down arrow
                num_items = len(self.menu_system.get_current_menu()["items"])
                self.menu_system.selection = min(num_items - 1, self.menu_system.selection + 1)
                return True
            elif key == 13:  # Enter
                menu = self.menu_system.get_current_menu()
                if 0 <= self.menu_system.selection < len(menu["items"]):
                    _, action = menu["items"][self.menu_system.selection]
                    action()
                return True
            elif key in [ord('a'), 81]:  # A or Left arrow
                if self.menu_system.selection >= len(self.menu_system.get_current_menu()["items"]):
                    setting_name, _ = self.menu_system.settings_sliders[self.menu_system.selection - len(self.menu_system.get_current_menu()["items"])][1]
                    if setting_name in ["detection_confidence_threshold", "detection_radius_tolerance", "detection_area_min", "detection_area_max", "detection_circularity_min", "detection_circularity_max"]:
                        value = getattr(self.menu_system.settings.config, setting_name)
                        min_val = 0.0 if "threshold" in setting_name else 0.0 if "min" in setting_name else 1.0
                        max_val = 1.0 if "threshold" in setting_name or "circularity" in setting_name else 2000.0 if "area_max" in setting_name else 100.0
                        step = (max_val - min_val) / 20
                        new_value = max(min_val, value - step)
                        setattr(self.menu_system.settings.config, setting_name, new_value)
                        self.menu_system.settings.save_config()
                        print(f"Updated {setting_name} to {new_value}")
                return True
            elif key in [ord('d'), 83]:  # D or Right arrow
                if self.menu_system.selection >= len(self.menu_system.get_current_menu()["items"]):
                    setting_name, _ = self.menu_system.settings_sliders[self.menu_system.selection - len(self.menu_system.get_current_menu()["items"])][1]
                    if setting_name in ["detection_confidence_threshold", "detection_radius_tolerance", "detection_area_min", "detection_area_max", "detection_circularity_min", "detection_circularity_max"]:
                        value = getattr(self.menu_system.settings.config, setting_name)
                        min_val = 0.0 if "threshold" in setting_name else 0.0 if "min" in setting_name else 1.0
                        max_val = 1.0 if "threshold" in setting_name or "circularity" in setting_name else 2000.0 if "area_max" in setting_name else 100.0
                        step = (max_val - min_val) / 20
                        new_value = min(max_val, value + step)
                        setattr(self.menu_system.settings.config, setting_name, new_value)
                        self.menu_system.settings.save_config()
                        print(f"Updated {setting_name} to {new_value}")
                return True

        elif self.menu_system.state in ["leaderboard", "about", "game_over"]:
            if key in [ord('w'), 82]:  # W or Up arrow
                self.menu_system.selection = max(0, self.menu_system.selection - 1)
                return True
            elif key in [ord('s'), 84]:  # S or Down arrow
                num_items = len(self.menu_system.get_current_menu()["items"])
                self.menu_system.selection = min(num_items - 1, self.menu_system.selection + 1)
                return True

        return False

    def mouse_callback(self, event, x, y, flags, param=None):
        """Handle mouse events for the menu system."""
        # Only log significant events (clicks, wheel, etc.), not mouse movement
        if event == cv2.EVENT_LBUTTONDOWN:
            print(f"Mouse click at ({x}, {y})")
            # Log menu item rectangles
            if self.menu_system.state in ["main_menu", "mode_selection"]:
                print("Menu item rectangles:", self.menu_system.menu_item_rects)

            # Check close button
            if self.menu_system.close_button_rect and self.menu_system.state != "closed":
                cx, cy, cw, ch = self.menu_system.close_button_rect
                print(f"Close button rect: ({cx}, {cy}, {cw}, {ch})")
                if cx <= x <= cx + cw and cy <= y <= cy + ch:
                    self.menu_system.set_state("closed")
                    if self.menu_system.sound_manager:
                        self.menu_system.sound_manager.update_settings()
                    return

            # Check menu bar button
            if self.menu_system.button_rect:
                bx, by, bw, bh = self.menu_system.button_rect
                print(f"Menu bar button rect: ({bx}, {by}, {bw}, {bh})")
                if bx <= x <= bx + bw and by <= y <= by + bh:
                    if self.menu_system.state == "closed":
                        self.menu_system.reset_menu()
                        self.menu_system.set_state("main_menu")
                    else:
                        self.menu_system.set_state("closed")
                        if self.menu_system.sound_manager:
                            self.menu_system.sound_manager.update_settings()
                    return

            # Check logo click on About page
            if self.menu_system.state == "about" and self.menu_system.image_rect:
                ix, iy, iw, ih = self.menu_system.image_rect
                if ix <= x <= ix + iw and iy <= y <= iy + ih:
                    if param and hasattr(param, 'is_splash_active'):
                        param.is_splash_active = True
                    return

            # Check back button
            if self.menu_system.back_button_rect and self.menu_system.state in ["settings", "leaderboard", "help", "about", "main_menu", "mode_selection", "game_over"]:
                bx, by, bw, bh = self.menu_system.back_button_rect
                print(f"Back button rect: ({bx}, {by}, {bw}, {bh})")
                if bx <= x <= bx + bw and by <= y <= by + bh:
                    if self.menu_system.menu_stack:
                        self.menu_system.current_menu = self.menu_system.menu_stack.pop()
                        self.menu_system.selection = 0
                        if not self.menu_system.menu_stack:
                            self.menu_system.set_state("main_menu")
                    else:
                        self.menu_system.set_state("main_menu")
                    return

            # Handle settings menu interactions
            if self.menu_system.state == "settings":
                for idx, (rect, (setting_name, _)) in enumerate(self.menu_system.settings_sliders):
                    rx, ry, rw, rh = rect
                    if rx <= x <= rx + rw and ry <= y <= ry + rh:
                        if setting_name in ["detection_confidence_threshold", "detection_radius_tolerance", "detection_area_min", "detection_area_max", "detection_circularity_min", "detection_circularity_max"]:
                            value = getattr(self.menu_system.settings.config, setting_name)
                            min_val = 0.0 if "threshold" in setting_name else 0.0 if "min" in setting_name else 1.0
                            max_val = 1.0 if "threshold" in setting_name or "circularity" in setting_name else 2000.0 if "area_max" in setting_name else 100.0
                            slider_pos = (x - rx) / rw
                            new_value = min_val + (max_val - min_val) * slider_pos
                            new_value = max(min_val, min(max_val, new_value))
                            setattr(self.menu_system.settings.config, setting_name, new_value)
                            self.menu_system.settings.save_config()
                            print(f"Updated {setting_name} to {new_value}")
                        return

            # Handle menu item clicks
            if self.menu_system.state in ["main_menu", "mode_selection"]:
                menu = self.menu_system.get_current_menu()
                for idx, rect in enumerate(self.menu_system.menu_item_rects):
                    rx, ry, rw, rh, item_idx = rect
                    if rx <= x <= rx + rw and ry <= y <= ry + rh:
                        print(f"Clicked menu item {item_idx} at ({x}, {y}) within rect ({rx}, {ry}, {rw}, {rh})")
                        if 0 <= item_idx < len(menu["items"]):
                            self.menu_system.selection = item_idx
                            _, action = menu["items"][item_idx]
                            print(f"Executing action for item {item_idx}: {menu['items'][item_idx][0]}")
                            action()
                            return
                print(f"Missed click on menu items at ({x}, {y})")

        elif event == cv2.EVENT_RBUTTONDOWN:
            print(f"Right-click detected at ({x}, {y})")

        elif event == cv2.EVENT_MOUSEMOVE and flags & cv2.EVENT_FLAG_LBUTTON:
            if self.menu_system.state == "settings":
                for idx, (rect, (setting_name, _)) in enumerate(self.menu_system.settings_sliders):
                    rx, ry, rw, rh = rect
                    if rx <= x <= rx + rw and ry <= y <= ry + rh:
                        if setting_name in ["detection_confidence_threshold", "detection_radius_tolerance", "detection_area_min", "detection_area_max", "detection_circularity_min", "detection_circularity_max"]:
                            value = getattr(self.menu_system.settings.config, setting_name)
                            min_val = 0.0 if "threshold" in setting_name else 0.0 if "min" in setting_name else 1.0
                            max_val = 1.0 if "threshold" in setting_name or "circularity" in setting_name else 2000.0 if "area_max" in setting_name else 100.0
                            slider_pos = (x - rx) / rw
                            new_value = min_val + (max_val - min_val) * slider_pos
                            new_value = max(min_val, min(max_val, new_value))
                            setattr(self.menu_system.settings.config, setting_name, new_value)
                            self.menu_system.settings.save_config()
                            print(f"Updated {setting_name} to {new_value}")
                        return

        elif event == cv2.EVENT_MOUSEWHEEL:
            if self.menu_system.state == "help":
                if flags > 0:
                    self.menu_system.scroll_offset = max(0, self.menu_system.scroll_offset - 1)
                else:
                    self.menu_system.scroll_offset += 1
                print(f"Scroll offset: {self.menu_system.scroll_offset}")