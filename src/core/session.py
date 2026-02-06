from __future__ import annotations
from typing import Optional

from src.hand.hand_tracker import HandTracker

class GameSession:
    def __init__(self, audio=None, **_ignored):
        # audio manager (can be None)
        self.audio = audio

        self.last_result = None

        # UI/Game language (words + labels)
        # Supported: "en" (English), "nl" (Dutch)
        self.lang = "en"

        self.player_count = 1

        # Game feel mode (UI/logic):
        # - "learning": gentle help (hint + soft magnet), no time limit.
        # - "challenge": timed, mistakes hurt score more.
        self.game_mode = "learning"

        self.left_camera_index = 0
        self.right_camera_index = 1

        self.tracker_left: Optional[HandTracker] = None
        self.tracker_right: Optional[HandTracker] = None

        self.ensure_trackers(player_count=1)

    def toggle_lang(self):
        self.lang = "nl" if self.lang == "en" else "en"

    def set_lang(self, lang: str):
        lang = (lang or "").strip().lower()
        if lang in ("en", "nl"):
            self.lang = lang

    def ensure_trackers(self, player_count: int):
        self.player_count = 1 if player_count != 2 else 2

        if self.tracker_left is None or self.tracker_left.camera_index != self.left_camera_index:
            if self.tracker_left is not None:
                self.tracker_left.stop()
            self.tracker_left = HandTracker(camera_index=self.left_camera_index)
            self.tracker_left.start()

        if self.player_count == 2:
            if self.tracker_right is None or self.tracker_right.camera_index != self.right_camera_index:
                if self.tracker_right is not None:
                    self.tracker_right.stop()
                self.tracker_right = HandTracker(camera_index=self.right_camera_index)
                self.tracker_right.start()
        else:
            if self.tracker_right is not None:
                self.tracker_right.stop()
                self.tracker_right = None

    def set_camera_indices(self, left_index: int, right_index: int):
        self.left_camera_index = int(left_index)
        self.right_camera_index = int(right_index)
        self.ensure_trackers(player_count=self.player_count)

    def shutdown(self):
        if self.tracker_left:
            self.tracker_left.stop()
            self.tracker_left = None
        if self.tracker_right:
            self.tracker_right.stop()
            self.tracker_right = None
