# sound_manager.py
import pygame
import os

class SoundManager:
    """Manages sound effects and background music for the game."""
    def __init__(self, menu_settings):
        pygame.mixer.init()
        self.menu_settings = menu_settings
        self.background_music = None
        self.sound_effects = {
            "score": None,
            "game_over": None,
            "menu_click": None
        }
        self.load_sounds()

    def load_sounds(self):
        """Load sound files from the sounds directory."""
        sound_dir = "sounds"
        if not os.path.exists(sound_dir):
            os.makedirs(sound_dir)
            print(f"Created {sound_dir} directory. Please add sound files.")
            return

        music_path = os.path.join(sound_dir, "background_music.mp3")
        if os.path.exists(music_path):
            self.background_music = music_path
        else:
            print(f"Warning: {music_path} not found.")

        effects = {
            "score": "score_effect.wav",
            "game_over": "game_over.wav",
            "menu_click": "menu_click.wav"
        }
        for key, filename in effects.items():
            path = os.path.join(sound_dir, filename)
            if os.path.exists(path):
                self.sound_effects[key] = pygame.mixer.Sound(path)
            else:
                print(f"Warning: {path} not found.")

    def play_background_music(self):
        """Play background music if enabled in settings."""
        if (self.menu_settings.config.background_music and 
            self.background_music and not pygame.mixer.music.get_busy()):
            pygame.mixer.music.load(self.background_music)
            pygame.mixer.music.set_volume(0.5)
            pygame.mixer.music.play(-1)

    def stop_background_music(self):
        """Stop background music if currently playing."""
        if pygame.mixer.music.get_busy():
            pygame.mixer.music.stop()

    def play_sound_effect(self, effect_name):
        """Play a sound effect if enabled in settings."""
        if (self.menu_settings.config.game_sounds and 
            effect_name in self.sound_effects and 
            self.sound_effects[effect_name]):
            self.sound_effects[effect_name].set_volume(0.7)
            self.sound_effects[effect_name].play()

    def update_settings(self):
        """Update sound settings based on the current configuration."""
        if self.menu_settings.config.background_music:
            self.play_background_music()
        else:
            self.stop_background_music()