"""viperf3 — a pseudo-graphical shell over the iperf3 client."""
from __future__ import annotations

from pathlib import Path

from textual.app import App

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


def main() -> None:
    ViperfApp().run()


if __name__ == "__main__":
    main()
