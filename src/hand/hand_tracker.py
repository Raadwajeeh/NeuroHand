import threading
import time
import math
from dataclasses import dataclass
from typing import List, Optional, Any

import cv2
import mediapipe as mp
import numpy as np

@dataclass
class HandObs:
    present: bool
    cx: float        # normalized 0..1 (palm center)
    cy: float        # normalized 0..1
    px: float        # normalized 0..1 (pointer position derived from palm pose)
    py: float        # normalized 0..1
    openness: float  # 0..1 (higher = more open)
    state: str       # 'open' | 'closing' | 'fist'
    landmarks: Optional[Any] = None

def _dist(ax, ay, bx, by):
    return math.hypot(ax - bx, ay - by)

def _angle(ax, ay, bx, by, cx, cy):
    # angle ABC (at B) in degrees
    abx, aby = ax - bx, ay - by
    cbx, cby = cx - bx, cy - by
    ab = math.hypot(abx, aby) + 1e-9
    cb = math.hypot(cbx, cby) + 1e-9
    dot = abx * cbx + aby * cby
    cosv = max(-1.0, min(1.0, dot / (ab * cb)))
    return math.degrees(math.acos(cosv))

class HandTracker:
    """Camera -> MediaPipe Hands -> stable palm center + openness score + state"""
    def __init__(self, camera_index: int = 0):
        self.camera_index = camera_index
        self._lock = threading.Lock()
        self._running = False
        self._thread = None

        self._frame_bgr = None
        self._error = None
        self._hands: List[HandObs] = []

        # Openness score thresholds (with hysteresis)
        self.OPEN_ON = 0.68
        self.OPEN_OFF = 0.58
        self.FIST_ON = 0.36
        self.FIST_OFF = 0.44

        # Temporal smoothing for openness (PER HAND).
        # IMPORTANT: using a single EMA/state for all hands causes "state bleeding"
        # between hands (and even between frames when MediaPipe changes ordering).
        # We keep a tiny per-hand memory keyed by handedness label when available.
        self.OP_ALPHA = 0.50
        self._per_hand = {
            "Left": {"op_ema": None, "last_state": "open"},
            "Right": {"op_ema": None, "last_state": "open"},
            "Unknown": {"op_ema": None, "last_state": "open"},
        }

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run_safe, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=1.0)
            self._thread = None

    def get_frame(self):
        with self._lock:
            return None if self._frame_bgr is None else self._frame_bgr.copy()

    def get_error(self):
        with self._lock:
            return self._error

    def get_hands(self) -> List[HandObs]:
        with self._lock:
            return list(self._hands)

    @staticmethod
    def _palm_center(lms) -> (float, float):
        # wrist + MCPs (stable anchors)
        ids = [0, 5, 9, 13, 17]
        xs = [lms.landmark[i].x for i in ids]
        ys = [lms.landmark[i].y for i in ids]
        return float(np.mean(xs)), float(np.mean(ys))

    @staticmethod
    def _pointer_from_palm_pose(lms) -> (float, float):
        """Compute a pointer that reacts to BOTH translation + rotation.

        Instead of pinning the cursor to a single point (like palm center), we
        build a simple palm coordinate frame using stable palm anchors, then
        offset forward/across the palm. This makes the cursor drift naturally
        when the hand rolls/yaws.
        """
        # anchors
        w = np.array([lms.landmark[0].x, lms.landmark[0].y], dtype=np.float32)   # wrist
        i = np.array([lms.landmark[5].x, lms.landmark[5].y], dtype=np.float32)   # index_mcp
        m = np.array([lms.landmark[9].x, lms.landmark[9].y], dtype=np.float32)   # middle_mcp
        p = np.array([lms.landmark[17].x, lms.landmark[17].y], dtype=np.float32) # pinky_mcp

        origin = (w + i + m + p) * 0.25

        # across-palm axis (pinky -> index)
        x_axis = i - p
        x_norm = float(np.linalg.norm(x_axis) + 1e-9)
        x_axis = x_axis / x_norm

        # forward axis (wrist -> middle)
        y_axis = m - w
        y_norm = float(np.linalg.norm(y_axis) + 1e-9)
        y_axis = y_axis / y_norm

        palm_size = 0.5 * (x_norm + y_norm)

        # offsets tuned for a "feels right" pointer:
        # - forward: towards fingers
        # - sideways: reacts to roll (small)
        forward = 1.05 * palm_size
        sideways = 0.18 * palm_size

        # roll proxy: how much middle knuckle is closer to index vs pinky
        roll = float(np.dot((m - origin), x_axis))
        side_term = sideways * np.clip(roll / (palm_size + 1e-9), -1.0, 1.0)

        pt = origin + forward * y_axis + side_term * x_axis
        return float(pt[0]), float(pt[1])

    @staticmethod
    def _openness_score(lms) -> float:
        """0..1 score: combine finger straightness + tip distance."""
        # landmark ids: (mcp, pip, tip)
        fingers = [
            (5, 6, 8),    # index
            (9, 10, 12),  # middle
            (13, 14, 16), # ring
            (17, 18, 20), # pinky
        ]

        wx, wy = lms.landmark[0].x, lms.landmark[0].y
        mx, my = lms.landmark[9].x, lms.landmark[9].y
        palm = _dist(wx, wy, mx, my) + 1e-6

        straightness = []
        tipdist = []
        for mcp, pip, tip in fingers:
            ax, ay = lms.landmark[mcp].x, lms.landmark[mcp].y
            bx, by = lms.landmark[pip].x, lms.landmark[pip].y
            cx, cy = lms.landmark[tip].x, lms.landmark[tip].y

            ang = _angle(ax, ay, bx, by, cx, cy)  # near 180 if straight
            straight = max(0.0, min(1.0, ang / 180.0))
            straightness.append(straight)

            td = _dist(cx, cy, wx, wy) / palm
            # normalize tip distance into 0..1 (empirical)
            td_n = max(0.0, min(1.0, (td - 1.1) / (2.4 - 1.1)))
            tipdist.append(td_n)

        s = sum(straightness) / len(straightness)
        d = sum(tipdist) / len(tipdist)

        # thumb contributes a bit via distance (thumb tip 4 to index mcp 5)
        tx, ty = lms.landmark[4].x, lms.landmark[4].y
        ix, iy = lms.landmark[5].x, lms.landmark[5].y
        thumb = _dist(tx, ty, ix, iy) / palm
        thumb_n = max(0.0, min(1.0, (thumb - 0.35) / (1.2 - 0.35)))

        score = 0.55 * s + 0.35 * d + 0.10 * thumb_n
        return max(0.0, min(1.0, score))

    def _classify(self, score: float, key: str = "Unknown") -> str:
        """Hysteresis classification (per-hand)."""
        mem = self._per_hand.get(key) or self._per_hand["Unknown"]
        st = mem.get("last_state", "open")

        if st == "open":
            if score <= self.OPEN_OFF:
                st = "closing"
        elif st == "closing":
            if score >= self.OPEN_ON:
                st = "open"
            elif score <= self.FIST_ON:
                st = "fist"
        elif st == "fist":
            if score >= self.FIST_OFF:
                st = "closing"

        mem["last_state"] = st
        return st

    def _run_safe(self):
        try:
            self._run()
        except Exception as e:
            with self._lock:
                self._error = repr(e)
            time.sleep(0.1)

    def _run(self):
        cap = cv2.VideoCapture(self.camera_index)
        if not cap.isOpened():
            with self._lock:
                self._error = "Camera could not be opened. Check permissions / camera index."
            return

        # Prefer a fast, stable capture mode for real-time tracking.
        # For gesture games, *latency* matters more than ultra-sharp frames.
        # We capture at a decent size for display, but we will run MediaPipe
        # on a downscaled frame to reduce processing time.
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        try:
            cap.set(cv2.CAP_PROP_FPS, 60)
        except Exception:
            pass
        try:
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        except Exception:
            pass

        mp_hands = mp.solutions.hands
        # model_complexity=0 is faster (lower latency) and usually good enough for games.
        hands = mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=2,
            model_complexity=0,
            # Slightly lower detection threshold helps quick reacquisition.
            min_detection_confidence=0.45,
            # Tracking threshold a bit higher keeps jitter down once locked.
            min_tracking_confidence=0.55
        )

        # Processing target size (only for the tracker, not the displayed frame)
        proc_w = 640

        while self._running and cap.isOpened():
            ok, frame = cap.read()
            if not ok:
                time.sleep(0.01)
                continue

            # Auto-fix camera orientation if the driver returns portrait frames.
            if frame.shape[0] > frame.shape[1]:
                frame = cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)

            frame = cv2.flip(frame, 1)
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            # Downscale for faster inference (normalized landmarks remain valid).
            if rgb.shape[1] > proc_w:
                scale = proc_w / float(rgb.shape[1])
                proc_h = max(1, int(rgb.shape[0] * scale))
                rgb_proc = cv2.resize(rgb, (proc_w, proc_h), interpolation=cv2.INTER_AREA)
            else:
                rgb_proc = rgb

            # MediaPipe speed hint
            rgb_proc.flags.writeable = False
            res = hands.process(rgb_proc)
            rgb_proc.flags.writeable = True

            obs: List[HandObs] = []
            if res.multi_hand_landmarks:
                handed = res.multi_handedness or []
                for idx, lms in enumerate(res.multi_hand_landmarks):
                    label = "Unknown"
                    if idx < len(handed) and handed[idx].classification:
                        label = handed[idx].classification[0].label or "Unknown"
                    cx, cy = self._palm_center(lms)
                    px, py = self._pointer_from_palm_pose(lms)
                    raw = self._openness_score(lms)

                    mem = self._per_hand.get(label) or self._per_hand["Unknown"]
                    if mem["op_ema"] is None:
                        mem["op_ema"] = raw
                    else:
                        mem["op_ema"] = self.OP_ALPHA * raw + (1.0 - self.OP_ALPHA) * float(mem["op_ema"])

                    score = float(mem["op_ema"])
                    st = self._classify(score, key=label)

                    obs.append(HandObs(True, cx, cy, px, py, score, st, lms))

                # Keep ordering stable to avoid flicker when two hands are visible.
                obs.sort(key=lambda h: h.px)

            with self._lock:
                self._frame_bgr = frame
                self._hands = obs

            time.sleep(0.001)

        hands.close()
        cap.release()
