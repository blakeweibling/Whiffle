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
                if self.menu_system.selection < self.menu_system.scroll_offset:
                    self.menu_system.scroll_offset = self.menu_system.selection
                return True
            elif key in [ord('s'), 84]:  # S or Down arrow
                self.menu_system.selection = min(num_items - 1, self.menu_system.selection + 1)
                if self.menu_system.selection >= self.menu_system.scroll_offset + 6:  # Adjust based on max visible items
                    self.menu_system.scroll_offset = self.menu_system.selection - 5
                return True
            elif key == 13:  # Enter
                if 0 <= self.menu_system.selection < num_items:
                    _, action = menu["items"][self.menu_system.selection]
                    action()
                return True

        elif self.menu_system.state == "settings":
            num_items = len(self.menu_system.get_current_menu()["items"])
            if key in [ord('w'), 82]:  # W or Up arrow
                self.menu_system.selection = max(0, self.menu_system.selection - 1)
                if self.menu_system.selection < self.menu_system.scroll_offset:
                    self.menu_system.scroll_offset = self.menu_system.selection
                return True
            elif key in [ord('s'), 84]:  # S or Down arrow
                self.menu_system.selection = min(num_items - 1, self.menu_system.selection + 1)
                if self.menu_system.selection >= self.menu_system.scroll_offset + 6:
                    self.menu_system.scroll_offset = self.menu_system.selection - 5
                return True
            elif key == 13:  # Enter
                menu = self.menu_system.get_current_menu()
                if 0 <= self.menu_system.selection < len(menu["items"]):
                    _, action = menu["items"][self.menu_system.selection]
                    action()
                return True
            elif key in [ord('a'), 81]:  # A or Left arrow
                if self.menu_system.selection >= 4:  # Sliders start after toggles
                    idx = self.menu_system.selection
                    setting_name = ["detection_confidence_threshold", "detection_radius_tolerance", 
                                    "detection_area_min", "detection_area_max", 
                                    "detection_circularity_min", "detection_circularity_max"][idx - 4]
                    value = getattr(self.menu_system.settings.config, setting_name)
                    min_val = 0.0 if "threshold" in setting_name else 0.0 if "min" in setting_name else 1.0
                    max_val = 1.0 if "threshold" in setting_name or "circularity" in setting_name else 5000.0 if "area_max" in setting_name else 1000.0
                    step = 0.01 if "threshold" in setting_name or "circularity" in setting_name else 10.0
                    new_value = max(min_val, value - step)
                    setattr(self.menu_system.settings.config, setting_name, new_value)
                    self.menu_system.settings.save_config()
                    print(f"Updated {setting_name} to {new_value}")
                return True
            elif key in [ord('d'), 83]:  # D or Right arrow
                if self.menu_system.selection >= 4:
                    idx = self.menu_system.selection
                    setting_name = ["detection_confidence_threshold", "detection_radius_tolerance", 
                                    "detection_area_min", "detection_area_max", 
                                    "detection_circularity_min", "detection_circularity_max"][idx - 4]
                    value = getattr(self.menu_system.settings.config, setting_name)
                    min_val = 0.0 if "threshold" in setting_name else 0.0 if "min" in setting_name else 1.0
                    max_val = 1.0 if "threshold" in setting_name or "circularity" in setting_name else 5000.0 if "area_max" in setting_name else 1000.0
                    step = 0.01 if "threshold" in setting_name or "circularity" in setting_name else 10.0
                    new_value = min(max_val, value + step)
                    setattr(self.menu_system.settings.config, setting_name, new_value)
                    self.menu_system.settings.save_config()
                    print(f"Updated {setting_name} to {new_value}")
                return True

        elif self.menu_system.state == "help":
            if key in [ord('w'), 82]:  # W or Up arrow
                self.menu_system.scroll_offset = max(0, self.menu_system.scroll_offset - 1)
                return True
            elif key in [ord('s'), 84]:  # S or Down arrow
                self.menu_system.scroll_offset += 1
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