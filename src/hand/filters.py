import math
from dataclasses import dataclass

def clamp(v, lo, hi):
    return lo if v < lo else (hi if v > hi else v)

@dataclass
class OneEuroParams:
    min_cutoff: float = 1.0
    beta: float = 0.02
    d_cutoff: float = 1.0

class _LowPass:
    def __init__(self, alpha: float, init: float = 0.0):
        self.alpha = alpha
        self.s = init
        self.initialized = False

    def filter(self, x: float, alpha: float):
        if not self.initialized:
            self.s = x
            self.initialized = True
            return x
        self.s = alpha * x + (1.0 - alpha) * self.s
        return self.s

def _alpha(cutoff: float, dt: float) -> float:
    # cutoff in Hz
    tau = 1.0 / (2.0 * math.pi * cutoff)
    return 1.0 / (1.0 + tau / max(1e-6, dt))

class OneEuroFilter1D:
    """One Euro Filter: smooth when slow, responsive when fast."""
    def __init__(self, params: OneEuroParams):
        self.p = params
        self.xf = _LowPass(0.0, 0.0)
        self.dxf = _LowPass(0.0, 0.0)
        self.last_x = None

    def reset(self):
        self.xf.initialized = False
        self.dxf.initialized = False
        self.last_x = None

    def filter(self, x: float, dt: float) -> float:
        if self.last_x is None:
            self.last_x = x
            return self.xf.filter(x, 1.0)

        dx = (x - self.last_x) / max(1e-6, dt)
        self.last_x = x

        ad = _alpha(self.p.d_cutoff, dt)
        edx = self.dxf.filter(dx, ad)

        cutoff = self.p.min_cutoff + self.p.beta * abs(edx)
        ax = _alpha(cutoff, dt)
        return self.xf.filter(x, ax)

class OneEuroFilter2D:
    def __init__(self, params: OneEuroParams):
        self.fx = OneEuroFilter1D(params)
        self.fy = OneEuroFilter1D(params)

    def reset(self):
        self.fx.reset()
        self.fy.reset()

    def filter(self, x: float, y: float, dt: float):
        return self.fx.filter(x, dt), self.fy.filter(y, dt)
