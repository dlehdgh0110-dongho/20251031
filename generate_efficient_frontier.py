"""Generate efficient frontier plot for assets in temp.csv.

This script relies only on the Python standard library. It computes daily
simple returns from closing prices, annualises them, enumerates long-only
portfolios on a coarse grid, filters the efficient frontier, and writes an SVG
visualisation to ``efficient_frontier.svg``.
"""
from __future__ import annotations

import csv
import math
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Iterable, List, Sequence, Tuple

TRADING_DAYS = 252
TICKERS = ["005930.KS", "AAPL", "NVDA"]


@dataclass(frozen=True)
class PortfolioPoint:
    risk: float  # annualised standard deviation
    expected_return: float  # annualised expected return
    weights: Tuple[float, ...]


def read_closing_prices(path: str) -> Tuple[List[datetime], Dict[str, List[float]]]:
    dates: List[datetime] = []
    closes: Dict[str, List[float]] = {ticker: [] for ticker in TICKERS}
    with open(path, newline="") as f:
        reader = csv.reader(f)
        # Skip header rows (metric level, ticker level, and the Date marker)
        try:
            next(reader)
            next(reader)
            next(reader)
        except StopIteration as exc:  # pragma: no cover - defensive guard
            raise ValueError("CSV appears to be empty") from exc

        for row in reader:
            if not row or not row[0]:
                continue
            try:
                date = datetime.strptime(row[0], "%Y-%m-%d")
            except ValueError:
                # Some rows might include stray whitespace; ignore them
                continue
            dates.append(date)
            for idx, ticker in enumerate(TICKERS):
                try:
                    value = float(row[1 + idx]) if row[1 + idx] else math.nan
                except (IndexError, ValueError):
                    value = math.nan
                closes[ticker].append(value)
    return dates, closes


def compute_daily_returns(closes: Dict[str, List[float]]) -> List[Tuple[float, ...]]:
    num_days = len(next(iter(closes.values())))
    returns: List[Tuple[float, ...]] = []
    for day in range(1, num_days):
        daily_values: List[float] = []
        skip_day = False
        for ticker in TICKERS:
            current = closes[ticker][day]
            previous = closes[ticker][day - 1]
            if not (math.isfinite(current) and math.isfinite(previous)) or previous == 0:
                skip_day = True
                break
            daily_values.append((current / previous) - 1.0)
        if not skip_day:
            returns.append(tuple(daily_values))
    return returns


def mean(values: Sequence[float]) -> float:
    if not values:
        raise ValueError("Cannot compute mean of empty sequence")
    return sum(values) / len(values)


def covariance_matrix(returns: Sequence[Tuple[float, ...]]) -> List[List[float]]:
    if not returns:
        raise ValueError("No returns supplied")
    num_assets = len(returns[0])
    avgs = [mean([row[i] for row in returns]) for i in range(num_assets)]
    matrix = [[0.0 for _ in range(num_assets)] for _ in range(num_assets)]
    for i in range(num_assets):
        for j in range(num_assets):
            total = 0.0
            for row in returns:
                total += (row[i] - avgs[i]) * (row[j] - avgs[j])
            matrix[i][j] = total / (len(returns) - 1)
    return matrix


def annualise_daily_stats(daily_returns: Sequence[Tuple[float, ...]]) -> Tuple[List[float], List[List[float]]]:
    means_daily = [mean([row[i] for row in daily_returns]) for i in range(len(TICKERS))]
    cov_daily = covariance_matrix(daily_returns)
    means_annual = [m * TRADING_DAYS for m in means_daily]
    cov_annual = [
        [cov_daily[i][j] * TRADING_DAYS for j in range(len(TICKERS))]
        for i in range(len(TICKERS))
    ]
    return means_annual, cov_annual


def enumerate_portfolios(means: Sequence[float], cov: Sequence[Sequence[float]], grid: int = 60) -> List[PortfolioPoint]:
    portfolios: List[PortfolioPoint] = []
    for i in range(grid + 1):
        for j in range(grid + 1 - i):
            k = grid - i - j
            weights = (i / grid, j / grid, k / grid)
            # Skip degenerate combinations that break the long-only constraint
            if any(w < 0 for w in weights):
                continue
            expected = sum(w * mu for w, mu in zip(weights, means))
            variance = 0.0
            for a in range(len(TICKERS)):
                for b in range(len(TICKERS)):
                    variance += weights[a] * weights[b] * cov[a][b]
            risk = math.sqrt(max(variance, 0.0))
            portfolios.append(PortfolioPoint(risk=risk, expected_return=expected, weights=weights))
    return portfolios


def filter_efficient_frontier(portfolios: Iterable[PortfolioPoint]) -> List[PortfolioPoint]:
    sorted_points = sorted(portfolios, key=lambda p: (p.risk, -p.expected_return))
    frontier: List[PortfolioPoint] = []
    best_return = -math.inf
    for point in sorted_points:
        if point.expected_return > best_return:
            frontier.append(point)
            best_return = point.expected_return
    return frontier


def format_weight_annotation(point: PortfolioPoint) -> str:
    parts = [
        f"{ticker}: {weight * 100:.1f}%"
        for ticker, weight in zip(TICKERS, point.weights)
    ]
    return " | ".join(parts)


def write_svg(
    portfolios: Sequence[PortfolioPoint],
    frontier: Sequence[PortfolioPoint],
    path: str,
    start_date: datetime,
    end_date: datetime,
) -> None:
    if not portfolios:
        raise ValueError("No portfolio data to plot")

    padding = 20
    margin_left = 90
    margin_bottom = 70
    width, height = 960, 600
    plot_width = width - margin_left - padding
    plot_height = height - margin_bottom - padding

    risks = [p.risk for p in portfolios]
    returns = [p.expected_return for p in portfolios]
    min_risk, max_risk = min(risks), max(risks)
    min_return, max_return = min(returns), max(returns)

    # Apply small margins to axes to prevent points from sitting on the border
    risk_pad = (max_risk - min_risk) * 0.05 or 0.01
    return_pad = (max_return - min_return) * 0.05 or 0.01
    min_risk -= risk_pad
    max_risk += risk_pad
    min_return -= return_pad
    max_return += return_pad

    def scale_x(value: float) -> float:
        return margin_left + (value - min_risk) / (max_risk - min_risk) * plot_width

    def scale_y(value: float) -> float:
        return padding + plot_height - (value - min_return) / (max_return - min_return) * plot_height

    def axis_ticks(start: float, end: float, steps: int = 5) -> List[float]:
        span = end - start
        return [start + span * i / steps for i in range(steps + 1)]

    lines = [
        "<?xml version='1.0' encoding='UTF-8'?>",
        f"<svg xmlns='http://www.w3.org/2000/svg' width='{width}' height='{height}' viewBox='0 0 {width} {height}'>",
        "  <style>\n    text { font-family: 'Arial', sans-serif; fill: #1a1a1a; }\n    .axis path, .axis line { stroke: #4a4a4a; stroke-width: 1; }\n  </style>",
        "  <rect x='0' y='0' width='100%' height='100%' fill='white' stroke='none'/>",
        "  <g id='axes'>",
        f"    <line x1='{margin_left}' y1='{padding}' x2='{margin_left}' y2='{padding + plot_height}' stroke='#4a4a4a' stroke-width='1.5'/>",
        f"    <line x1='{margin_left}' y1='{padding + plot_height}' x2='{margin_left + plot_width}' y2='{padding + plot_height}' stroke='#4a4a4a' stroke-width='1.5'/>",
        "  </g>",
    ]

    # Axis labels
    lines.append(
        f"  <text x='{margin_left + plot_width / 2}' y='{height - 20}' text-anchor='middle' font-size='18'>Risk (annualised volatility, %)</text>"
    )
    lines.append(
        f"  <text x='25' y='{padding + plot_height / 2}' transform='rotate(-90 25 {padding + plot_height / 2})' text-anchor='middle' font-size='18'>Expected return (annualised, %)</text>"
    )

    # Axis ticks and labels
    for tick in axis_ticks(min_risk, max_risk):
        x = scale_x(tick)
        lines.append(
            f"  <line x1='{x}' y1='{padding + plot_height}' x2='{x}' y2='{padding + plot_height + 6}' stroke='#4a4a4a'/>"
        )
        lines.append(
            f"  <text x='{x}' y='{padding + plot_height + 24}' text-anchor='middle' font-size='14'>{tick * 100:.1f}</text>"
        )

    for tick in axis_ticks(min_return, max_return):
        y = scale_y(tick)
        lines.append(
            f"  <line x1='{margin_left - 6}' y1='{y}' x2='{margin_left}' y2='{y}' stroke='#4a4a4a'/>"
        )
        lines.append(
            f"  <text x='{margin_left - 12}' y='{y + 5}' text-anchor='end' font-size='14'>{tick * 100:.1f}</text>"
        )

    # Scatter plot of all portfolios
    for point in portfolios:
        x = scale_x(point.risk)
        y = scale_y(point.expected_return)
        lines.append(
            f"  <circle cx='{x:.2f}' cy='{y:.2f}' r='3' fill='#3b82f6' fill-opacity='0.35' stroke='none'/>"
        )

    # Frontier polyline
    frontier_points = " ".join(
        f"{scale_x(p.risk):.2f},{scale_y(p.expected_return):.2f}" for p in frontier
    )
    lines.append(
        f"  <polyline fill='none' stroke='#ef4444' stroke-width='3' points='{frontier_points}'/>"
    )

    # Highlight specific portfolios: minimum variance and maximum return
    if frontier:
        min_var = min(frontier, key=lambda p: p.risk)
        max_ret = max(frontier, key=lambda p: p.expected_return)
        highlights = [(min_var, "Minimum variance"), (max_ret, "Maximum return")]
        for point, label in highlights:
            x = scale_x(point.risk)
            y = scale_y(point.expected_return)
            lines.append(
                f"  <circle cx='{x:.2f}' cy='{y:.2f}' r='6' fill='#ffffff' stroke='#ef4444' stroke-width='2'/>"
            )
            lines.append(
                f"  <text x='{x + 10:.2f}' y='{y - 10:.2f}' font-size='14'>{label}</text>"
            )
            lines.append(
                f"  <text x='{x + 10:.2f}' y='{y + 8:.2f}' font-size='12'>{format_weight_annotation(point)}</text>"
            )

    lines.append(
        f"  <text x='{margin_left}' y='{padding - 10}' font-size='16'>Efficient frontier derived from daily close prices ({start_date:%Y-%m-%d} to {end_date:%Y-%m-%d})</text>"
    )
    lines.append("</svg>")

    with open(path, "w", encoding="utf-8") as svg_file:
        svg_file.write("\n".join(lines))


def main() -> None:
    dates, closes = read_closing_prices("temp.csv")
    if not dates:
        raise SystemExit("No price data found in temp.csv")
    returns = compute_daily_returns(closes)
    if not returns:
        raise SystemExit("Insufficient data to compute returns")
    means, cov = annualise_daily_stats(returns)
    portfolios = enumerate_portfolios(means, cov)
    frontier = filter_efficient_frontier(portfolios)
    write_svg(portfolios, frontier, "efficient_frontier.svg", dates[0], dates[-1])

    # Display quick textual summary in the console for validation
    min_var = min(frontier, key=lambda p: p.risk)
    max_ret = max(frontier, key=lambda p: p.expected_return)
    print("Minimum variance portfolio:")
    print(f"  Risk: {min_var.risk * 100:.2f}% | Return: {min_var.expected_return * 100:.2f}%")
    print(f"  Weights: {format_weight_annotation(min_var)}")
    print("Maximum return portfolio:")
    print(f"  Risk: {max_ret.risk * 100:.2f}% | Return: {max_ret.expected_return * 100:.2f}%")
    print(f"  Weights: {format_weight_annotation(max_ret)}")


if __name__ == "__main__":
    main()
