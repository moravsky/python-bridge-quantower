import argparse
import json
import re
import time
from collections import deque
from datetime import datetime
from pathlib import Path

import zmq
from google.protobuf.json_format import MessageToJson, Parse
from rich.table import Table
from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Static, Footer

from messages_pb2 import DomMessage, TradeMessage

SIDE_COLORS = {"buy": "#33bb33", "sell": "#bb3333", "unknown": "dim"}
BID_COLOR = "#33aa33"
ASK_COLOR = "#bb3333"
BEST_BID_BG = "on #114422"
BEST_ASK_BG = "on #441111"
CAPTURES_DIR = Path(__file__).resolve().parent / "captures"


def build_dom_table(dom: DomMessage, max_levels=None, bar_width=15):
    bids = list(dom.bids)
    asks = list(dom.asks)
    if max_levels is not None:
        bids = bids[:max_levels]
        asks = asks[:max_levels]

    all_sizes = [b.size for b in bids] + [a.size for a in asks]
    max_size = max(all_sizes) if all_sizes else 1
    bid_width = max((len(str(b.size)) for b in bids), default=1)
    ask_width = max((len(str(a.size)) for a in asks), default=1)

    table = Table(show_header=True, header_style="bold", expand=True)
    table.add_column("Bids", justify="right", ratio=1)
    table.add_column("Price", justify="center", width=12)
    table.add_column("Asks", justify="left", ratio=1)

    for i, ask in enumerate(reversed(asks)):
        is_best = i == len(asks) - 1
        size = ask.size
        bars = "█" * max(int(size / max_size * bar_width), 1)
        label = str(size).rjust(ask_width)
        table.add_row(
            "",
            f"{ask.price:.2f}",
            Text(f"{label} {bars}", style=ASK_COLOR),
            style=BEST_ASK_BG if is_best else "",
        )

    for i, bid in enumerate(bids):
        is_best = i == 0
        size = bid.size
        bars = "█" * max(int(size / max_size * bar_width), 1)
        label = str(size).rjust(bid_width)
        table.add_row(
            Text(f"{bars} {label}", style=BID_COLOR),
            f"{bid.price:.2f}",
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

    for pb in trades:
        side = pb.side or "unknown"
        color = SIDE_COLORS.get(side, "dim")
        ts = pb.ts
        if "T" in ts:
            ts = ts.split("T")[1][:12]
        table.add_row(
            ts,
            f"{pb.price:.2f}",
            str(pb.size),
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
        self._trades: deque[TradeMessage] = deque(maxlen=50)
        self._dom: DomMessage | None = None
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
            self.title = f"Subscribing to tcp://127.0.0.1:{self._port}"
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

        if dom_panel.display and self._dom and self._dom.bids:
            dom_panel.styles.height = len(self._dom.bids) + len(self._dom.asks) + 4
            dom_panel.update(build_dom_table(self._dom))

    def action_toggle_dom(self):
        panel = self.query_one(DomPanel)
        panel.display = not panel.display

    def action_toggle_tape(self):
        panel = self.query_one(TapePanel)
        panel.display = not panel.display

    def _set_symbol_from(self, pb):
        if self._symbol is None and pb.symbol:
            self._symbol = pb.symbol
            self.call_from_thread(setattr, self, "title", self._symbol)

    def _handle_trade(self, pb: TradeMessage):
        self._set_symbol_from(pb)
        self._trades.append(pb)
        self._trade_count += 1

    def _handle_dom(self, pb: DomMessage):
        self._set_symbol_from(pb)
        self._dom = pb

    def _open_capture(self, symbol_hint: str):
        if self._capture_file is not None:
            return
        CAPTURES_DIR.mkdir(exist_ok=True)
        safe_sym = re.sub(r"[^A-Za-z0-9._-]+", "-", symbol_hint or "LIVE").strip("-") or "LIVE"
        name = f"{safe_sym}-{datetime.now().strftime('%Y-%m-%d-%H%M%S')}.jsonl"
        self._capture_path = CAPTURES_DIR / name
        self._capture_file = open(self._capture_path, "a")

    def _write_capture(self, topic: str, pb):
        self._open_capture(pb.symbol)
        # Wire topic stays at the I/O boundary; protobuf goes to JSON via MessageToJson.
        body = MessageToJson(pb, preserving_proto_field_name=True, indent=None)
        self._capture_file.write(f'{{"topic":"{topic}","msg":{body}}}\n')
        self._capture_file.flush()

    def _read_file(self):
        with open(self._source_file) as f:
            for line in f:
                if not self._running:
                    break
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                    topic = record["topic"]
                    body = json.dumps(record["msg"])
                    if topic == "trade":
                        pb = TradeMessage()
                        Parse(body, pb)
                        self._handle_trade(pb)
                    elif topic == "dom":
                        pb = DomMessage()
                        Parse(body, pb)
                        self._handle_dom(pb)
                except Exception:
                    continue
                if self._delay > 0:
                    time.sleep(self._delay)

    def _read_socket(self):
        ctx = zmq.Context()
        sub = ctx.socket(zmq.SUB)
        sub.connect(f"tcp://127.0.0.1:{self._port}")
        sub.setsockopt(zmq.SUBSCRIBE, b"")
        sub.setsockopt(zmq.RCVTIMEO, 500)

        try:
            while self._running:
                try:
                    parts = sub.recv_multipart()
                except zmq.Again:
                    continue
                except zmq.ContextTerminated:
                    break

                if len(parts) != 2:
                    continue

                topic = parts[0].decode("utf-8", errors="replace")
                try:
                    if topic == "trade":
                        pb = TradeMessage()
                        pb.ParseFromString(parts[1])
                        self._write_capture("trade", pb)
                        self._handle_trade(pb)
                    elif topic == "dom":
                        pb = DomMessage()
                        pb.ParseFromString(parts[1])
                        self._write_capture("dom", pb)
                        self._handle_dom(pb)
                except Exception:
                    continue
        finally:
            if self._capture_file:
                self._capture_file.close()
            sub.close()
            ctx.term()


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
