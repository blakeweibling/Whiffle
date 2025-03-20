# menu_input_handler.py
import cv2

class MenuInputHandler:
    """Handles keyboard and mouse input for the menu system, including dragging."""
    def __init__(self, menu_system):
        self.menu_system = menu_system

    def handle_input(self, key):
        """Handle keyboard input based on the current menu state."""
        # Handle input for Help, About, or Leaderboard states
        if self.menu_system.state in ["help", "about", "leaderboard"]:
            if key != 255:  # Any key to go back
                self.menu_system.set_state("main_menu")
            return True

        # Handle input for Settings state
        if self.menu_system.state == "settings":
            if key == 82:  # Up arrow
                self.menu_system.selection = (self.menu_system.selection - 1) % 4  # 4 settings items
            elif key == 84:  # Down arrow
                self.menu_system.selection = (self.menu_system.selection + 1) % 4
            elif key == 13:  # Enter
                if self.menu_system.selection == 0:
                    self.menu_system.settings.toggle('white_ball_detection')
                    self.menu_system.save_settings()
                elif self.menu_system.selection == 1:
                    self.menu_system.settings.toggle('red_ball_detection')
                    self.menu_system.save_settings()
                elif self.menu_system.selection == 2:
                    self.menu_system.settings.toggle('game_sounds')
                    self.menu_system.save_settings()
                elif self.menu_system.selection == 3:
                    self.menu_system.settings.toggle('background_music')
                    self.menu_system.save_settings()
                    self.menu_system.sound_manager.update_settings()
            elif key == 27:  # Escape
                self.menu_system.set_state("main_menu")
            return True

        # Handle input for Game Over state
        if self.menu_system.state == "game_over":
            if key != 255:
                self.menu_system.set_state("main_menu")
            return True

        # Handle input for Main Menu state
        if self.menu_system.state != "main_menu":
            return False

        menu_items = list(self.menu_system.current_menu.keys())
        if key == 82:  # Up arrow
            self.menu_system.selection = (self.menu_system.selection - 1) % len(menu_items)
        elif key == 84:  # Down arrow
            self.menu_system.selection = (self.menu_system.selection + 1) % len(menu_items)
        elif key == 13:  # Enter
            selected = menu_items[self.menu_system.selection]
            action = self.menu_system.current_menu[selected]
            if isinstance(action, dict):
                self.menu_system.menu_stack.append(self.menu_system.current_menu)
                self.menu_system.current_menu = action
                self.menu_system.selection = 0
            else:
                action()
                self.menu_system.current_menu = self.menu_system.options
                self.menu_system.menu_stack = []
                self.menu_system.selection = 0
        elif key == 27:  # Escape
            if self.menu_system.menu_stack:
                self.menu_system.current_menu = self.menu_system.menu_stack.pop()
                self.menu_system.selection = 0
            else:
                self.menu_system.current_menu = self.menu_system.options
                self.menu_system.menu_stack = []
                self.menu_system.set_state("closed")
                self.menu_system.selection = 0
        return True

    def mouse_callback(self, event, x, y, flags, param):
        """Handle mouse input based on the current menu state, including dragging."""
        # Check for menu bar button click
        if event == cv2.EVENT_LBUTTONDOWN:
            bx, by, bw, bh = self.menu_system.button_rect
            if bx <= x <= bx + bw and by <= y <= by + bh:
                if self.menu_system.state == "closed":
                    self.menu_system.set_state("main_menu")
                else:
                    self.menu_system.set_state("closed")
                print("Menu toggled via button")
                return

        # Handle clicks in Help, About, Game Over, or Leaderboard states
        if self.menu_system.state in ["help", "about", "game_over", "leaderboard"]:
            if self.menu_system.close_button_rect:
                cx, cy, cw, ch = self.menu_system.close_button_rect
                if event == cv2.EVENT_LBUTTONDOWN and cx <= x <= cx + cw and cy <= y <= cy + ch:
                    self.menu_system.set_state("main_menu")
                    print(f"{self.menu_system.state.capitalize()} closed via close button")
                    return

            if self.menu_system.back_button_rect:
                bx, by, bw, bh = self.menu_system.back_button_rect
                if event == cv2.EVENT_LBUTTONDOWN and bx <= x <= bx + bw and by <= y <= by + bh:
                    self.menu_system.set_state("main_menu")
                    print(f"{self.menu_system.state.capitalize()} closed via Back button")
                    return

            if self.menu_system.menu_area:
                mx, my, mw, mh = self.menu_system.menu_area
                if event == cv2.EVENT_LBUTTONDOWN and not (mx <= x <= mx + mw and my <= y <= my + mh):
                    self.menu_system.set_state("main_menu")
                    print(f"{self.menu_system.state.capitalize()} closed due to outside click")
                    return
            return

        # Handle clicks in Settings state
        if self.menu_system.state == "settings":
            if self.menu_system.close_button_rect:
                cx, cy, cw, ch = self.menu_system.close_button_rect
                if event == cv2.EVENT_LBUTTONDOWN and cx <= x <= cx + cw and cy <= y <= cy + ch:
                    self.menu_system.set_state("main_menu")
                    print("Settings closed via close button")
                    return

            if self.menu_system.back_button_rect:
                bx, by, bw, bh = self.menu_system.back_button_rect
                if event == cv2.EVENT_LBUTTONDOWN and bx <= x <= bx + bw and by <= y <= by + bh:
                    self.menu_system.set_state("main_menu")
                    print("Settings closed via Back button")
                    return

            if self.menu_system.menu_area:
                mx, my, mw, mh = self.menu_system.menu_area
                if event == cv2.EVENT_LBUTTONDOWN and not (mx <= x <= mx + mw and my <= y <= my + mh):
                    self.menu_system.set_state("main_menu")
                    print("Settings closed due to outside click")
                    return

            if event == cv2.EVENT_LBUTTONDOWN:
                for rect_x, rect_y, rect_w, rect_h, idx in self.menu_system.menu_item_rects:
                    if rect_x <= x <= rect_x + rect_w and rect_y <= y <= rect_y + rect_h:
                        self.menu_system.selection = idx
                        if idx == 0:
                            self.menu_system.settings.toggle('white_ball_detection')
                            self.menu_system.save_settings()
                        elif idx == 1:
                            self.menu_system.settings.toggle('red_ball_detection')
                            self.menu_system.save_settings()
                        elif idx == 2:
                            self.menu_system.settings.toggle('game_sounds')
                            self.menu_system.save_settings()
                        elif idx == 3:
                            self.menu_system.settings.toggle('background_music')
                            self.menu_system.save_settings()
                            self.menu_system.sound_manager.update_settings()
                        break
            return

        # Handle clicks in Main Menu state
        if self.menu_system.state != "main_menu":
            return

        if self.menu_system.close_button_rect:
            cx, cy, cw, ch = self.menu_system.close_button_rect
            if event == cv2.EVENT_LBUTTONDOWN and cx <= x <= cx + cw and cy <= y <= cy + ch:
                self.menu_system.current_menu = self.menu_system.options
                self.menu_system.menu_stack = []
                self.menu_system.set_state("closed")
                self.menu_system.selection = 0
                print("Menu closed via close button")
                return

        # Handle dragging for active menu states (after checking close button)
        if self.menu_system.state in ["main_menu", "settings", "help", "about", "game_over", "leaderboard"]:
            if self.menu_system.header_rect:
                hx, hy, hw, hh = self.menu_system.header_rect
                if event == cv2.EVENT_LBUTTONDOWN and hx <= x <= hx + hw and hy <= y <= hy + hh:
                    self.menu_system.is_dragging = True
                    self.menu_system.drag_offset_x = x - self.menu_system.menu_pos_x
                    self.menu_system.drag_offset_y = y - self.menu_system.menu_pos_y
                    return
                elif event == cv2.EVENT_MOUSEMOVE and self.menu_system.is_dragging:
                    self.menu_system.menu_pos_x = x - self.menu_system.drag_offset_x
                    self.menu_system.menu_pos_y = y - self.menu_system.drag_offset_y
                    return
                elif event == cv2.EVENT_LBUTTONUP and self.menu_system.is_dragging:
                    self.menu_system.is_dragging = False
                    return

        if self.menu_system.menu_area:
            mx, my, mw, mh = self.menu_system.menu_area
            if event == cv2.EVENT_LBUTTONDOWN and not (mx <= x <= mx + mw and my <= y <= my + mh):
                self.menu_system.current_menu = self.menu_system.options
                self.menu_system.menu_stack = []
                self.menu_system.set_state("closed")
                self.menu_system.selection = 0
                print("Menu closed due to outside click")
                return

        if self.menu_system.back_button_rect and self.menu_system.menu_stack:
            bx, by, bw, bh = self.menu_system.back_button_rect
            if event == cv2.EVENT_LBUTTONDOWN and bx <= x <= bx + bw and by <= y <= by + bh:
                self.menu_system.current_menu = self.menu_system.menu_stack.pop()
                self.menu_system.selection = 0
                print("Navigated back via Back button")
                return

        if event == cv2.EVENT_LBUTTONDOWN:
            for rect_x, rect_y, rect_w, rect_h, idx in self.menu_system.menu_item_rects:
                if rect_x <= x <= rect_x + rect_w and rect_y <= y <= rect_y + rect_h:
                    self.menu_system.selection = idx
                    menu_items = list(self.menu_system.current_menu.keys())
                    selected = menu_items[self.menu_system.selection]
                    action = self.menu_system.current_menu[selected]
                    if isinstance(action, dict):
                        self.menu_system.menu_stack.append(self.menu_system.current_menu)
                        self.menu_system.current_menu = action
                        self.menu_system.selection = 0
                    else:
                        action()
                        self.menu_system.current_menu = self.menu_system.options
                        self.menu_system.menu_stack = []
                        self.menu_system.selection = 0
                    break