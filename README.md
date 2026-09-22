# viperf3

[![CI](https://github.com/ilkz/viperf3/actions/workflows/ci.yml/badge.svg)](https://github.com/ilkz/viperf3/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/downloads/)

A pseudo-graphical (TUI) shell over the **iperf3** client — visualise network
throughput as live charts and gauges, and configure the client from a simple form.

Built with [Textual](https://textual.textualize.io/).

![viperf3 running a TCP throughput test](viperf3.jpg)

## Features

- **Live throughput gauges** — auto-scaling bars for the current speed. In
  bidirectional mode there are two, Up and Down, each with its own colour.
- **Scale to link speed** — optional: peg the gauge maximum to the link speed
  of the egress interface instead of the peak observed during the run.
- **Egress interface readout** — shows which interface the kernel routes the
  test through, and the link speed reported by sysfs.
- **Time-series chart** — a custom braille renderer. Both directions are
  rasterised into one shared sub-pixel grid, so overlapping lines blend
  instead of erasing one another, and crossings are highlighted.
- **Per-stream histogram** — one bar per stream for the latest interval when
  running with `-P N`, paired Up/Down bars under `--bidir`.
- **Stats panel** — current / average / peak / elapsed, plus TCP retransmits
  or UDP jitter & loss.
- **Run log** — the exact iperf3 command line, connection details, events and
  the closing summary with retransmits and CPU usage.
- **Stop and restart** — explicit run status in the header. Stopping a run
  yourself is not reported as an error, and the button turns into **Restart**
  to repeat the same configuration on a cleared chart.
- **Configuration form** — host, port, duration (`-t`), parallel streams (`-P`),
  interval (`-i`), omit (`-O`), UDP mode, target bitrate (`-b`), reverse (`-R`),
  bidirectional (`--bidir`), TCP window (`-w`) and raw extra flags, all
  validated before the client is launched.
- **Presets** — save/load/delete named client configurations
  (stored in `~/.config/viperf3/presets.json`).
- Robust, version-tolerant parsing via iperf3's `--json-stream` (requires
  iperf3 **≥ 3.17**).

## Requirements

- Python **3.9+**
- **iperf3 ≥ 3.17** on `PATH` (or at `/usr/local/bin/iperf3`)

> [!IMPORTANT]
> **The `apt` package is too old.** Ubuntu 22.04 ships iperf3 **3.9**, which
> has no `--json-stream` and will not work with viperf3. Debian and other
> LTS distributions are usually in the same boat.
>
> Check what you have:
>
> ```bash
> iperf3 --version
> ```
>
> If it is below 3.17, build it from source:
>
> ```bash
> wget https://github.com/esnet/iperf/archive/refs/tags/3.17.1.tar.gz
> tar xzf 3.17.1.tar.gz && cd iperf-3.17.1
> ./configure && make -j"$(nproc)" && sudo make install && sudo ldconfig
> ```
>
> This installs to `/usr/local/bin/iperf3`, which viperf3 prefers over any
> older binary earlier on `PATH`.

## Install

```bash
python3 -m venv .venv
.venv/bin/pip install -e .
# make it available system-wide (no venv activation needed):
sudo ln -sf "$(pwd)/.venv/bin/viperf3" /usr/local/bin/viperf3
```

## Run

```bash
viperf3            # from anywhere
```

Fill in the server host/port and parameters, then press **Enter** (or the
**▶ Start test** button).

| Key | Screen | Action |
|-----|--------|--------|
| `Enter`  | config | Start the test |
| `Ctrl+S` | config | Save the current settings as a preset |
| `Q`      | config | Quit |
| `S`      | test   | Stop the running test |
| `Esc` / `B` | test | Back to the configuration form |

You need an iperf3 **server** to test against:

```bash
iperf3 -s            # on the remote host
```

## Standalone binary

Build a single self-contained executable (no Python required on the target):

```bash
.venv/bin/pip install pyinstaller   # plus: apt install libpython3.10
bash build_scripts/build_binary.sh  # → dist/viperf3 (~18 MB)
```

The target machine still needs **iperf3 ≥ 3.17** on `PATH` and a glibc at
least as new as the build machine's.

## Development

```bash
pip install -e '.[dev]'
pytest
```

The parser is covered by fixture-based tests (`viperf3/tests/fixtures/*.jsonl`)
so it can be validated without a running server.

## Architecture

| Module | Responsibility |
|--------|----------------|
| `models.py`  | Dataclasses for stream events: `StreamSample`, `Interval`, `StartInfo`, `Summary`. |
| `parser.py`  | Tolerant `--json-stream` line parser. |
| `config.py`  | `ClientConfig`, CLI argument builder, preset persistence. |
| `netinfo.py` | Egress interface via `ip route get`, link speed from sysfs. |
| `runner.py`  | Locates the iperf3 binary, runs it as an async subprocess, streams parsed events. |
| `widgets.py` | `SpeedGauge`, `DualLineChart`, `StatsPanel`, `TickCheckbox`. |
| `screens.py` | `ConfigScreen`, `TestScreen`, `SavePresetModal`. |
| `app.py`     | Textual `App` entry point. |

Data flow: `IperfRunner` spawns `iperf3 … --json-stream`, reads stdout line by
line, `parser.parse_line` turns each line into a dataclass, and `TestScreen`
updates the widgets. A rendering error on one event is logged but never aborts
the run.

## Roadmap ideas

- Export results to CSV / JSON / PNG.
- Run history, with past runs overlaid on the chart for comparison.
- Server address book and quick re-run.
- Per-stream min/avg/max across the whole run, not just the latest interval.
- Separate jitter and packet-loss gauges for UDP.
