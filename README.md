# Gesture Word Duel (v5) — Advanced Tracking + UI + Camera Settings

## New in v5
### Advanced hand tracking
- Uses **full hand** (palm center from multiple stable landmarks)
- Openness score uses **finger straightness + distances + thumb**
- Hysteresis + EMA smoothing for stable states:
  - open -> closing -> fist

### Ultra-smooth motion
- Uses a **One Euro Filter** (velocity-based smoothing):
  - smooth when slow (kills jitter)
  - responsive when fast (no lag)

### Fist detection improvements
- Clear separation: OPEN / CLOSING / FIST
- No double-clicks: click is debounced and requires stable fist frames

### New screens
- **Camera Settings**: choose camera per player inside the game

## Run (PowerShell)
```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python main.py
```

## Notes
- Two-player mode uses **two independent trackers** (two cameras).
- If your second camera is not index 1, open **Camera Settings** and pick the correct camera.
