import argparse
import json
import socket
import time
from collections import deque
from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.live import Live
from rich.table import Table
from rich.text import Text

SIDE_COLORS = {"buy": "green", "sell": "red", "unknown": "dim"}
CAPTURES_DIR = Path(__file__).resolve().parent.parent / "captures"


def build_table(prints, symbol, count, elapsed):
    mps = count / elapsed if elapsed > 0 else 0.0
    table = Table(
        title=f"{symbol}  |  {count} prints  |  {mps:.1f} msgs/sec",
        show_header=True,
        header_style="bold",
        expand=True,
    )
    table.add_column("Time", style="dim")
    table.add_column("Price", justify="right")
    table.add_column("Size", justify="right")
    table.add_column("Side", justify="center")

    for msg in prints:
        side = msg.get("side", "unknown")
        color = SIDE_COLORS.get(side, "dim")
        ts = msg.get("ts", "")
        if "T" in ts:
            ts = ts.split("T")[1][:12]
        table.add_row(
            ts,
            f"{msg.get('price', 0):.2f}",
            str(msg.get('size', 0)),
            Text(side, style=color),
        )

    return table


def run_file_mode(args):
    console = Console()
    tape_depth = max(console.size.height - 6, 5)
    prints = deque(maxlen=tape_depth)
    symbol = None
    count = 0
    start = time.monotonic()

    with open(args.file) as f:
        with Live(console=console, refresh_per_second=30) as live:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                msg = json.loads(line)
                if symbol is None:
                    symbol = msg.get("symbol", "UNKNOWN")
                prints.append(msg)
                count += 1
                elapsed = time.monotonic() - start
                live.update(build_table(prints, symbol, count, elapsed))
                if args.delay > 0:
                    time.sleep(args.delay)


def run_socket_mode(args):
    console = Console()
    tape_depth = max(console.size.height - 6, 5)
    prints = deque(maxlen=tape_depth)
    symbol = None
    count = 0
    capture_file = None
    capture_path = None

    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", args.port))
    srv.listen(1)
    console.print(f"Listening on 127.0.0.1:{args.port} ...")

    conn, addr = srv.accept()
    conn.settimeout(0.5)
    console.print(f"Connected: {addr}")

    start = time.monotonic()

    try:
        with Live(console=console, refresh_per_second=15) as live:
            buf = ""
            while True:
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
                    if symbol is None:
                        symbol = msg.get("symbol", "LIVE")
                        CAPTURES_DIR.mkdir(exist_ok=True)
                        capture_name = f"{symbol}-{datetime.now().strftime('%Y-%m-%d-%H%M%S')}.jsonl"
                        capture_path = CAPTURES_DIR / capture_name
                        capture_file = open(capture_path, "a")
                    if capture_file:
                        capture_file.write(line + "\n")
                        capture_file.flush()
                    if msg.get("type", "trade") != "trade":
                        continue
                    prints.append(msg)
                    count += 1
                    elapsed = time.monotonic() - start
                    live.update(build_table(prints, symbol, count, elapsed))
    except KeyboardInterrupt:
        pass
    finally:
        if capture_file:
            capture_file.close()
        conn.close()
        srv.close()
        if capture_path:
            console.print(f"Captured {count} prints to {capture_path}")


def main():
    parser = argparse.ArgumentParser(description="Trade tape TUI")
    parser.add_argument("file", nargs="?", help="JSONL capture file (omit for socket mode)")
    parser.add_argument("--port", type=int, default=8765, help="TCP port for socket mode")
    parser.add_argument("--delay", type=float, default=0.0, help="seconds between lines in file mode")
    args = parser.parse_args()

    if args.file:
        run_file_mode(args)
    else:
        run_socket_mode(args)


if __name__ == "__main__":
    main()
