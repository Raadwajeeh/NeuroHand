import os
import pygame

class AudioManager:
    def __init__(self, base_path: str):
        self.base_path = base_path
        self.music_volume = 0.12
        self.sfx_volume = 0.68
        self.hover_volume = 0.14
        self._music_key = None
        self._sfx = {}
        self._tts = None

        try:
            import pyttsx3
            self._tts = pyttsx3.init()
            try:
                self._tts.setProperty("rate", 185)
                self._tts.setProperty("volume", 0.9)
            except Exception:
                pass
        except Exception:
            self._tts = None

    def _p(self, filename: str) -> str:
        return os.path.join(self.base_path, filename)

    def preload(self):
        self._sfx["type"] = pygame.mixer.Sound(self._p("type.wav"))
        self._sfx["backspace"] = pygame.mixer.Sound(self._p("backspace.wav"))
        self._sfx["select"] = pygame.mixer.Sound(self._p("select.wav"))
        self._sfx["hover"] = pygame.mixer.Sound(self._p("hover.wav"))
        self._sfx["win"] = pygame.mixer.Sound(self._p("win.wav"))
        self._sfx["word_complete"] = pygame.mixer.Sound(self._p("word_complete.wav"))
        self._sfx["robot_p1"] = pygame.mixer.Sound(self._p("robot_beep_p1.wav"))
        self._sfx["robot_p2"] = pygame.mixer.Sound(self._p("robot_beep_p2.wav"))

        for k, s in self._sfx.items():
            if k == "hover":
                s.set_volume(self.hover_volume)
            else:
                s.set_volume(self.sfx_volume)

    def set_volumes(self, music: float = None, sfx: float = None, hover: float = None):
        if music is not None:
            self.music_volume = float(music)
            try:
                pygame.mixer.music.set_volume(self.music_volume)
            except Exception:
                pass
        if sfx is not None:
            self.sfx_volume = float(sfx)
            for k, s in self._sfx.items():
                if k != "hover":
                    try:
                        s.set_volume(self.sfx_volume)
                    except Exception:
                        pass
        if hover is not None:
            self.hover_volume = float(hover)
            if "hover" in self._sfx:
                try:
                    self._sfx["hover"].set_volume(self.hover_volume)
                except Exception:
                    pass

    def play_music(self, key: str):
        if key == self._music_key:
            return
        self._music_key = key

        if key == "welcome":
            path = self._p("welcome_music.wav")
        elif key == "game":
            path = self._p("game_music.wav")
        else:
            try:
                pygame.mixer.music.stop()
            except Exception:
                pass
            return

        try:
            pygame.mixer.music.load(path)
            pygame.mixer.music.set_volume(self.music_volume)
            pygame.mixer.music.play(-1)
        except Exception:
            pass

    def sfx(self, name: str):
        s = self._sfx.get(name)
        if s:
            try:
                s.play()
            except Exception:
                pass

    def announce_winner(self, winner: int):
        if winner == 0:
            text = "Player one wins!"
            beep = "robot_p1"
        else:
            text = "Player two wins!"
            beep = "robot_p2"

        if self._tts is not None:
            try:
                self._tts.say(text)
                self._tts.runAndWait()
                return
            except Exception:
                pass

        self.sfx(beep)
