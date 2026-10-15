"""Simple explainable forecasting for prototype — linear trend on simulated history."""

from datetime import datetime, timedelta
from models.schemas import ForecastResult, ForecastPoint


def generate_historical(current_score: float, previous_score: float, threat_type: str) -> list[dict]:
    """Build simulated historical threat scores leading to current."""
    now = datetime.now()
    if threat_type == "Normal":
        base_scores = [8, 10, 9, 11, 10, 12]
    else:
        start = max(5, previous_score - 30)
        step = (current_score - start) / 5
        base_scores = [round(start + step * i, 1) for i in range(6)]
        base_scores[-1] = current_score

    points = []
    for i, s in enumerate(base_scores):
        t = now - timedelta(minutes=5 - i)
        points.append({"time": t.strftime("%H:%M"), "score": s, "type": "historical"})
    return points


def linear_regression_forecast(scores: list[float], horizons: list[int], slope_cap: float = 2.2) -> tuple[list[ForecastPoint], float]:
    n = len(scores)
    if n < 2:
        return (
            [ForecastPoint(label=f"+{h} min", minutes_ahead=h, score=scores[-1] if scores else 0) for h in horizons],
            0.0,
        )

    x_mean = (n - 1) / 2
    y_mean = sum(scores) / n
    num = sum((i - x_mean) * (scores[i] - y_mean) for i in range(n))
    den = sum((i - x_mean) ** 2 for i in range(n)) or 1
    slope = num / den
    intercept = y_mean - slope * x_mean

    # Cap projection slope for prototype — avoids unrealistic 0→100 jumps in demo
    projection_slope = min(slope, slope_cap) if slope > 0 else slope

    results = []
    current = scores[-1]
    for h in horizons:
        if slope > 0:
            predicted = current + projection_slope * h
        else:
            future_x = (n - 1) + h
            predicted = intercept + slope * future_x
        predicted = max(0, min(100, round(predicted, 1)))
        results.append(ForecastPoint(label=f"+{h} min", minutes_ahead=h, score=predicted))
    return results, slope


def trend_label(slope: float) -> str:
    if slope > 2:
        return "ESCALATING"
    if slope < -2:
        return "DE-ESCALATING"
    return "STABLE"


def compute_forecast(current_score: float, previous_score: float, threat_type: str) -> ForecastResult:
    historical = generate_historical(current_score, previous_score, threat_type)
    scores = [p["score"] for p in historical]

    n = len(scores)
    x_mean = (n - 1) / 2
    y_mean = sum(scores) / n
    num = sum((i - x_mean) * (scores[i] - y_mean) for i in range(n))
    den = sum((i - x_mean) ** 2 for i in range(n)) or 1
    slope = num / den

    forecast_points, slope = linear_regression_forecast(scores, [5, 10, 15])
    trend = trend_label(slope)

    historical_with_current = historical + [
        {"time": datetime.now().strftime("%H:%M"), "score": current_score, "type": "current"}
    ]

    return ForecastResult(
        historical=historical_with_current,
        current_score=current_score,
        forecast_points=forecast_points,
        trend=trend,
        trend_slope=round(slope, 2),
        method="Linear Regression (Prototype / Conceptual Forecast)",
        confidence="MEDIUM" if len(scores) >= 5 else "LOW",
    )
