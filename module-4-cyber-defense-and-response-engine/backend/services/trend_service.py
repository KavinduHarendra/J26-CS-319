"""Trend analysis service — short-term threat trend over rolling risk history.

Implements simple, explainable trend detection:
  ESCALATING     — risk is increasing significantly across recent observations
  IMPROVING      — risk is decreasing significantly
  STABLE         — risk is not changing significantly
  INSUFFICIENT_DATA — too few observations to determine trend

No deep learning. Uses a simple delta-comparison approach across the
rolling window. Explainable and auditable for PP1 demonstration.
"""

from collections import deque

from models.defense import TrendWindow
from config.scoring_weights import (
    TREND_WINDOW_SIZE,
    TREND_ESCALATING_THRESHOLD,
    TREND_IMPROVING_THRESHOLD,
    TREND_MIN_OBSERVATIONS,
)

# In-memory rolling risk history (persisted to SQLite in audit_service)
_risk_history: deque[float] = deque(maxlen=TREND_WINDOW_SIZE)


def reset_history() -> None:
    """Clear the rolling history (called on simulation reset)."""
    _risk_history.clear()


def push_score(score: float) -> None:
    """Append a new risk score to the rolling window."""
    _risk_history.append(score)


def get_history() -> list[float]:
    """Return current rolling window as a list."""
    return list(_risk_history)


def compute_trend() -> TrendWindow:
    """Compute trend over the current rolling window.

    Method:
      If < TREND_MIN_OBSERVATIONS → INSUFFICIENT_DATA
      Compare first and last scores in window:
        delta > ESCALATING_THRESHOLD  → ESCALATING
        delta < -IMPROVING_THRESHOLD  → IMPROVING
        otherwise                     → STABLE

    Returns:
        TrendWindow with trend label, slope, and window snapshot.
    """
    scores = list(_risk_history)
    n = len(scores)

    if n < TREND_MIN_OBSERVATIONS:
        return TrendWindow(
            scores=scores,
            trend="INSUFFICIENT_DATA",
            slope=0.0,
            window_size=n,
        )

    delta = scores[-1] - scores[0]
    slope = round(delta / max(n - 1, 1), 2)

    if delta >= TREND_ESCALATING_THRESHOLD:
        trend = "ESCALATING"
    elif delta <= -TREND_IMPROVING_THRESHOLD:
        trend = "IMPROVING"
    else:
        trend = "STABLE"

    return TrendWindow(
        scores=scores,
        trend=trend,
        slope=slope,
        window_size=n,
    )
