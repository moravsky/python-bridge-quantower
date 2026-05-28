import argparse
import json
import re
import socket
import time
from collections import deque
from datetime import datetime
from pathlib import Path

from rich.table import Table
from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Static, Footer

SIDE_COLORS = {"buy": "#33bb33", "sell": "#bb3333", "unknown": "dim"}
BID_COLOR = "#33aa33"
ASK_COLOR = "#bb3333"
BEST_BID_BG = "on #114422"
BEST_ASK_BG = "on #441111"
CAPTURES_DIR = Path(__file__).resolve().parent / "captures"


def build_dom_table(bids, asks, max_levels=None, bar_width=15):
    if max_levels is not None:
        bids = bids[:max_levels]
        asks = asks[:max_levels]

    all_sizes = [b["size"] for b in bids] + [a["size"] for a in asks]
    max_size = max(all_sizes) if all_sizes else 1
    bid_width = max((len(str(b["size"])) for b in bids), default=1)
    ask_width = max((len(str(a["size"])) for a in asks), default=1)

    table = Table(show_header=True, header_style="bold", expand=True)
    table.add_column("Bids", justify="right", ratio=1)
    table.add_column("Price", justify="center", width=12)
    table.add_column("Asks", justify="left", ratio=1)

    for i, ask in enumerate(reversed(asks)):
        is_best = i == len(asks) - 1
        size = ask["size"]
        bars = "█" * max(int(size / max_size * bar_width), 1)
        label = str(size).rjust(ask_width)
        table.add_row(
            "",
            f"{ask['price']:.2f}",
            Text(f"{label} {bars}", style=ASK_COLOR),
            style=BEST_ASK_BG if is_best else "",
        )

    for i, bid in enumerate(bids):
        is_best = i == 0
        size = bid["size"]
        bars = "█" * max(int(size / max_size * bar_width), 1)
        label = str(size).rjust(bid_width)
        table.add_row(
            Text(f"{bars} {label}", style=BID_COLOR),
            f"{bid['price']:.2f}",
            "",
            style=BEST_BID_BG if is_best else "",
        )

    return table


def build_tape_table(trades, symbol="", count=0, elapsed=0):
    mps = count / elapsed if elapsed > 0 else 0.0
    title = f"{symbol}  |  {count} prints  |  {mps:.1f} msgs/sec" if symbol else ""
    table = Table(
        title=title,
        show_header=True,
        header_style="bold",
        expand=True,
    )
    table.add_column("Time", style="dim")
    table.add_column("Price", justify="right")
    table.add_column("Size", justify="right")
    table.add_column("Side", justify="center")

    for msg in trades:
        side = msg.get("side", "unknown")
        color = SIDE_COLORS.get(side, "dim")
        ts = msg.get("ts", "")
        if "T" in ts:
            ts = ts.split("T")[1][:12]
        table.add_row(
            ts,
            f"{msg.get('price', 0):.2f}",
            str(msg.get("size", 0)),
            Text(side, style=color),
        )

    return table


class DomPanel(Static):
    pass


class TapePanel(Static):
    pass


class TradeApp(App):
    CSS = """
    DomPanel { min-height: 3; }
    TapePanel { height: 1fr; min-height: 8; }
    """

    BINDINGS = [
        Binding("d", "toggle_dom", "DOM"),
        Binding("t", "toggle_tape", "Trades"),
        Binding("q", "quit", "Quit"),
        Binding("ctrl+c", "quit", show=False),
    ]

    def __init__(self, source_file=None, port=8765, delay=0.0):
        super().__init__()
        self._source_file = source_file
        self._port = port
        self._delay = delay
        self._symbol = None
        self._trade_count = 0
        self._start = time.monotonic()
        self._trades = deque(maxlen=50)
        self._bids = []
        self._asks = []
        self._capture_file = None
        self._capture_path = None
        self._running = True

    def compose(self) -> ComposeResult:
        yield TapePanel("Waiting for trades...")
        yield DomPanel("Waiting for DOM data...")
        yield Footer()

    def on_mount(self):
        self.set_interval(1 / 15, self._refresh_ui)
        if self._source_file:
            self.run_worker(self._read_file, thread=True)
        else:
            self.title = f"Listening on 127.0.0.1:{self._port}"
            self.run_worker(self._read_socket, thread=True)

    def on_unmount(self):
        self._running = False

    def _refresh_ui(self):
        dom_panel = self.query_one(DomPanel)
        tape_panel = self.query_one(TapePanel)

        elapsed = time.monotonic() - self._start

        if tape_panel.display:
            tape_panel.update(build_tape_table(
                self._trades,
                symbol=self._symbol or "...",
                count=self._trade_count,
                elapsed=elapsed,
            ))

        if dom_panel.display and self._bids:
            dom_panel.styles.height = len(self._bids) + len(self._asks) + 4
            dom_panel.update(build_dom_table(self._bids, self._asks))

    def action_toggle_dom(self):
        panel = self.query_one(DomPanel)
        panel.display = not panel.display

    def action_toggle_tape(self):
        panel = self.query_one(TapePanel)
        panel.display = not panel.display

    def _process_msg(self, msg):
        if self._symbol is None:
            self._symbol = msg.get("symbol", "UNKNOWN")
            self.call_from_thread(setattr, self, "title", self._symbol)

        msg_type = msg.get("type", "trade")
        if msg_type == "trade":
            self._trades.append(msg)
            self._trade_count += 1
        elif msg_type == "dom":
            self._bids = msg.get("bids", [])
            self._asks = msg.get("asks", [])

    def _read_file(self):
        with open(self._source_file) as f:
            for line in f:
                if not self._running:
                    break
                line = line.strip()
                if not line:
                    continue
                self._process_msg(json.loads(line))
                if self._delay > 0:
                    time.sleep(self._delay)

    def _read_socket(self):
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind(("127.0.0.1", self._port))
        srv.listen(1)
        srv.settimeout(0.5)

        conn = None
        while self._running and conn is None:
            try:
                conn, addr = srv.accept()
            except socket.timeout:
                continue

        if conn is None:
            srv.close()
            return
        conn.settimeout(0.5)

        CAPTURES_DIR.mkdir(exist_ok=True)

        try:
            buf = ""
            while self._running:
                try:
                    data = conn.recv(4096)
                except socket.timeout:
                    continue
                if not data:
                    break
                buf += data.decode("utf-8")
                while "\n" in buf:
                    line, buf = buf.split("\n", 1)
                    line = line.strip()
                    if not line:
                        continue

                    msg = json.loads(line)

                    if self._capture_file is None:
                        sym = msg.get("symbol", "LIVE")
                        safe_sym = re.sub(r"[^A-Za-z0-9._-]+", "-", sym).strip("-") or "LIVE"
                        name = f"{safe_sym}-{datetime.now().strftime('%Y-%m-%d-%H%M%S')}.jsonl"
                        self._capture_path = CAPTURES_DIR / name
                        self._capture_file = open(self._capture_path, "a")

                    self._capture_file.write(line + "\n")
                    self._capture_file.flush()
                    self._process_msg(msg)
        finally:
            if self._capture_file:
                self._capture_file.close()
            conn.close()
            srv.close()


def main():
    parser = argparse.ArgumentParser(description="Trade tape TUI")
    parser.add_argument("file", nargs="?", help="JSONL capture file (omit for socket mode)")
    parser.add_argument("--port", type=int, default=8765, help="TCP port for socket mode")
    parser.add_argument("--delay", type=float, default=0.0, help="seconds between lines in file mode")
    args = parser.parse_args()

    app = TradeApp(source_file=args.file, port=args.port, delay=args.delay)
    app.run()


if __name__ == "__main__":
    main()
