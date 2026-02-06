import pygame
import math
from .base import ScreenBase

from src.ui.theme import TEXT, MUTED, ACCENT, GOOD, DIVIDER, DANGER
from src.ui.font import get_fonts
from src.ui.widgets import draw_label
from src.ui.arcade_fx import ArcadeFX
from src.gameplay.word_game import WordGame
from src.gameplay.board_layout import KEY_ROWS, BACKSPACE
from src.ui.i18n import t
from .cam_view import (
    render_single_camera_raw,
    render_two_cameras_raw,
    render_single_camera,
    render_two_cameras,
)

from src.hand.filters import OneEuroFilter2D, OneEuroParams


def clamp(v, lo, hi):
    return lo if v < lo else (hi if v > hi else v)


class _InputFSM:
    def __init__(self):
        self.mode = "move"   # move | freeze | clicked
        self.fist_frames = 0
        self.open_frames = 0
        self.locked_key = None


class GameScreen(ScreenBase):
    def __init__(self, router):
        super().__init__(router)
        self.title, self.h2, self.body, self.small, self.mono = get_fonts()
        self.big_word = pygame.font.SysFont("Segoe UI", 64, bold=True)
        self.w, self.h = self.screen.get_width(), self.screen.get_height()
        self.half_w = self.w // 2
        self.players = self.session.player_count

        # audio: switch to game music
        if self.session.audio:
            self.session.audio.play_music("game")

        # Game feel mode
        self.mode = getattr(self.session, "game_mode", "learning")
        # Challenge feels stricter: timer + stronger mistake penalty
        time_limit = 35.0 if self.mode == "challenge" else None
        mistake_w = 1.0 if self.mode == "challenge" else 0.5
        # Word list depends on current language (en/nl)
        self.game = WordGame(lang=self.session.lang, mistake_weight=mistake_w, time_limit=time_limit)

        # Cursor start position:
        # Put it in a neutral, comfortable area (not on top of the keyboard)
        # to prevent accidental selection at round start.
        start_y = self.h * 0.45
        if self.players == 1:
            self.cursor = [(self.w * 0.5, start_y), (0, 0)]
        else:
            self.cursor = [(self.half_w * 0.5, start_y), (self.half_w * 1.5, start_y)]

        # Cursor smoothing (post-integrator) + hand smoothing (pre-delta)
        # هدفنا: حركة ناعمة بدون اهتزاز، خصوصاً عند الحركة البطيئة.
        # Filters tuned for "fast but stable" gameplay:
        # - slightly higher min_cutoff reduces lag
        # - higher beta keeps it responsive during quick moves
        cursor_params = OneEuroParams(min_cutoff=1.6, beta=0.030, d_cutoff=1.0)
        hand_params = OneEuroParams(min_cutoff=1.2, beta=0.030, d_cutoff=1.0)
        self.filters = [OneEuroFilter2D(cursor_params), OneEuroFilter2D(cursor_params)]
        self.hand_filters = [OneEuroFilter2D(hand_params), OneEuroFilter2D(hand_params)]

        # Micro deadzone (normalized) to kill tiny tremor.
        self.HAND_DEADZONE = 0.0018

        # Faster selection: fewer frames required to confirm fist/open.
        self.FIST_HOLD_FRAMES = 2
        self.OPEN_RESET_FRAMES = 1
        self.fsm = [_InputFSM(), _InputFSM()]

        self.keys = [[], []]
        self._build_keyboards()

        self._ended = False

        # Debug / visual aid mode (toggle with D): shows landmarks & connections.
        self.debug_mode = False

        # Interaction-zone expansion: lets players reach screen edges without
        # physically stretching their arm too far.
        self.zone_pad = 0.12


        # Relative cursor control (mouse-like): we integrate hand deltas instead of mapping absolute hand position.
        self.hand_prev = [None, None]  # per player: (hx, hy) in normalized interaction-zone space
        self.REL_GAIN = 2.2            # sensitivity multiplier (tune feel)
        self.RECENTER_JUMP = 0.18      # normalized jump threshold to treat as re-center (no cursor move)
        # Arcade visuals (Kids Mode) - visual only
        self.arcade_fx = ArcadeFX(self.w, self.h)

        # Focus UI (reduces clutter over camera)
        self.focus_mode = True

        # Word feedback animations (per player)
        self.word_pulse = [0.0, 0.0]  # correct letter pop
        self.word_shake = [0.0, 0.0]  # wrong letter shake
        self.word_wave  = [0.0, 0.0]  # completion wave

        # Soft-magnet tuning (learning mode)
        self.MAGNET_RADIUS = 150.0
        self.MAGNET_STRENGTH = 0.18

        # hover sound tracking
        self.last_hover = [None, None]
        self.hover_cd = [0.0, 0.0]

        # Top UI (Nav Bars + Home buttons)
        # UI/layout only. We keep hand tracking + cursor math untouched.
        self.nav_h = int(self.h * 0.11)
        self.home_btn_rects = []  # per player (or single)
        self.restart_btn_rects = []
        self._rebuild_top_ui()

    def _rebuild_top_ui(self):
        """Build top UI rects (Home/Restart buttons)."""
        btn_w = 126
        btn_h = 42
        margin = 14
        self.home_btn_rects = []
        self.restart_btn_rects = []
        if self.players == 1:
            self.home_btn_rects.append(pygame.Rect(margin, margin, btn_w, btn_h))
            self.restart_btn_rects.append(pygame.Rect(self.w - margin - btn_w, margin, btn_w, btn_h))
        else:
            # One button inside each half so both players can click it.
            self.home_btn_rects.append(pygame.Rect(margin, margin, btn_w, btn_h))
            self.home_btn_rects.append(pygame.Rect(self.half_w + margin, margin, btn_w, btn_h))

            self.restart_btn_rects.append(pygame.Rect(self.half_w - margin - btn_w, margin, btn_w, btn_h))
            self.restart_btn_rects.append(pygame.Rect(self.w - margin - btn_w, margin, btn_w, btn_h))

    def _restart_round(self):
        """Restart current round without leaving the game screen."""
        self.game.restart_round(keep_word=True)
        self._ended = False

        # Reset interaction state
        self.hand_prev = [None, None]
        for f in self.filters:
            f.reset()
        for hf in self.hand_filters:
            hf.reset()
        self.fsm = [_InputFSM(), _InputFSM()]
        self.last_hover = [None, None]
        self.hover_cd = [0.0, 0.0]

        # Reset visuals (purely cosmetic)
        if hasattr(self.arcade_fx, "reset"):
            self.arcade_fx.reset()

        # Re-center cursor(s) in a neutral zone (not on the keyboard)
        start_y = self.h * 0.45
        if self.players == 1:
            self.cursor[0] = (self.w * 0.5, start_y)
        else:
            self.cursor[0] = (self.half_w * 0.5, start_y)
            self.cursor[1] = (self.half_w * 1.5, start_y)

        if self.session.audio:
            self.session.audio.sfx("select")

    def _go_home(self):
        from .welcome import WelcomeScreen
        if self.session.audio:
            self.session.audio.play_music("welcome")
        self.router.go(WelcomeScreen(self.router))

    def _build_keyboards(self):
        self.keys = [[], []]
        top = int(self.h * 0.62)
        key_w, key_h = 62, 54
        gap = 10

        if self.players == 1:
            for row_i, row in enumerate(KEY_ROWS):
                row_w = len(row) * key_w + (len(row) - 1) * gap
                x = (self.w - row_w) // 2
                y = top + row_i * (key_h + gap)
                for col_i, ch in enumerate(row):
                    self.keys[0].append((ch, pygame.Rect(x + col_i * (key_w + gap), y, key_w, key_h)))
            self.keys[0].append((BACKSPACE, pygame.Rect((self.w - 220) // 2, top + 3 * (key_h + gap), 220, key_h)))
        else:
            for pid in (0, 1):
                base_x = pid * self.half_w
                for row_i, row in enumerate(KEY_ROWS):
                    row_w = len(row) * key_w + (len(row) - 1) * gap
                    x = base_x + (self.half_w - row_w) // 2
                    y = top + row_i * (key_h + gap)
                    for col_i, ch in enumerate(row):
                        self.keys[pid].append((ch, pygame.Rect(x + col_i * (key_w + gap), y, key_w, key_h)))
                self.keys[pid].append((BACKSPACE, pygame.Rect(base_x + (self.half_w - 220) // 2, top + 3 * (key_h + gap), 220, key_h)))

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN and event.key == pygame.K_d:
            self.debug_mode = not self.debug_mode
            return

        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            # Quick exit to home (also available via the on-screen Home button).
            self._go_home()

    def _map_interaction_zone(self, nx, ny):
        """Map normalized hand coords to a larger effective zone.

        With pad>0, the usable area becomes larger: you don't need to move your
        hand all the way to the camera edge to reach the screen edge.
        """
        p = self.zone_pad
        nx2 = (nx - p) / max(1e-6, (1.0 - 2.0 * p))
        ny2 = (ny - p) / max(1e-6, (1.0 - 2.0 * p))
        return clamp(nx2, 0.0, 1.0), clamp(ny2, 0.0, 1.0)

    def _map_to_cropped_view(self, nx: float, ny: float, frame_w: int, frame_h: int, target_w: int, target_h: int):
        """Match hand coords to the same center-crop used when rendering the camera.

        Camera feed is rendered via _fit_crop (center-crop to target aspect). If we
        use raw MediaPipe normalized coords (0..1) without applying the same crop,
        cursor vs. camera will feel "misaligned" near edges.
        """
        if frame_w <= 0 or frame_h <= 0 or target_w <= 0 or target_h <= 0:
            return clamp(nx, 0.0, 1.0), clamp(ny, 0.0, 1.0)

        src_ar = frame_w / float(frame_h)
        target_ar = target_w / float(target_h)

        # Mirror the exact logic in cam_view._fit_crop
        if src_ar > target_ar:
            new_w = int(frame_h * target_ar)
            x0 = max(0, (frame_w - new_w) // 2)
            x0n = x0 / float(frame_w)
            wn = new_w / float(frame_w)
            nx = (nx - x0n) / max(1e-6, wn)
        else:
            new_h = int(frame_w / target_ar)
            y0 = max(0, (frame_h - new_h) // 2)
            y0n = y0 / float(frame_h)
            hn = new_h / float(frame_h)
            ny = (ny - y0n) / max(1e-6, hn)

        return clamp(nx, 0.0, 1.0), clamp(ny, 0.0, 1.0)

    def _camera_crop_map(self, pid: int, nx: float, ny: float):
        """Apply crop compensation based on the actual camera frame & the area we render.

        - 1P: target area is full screen (w x h)
        - 2P: each camera is rendered into half screen (half_w x h)
        """
        if self.players == 1:
            trk = self.session.tracker_left
            frame = trk.get_frame() if trk else None
            if frame is None:
                return clamp(nx, 0.0, 1.0), clamp(ny, 0.0, 1.0)
            fh, fw = frame.shape[:2]
            return self._map_to_cropped_view(nx, ny, fw, fh, self.w, self.h)

        # 2 players
        if pid == 0:
            trk = self.session.tracker_left
            frame = trk.get_frame() if trk else None
        else:
            trk = self.session.tracker_right
            frame = trk.get_frame() if trk else None

        if frame is None:
            return clamp(nx, 0.0, 1.0), clamp(ny, 0.0, 1.0)

        fh, fw = frame.shape[:2]
        return self._map_to_cropped_view(nx, ny, fw, fh, self.half_w, self.h)

    def _hovered_key(self, pid, pos):
        x, y = pos

        # Home button (per-player in 2P, single in 1P)
        if pid < len(self.home_btn_rects):
            if self.home_btn_rects[pid].collidepoint((x, y)):
                return "__HOME__"

        # Restart button (per-player in 2P, single in 1P)
        if pid < len(self.restart_btn_rects):
            if self.restart_btn_rects[pid].collidepoint((x, y)):
                return "__RESTART__"

        for key, rect in self.keys[pid]:
            if rect.collidepoint((x, y)):
                return key
        return None

    def _next_char(self, pid: int):
        """Next correct character needed for this player (or None)."""
        pl = self.game.p[pid]
        if len(pl.typed) >= len(self.game.target):
            return None
        return self.game.target[len(pl.typed)]

    def _rect_for_char(self, pid: int, ch: str):
        if not ch:
            return None
        for k, r in self.keys[pid]:
            if k == ch:
                return r
        return None

    def _update_hover_sound(self, pid, dt):
        self.hover_cd[pid] = max(0.0, self.hover_cd[pid] - dt)
        key = self._hovered_key(pid, self.cursor[pid])
        if key != self.last_hover[pid]:
            self.last_hover[pid] = key
            if key is not None and self.hover_cd[pid] <= 0.0 and self.session.audio:
                self.session.audio.sfx("hover")
                self.arcade_fx.on_hover(pid)
                self.hover_cd[pid] = 0.06

    def _pick_hand_any(self, hands, pid=0):
        if not hands:
            return None
        cx, cy = self.cursor[pid]
        best, best_d = None, 1e18
        for h in hands:
            if not h.present:
                continue
            # Use the derived pointer position if available (reacts to rotation).
            hx = getattr(h, "px", h.cx)
            hy = getattr(h, "py", h.cy)
            px, py = hx * self.w, hy * self.h
            d = (px - cx) ** 2 + (py - cy) ** 2
            if d < best_d:
                best_d = d
                best = h
        return best

    def _move_cursor(self, pid, nx, ny, dt):
        cx, cy = self.filters[pid].filter(nx, ny, dt)
        self.cursor[pid] = (cx, cy)

    def _click_key(self, pid, key):
        if key is None:
            return

        if key == "__HOME__":
            # End current round and go straight to home.
            self._go_home()
            return

        if key == "__RESTART__":
            self._restart_round()
            return

        if key == BACKSPACE:
            deleted = self.game.backspace(pid)
            if deleted and self.session.audio:
                self.session.audio.sfx("backspace")
            self.arcade_fx.on_click(pid, self.cursor[pid])
            return

        # Normal character
        pl = self.game.p[pid]
        was_done = pl.done
        before = pl.typed
        completed = self.game.try_add_char(pid, key)
        after = pl.typed

        # Word feedback (UI only)
        if (not was_done) and (after != before):
            if self.game.target.startswith(after):
                self.word_pulse[pid] = 1.0
            else:
                self.word_shake[pid] = 1.0

        if self.session.audio and (not was_done):
            # play typing only if it actually changed input (try_add_char increments mistakes too,
            # but we want the UX to feel responsive)
            self.session.audio.sfx("type")
        self.arcade_fx.on_click(pid, self.cursor[pid])

        if completed and self.session.audio:
            self.session.audio.sfx("word_complete")
            self.arcade_fx.on_success(self.cursor[pid])
            self.word_wave[pid] = 1.0


    def _apply_fsm(self, pid, hand):
        f = self.fsm[pid]

        if hand is None:
            f.mode = "move"
            f.fist_frames = 0
            f.open_frames = 0
            f.locked_key = None
            return

        if f.mode == "move":
            if hand.state != "open":
                f.mode = "freeze"
                f.locked_key = self._hovered_key(pid, self.cursor[pid])
                f.fist_frames = 0
                f.open_frames = 0

        elif f.mode == "freeze":
            if hand.state == "fist":
                f.fist_frames += 1
                if f.fist_frames >= self.FIST_HOLD_FRAMES:
                    if self.session.audio:
                        self.session.audio.sfx("select")
                    self.arcade_fx.on_click(pid, self.cursor[pid])
                    self._click_key(pid, f.locked_key)
                    f.mode = "clicked"
                    f.locked_key = None
            elif hand.state == "open":
                f.open_frames += 1
                if f.open_frames >= self.OPEN_RESET_FRAMES:
                    f.mode = "move"
                    f.locked_key = None
                    f.fist_frames = 0
                    f.open_frames = 0
            else:
                f.open_frames = 0

        elif f.mode == "clicked":
            if hand.state == "open":
                f.open_frames += 1
                if f.open_frames >= self.OPEN_RESET_FRAMES:
                    f.mode = "move"
                    f.fist_frames = 0
                    f.open_frames = 0
            else:
                f.open_frames = 0

    def _update_cursor_relative(self, pid, hand, dt, x_lo, x_hi, allow_move=True):
        """Mouse-like control: cursor += (hand_delta * gain). Large hand jumps are treated as re-centering."""
        if hand is None:
            self.hand_prev[pid] = None
            return

        hx = getattr(hand, "px", hand.cx)
        hy = getattr(hand, "py", hand.cy)

        # Camera crop compensation: map MediaPipe normalized coords to the *cropped* image
        # that we actually display on-screen (same logic as _fit_crop in cam_view).
        hx, hy = self._camera_crop_map(pid, hx, hy)

        # Hand-space smoothing (pre-delta) to reduce micro jitter.
        hx, hy = self.hand_filters[pid].filter(hx, hy, dt)

        # map to expanded interaction zone to reduce required physical reach
        hx, hy = self._map_interaction_zone(hx, hy)

        prev = self.hand_prev[pid]
        self.hand_prev[pid] = (hx, hy)

        # First sample: just latch, no movement.
        if prev is None:
            return

        if not allow_move:
            return

        dx = hx - prev[0]
        dy = hy - prev[1]

        # Deadzone for tiny tremor
        if abs(dx) < self.HAND_DEADZONE:
            dx = 0.0
        if abs(dy) < self.HAND_DEADZONE:
            dy = 0.0

        # If the hand was re-positioned abruptly inside the camera frame,
        # treat it as a re-center action: do not move the cursor.
        if abs(dx) > self.RECENTER_JUMP or abs(dy) > self.RECENTER_JUMP:
            return

        # Apply deltas to current cursor position (integrator).
        cx, cy = self.cursor[pid]
        span_w = max(1.0, float(x_hi - x_lo))
        nx = cx + dx * span_w * self.REL_GAIN
        ny = cy + dy * self.h * self.REL_GAIN

        # Soft magnet (Learning Mode): gently pull toward the next correct key
        # when the cursor is already close. This is NOT auto-aim; just a tiny assist.
        if self.mode == "learning":
            nch = self._next_char(pid)
            rr = self._rect_for_char(pid, nch) if nch else None
            if rr is not None:
                kx, ky = rr.centerx, rr.centery
                ddx = kx - nx
                ddy = ky - ny
                dist = (ddx * ddx + ddy * ddy) ** 0.5
                if dist < self.MAGNET_RADIUS:
                    s = self.MAGNET_STRENGTH * (1.0 - dist / self.MAGNET_RADIUS)
                    nx += ddx * s
                    ny += ddy * s

        nx = clamp(nx, x_lo, x_hi)
        ny = clamp(ny, 0, self.h - 1)

        self._move_cursor(pid, nx, ny, dt)


    def update(self, dt):
        self.game.step_time(dt)
        self.arcade_fx.update(dt)

        # decay word feedback animations
        for i in (0, 1):
            self.word_pulse[i] = max(0.0, self.word_pulse[i] - dt * 6.0)
            self.word_shake[i] = max(0.0, self.word_shake[i] - dt * 5.0)
            self.word_wave[i] = max(0.0, self.word_wave[i] - dt * 2.0)
        if self.players == 1:
            trk = self.session.tracker_left
            hands = trk.get_hands() if trk else []
            h = self._pick_hand_any(hands, pid=0)

            # Relative (delta-based) cursor control: no absolute jumps when the hand re-centers.
            if h is not None and h.state == "open" and self.fsm[0].mode == "move":
                self._update_cursor_relative(0, h, dt, 0, self.w - 1, allow_move=True)
            else:
                # Latch position without moving cursor (supports re-centering).
                self._update_cursor_relative(0, h, dt, 0, self.w - 1, allow_move=False)

            self._update_hover_sound(0, dt)
            self._apply_fsm(0, h)

        else:
            tL = self.session.tracker_left
            tR = self.session.tracker_right
            handsL = tL.get_hands() if tL else []
            handsR = tR.get_hands() if tR else []

            h0 = self._pick_hand_any(handsL, pid=0)
            h1 = self._pick_hand_any(handsR, pid=1)

            # Player 1: relative cursor control within left half.
            if h0 is not None and h0.state == "open" and self.fsm[0].mode == "move":
                self._update_cursor_relative(0, h0, dt, 0, self.half_w - 1, allow_move=True)
            else:
                self._update_cursor_relative(0, h0, dt, 0, self.half_w - 1, allow_move=False)

            # Player 2: relative cursor control within right half.
            if h1 is not None and h1.state == "open" and self.fsm[1].mode == "move":
                self._update_cursor_relative(1, h1, dt, self.half_w, self.w - 1, allow_move=True)
            else:
                self._update_cursor_relative(1, h1, dt, self.half_w, self.w - 1, allow_move=False)

            self._update_hover_sound(0, dt)
            self._update_hover_sound(1, dt)
            self._apply_fsm(0, h0)
            self._apply_fsm(1, h1)

        # Challenge mode can also end by time
        if self.mode == "challenge" and (not self._ended) and self.game.is_time_up():
            self._ended = True
            # winner by score (ties -> None)
            s0 = self.game.score(0)
            s1 = self.game.score(1) if self.players == 2 else -1e9
            winner = None
            if self.players == 1:
                winner = 0 if s0 > 0 else None
            else:
                if abs(s0 - s1) < 1e-6:
                    winner = None
                else:
                    winner = 0 if s0 > s1 else 1

            if self.session.audio:
                self.session.audio.sfx("win")

            self.session.last_result = {
                "mode": self.players,
                "target": self.game.target,
                "p1": self.game.p[0],
                "p2": self.game.p[1] if self.players == 2 else None,
                "winner": winner,
                "time": self.game.elapsed,
            }
            from .results import ResultsScreen
            self.router.go(ResultsScreen(self.router))
            return

        if self.game.is_round_over() and not self._ended:
            self._ended = True
            winner = self.game.winner()

            if self.session.audio:
                self.session.audio.sfx("win")
                if winner is not None:
                    self.session.audio.announce_winner(winner)

            self.session.last_result = {
                "mode": self.players,
                "target": self.game.target,
                "p1": self.game.p[0],
                "p2": self.game.p[1] if self.players == 2 else None,
                "winner": winner,
                "time": self.game.elapsed,
                            }
            from .results import ResultsScreen
            self.router.go(ResultsScreen(self.router))

    def _draw_hud_panel(self, x, y, w, h, pid, color):
        panel = pygame.Surface((w, h), pygame.SRCALPHA)
        panel.fill((10, 12, 18, 150))
        pygame.draw.rect(panel, (255, 255, 255, 60), pygame.Rect(0, 0, w, h), width=2, border_radius=16)
        self.screen.blit(panel, (x, y))

        pl = self.game.p[pid]
        acc = int(self.game.accuracy(pid) * 100)
        score = self.game.score(pid)
        elapsed = self.game.elapsed

        draw_label(self.screen, f"P{pid+1}", self.h2, color, (x + 14, y + 10))
        draw_label(self.screen, f"{t(self.session.lang,'target')}: {self.game.target}", self.body, TEXT, (x + 14, y + 44))
        draw_label(self.screen, f"{t(self.session.lang,'typed')}: {pl.typed}", self.body, TEXT, (x + 14, y + 72))
        draw_label(self.screen, f"{t(self.session.lang,'time')}: {elapsed:.1f}s", self.body, MUTED, (x + 14, y + 100))
        draw_label(self.screen, f"{t(self.session.lang,'chars')}: {len(pl.typed)}/{len(self.game.target)}", self.body, MUTED, (x + 14, y + 128))
        draw_label(self.screen, f"{t(self.session.lang,'deletes')}: {pl.deletes}", self.body, MUTED, (x + 14, y + 156))
        draw_label(self.screen, f"{t(self.session.lang,'accuracy')}: {acc}%", self.body, MUTED, (x + 14, y + 184))
        draw_label(self.screen, f"{t(self.session.lang,'score')}: {score:.1f}", self.body, MUTED, (x + 14, y + 212))

    def _measure_word_banner(self, word: str, typed: str, font_big: pygame.font.Font):
        """Compute ArcadeFX word banner size so we can center it inside a Nav Bar."""
        if not word:
            return 0, 0
        padx, pady = 18, 14
        text_w = 0
        text_h = 0
        for i, ch in enumerate(word):
            # Render per-letter like ArcadeFX does (width can vary per glyph).
            col = (255, 255, 255)
            if i < len(typed):
                col = (124, 255, 170) if word.startswith(typed[: i + 1]) else (255, 153, 88)
            rs = font_big.render(ch, True, col)
            text_w += rs.get_width()
            text_h = max(text_h, rs.get_height())
        bw = text_w + padx * 2
        bh = text_h + pady * 2
        return bw, bh

    def _draw_home_button(self, pid: int, hovered_key):
        if pid >= len(self.home_btn_rects):
            return
        rect = self.home_btn_rects[pid]

        is_h = (hovered_key == "__HOME__")
        btn = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
        btn.fill((18, 22, 34, 175 if not is_h else 230))
        pygame.draw.rect(btn, (255, 255, 255, 90), btn.get_rect(), width=2, border_radius=14)
        self.screen.blit(btn, rect.topleft)

        label = self.small.render(t(self.session.lang, "home"), True, TEXT)
        self.screen.blit(label, label.get_rect(center=rect.center))

    def _draw_restart_button(self, pid: int, hovered_key):
        if pid >= len(self.restart_btn_rects):
            return
        rect = self.restart_btn_rects[pid]

        is_h = (hovered_key == "__RESTART__")
        btn = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
        # slightly less prominent than HOME but still clearly clickable
        btn.fill((18, 22, 34, 160 if not is_h else 220))
        pygame.draw.rect(btn, (255, 255, 255, 80), btn.get_rect(), width=2, border_radius=14)
        self.screen.blit(btn, rect.topleft)

        label = self.small.render(t(self.session.lang, "restart"), True, TEXT)
        self.screen.blit(label, label.get_rect(center=rect.center))

    def _draw_nav_bar(self, pid: int, rect: pygame.Rect, color):
        """Per-player top Nav Bar. Word is centered with ArcadeFX animations per player."""
        bar = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
        a = 120 if self.focus_mode else 170
        b = 40 if self.focus_mode else 70
        bar.fill((10, 12, 18, a))
        pygame.draw.rect(bar, (255, 255, 255, b), bar.get_rect(), width=2 if not self.focus_mode else 1, border_radius=18)
        self.screen.blit(bar, rect.topleft)

        pl = self.game.p[pid]
        acc = int(self.game.accuracy(pid) * 100)
        score = self.game.score(pid)
        progress = f"{len(pl.typed)}/{len(self.game.target)}"

        # Left block
        lx = rect.x + 16
        ly = rect.y + 10
        draw_label(self.screen, f"P{pid+1}", self.h2, color, (lx, ly))
        draw_label(self.screen, f"{t(self.session.lang,'score')} {score:.1f}", self.small, TEXT, (lx, ly + 34))

        # Challenge: show time left
        if self.mode == "challenge" and self.game.time_limit is not None:
            left = max(0.0, float(self.game.time_limit) - float(self.game.elapsed))
            tl = f"{t(self.session.lang,'time_left')} {left:.0f}s"
            draw_label(self.screen, tl, self.small, MUTED, (lx, ly + 60))

        # Right block
        rx = rect.right - 16
        acc_lbl = f"{t(self.session.lang,'acc')} {acc}%"
        chars_lbl = f"{t(self.session.lang,'chars')} {progress}"
        draw_label(self.screen, acc_lbl, self.small, TEXT, (rx - self.small.size(acc_lbl)[0], ly))
        draw_label(self.screen, chars_lbl, self.small, MUTED, (rx - self.small.size(chars_lbl)[0], ly + 34))

        # Center word banner (animated, per player)
        word = self.game.target
        typed = pl.typed
        bw, bh = self._measure_word_banner(word, typed, self.big_word)
        if bw > 0 and bh > 0:
            bx = rect.x + (rect.width - bw) // 2
            by = rect.y + (rect.height - bh) // 2

            # Feedback transforms (pulse/shake/wave)
            if self.word_shake[pid] > 0:
                amp = 6 * self.word_shake[pid]
                bx += int(math.sin(self.arcade_fx.t * 40) * amp)
                by += int(math.cos(self.arcade_fx.t * 44) * amp)
            if self.word_pulse[pid] > 0:
                by -= int(6 * self.word_pulse[pid])

            self.arcade_fx.draw_word_banner(self.screen, word, typed, bx, by, self.big_word)

            # Completion wave: subtle translucent sweep over the banner
            if self.word_wave[pid] > 0:
                wv = self.word_wave[pid]
                sweep = int((1.0 - wv) * (bw + 80)) - 40
                wave = pygame.Surface((bw, bh), pygame.SRCALPHA)
                pygame.draw.rect(wave, (255, 255, 255, int(90 * wv)), pygame.Rect(sweep, 0, 60, bh), border_radius=18)
                self.screen.blit(wave, (bx, by), special_flags=pygame.BLEND_RGBA_ADD)

            # Progress dots (●●●○○) under the banner
            total = max(1, len(word))
            done = min(len(typed), total)
            dot_r = 5
            gap = 10
            row_w = total * (dot_r * 2) + (total - 1) * gap
            dx0 = rect.x + (rect.width - row_w) // 2
            dy0 = rect.bottom - 16
            for i in range(total):
                cx = dx0 + i * (dot_r * 2 + gap) + dot_r
                if i < done:
                    pygame.draw.circle(self.screen, TEXT, (cx, dy0), dot_r)
                else:
                    pygame.draw.circle(self.screen, TEXT, (cx, dy0), dot_r, width=2)

    def _draw_target_word_big(self):
        """Big target word: upper-right, clear, no overlap with keyboard."""
        word = self.game.target
        if not word:
            return

        text = self.big_word.render(word, True, (255, 255, 255))
        pad_x, pad_y = 18, 10
        bg = pygame.Surface((text.get_width() + pad_x * 2, text.get_height() + pad_y * 2), pygame.SRCALPHA)
        bg.fill((10, 12, 18, 160))
        pygame.draw.rect(bg, (255, 255, 255, 70), bg.get_rect(), width=2, border_radius=18)

        # Top-right placement (visually centered within the upper-right area)
        margin = 24
        bx = self.w - margin - bg.get_width()
        by = margin
        self.screen.blit(bg, (bx, by))
        self.screen.blit(text, (bx + pad_x, by + pad_y))

    def draw(self):
        # Background = camera only (landscape)
        if self.players == 1:
            trk = self.session.tracker_left
            frame = trk.get_frame() if trk else None
            if self.debug_mode:
                hands = trk.get_hands() if trk else []
                render_single_camera(self.screen, frame, hands, (0, 0, self.w, self.h))
            else:
                render_single_camera_raw(self.screen, frame, (0, 0, self.w, self.h), rotate_portrait=False)
        else:
            tL = self.session.tracker_left
            tR = self.session.tracker_right
            frameL = tL.get_frame() if tL else None
            frameR = tR.get_frame() if tR else None
            if self.debug_mode:
                handsL = tL.get_hands() if tL else []
                handsR = tR.get_hands() if tR else []
                render_two_cameras(self.screen, frameL, handsL, frameR, handsR, (0, 0, self.w, self.h))
            else:
                render_two_cameras_raw(self.screen, frameL, frameR, (0, 0, self.w, self.h), rotate_portrait=False)
            pygame.draw.line(self.screen, DIVIDER, (self.half_w, 0), (self.half_w, self.h), 3)

        # Visual overlay: keep it very light in Focus Mode
        if not self.focus_mode:
            self.arcade_fx.draw_background_overlay(self.screen)
        else:
            # subtle vignette only (no stripes)
            v = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
            v.fill((0, 0, 0, 30))
            self.screen.blit(v, (0, 0))
        self.arcade_fx.draw_particles(self.screen)

        # Top Nav Bars (balanced per player)
        if self.players == 1:
            self._draw_nav_bar(0, pygame.Rect(12, 10, self.w - 24, self.nav_h), ACCENT)
        else:
            self._draw_nav_bar(0, pygame.Rect(12, 10, self.half_w - 24, self.nav_h), ACCENT)
            self._draw_nav_bar(1, pygame.Rect(self.half_w + 12, 10, self.half_w - 24, self.nav_h), GOOD)

        # Keyboard overlay + Home buttons
        for pid in (0,) if self.players == 1 else (0, 1):
            hovered = self._hovered_key(pid, self.cursor[pid])

            # Learning hint: next correct key
            hint_ch = self._next_char(pid) if self.mode == "learning" else None

            # Home button sits above gameplay UI and is clickable via the same fist-click.
            self._draw_home_button(pid, hovered)

            # Restart button (same interaction as keys/buttons)
            self._draw_restart_button(pid, hovered)

            for key, rect in self.keys[pid]:
                is_h = (hovered == key)
                is_hint = (hint_ch is not None and key == hint_ch)
                ksurf = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
                base_a = 120 if self.focus_mode else 170
                hover_a = 200 if self.focus_mode else 210
                hint_a = 175 if self.focus_mode else 190
                a = hover_a if is_h else (hint_a if is_hint else base_a)
                ksurf.fill((18, 22, 34, a))
                # minimal borders in Focus Mode (less clutter)
                br_a = 55 if (is_h or is_hint) else (35 if self.focus_mode else 80)
                pygame.draw.rect(ksurf, (255, 255, 255, br_a), pygame.Rect(0, 0, rect.width, rect.height), width=1 if self.focus_mode else 2, border_radius=14)
                # glow for hint key
                if is_hint:
                    pygame.draw.rect(ksurf, (124, 255, 170, 70), pygame.Rect(2, 2, rect.width - 4, rect.height - 4), width=0, border_radius=12)
                self.screen.blit(ksurf, rect.topleft)

                # Backspace label: show a real word instead of a glyph that may not exist in the font.
                disp = t(self.session.lang, "delete_key") if key == BACKSPACE else key
                label = self.mono.render(disp, True, TEXT)
                self.screen.blit(label, label.get_rect(center=rect.center))

            # Cursor (Arcade Hero) - visual only
            x, y = self.cursor[pid]
            color = ACCENT if pid == 0 else GOOD
            self.arcade_fx.draw_cursor(self.screen, pid, (x, y), color)

        # Camera errors
        errL = (self.session.tracker_left.get_error() if self.session.tracker_left else None)
        errR = (self.session.tracker_right.get_error() if self.session.tracker_right else None)
        if errL:
            draw_label(self.screen, f"Left camera error: {errL}", self.small, DANGER, (20, self.h - 30))
        if self.players == 2 and errR:
            draw_label(self.screen, f"Right camera error: {errR}", self.small, DANGER, (self.half_w + 20, self.h - 30))
