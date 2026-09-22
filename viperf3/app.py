"""viperf3 — a pseudo-graphical shell over the iperf3 client."""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Optional, Sequence

from textual.app import App

from . import __version__
from .config import ClientConfig
from .screens import ConfigScreen


class ViperfApp(App):
    """Textual application entry point."""

    CSS_PATH = Path(__file__).parent / "app.tcss"
    TITLE = "viperf3"

    def __init__(self, config: ClientConfig | None = None):
        super().__init__()
        self.config: ClientConfig = config or ClientConfig()

    def on_mount(self) -> None:
        self.push_screen(ConfigScreen())


def main(argv: Optional[Sequence[str]] = None) -> None:
    parser = argparse.ArgumentParser(
        prog="viperf3",
        description="A pseudo-graphical (TUI) shell over the iperf3 client.",
        epilog="Requires iperf3 >= 3.17 on PATH. Run without arguments to "
               "open the interface.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"viperf3 {__version__}",
    )
    parser.parse_args(argv)
    ViperfApp().run()


if __name__ == "__main__":
    main()
