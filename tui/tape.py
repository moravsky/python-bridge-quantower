import argparse
import json
import time
from collections import deque
from pathlib import Path

from rich.console import Console
from rich.live import Live
from rich.table import Table
from rich.text import Text

SIDE_COLORS = {"buy": "green", "sell": "red", "unknown": "dim"}


def parse_symbol(filepath):
    stem = Path(filepath).stem
    parts = stem.split("-")
    for i, part in enumerate(parts):
        if len(part) == 4 and part.isdigit():
            return "-".join(parts[:i]) if i > 0 else stem
    return stem


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


def main():
    parser = argparse.ArgumentParser(description="Trade tape TUI")
    parser.add_argument("file", help="JSONL capture file to display")
    parser.add_argument(
        "--delay", type=float, default=0.0,
        help="seconds between lines (0 = fast as possible)",
    )
    args = parser.parse_args()

    console = Console()
    tape_depth = max(console.size.height - 6, 5)

    prints = deque(maxlen=tape_depth)
    symbol = parse_symbol(args.file)
    count = 0
    start = time.monotonic()

    with open(args.file) as f:
        with Live(console=console, refresh_per_second=30) as live:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                msg = json.loads(line)
                prints.append(msg)
                count += 1
                elapsed = time.monotonic() - start
                live.update(build_table(prints, symbol, count, elapsed))
                if args.delay > 0:
                    time.sleep(args.delay)



if __name__ == "__main__":
    main()
