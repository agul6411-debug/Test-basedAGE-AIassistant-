"""One Euro Filter for 2D cursor smoothing with jitter suppression and low latency.

Reference: Géry Casiez, Nicolas Roussel, Daniel Vogel.
1 € Filter: A Simple Speed-based Low-pass Filter for Noisy Input in HCI.
ACM CHI 2012.
"""

import math


def _alpha(rate: float, cutoff: float) -> float:
    """Compute low-pass filter smoothing factor alpha."""
    tau = 1.0 / (2.0 * math.pi * cutoff)
    te = 1.0 / rate
    return 1.0 / (1.0 + tau / te)


class LowPassFilter:
    """Standard single-pole exponential smoothing low-pass filter."""

    def __init__(self, alpha: float = 0.5) -> None:
        self._alpha = alpha
        self._y: float | None = None
        self._s: float | None = None

    def filter(self, value: float, alpha: float | None = None) -> float:
        if alpha is not None:
            self._alpha = alpha
        if self._y is None:
            self._s = value
        else:
            self._s = self._alpha * value + (1.0 - self._alpha) * self._s
        self._y = value
        return self._s

    def last_value(self) -> float | None:
        return self._s

    def reset(self) -> None:
        self._y = None
        self._s = None


class OneEuroFilter1D:
    """1D One Euro filter with adaptive cutoff frequency."""

    def __init__(
        self,
        freq: float = 30.0,
        min_cutoff: float = 1.0,
        beta: float = 0.007,
        d_cutoff: float = 1.0,
    ) -> None:
        """Initialize 1D filter.

        Args:
            freq: Expected signal sampling rate in Hz.
            min_cutoff: Minimum cutoff frequency for jitter suppression at low speed.
            beta: Speed coefficient for lag reduction at high speed.
            d_cutoff: Cutoff frequency for derivative calculation.
        """
        self.freq = max(1.0, freq)
        self.min_cutoff = min_cutoff
        self.beta = beta
        self.d_cutoff = d_cutoff

        self._x_filter = LowPassFilter()
        self._dx_filter = LowPassFilter()
        self._last_time: float | None = None

    def filter(self, x: float, timestamp: float | None = None) -> float:
        """Filter value x given an optional timestamp (in seconds)."""
        if self._last_time is not None and timestamp is not None:
            dt = timestamp - self._last_time
            if dt > 0.0001:
                self.freq = 1.0 / dt
        self._last_time = timestamp

        prev_x = self._x_filter.last_value()
        dx = 0.0 if prev_x is None else (x - prev_x) * self.freq
        edx = self._dx_filter.filter(dx, _alpha(self.freq, self.d_cutoff))

        cutoff = self.min_cutoff + self.beta * abs(edx)
        return self._x_filter.filter(x, _alpha(self.freq, cutoff))

    def reset(self) -> None:
        self._x_filter.reset()
        self._dx_filter.reset()
        self._last_time = None


class OneEuroFilter2D:
    """2D One Euro filter for (x, y) coordinates."""

    def __init__(
        self,
        freq: float = 30.0,
        min_cutoff: float = 1.0,
        beta: float = 0.007,
        d_cutoff: float = 1.0,
    ) -> None:
        self.x_filter = OneEuroFilter1D(freq, min_cutoff, beta, d_cutoff)
        self.y_filter = OneEuroFilter1D(freq, min_cutoff, beta, d_cutoff)

    def filter(self, x: float, y: float, timestamp: float | None = None) -> tuple[float, float]:
        """Filter 2D point (x, y).

        Returns:
            Smoothed (filtered_x, filtered_y).
        """
        fx = self.x_filter.filter(x, timestamp)
        fy = self.y_filter.filter(y, timestamp)
        return (fx, fy)

    def reset(self) -> None:
        """Reset filter states."""
        self.x_filter.reset()
        self.y_filter.reset()
