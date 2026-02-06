import pygame
from .base import ScreenBase
from src.ui.theme import TEXT, MUTED, ACCENT, GOOD, DIVIDER, CARD, BORDER
from src.ui.font import get_fonts
from src.ui.widgets import Button, draw_label, draw_vertical_gradient, draw_shadow_card
from src.ui.i18n import t
from .cam_view import render_single_camera
from .camera_settings import CameraSettingsScreen

class ChoosePlayersScreen(ScreenBase):
    def __init__(self, router):
        super().__init__(router)
        if self.session.audio:
            self.session.audio.play_music('welcome')
        self.title, self.h2, self.body, self.small, self.mono = get_fonts()
        self.w, self.h = self.screen.get_width(), self.screen.get_height()
        self.selected = 1
        self.session.ensure_trackers(player_count=1)

        btn_w, btn_h = 300, 64
        self.one_btn = Button((self.w//2 - btn_w - 20, self.h - 170, btn_w, btn_h), t(self.session.lang, "one_player"), self.h2, self._one, primary=True)
        self.two_btn = Button((self.w//2 + 20, self.h - 170, btn_w, btn_h), t(self.session.lang, "two_players"), self.h2, self._two, primary=False)
        self.start_btn = Button((self.w//2 - 170, self.h - 95, 340, 60), t(self.session.lang, "start_game"), self.h2, self._start, primary=True)

        # Mode select (Learning vs Challenge)
        mode_w, mode_h = 220, 54
        gap = 16
        y_mode = self.h - 250
        x_mode = self.w//2 - (mode_w*2 + gap)//2
        self.learn_btn = Button((x_mode, y_mode, mode_w, mode_h), t(self.session.lang, "learning_mode"), self.body, self._set_learning, primary=True)
        self.chal_btn  = Button((x_mode + mode_w + gap, y_mode, mode_w, mode_h), t(self.session.lang, "challenge_mode"), self.body, self._set_challenge, primary=False)

        self.cam_btn = Button((30, self.h - 95, 240, 56), t(self.session.lang, "camera_settings"), self.body, self._cams, primary=False)
        self.back_btn = Button((30, 28, 160, 52), t(self.session.lang, "back"), self.h2, self._back, primary=False)
        self.lang_btn = Button((self.w - 30 - 180, 28, 180, 52), self._lang_label(), self.body, self._toggle_lang, primary=False)

    def _lang_label(self):
        code = (self.session.lang or "en").upper()
        return f"{t(self.session.lang, 'language')}: {code}"

    def _toggle_lang(self):
        self.session.toggle_lang()
        self.one_btn.label = t(self.session.lang, "one_player")
        self.two_btn.label = t(self.session.lang, "two_players")
        self.start_btn.label = t(self.session.lang, "start_game")
        self.cam_btn.label = t(self.session.lang, "camera_settings")
        self.back_btn.label = t(self.session.lang, "back")
        self.lang_btn.label = self._lang_label()
        self.learn_btn.label = t(self.session.lang, "learning_mode")
        self.chal_btn.label = t(self.session.lang, "challenge_mode")

    def _one(self):
        self.selected = 1
        self.session.ensure_trackers(player_count=1)

    def _two(self):
        self.selected = 2
        self.session.ensure_trackers(player_count=2)

    def _set_learning(self):
        self.session.game_mode = "learning"

    def _set_challenge(self):
        self.session.game_mode = "challenge"

    def _cams(self):
        self.router.go(CameraSettingsScreen(self.router, back_screen_factory=lambda: ChoosePlayersScreen(self.router)))

    def _back(self):
        from .welcome import WelcomeScreen
        self.router.go(WelcomeScreen(self.router))

    def _start(self):
        from .game import GameScreen
        self.session.ensure_trackers(player_count=self.selected)
        self.router.go(GameScreen(self.router))

    def handle_event(self, event):
        self.one_btn.handle_event(event)
        self.two_btn.handle_event(event)
        self.learn_btn.handle_event(event)
        self.chal_btn.handle_event(event)
        self.start_btn.handle_event(event)
        self.cam_btn.handle_event(event)
        self.back_btn.handle_event(event)
        self.lang_btn.handle_event(event)
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self._back()

    def draw(self):
        draw_vertical_gradient(self.screen, (0,0,self.w,self.h), (10,14,30), (20,26,44))
        draw_label(self.screen, t(self.session.lang, "choose_players"), self.title, TEXT, (40, 30))
        draw_label(self.screen, t(self.session.lang, "choose_players_sub"), self.body, MUTED, (40, 95))

        # preview from left tracker
        cam_rect = (40, 140, self.w - 80, self.h - 380)
        panel = pygame.Rect(cam_rect)
        draw_shadow_card(self.screen, panel)
        pygame.draw.rect(self.screen, CARD, panel, border_radius=18)
        pygame.draw.rect(self.screen, BORDER, panel, width=2, border_radius=18)

        t0 = self.session.tracker_left
        frame = t0.get_frame() if t0 else None
        hands = t0.get_hands() if t0 else []
        render_single_camera(self.screen, frame, hands, cam_rect)

        # selection styles
        self.one_btn.primary = (self.selected == 1)
        self.two_btn.primary = (self.selected == 2)

        self.learn_btn.primary = (getattr(self.session, "game_mode", "learning") == "learning")
        self.chal_btn.primary = (getattr(self.session, "game_mode", "learning") == "challenge")

        self.back_btn.draw(self.screen)
        self.lang_btn.draw(self.screen)
        self.cam_btn.draw(self.screen)
        self.one_btn.draw(self.screen)
        self.two_btn.draw(self.screen)

        # Mode row
        draw_label(self.screen, f"{t(self.session.lang,'mode')}: ", self.body, MUTED, (self.w//2 - 210, self.h - 285))
        self.learn_btn.draw(self.screen)
        self.chal_btn.draw(self.screen)

        self.start_btn.draw(self.screen)
