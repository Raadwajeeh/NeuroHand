import math
import pygame
from .base import ScreenBase
from src.ui.theme import TEXT, MUTED, DANGER, ACCENT, GOOD, DIVIDER, CARD, BORDER
from src.ui.font import get_fonts
from src.ui.widgets import Button, draw_label, draw_vertical_gradient, draw_shadow_card
from src.ui.i18n import t
from .cam_view import render_single_camera
from .camera_settings import CameraSettingsScreen

class WelcomeScreen(ScreenBase):
    def __init__(self, router):
        super().__init__(router)
        if self.session.audio:
            self.session.audio.play_music('welcome')
        self.title, self.h2, self.body, self.small, self.mono = get_fonts()
        self.w, self.h = self.screen.get_width(), self.screen.get_height()

        self.session.ensure_trackers(player_count=1)

        btn_w, btn_h = 280, 64
        self.start_btn = Button((self.w//2 - btn_w//2, self.h - 115, btn_w, btn_h), t(self.session.lang, "start"), self.h2, self._start, primary=True)
        self.cam_btn = Button((30, self.h - 95, 240, 56), t(self.session.lang, "camera_settings"), self.body, self._cams, primary=False)
        self.lang_btn = Button((self.w - 30 - 180, 28, 180, 52), self._lang_label(), self.body, self._toggle_lang, primary=False)

        self.t = 0.0

    def _lang_label(self):
        code = (self.session.lang or "en").upper()
        return f"{t(self.session.lang, 'language')}: {code}"

    def _toggle_lang(self):
        # Toggle EN <-> NL
        self.session.toggle_lang()
        # Update button labels immediately
        self.start_btn.label = t(self.session.lang, "start")
        self.cam_btn.label = t(self.session.lang, "camera_settings")
        self.lang_btn.label = self._lang_label()

    def _start(self):
        from .choose_players import ChoosePlayersScreen
        self.router.go(ChoosePlayersScreen(self.router))

    def _cams(self):
        self.router.go(CameraSettingsScreen(self.router, back_screen_factory=lambda: WelcomeScreen(self.router)))

    def handle_event(self, event):
        self.start_btn.handle_event(event)
        self.cam_btn.handle_event(event)
        self.lang_btn.handle_event(event)

    def update(self, dt):
        self.t += dt

    def _draw_tutorial(self, x, y, w, h):
        # simple hand + cursor animation:
        # phase 0: open hand moving left/right, cursor follows
        # phase 1: closing -> cursor freezes
        # phase 2: fist -> click pulse
        surf = self.screen
        box = pygame.Rect(x, y, w, h)
        draw_shadow_card(surf, box)
        pygame.draw.rect(surf, CARD, box, border_radius=18)
        pygame.draw.rect(surf, BORDER, box, width=2, border_radius=18)

        draw_label(surf, t(self.session.lang, "how_to_play"), self.h2, TEXT, (x+18, y+12))

        tt = self.t % 6.0
        phase = 0
        if tt < 2.5:
            phase = 0
        elif tt < 4.0:
            phase = 1
        else:
            phase = 2

        # virtual keyboard key
        key = pygame.Rect(x + w//2 - 55, y + h - 78, 110, 52)
        pygame.draw.rect(surf, (28,34,60), key, border_radius=14)
        pygame.draw.rect(surf, BORDER, key, width=2, border_radius=14)
        draw_label(surf, "A", self.h2, TEXT, (key.centerx-10, key.centery-16))

        # hand position
        move = math.sin(self.t * 1.6) * (w*0.28)
        hx = x + w//2 + move
        hy = y + h*0.45

        # cursor: follow in phase 0, freeze in 1, click pulse in 2
        if phase == 0:
            cx, cy = hx, hy
        else:
            # freeze at last open position
            # approximate by using a fixed position at transition point:
            cx, cy = x + w//2 + math.sin(2.5 * 1.6) * (w*0.28), hy

        # draw hand (3D-like blob)
        hand_col = ACCENT if phase == 0 else (GOOD if phase == 1 else (251,113,133))
        pygame.draw.circle(surf, hand_col, (int(hx), int(hy)), 32)
        pygame.draw.circle(surf, (255,255,255), (int(hx-10), int(hy-10)), 8)

        # fingers or fist
        if phase == 0:
            # 4 small finger circles
            for i in range(4):
                pygame.draw.circle(surf, hand_col, (int(hx - 22 + i*14), int(hy - 32)), 10)
        elif phase == 1:
            # closing: semi-fingers
            for i in range(3):
                pygame.draw.circle(surf, hand_col, (int(hx - 16 + i*16), int(hy - 26)), 8)
        else:
            # fist: no fingers
            pass

        # cursor
        pygame.draw.circle(surf, TEXT, (int(cx), int(cy)), 16, width=2)
        pygame.draw.circle(surf, hand_col, (int(cx), int(cy)), 8)

        # click pulse
        if phase == 2:
            pulse = 10 + int(8 * abs(math.sin(self.t * 8)))
            pygame.draw.circle(surf, hand_col, (key.centerx, key.centery), pulse, width=3)

        # captions
        if phase == 0:
            msg = t(self.session.lang, "open_move")
        elif phase == 1:
            msg = t(self.session.lang, "closing_freeze")
        else:
            msg = t(self.session.lang, "fist_click")
        draw_label(surf, msg, self.body, MUTED, (x+18, y+50))

    def draw(self):
        # 3D-like gradient background
        draw_vertical_gradient(self.screen, (0,0,self.w,self.h), (10,14,30), (20,26,44))

        # animated title
        wobble = 6 * math.sin(self.t * 2.2)
        draw_label(self.screen, "Gesture Word Duel", self.title, TEXT, (40, 30 + int(wobble)))
        draw_label(self.screen, t(self.session.lang, "tagline"), self.body, MUTED, (40, 100))

        # camera preview (single)
        t0 = self.session.tracker_left
        err = t0.get_error() if t0 else None
        if err:
            draw_label(self.screen, f"{t(self.session.lang,'cam_error')}: {err}", self.body, DANGER, (40, 130))

        cam_rect = (40, 150, self.w - 80, int(self.h*0.34))
        frame = t0.get_frame() if t0 else None
        hands = t0.get_hands() if t0 else []
        render_single_camera(self.screen, frame, hands, cam_rect)

        # tutorial panel
        self._draw_tutorial(40, cam_rect[1] + cam_rect[3] + 25, 520, 220)

        # moving welcome message (typewriter-ish feel)
        msg = t(self.session.lang, "welcome_line")
        n = int((self.t * 24) % (len(msg) + 8))
        shown = msg[:max(0, min(len(msg), n))]
        draw_label(self.screen, shown, self.body, ACCENT, (600, cam_rect[1] + cam_rect[3] + 55))

        self.cam_btn.draw(self.screen)
        self.start_btn.draw(self.screen)
        self.lang_btn.draw(self.screen)
