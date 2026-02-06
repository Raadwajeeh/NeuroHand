import pygame
import cv2
from .base import ScreenBase
from src.ui.theme import BG, TEXT, MUTED, ACCENT, GOOD, DANGER, DIVIDER, CARD, CARD2, BORDER
from src.ui.font import get_fonts
from src.ui.widgets import Button, draw_label, draw_shadow_card, draw_vertical_gradient
from src.ui.i18n import t
from .cam_view import render_two_cameras, render_single_camera

def probe_cameras(max_index=6):
    found = []
    for i in range(max_index):
        cap = cv2.VideoCapture(i)
        ok = cap.isOpened()
        if ok:
            found.append(i)
        cap.release()
    return found

class CameraSettingsScreen(ScreenBase):
    def __init__(self, router, back_screen_factory=None):
        super().__init__(router)
        if self.session.audio:
            self.session.audio.play_music('welcome')
        self.title, self.h2, self.body, self.small, self.mono = get_fonts()
        self.w, self.h = self.screen.get_width(), self.screen.get_height()
        self.back_factory = back_screen_factory

        self.available = probe_cameras(8)
        if not self.available:
            self.available = [0]

        self.left_idx = self.session.left_camera_index
        self.right_idx = self.session.right_camera_index

        btn_w, btn_h = 220, 58
        self.back_btn = Button((30, 28, 160, 52), t(self.session.lang, "back"), self.h2, self._back, primary=False)

        self.apply_btn = Button((self.w - 30 - 220, self.h - 90, 220, 60), t(self.session.lang, "apply"), self.h2, self._apply, primary=True)

        self.left_buttons = []
        self.right_buttons = []
        self._build_lists()

    def _build_lists(self):
        self.left_buttons = []
        self.right_buttons = []

        start_y = 170
        for k, idx in enumerate(self.available):
            y = start_y + k * 64
            self.left_buttons.append(Button((60, y, 220, 54), f"Camera {idx}", self.body, lambda i=idx: self._set_left(i), primary=(idx==self.left_idx)))
            self.right_buttons.append(Button((self.w - 60 - 220, y, 220, 54), f"Camera {idx}", self.body, lambda i=idx: self._set_right(i), primary=(idx==self.right_idx)))

    def _set_left(self, idx):
        self.left_idx = idx
        self._build_lists()

    def _set_right(self, idx):
        self.right_idx = idx
        self._build_lists()

    def _apply(self):
        self.session.set_camera_indices(self.left_idx, self.right_idx)

    def _back(self):
        if self.back_factory is not None:
            self.router.go(self.back_factory())
        else:
            from .welcome import WelcomeScreen
            self.router.go(WelcomeScreen(self.router))

    def handle_event(self, event):
        self.back_btn.handle_event(event)
        self.apply_btn.handle_event(event)
        for b in self.left_buttons + self.right_buttons:
            b.handle_event(event)
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self._back()

    def draw(self):
        # 3D-like background gradient
        draw_vertical_gradient(self.screen, (0,0,self.w,self.h), (10,14,30), (20,26,44))

        draw_label(self.screen, t(self.session.lang, "camera_settings_title"), self.title, TEXT, (40, 30))
        draw_label(self.screen, t(self.session.lang, "camera_settings_sub"), self.body, MUTED, (40, 92))

        # Preview area
        cam_rect = (40, 120, self.w - 80, int(self.h*0.32))

        # Temporarily show preview using selected indices (without restarting trackers)
        # We'll use existing trackers frames for speed; after Apply they swap.
        tL = self.session.tracker_left
        tR = self.session.tracker_right

        if self.session.player_count == 2 and tR is not None:
            frameL = tL.get_frame() if tL else None
            frameR = tR.get_frame() if tR else None
            handsL = tL.get_hands() if tL else []
            handsR = tR.get_hands() if tR else []
            render_two_cameras(self.screen, frameL, handsL, frameR, handsR, cam_rect)
            cx = cam_rect[0] + cam_rect[2]//2
            pygame.draw.line(self.screen, DIVIDER, (cx, cam_rect[1]), (cx, cam_rect[1]+cam_rect[3]), 4)
        else:
            frame = tL.get_frame() if tL else None
            hands = tL.get_hands() if tL else []
            render_single_camera(self.screen, frame, hands, cam_rect)

        # Panels
        panel_h = self.h - (cam_rect[1] + cam_rect[3]) - 140
        left_panel = pygame.Rect(40, cam_rect[1] + cam_rect[3] + 30, 300, panel_h)
        right_panel = pygame.Rect(self.w - 40 - 300, cam_rect[1] + cam_rect[3] + 30, 300, panel_h)

        draw_shadow_card(self.screen, left_panel)
        pygame.draw.rect(self.screen, CARD, left_panel, border_radius=18)
        pygame.draw.rect(self.screen, BORDER, left_panel, width=2, border_radius=18)

        draw_shadow_card(self.screen, right_panel)
        pygame.draw.rect(self.screen, CARD, right_panel, border_radius=18)
        pygame.draw.rect(self.screen, BORDER, right_panel, width=2, border_radius=18)

        draw_label(self.screen, t(self.session.lang, "left_player_camera"), self.h2, TEXT, (left_panel.x + 18, left_panel.y + 14))
        draw_label(self.screen, t(self.session.lang, "right_player_camera"), self.h2, TEXT, (right_panel.x + 18, right_panel.y + 14))

        for b in self.left_buttons:
            b.draw(self.screen)
        for b in self.right_buttons:
            b.draw(self.screen)

        self.back_btn.draw(self.screen)
        self.apply_btn.draw(self.screen)
