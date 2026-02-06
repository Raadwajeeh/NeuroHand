import traceback
import os
import pygame

from src.core.session import GameSession
from src.core.router import Router
from src.screens.welcome import WelcomeScreen
from src.audio.audio_manager import AudioManager

def _safe_set_mode():
    try:
        return pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
    except Exception:
        return pygame.display.set_mode((1280, 720))

def _show_crash_screen(err_text: str):
    try:
        pygame.init()
        screen = pygame.display.set_mode((900, 520))
        pygame.display.set_caption("Gesture Word Duel - Crash")
        font = pygame.font.SysFont("consolas", 18)
        clock = pygame.time.Clock()

        lines = [
            "The game crashed. A log was written to crash_log.txt",
            "Run from PowerShell to see the full error:",
            "  .\\.venv\\Scripts\\Activate.ps1",
            "  python main.py",
            "",
            "Error (first lines):",
        ] + err_text.splitlines()[:18] + ["", "Press ESC to close."]

        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    running = False

            screen.fill((15, 18, 26))
            y = 20
            for ln in lines:
                surf = font.render(ln, True, (230, 230, 230))
                screen.blit(surf, (20, y))
                y += 24
            pygame.display.flip()
            clock.tick(30)
    except Exception:
        pass
    finally:
        try:
            pygame.quit()
        except Exception:
            pass

def main():
    try:
        pygame.init()
        try:
            pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
        except Exception:
            pass

        pygame.display.set_caption("Gesture Word Duel — v6.1 (Crash Log Enabled)")
        screen = _safe_set_mode()
        clock = pygame.time.Clock()

        audio = AudioManager(base_path=os.path.join("assets", "audio"))
        try:
            audio.preload()
        except Exception:
            pass

        session = GameSession(audio)
        router = Router(session=session, screen=screen)
        router.go(WelcomeScreen(router))

        running = True
        while running:
            dt = clock.tick(60) / 1000.0
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_q:
                    running = False
                else:
                    router.handle_event(event)

            router.update(dt)
            router.draw()
            pygame.display.flip()

        session.shutdown()
        pygame.quit()

    except Exception:
        err = traceback.format_exc()
        try:
            with open("crash_log.txt", "w", encoding="utf-8") as f:
                f.write(err)
        except Exception:
            pass
        _show_crash_screen(err)

if __name__ == "__main__":
    main()
