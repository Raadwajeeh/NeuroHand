import random
from dataclasses import dataclass

WORDS_EN = [
    "CODE", "DATA", "AI", "PYTHON", "UNITY", "ROBOT", "VISION", "INPUT",
    "CURSOR", "PIXEL", "LOGIC", "DEBUG", "ARRAY", "STACK", "LOOP",
]

# Dutch word list (uppercase). Keep it simple + kid-friendly.
WORDS_NL = [
    "HUIS", "WATER", "SCHOOL", "VRIEND", "BOEK", "TAFEL", "STOEL",
    "FOTO", "FIETS", "MELK", "BROOD", "APPEL", "BLOEM", "KLEUR",
    "SPELLEN", "SNEL", "LANG", "GOED", "NIEUW",
]


@dataclass
class PlayerState:
    typed: str = ""
    done: bool = False
    time_done: float = 0.0
    clicks: int = 0
    mistakes: int = 0
    deletes: int = 0


class WordGame:
    """Word typing game without a countdown timer.

    - The round never ends بسبب الوقت.
    - نستخدم elapsed فقط كإحصائية (وأيضًا لتسجيل زمن إنهاء الكلمة).
    """

    def __init__(self, lang: str = "en", mistake_weight: float = 0.5, time_limit: float | None = None):
        self.lang = (lang or "en").strip().lower()
        # Scoring feel
        self.mistake_weight = float(mistake_weight)
        # Optional challenge timer (seconds). If None: no time limit.
        self.time_limit = (None if time_limit is None else float(time_limit))
        self.reset()

    def _words_for_lang(self):
        if self.lang == "nl":
            return WORDS_NL
        return WORDS_EN

    def reset(self):
        self.target = random.choice(self._words_for_lang())
        self.p = [PlayerState(), PlayerState()]
        self.elapsed = 0.0

    def restart_round(self, keep_word: bool = True):
        """Restart the current round.

        - keep_word=True: keep the same target word, reset players + timer.
        - keep_word=False: pick a new word (same as reset()).
        """
        if not keep_word:
            self.reset()
            return
        # keep the same target
        self.p = [PlayerState(), PlayerState()]
        self.elapsed = 0.0

    def step_time(self, dt: float):
        # No time limit: we فقط نسجل الوقت الذي مرّ.
        self.elapsed += max(0.0, float(dt))

    def is_time_up(self) -> bool:
        return (self.time_limit is not None) and (self.elapsed >= self.time_limit)

    def time_left(self) -> float | None:
        if self.time_limit is None:
            return None
        return max(0.0, float(self.time_limit) - float(self.elapsed))

    def is_time_up(self) -> bool:
        return (self.time_limit is not None) and (self.elapsed >= self.time_limit)

    def try_add_char(self, pid: int, ch: str) -> bool:
        """Add a character. Returns True if this input completed the word."""
        pl = self.p[pid]
        if pl.done:
            return False

        pl.clicks += 1

        if len(pl.typed) >= len(self.target):
            pl.mistakes += 1
            return False

        pl.typed += ch

        if not self.target.startswith(pl.typed):
            pl.mistakes += 1

        if pl.typed == self.target:
            pl.done = True
            pl.time_done = self.elapsed
            return True

        return False

    def backspace(self, pid: int) -> bool:
        """Backspace. Returns True if something was deleted."""
        pl = self.p[pid]
        if pl.done:
            return False

        pl.clicks += 1
        if pl.typed:
            pl.typed = pl.typed[:-1]
            pl.deletes += 1
            return True
        return False

    def is_round_over(self) -> bool:
        # End only when someone completes the word.
        return self.p[0].done or self.p[1].done

    def score(self, pid: int) -> float:
        pl = self.p[pid]
        correct = 0
        for i, ch in enumerate(pl.typed):
            if i < len(self.target) and self.target[i] == ch:
                correct += 1
            else:
                break
        return max(0.0, correct - self.mistake_weight * pl.mistakes)

    def accuracy(self, pid: int) -> float:
        pl = self.p[pid]
        inputs = max(1, pl.clicks)
        return max(0.0, min(1.0, (inputs - pl.mistakes) / inputs))

    def winner(self):
        # If someone finished, fastest finisher wins.
        done = [(i, pl.time_done) for i, pl in enumerate(self.p) if pl.done]
        if done:
            done.sort(key=lambda t: t[1])
            return done[0][0]
        return None
