"""Textual screens: client configuration and the live test view."""
from __future__ import annotations

import statistics
from typing import Optional

from textual import on, work
from textual.app import ComposeResult
from textual.containers import Grid, Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen, Screen
from textual.widgets import (
    Button,
    Checkbox,
    Footer,
    Header,
    Input,
    Label,
    Log,
    Select,
    Static,
)

from textual_plotext import PlotextPlot

from .config import (
    ClientConfig,
    delete_preset,
    load_presets,
    save_preset,
)
from .netinfo import egress_interface, link_speed_mbps
from .parser import ErrorEvent
from .models import Interval, StartInfo, Summary
from .runner import IperfRunner
from .widgets import (
    DualLineChart,
    SpeedGauge,
    StatsPanel,
    TickCheckbox,
    humanize_bps,
)


class ConfigScreen(Screen):
    """Form to configure iperf3 client parameters."""

    BINDINGS = [
        ("enter", "start", "Start test"),
        ("ctrl+s", "save_preset", "Save preset"),
        ("q", "quit", "Quit"),
    ]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with VerticalScroll(id="config-body"):
            yield Label("[b]Server[/b]")
            with Horizontal(classes="row"):
                yield Input(value=self.app.config.host, placeholder="host / IP", id="host")
                yield Input(value=str(self.app.config.port), placeholder="port", id="port")
            yield Label("[b]Test parameters[/b]")
            with Grid(id="params-grid"):
                yield Label("Duration (s)")
                yield Input(value=str(self.app.config.duration), id="duration")
                yield Label("Parallel streams")
                yield Input(value=str(self.app.config.parallel), id="parallel")
                yield Label("Interval (s)")
                yield Input(value=str(self.app.config.interval), id="interval")
                yield Label("Omit (s)")
                yield Input(value=str(self.app.config.omit), id="omit")
                yield Label("Bitrate (UDP, e.g. 100M)")
                yield Input(value=self.app.config.bitrate, placeholder="unlimited", id="bitrate")
                yield Label("TCP window (e.g. 256K)")
                yield Input(value=self.app.config.window, placeholder="auto", id="window")
                yield Label("Extra flags")
                yield Input(value=self.app.config.extra, placeholder="raw iperf3 flags", id="extra")
            with Horizontal(classes="row"):
                yield TickCheckbox("UDP", value=self.app.config.udp, id="udp")
                yield TickCheckbox("Reverse (-R)", value=self.app.config.reverse, id="reverse")
                yield TickCheckbox("Bidirectional", value=self.app.config.bidir, id="bidir")
            yield Label("[b]Presets[/b]")
            with Horizontal(classes="row"):
                yield Select([], prompt="Select preset…", id="preset-select", allow_blank=True)
                yield Button("Load", id="load-preset", variant="primary")
                yield Button("Save as…", id="save-preset", variant="success")
                yield Button("Delete", id="delete-preset", variant="error")
            yield Static("", id="config-error", classes="error")
            with Horizontal(id="action-row"):
                yield Button("▶ Start test", id="start", variant="success")
        yield Footer()

    def on_mount(self) -> None:
        self.title = "viperf3"
        self.sub_title = "client configuration"
        self._refresh_presets()

    def _refresh_presets(self) -> None:
        presets = load_presets()
        select = self.query_one("#preset-select", Select)
        select.set_options([(name, name) for name in sorted(presets)])

    # ---- collecting the form ------------------------------------------- #
    def _collect(self) -> Optional[ClientConfig]:
        try:
            cfg = ClientConfig(
                host=self.query_one("#host", Input).value,
                port=int(self.query_one("#port", Input).value or 0),
                duration=int(self.query_one("#duration", Input).value or 0),
                parallel=int(self.query_one("#parallel", Input).value or 0),
                interval=float(self.query_one("#interval", Input).value or 1),
                omit=int(self.query_one("#omit", Input).value or 0),
                bitrate=self.query_one("#bitrate", Input).value,
                window=self.query_one("#window", Input).value,
                extra=self.query_one("#extra", Input).value,
                udp=self.query_one("#udp", Checkbox).value,
                reverse=self.query_one("#reverse", Checkbox).value,
                bidir=self.query_one("#bidir", Checkbox).value,
            )
        except ValueError:
            self._show_error("Numeric fields must contain valid numbers")
            return None
        errors = cfg.validate()
        if errors:
            self._show_error("; ".join(errors))
            return None
        self._show_error("")
        return cfg

    def _show_error(self, message: str) -> None:
        self.query_one("#config-error", Static).update(message)

    # ---- actions ------------------------------------------------------- #
    @on(Button.Pressed, "#start")
    def action_start(self) -> None:
        cfg = self._collect()
        if cfg is None:
            return
        self.app.config = cfg
        self.app.push_screen(TestScreen(cfg))

    @on(Button.Pressed, "#save-preset")
    def action_save_preset(self) -> None:
        cfg = self._collect()
        if cfg is None:
            return
        self.app.push_screen(SavePresetModal(cfg), self._after_save)

    def _after_save(self, _result) -> None:
        self._refresh_presets()

    @on(Button.Pressed, "#load-preset")
    def _load_preset(self) -> None:
        select = self.query_one("#preset-select", Select)
        if select.value is Select.BLANK:
            self._show_error("Select a preset to load")
            return
        presets = load_presets()
        cfg = presets.get(str(select.value))
        if cfg:
            self.app.config = cfg
            self.app.pop_screen()
            self.app.push_screen(ConfigScreen())

    @on(Button.Pressed, "#delete-preset")
    def _delete_preset(self) -> None:
        select = self.query_one("#preset-select", Select)
        if select.value is not Select.BLANK:
            delete_preset(str(select.value))
            self._refresh_presets()

    def action_quit(self) -> None:
        self.app.exit()


class SavePresetModal(ModalScreen[bool]):
    """Ask for a preset name and persist the config."""

    def __init__(self, config: ClientConfig):
        super().__init__()
        self._config = config

    def compose(self) -> ComposeResult:
        with Vertical(id="modal-box"):
            yield Label("Save preset as:")
            yield Input(placeholder="preset name", id="preset-name")
            with Horizontal():
                yield Button("Save", variant="success", id="confirm")
                yield Button("Cancel", id="cancel")

    @on(Button.Pressed, "#confirm")
    @on(Input.Submitted, "#preset-name")
    def _confirm(self) -> None:
        name = self.query_one("#preset-name", Input).value.strip()
        if name:
            save_preset(name, self._config)
            self.dismiss(True)

    @on(Button.Pressed, "#cancel")
    def _cancel(self) -> None:
        self.dismiss(False)


class TestScreen(Screen):
    """Live view: gauge, chart and stats while iperf3 runs."""

    BINDINGS = [
        ("s", "stop", "Stop"),
        ("escape", "back", "Back"),
        ("b", "back", "Back"),
    ]

    def __init__(self, config: ClientConfig):
        super().__init__()
        self._config = config
        self._runner: Optional[IperfRunner] = None
        self._times: list[float] = []
        self._tx: list[float] = []     # client→server ("Up") mbps
        self._rx: list[float] = []     # server→client ("Down") mbps, --bidir only
        self._last_streams: list = []  # per-stream samples of the latest interval
        self._iface: Optional[str] = None
        self._link_mbps: Optional[int] = None
        self._peak = 0.0
        self._finished = False
        self._had_error = False

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="test-body"):
            with Vertical(id="left-col"):
                yield SpeedGauge(id="gauge")
                yield SpeedGauge(id="gauge-rx")
                with Horizontal(id="gauge-opts"):
                    yield Static("", id="iface-info")
                    yield TickCheckbox("Scale to link speed", id="link-scale")
                yield DualLineChart(id="chart")
                yield PlotextPlot(id="bars")
            with Vertical(id="right-col"):
                yield StatsPanel(id="stats")
                yield Log(id="log", highlight=False)
        with Horizontal(id="test-actions"):
            yield Button("■ Stop", id="stop", variant="error")
            yield Button("◀ Back", id="back")
        yield Footer()

    @property
    def _target(self) -> str:
        proto = "UDP" if self._config.udp else "TCP"
        return f"{proto} → {self._config.host}:{self._config.port}"

    def on_mount(self) -> None:
        self.title = "viperf3"
        self.sub_title = f"{self._target} — running"
        gauge = self.query_one("#gauge", SpeedGauge)
        gauge_rx = self.query_one("#gauge-rx", SpeedGauge)
        if self._config.bidir:
            gauge.label = "Up ↑"
            gauge_rx.label = "Down ↓"
            gauge_rx.bar_color = "blue"
        else:
            gauge.label = "Throughput"
            gauge_rx.display = False
        chart = self.query_one("#chart", DualLineChart)
        chart.border_title = "Throughput over time"

        # Detect the egress interface and its link speed for the gauge scale.
        self._iface = egress_interface(self._config.host)
        self._link_mbps = link_speed_mbps(self._iface) if self._iface else None
        iface_text = f"Interface: [b]{self._iface or '?'}[/b]"
        if self._link_mbps:
            iface_text += f" · link {humanize_bps(self._link_mbps * 1e6)}"
        else:
            iface_text += " · link speed unknown"
        self.query_one("#iface-info", Static).update(iface_text)
        link_box = self.query_one("#link-scale", TickCheckbox)
        if not self._link_mbps:
            link_box.disabled = True
            link_box.tooltip = "Link speed is not reported for this interface"

        bars = self.query_one("#bars", PlotextPlot)
        bars.plt.title("Per-stream histogram")
        bars.plt.xlabel("stream")
        bars.plt.ylabel("Mbit/s")
        if self._iface:
            speed = (
                humanize_bps(self._link_mbps * 1e6) if self._link_mbps else "speed unknown"
            )
            self._log(f"Interface: {self._iface} ({speed})")
        self._log(f"$ {' '.join(IperfRunner(self._config).command)}")
        self.run_test()

    def _log(self, message: str) -> None:
        self.query_one("#log", Log).write_line(message)

    @work(exclusive=True)
    async def run_test(self) -> None:
        self._runner = IperfRunner(self._config)
        try:
            async for event in self._runner.run():
                try:
                    self._handle_event(event)
                except Exception as exc:  # noqa: BLE001 - keep consuming events
                    self._log(f"[ui error] {type(exc).__name__}: {exc}")
        except Exception as exc:  # pragma: no cover - defensive
            self._had_error = True
            self._log(f"[error] {exc}")
        # A user-requested stop wins: iperf3 reports an "interrupt" error on
        # SIGTERM which should not be classified as a failure.
        if self._runner and self._runner._stopped:
            self._log("Test stopped by user.")
            self._set_finished("stopped")
        elif self._had_error:
            self._set_finished("error")
        else:
            self._set_finished("finished")

    def _set_finished(self, status: str) -> None:
        """Flip the screen into its terminal state and repurpose the button."""
        self._finished = True
        self.sub_title = f"{self._target} — {status}"
        button = self.query_one("#stop", Button)
        button.label = "▶ Restart"
        button.variant = "success"

    def _handle_event(self, event) -> None:
        if isinstance(event, StartInfo):
            self._log(
                f"Connected to {event.connecting_to} "
                f"({event.protocol}, {event.num_streams} stream(s))"
            )
        elif isinstance(event, Interval):
            self._on_interval(event)
        elif isinstance(event, Summary):
            self._on_summary(event)
        elif isinstance(event, ErrorEvent):
            self._had_error = True
            self._log(f"[error] {event.message}")

    def _on_interval(self, interval: Interval) -> None:
        if interval.omitted:
            self._log(f"[omitted] {humanize_bps(interval.bits_per_second)}")
            return
        bps = interval.bits_per_second
        self._peak = max(self._peak, bps)
        self._times.append(interval.midpoint)
        self._tx.append(interval.mbps)
        self._last_streams = interval.streams
        if interval.reverse_bps is not None:
            self._rx.append(interval.reverse_mbps)
            self.query_one("#gauge-rx", SpeedGauge).update_value(interval.reverse_bps)

        gauge = self.query_one("#gauge", SpeedGauge)
        gauge.update_value(bps)

        avg = statistics.fmean([v * 1e6 for v in self._tx]) if self._tx else 0.0
        self.query_one("#stats", StatsPanel).update_stats(
            current=bps,
            avg=avg,
            peak=self._peak,
            retransmits=interval.retransmits,
            jitter_ms=interval.jitter_ms,
            lost_percent=interval.lost_percent,
            protocol="UDP" if self._config.udp else "TCP",
            elapsed=interval.end,
        )
        self._redraw_chart()

    def _on_summary(self, summary: Summary) -> None:
        self._log("─" * 30)
        if summary.bidir_sent_bps is not None:
            self._log(f"Up   ↑   : {humanize_bps(summary.sent_bps)}")
            self._log(f"Down ↓   : {humanize_bps(summary.bidir_sent_bps)}")
        else:
            self._log(f"Sender   : {humanize_bps(summary.sent_bps)}")
            self._log(f"Receiver : {humanize_bps(summary.received_bps)}")
        if summary.retransmits is not None:
            self._log(f"Retransmits: {summary.retransmits}")
        if summary.jitter_ms is not None:
            self._log(f"Jitter   : {summary.jitter_ms:.3f} ms")
        if summary.lost_percent is not None:
            self._log(f"Loss     : {summary.lost_percent:.2f} %")
        if summary.cpu_local is not None:
            self._log(f"CPU local/remote: {summary.cpu_local:.1f}% / "
                      f"{summary.cpu_remote or 0:.1f}%")

    def _redraw_chart(self) -> None:
        bidir = bool(self._rx)
        self.query_one("#chart", DualLineChart).update_data(
            self._times, self._tx, self._rx if bidir else None
        )

        bars = self.query_one("#bars", PlotextPlot)
        bars.plt.clear_data()
        # Histogram of the latest interval broken down by stream.  A
        # categorical x-axis with the "sd" (full-block) marker keeps bar tops
        # aligned with their bases at any terminal width.
        up = [s.bits_per_second / 1e6 for s in self._last_streams if s.sender]
        down = [s.bits_per_second / 1e6 for s in self._last_streams if not s.sender]
        if not up and not down and self._tx:
            up = [self._tx[-1]]  # fall back to the interval sum
        n = max(len(up), len(down))
        if n:
            labels = [f"S{i}" for i in range(1, n + 1)]
            if down:
                up += [0.0] * (n - len(up))
                down += [0.0] * (n - len(down))
                bars.plt.multiple_bar(
                    labels, [up, down],
                    marker="sd", color=["green", "blue"],
                    labels=["Up ↑", "Down ↓"], width=0.6,
                )
            else:
                bars.plt.bar(labels, up, marker="sd", color="cyan", width=0.6)
        bars.refresh()

    @on(Checkbox.Changed, "#link-scale")
    def _toggle_link_scale(self, event: Checkbox.Changed) -> None:
        fixed = self._link_mbps * 1e6 if (event.value and self._link_mbps) else None
        self.query_one("#gauge", SpeedGauge).set_fixed_max(fixed)
        self.query_one("#gauge-rx", SpeedGauge).set_fixed_max(fixed)

    # ---- actions ------------------------------------------------------- #
    @on(Button.Pressed, "#stop")
    def action_stop(self) -> None:
        if not self._finished:
            if self._runner:
                self._runner.stop()
                self._log("Stopping test…")
            return
        self._restart()

    def _restart(self) -> None:
        """Reset state and run the same configuration again."""
        self._times.clear()
        self._tx.clear()
        self._rx.clear()
        self._last_streams = []
        self._peak = 0.0
        self._finished = False
        self._had_error = False
        self.sub_title = f"{self._target} — running"
        button = self.query_one("#stop", Button)
        button.label = "■ Stop"
        button.variant = "error"
        self.query_one("#gauge", SpeedGauge).reset()
        self.query_one("#gauge-rx", SpeedGauge).reset()
        self._log("")
        self._log(f"$ {' '.join(IperfRunner(self._config).command)}")
        self.run_test()

    @on(Button.Pressed, "#back")
    def action_back(self) -> None:
        if self._runner:
            self._runner.stop()
        self.app.pop_screen()
