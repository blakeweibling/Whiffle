import cv2

class MenuInputHandler:
    """Handles user input for the menu system, including keyboard and mouse events."""
    def __init__(self, menu_system):
        self.menu_system = menu_system
        self.last_key = None
        self.last_key_time = 0
        self.key_repeat_delay = 0.5  # Initial delay before repeating
        self.key_repeat_rate = 0.1   # Rate of repetition after initial delay

    def handle_input(self, key):
        """Handle keyboard input for menu navigation and selection."""
        if key == -1:
            return False

        current_time = cv2.getTickCount() / cv2.getTickFrequency()
        if key == self.last_key and (current_time - self.last_key_time) < self.key_repeat_rate:
            return False

        if key != self.last_key:
            self.last_key = key
            self.last_key_time = current_time
        else:
            self.last_key_time = current_time

        if not self.menu_system.is_menu_active():
            if key == 27:  # Esc key
                self.menu_system.set_state("main_menu")
                self.menu_system.reset_menu()
                return True
            return False

        if key == 27:  # Esc key
            if self.menu_system.has_parent_menu():
                self.menu_system.current_menu = self.menu_system.menu_stack.pop()
                self.menu_system.set_state("main_menu")
            else:
                self.menu_system.set_state("closed")
                if self.menu_system.sound_manager:
                    self.menu_system.sound_manager.update_settings()
            return True

        if key == 13:  # Enter key
            menu = self.menu_system.get_current_menu()
            if 0 <= self.menu_system.selection < len(menu["items"]):
                _, action = menu["items"][self.menu_system.selection]
                action()
            return True

        if key in [ord('w'), ord('W'), 82]:  # W or Up arrow
            self.menu_system.selection = max(0, self.menu_system.selection - 1)
            if self.menu_system.state == "help":
                self.menu_system.scroll_offset = max(0, self.menu_system.scroll_offset - 1)
            return True

        if key in [ord('s'), ord('S'), 84]:  # S or Down arrow
            menu = self.menu_system.get_current_menu()
            max_selection = len(menu["items"]) - 1
            self.menu_system.selection = min(max_selection, self.menu_system.selection + 1)
            if self.menu_system.state == "help":
                all_items = [
                    ("Click 'New Game' to start playing", lambda: None),
                    ("W/S or Arrows: Navigate menu", lambda: None),
                    ("Enter: Select menu item", lambda: None),
                    ("Esc: Close menu", lambda: None),
                    ("Red balls: 2x points, White: 1x", lambda: None),
                    ("Half balls: 1.5x points", lambda: None),
                    ("'c': Calibrate zones", lambda: None),
                    ("'r': Reset score", lambda: None),
                    ("'q': Submit score when game ends", lambda: None),
                    ("'f': Flip camera horizontally", lambda: None),
                    ("'d': Toggle debug mode", lambda: None)
                ]
                max_scroll = max(0, len(all_items) - 9)  # Match your max_visible_items
                self.menu_system.scroll_offset = min(max_scroll, self.menu_system.scroll_offset + 1)
            return True

        return False

    def mouse_callback(self, event, x, y, flags, param=None):
        """Handle mouse events for menu interaction."""
        if event == cv2.EVENT_LBUTTONDOWN:
            print(f"Mouse clicked at ({x}, {y})")

            # Check close button first
            if self.menu_system.close_button_rect and self.menu_system.state != "closed":
                cx, cy, cw, ch = self.menu_system.close_button_rect
                print(f"Close button rect: ({cx}, {cy}, {cw}, {ch})")
                if cx <= x <= cx + cw and cy <= y <= cy + ch:
                    print("Close button clicked")
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
                        print("Menu opened via button")
                    else:
                        self.menu_system.set_state("closed")
                        if self.menu_system.sound_manager:
                            self.menu_system.sound_manager.update_settings()
                        print("Menu closed via button")
                    return

            # Check logo click on About page
            if self.menu_system.state == "about" and self.menu_system.image_rect:
                ix, iy, iw, ih = self.menu_system.image_rect
                if ix <= x <= ix + iw and iy <= y <= iy + ih:
                    print("Logo clicked on About page")
                    if param and hasattr(param, 'is_splash_active'):
                        param.is_splash_active = True
                    return

            # Check back button
            if self.menu_system.back_button_rect and self.menu_system.state in ["settings", "leaderboard", "help", "about", "main_menu", "mode_selection"]:
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

            # Handle slider clicks and dragging in settings
            if self.menu_system.state == "settings":
                for idx, item in enumerate(self.menu_system.menu_item_rects):
                    if isinstance(item, dict) and item["type"] == "slider":
                        sx, sy, sw, sh = item["rect"]
                        print(f"Slider item {idx}: ({sx}, {sy}, {sw}, {sh})")
                        if sx <= x <= sx + sw and sy <= y <= sy + sh:
                            self.menu_system.selection = idx
                            self.menu_system.is_dragging = True
                            self.update_slider_value(item, x)
                            return
                if self.menu_system.reset_button_rect:
                    rx, ry, rw, rh = self.menu_system.reset_button_rect
                    if rx <= x <= rx + rw and ry <= y <= ry + rh:
                        self.menu_system.settings.reset_to_defaults()
                        self.menu_system.save_settings()
                        return

            # Handle menu item clicks for main_menu and mode_selection states
            if self.menu_system.state in ["main_menu", "mode_selection"]:
                menu = self.menu_system.get_current_menu()
                for idx, rect in enumerate(self.menu_system.menu_item_rects):
                    if len(rect) < 5:  # Ensure rect has enough elements
                        continue
                    rx, ry, rw, rh, item_idx = rect
                    print(f"Checking menu item {item_idx}: ({rx}, {ry}, {rw}, {rh})")
                    if rx <= x <= rx + rw and ry <= y <= ry + rh:
                        if 0 <= item_idx < len(menu["items"]):
                            _, action = menu["items"][item_idx]
                            print(f"Clicked menu item: {menu['items'][item_idx][0]}")
                            action()
                            return

        elif event == cv2.EVENT_MOUSEWHEEL:
            if self.menu_system.state == "help":
                total_items = 11
                max_visible_items = 9
                if flags > 0:  # Wheel up
                    self.menu_system.selection = max(0, self.menu_system.selection - 1)
                    if self.menu_system.selection < self.menu_system.scroll_offset:
                        self.menu_system.scroll_offset = self.menu_system.selection
                elif flags < 0:  # Wheel down
                    self.menu_system.selection = min(total_items - 1, self.menu_system.selection + 1)
                    if self.menu_system.selection >= self.menu_system.scroll_offset + max_visible_items:
                        self.menu_system.scroll_offset = self.menu_system.selection - max_visible_items + 1
                return True

        elif event == cv2.EVENT_MOUSEMOVE and self.menu_system.is_dragging:
            if self.menu_system.state != "closed":
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

        relative_x = max(0, min(sw, x - sx))
        value_range = max_val - min_val
        new_value = min_val + (relative_x / sw) * value_range
        new_value = round(new_value / step) * step
        new_value = max(min_val, min(max_val, new_value))

        setattr(self.menu_system.settings.config, key, new_value)
        self.menu_system.save_settings()
        print(f"Updated {key} to {new_value}")