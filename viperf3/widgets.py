"""Custom display widgets: an auto-scaling speed gauge and stats panel."""
from __future__ import annotations

from rich.text import Text
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Checkbox, Static


class TickCheckbox(Checkbox):
    """Checkbox that shows a clear ✓ when checked and nothing when not."""

    @property
    def BUTTON_INNER(self) -> str:  # type: ignore[override]
        return "✓" if self.value else " "


def humanize_bps(bps: float) -> str:
    """Format bits/second with an adaptive unit."""
    if bps >= 1e9:
        return f"{bps / 1e9:.2f} Gbit/s"
    if bps >= 1e6:
        return f"{bps / 1e6:.2f} Mbit/s"
    if bps >= 1e3:
        return f"{bps / 1e3:.2f} Kbit/s"
    return f"{bps:.0f} bit/s"


class SpeedGauge(Widget):
    """A horizontal bar showing the current throughput vs an auto-scaling max."""

    DEFAULT_CSS = """
    SpeedGauge {
        height: 3;
        content-align: left middle;
    }
    """

    value = reactive(0.0)        # current bits_per_second
    scale_max = reactive(1.0)    # upper bound for the bar
    label = reactive("Throughput")
    bar_color = reactive("green")

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._observed_peak = 0.0
        self._fixed_max: float | None = None  # e.g. the link speed

    def watch_value(self) -> None:
        self.refresh()

    def watch_scale_max(self) -> None:
        self.refresh()

    def set_fixed_max(self, bps: float | None) -> None:
        """Pin the scale to a fixed value (link speed), or None for auto."""
        self._fixed_max = bps
        self._rescale()

    def reset(self) -> None:
        self._observed_peak = 0.0
        self.value = 0.0
        self._rescale()

    def update_value(self, bps: float) -> None:
        self._observed_peak = max(self._observed_peak, bps)
        self._rescale()
        self.value = bps

    def _rescale(self) -> None:
        if self._fixed_max:
            self.scale_max = self._fixed_max
        else:
            # Auto mode: the scale top is the peak observed so far.
            self.scale_max = max(self._observed_peak, 1.0)

    def render(self) -> Text:
        width = max(self.size.width - 2, 10)
        frac = 0.0 if self.scale_max <= 0 else min(self.value / self.scale_max, 1.0)
        filled = int(frac * width)
        bar = Text()
        bar.append(f"{self.label}: ", style="bold")
        bar.append(humanize_bps(self.value), style=f"bold {self.bar_color}")
        bar.append("\n")
        bar.append("█" * filled, style=self.bar_color)
        bar.append("░" * (width - filled), style="grey37")
        right = humanize_bps(self.scale_max)
        pad = max(width - 1 - len(right), 1)
        bar.append(f"\n0{' ' * pad}{right}", style="dim")
        return bar


# --------------------------------------------------------------------------- #
# Braille line chart with proper two-series compositing                        #
# --------------------------------------------------------------------------- #
# Dot bit for sub-pixel (px, py) inside a braille cell: px in 0..1, py in 0..3
_DOT_BITS = ((0x01, 0x08), (0x02, 0x10), (0x04, 0x20), (0x40, 0x80))
_BRAILLE_OFFSET = 0x2800


def _bresenham(x0: int, y0: int, x1: int, y1: int):
    """Yield integer points of the line segment (x0,y0)-(x1,y1)."""
    dx, dy = abs(x1 - x0), -abs(y1 - y0)
    sx, sy = (1 if x0 < x1 else -1), (1 if y0 < y1 else -1)
    err = dx + dy
    while True:
        yield x0, y0
        if x0 == x1 and y0 == y1:
            return
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            x0 += sx
        if e2 <= dx:
            err += dx
            y0 += sy


def _rasterize(times: list[float], values: list[float],
               x_min: float, x_span: float, y_min: float, y_span: float,
               sub_w: int, sub_h: int) -> dict[tuple[int, int], int]:
    """Draw a polyline into a braille sub-pixel grid; return cell→bits map."""
    grid: dict[tuple[int, int], int] = {}
    pts = []
    for t, v in zip(times, values):
        px = round((t - x_min) / x_span * (sub_w - 1))
        py = round((1.0 - (v - y_min) / y_span) * (sub_h - 1))
        pts.append((min(max(px, 0), sub_w - 1), min(max(py, 0), sub_h - 1)))
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        for x, y in _bresenham(x0, y0, x1, y1):
            cell = (x // 2, y // 4)
            grid[cell] = grid.get(cell, 0) | _DOT_BITS[y % 4][x % 2]
    if len(pts) == 1:
        x, y = pts[0]
        grid[(x // 2, y // 4)] = _DOT_BITS[y % 4][x % 2]
    return grid


class DualLineChart(Widget):
    """Braille line chart for one or two series.

    Unlike plotext, both series are rasterized into the same braille grid, so
    their dots merge instead of the later series erasing the earlier one when
    the lines run close together.  Cells shared by both series are drawn in a
    blend colour.
    """

    DEFAULT_CSS = """
    DualLineChart {
        height: 1fr;
    }
    """

    color_a = "green"
    color_b = "blue"
    color_mix = "cyan"

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._times: list[float] = []
        self._a: list[float] = []
        self._b: list[float] = []

    def update_data(self, times: list[float], a: list[float],
                    b: list[float] | None = None) -> None:
        self._times = list(times)
        self._a = list(a)
        self._b = list(b or [])
        self.refresh()

    def render(self) -> Text:
        width, height = self.size.width, self.size.height
        if width < 20 or height < 6 or len(self._times) < 1 or not self._a:
            return Text("waiting for data…", style="dim")

        # Layout: legend row, plot rows, x-labels row.
        values = self._a + (self._b or [])
        y_max, y_min = max(values), min(values)
        if y_max == y_min:
            y_max += 1.0
            y_min -= 1.0
        pad = (y_max - y_min) * 0.05
        y_min, y_max = y_min - pad, y_max + pad
        y_span = y_max - y_min

        label_w = max(len(self._fmt(y_max)), len(self._fmt(y_min))) + 1
        plot_w = width - label_w - 1
        plot_h = height - 2
        if plot_w < 10 or plot_h < 3:
            return Text("…", style="dim")

        x_min, x_max = self._times[0], self._times[-1]
        x_span = (x_max - x_min) or 1.0
        sub_w, sub_h = plot_w * 2, plot_h * 4

        n = len(self._b)
        grid_a = _rasterize(self._times[: len(self._a)], self._a,
                            x_min, x_span, y_min, y_span, sub_w, sub_h)
        grid_b = _rasterize(self._times[:n], self._b,
                            x_min, x_span, y_min, y_span, sub_w, sub_h) if n else {}

        text = Text()
        # Legend
        if self._b:
            text.append(" " * label_w)
            text.append("⣿ Up ↑ ", style=f"bold {self.color_a}")
            text.append("⣿ Down ↓", style=f"bold {self.color_b}")
        else:
            text.append(" " * label_w)
            text.append("⣿ Mbit/s", style=f"bold {self.color_a}")
        text.append("\n")

        # Y tick rows: top, 1/3, 2/3, bottom
        tick_rows = {0: y_max, plot_h // 3: None, 2 * plot_h // 3: None, plot_h - 1: y_min}
        for row, val in list(tick_rows.items()):
            if val is None:
                frac = 1.0 - (row + 0.5) / plot_h
                tick_rows[row] = y_min + frac * y_span

        for row in range(plot_h):
            if row in tick_rows:
                text.append(f"{self._fmt(tick_rows[row]):>{label_w}}", style="dim")
                text.append("┤", style="dim")
            else:
                text.append(" " * label_w)
                text.append("│", style="dim")
            for col in range(plot_w):
                bits_a = grid_a.get((col, row), 0)
                bits_b = grid_b.get((col, row), 0)
                bits = bits_a | bits_b
                if not bits:
                    text.append(" ")
                    continue
                char = chr(_BRAILLE_OFFSET + bits)
                if bits_a and bits_b:
                    text.append(char, style=self.color_mix)
                elif bits_a:
                    text.append(char, style=self.color_a)
                else:
                    text.append(char, style=self.color_b)
            text.append("\n")

        # X labels: start, middle, end (seconds)
        left = f"{x_min:.1f}"
        mid = f"{(x_min + x_max) / 2:.1f}"
        right = f"{x_max:.1f}s"
        gap1 = max(plot_w // 2 - len(left) - len(mid) // 2, 1)
        gap2 = max(plot_w - len(left) - gap1 - len(mid) - len(right), 1)
        text.append(" " * (label_w + 1))
        text.append(left + " " * gap1 + mid + " " * gap2 + right, style="dim")
        return text

    @staticmethod
    def _fmt(value: float) -> str:
        if abs(value) >= 10000:
            return f"{value:,.0f}"
        if abs(value) >= 100:
            return f"{value:.0f}"
        return f"{value:.1f}"


class StatsPanel(Static):
    """Shows numeric summary: current / average / max / retransmits / jitter."""

    DEFAULT_CSS = """
    StatsPanel {
        height: auto;
        border: round $primary;
        padding: 0 1;
    }
    """

    def update_stats(
        self,
        current: float,
        avg: float,
        peak: float,
        *,
        retransmits: int | None = None,
        jitter_ms: float | None = None,
        lost_percent: float | None = None,
        protocol: str = "TCP",
        elapsed: float = 0.0,
    ) -> None:
        text = Text()
        text.append("Current  ", style="bold")
        text.append(humanize_bps(current) + "\n", style="bold green")
        text.append("Average  ", style="bold")
        text.append(humanize_bps(avg) + "\n", style="cyan")
        text.append("Peak     ", style="bold")
        text.append(humanize_bps(peak) + "\n", style="magenta")
        text.append("Elapsed  ", style="bold")
        text.append(f"{elapsed:.0f} s\n")
        if protocol.upper() == "UDP":
            if jitter_ms is not None:
                text.append("Jitter   ", style="bold")
                text.append(f"{jitter_ms:.3f} ms\n", style="yellow")
            if lost_percent is not None:
                color = "red" if lost_percent > 1 else "green"
                text.append("Loss     ", style="bold")
                text.append(f"{lost_percent:.2f} %\n", style=color)
        else:
            if retransmits is not None:
                color = "red" if retransmits > 0 else "green"
                text.append("Retr     ", style="bold")
                text.append(f"{retransmits}\n", style=color)
        self.update(text)
