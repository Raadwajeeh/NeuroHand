from .base import ScreenBase
from src.ui.theme import BG, TEXT, MUTED, ACCENT, GOOD
from src.ui.font import get_fonts
from src.ui.widgets import Button, draw_label
from src.ui.i18n import t

class ResultsScreen(ScreenBase):
    def __init__(self, router):
        super().__init__(router)
        if self.session.audio:
            self.session.audio.play_music('welcome')
        self.title, self.h2, self.body, self.small, self.mono = get_fonts()
        self.w, self.h = self.screen.get_width(), self.screen.get_height()

        btn_w, btn_h = 260, 60
        self.play_again = Button((self.w//2 - btn_w - 20, self.h - 130, btn_w, btn_h), t(self.session.lang, "play_again"), self.h2, self._again, primary=True)
        self.menu = Button((self.w//2 + 20, self.h - 130, btn_w, btn_h), t(self.session.lang, "main_menu"), self.h2, self._menu, primary=False)

    def _again(self):
        from .game import GameScreen
        self.router.go(GameScreen(self.router))

    def _menu(self):
        from .welcome import WelcomeScreen
        self.router.go(WelcomeScreen(self.router))

    def handle_event(self, event):
        self.play_again.handle_event(event)
        self.menu.handle_event(event)

    def draw(self):
        self.screen.fill(BG)
        r = self.session.last_result or {}
        mode = r.get("mode", self.session.player_count)
        target = r.get("target", "????")

        draw_label(self.screen, t(self.session.lang, "results"), self.title, TEXT, (40, 30))
        draw_label(self.screen, f"{t(self.session.lang,'word')}: {target}", self.h2, MUTED, (40, 100))

        if mode == 1:
            p1 = r.get("p1")
            elapsed = r.get("time", 0.0)
            draw_label(self.screen, t(self.session.lang, "single_player"), self.h2, MUTED, (40, 150))
            if p1:
                draw_label(self.screen, f"{t(self.session.lang,'time')}: {elapsed:.2f}s", self.body, TEXT, (40, 190))
                draw_label(self.screen, f"{t(self.session.lang,'typed')}: {p1.typed}", self.body, TEXT, (40, 220))
                draw_label(self.screen, f"{t(self.session.lang,'clicks')}: {p1.clicks} | {t(self.session.lang,'mistakes')}: {p1.mistakes}", self.body, MUTED, (40, 250))
        else:
            winner = r.get("winner", None)
            p1 = r.get("p1")
            p2 = r.get("p2")
            elapsed = r.get("time", 0.0)

            if winner == 0:
                wtxt, col = t(self.session.lang, "winner_p1"), ACCENT
            elif winner == 1:
                wtxt, col = t(self.session.lang, "winner_p2"), GOOD
            else:
                wtxt, col = t(self.session.lang, "no_winner"), MUTED

            draw_label(self.screen, wtxt, self.title, col, (40, 160))
            draw_label(self.screen, f"{t(self.session.lang,'time')}: {elapsed:.2f}s", self.body, MUTED, (40, 215))

            if p1:
                draw_label(self.screen, f"{t(self.session.lang,'p1_typed')}: {p1.typed} | {t(self.session.lang,'clicks')}: {p1.clicks} | {t(self.session.lang,'mistakes')}: {p1.mistakes}", self.body, TEXT, (40, 250))
            if p2:
                draw_label(self.screen, f"{t(self.session.lang,'p2_typed')}: {p2.typed} | {t(self.session.lang,'clicks')}: {p2.clicks} | {t(self.session.lang,'mistakes')}: {p2.mistakes}", self.body, TEXT, (40, 280))

        self.play_again.draw(self.screen)
        self.menu.draw(self.screen)
