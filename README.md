# python-bridge-quantower

Streams live trade prints and Level 2 order book data from Quantower into a
Python terminal UI over a localhost TCP socket.

https://github.com/user-attachments/assets/dc364044-a92d-4e19-bd40-35471f3ce35e

## What it does

- **C# Strategy** runs inside Quantower, subscribes to trades and L2 data,
  and pushes newline-delimited JSON to a TCP socket.
- **Python TUI** listens on the socket and renders a live scrolling trade
  tape and a DOM (depth of market) price ladder with proportional bars.

## Quick start

### Prerequisites

- Quantower with a data feed connected (L2 data for DOM)
- .NET 8.0 SDK (x64)
- Python 3.10+

### Install Python dependencies

```
pip install -r requirements.txt
```

### Build and deploy the strategy

```powershell
dotnet build PythonBridgeQuantower/PythonBridgeQuantower.csproj -c Debug
.\deploy.ps1                     # deploys to C:\QuantowerDev
.\deploy.ps1 -Config Release     # deploys to C:\Quantower
```

### Run

```powershell
# 1. Start the TUI (server -- must start first)
python tui/tape.py --port 8765

# 2. In Quantower: add the "Trade Stream" strategy, pick a symbol, run it
```

The TUI will show the symbol name, trade tape, and DOM ladder as data flows in.
A capture file is saved automatically to `captures/`.

### Replay a capture file

```powershell
python tui/tape.py captures/NQ-2026-05-27-004814.jsonl
python tui/tape.py captures/NQ-2026-05-27-004814.jsonl --delay 0.05
```

## TUI keyboard shortcuts

| Key | Action         |
|-----|----------------|
| `d` | Toggle DOM     |
| `t` | Toggle trades  |
| `q` | Quit           |

Panels resize automatically when toggled. The DOM adapts its visible depth
to fit the available terminal height.

## Strategy parameters

Set these in Quantower's strategy UI:

| Parameter      | Default | Description                          |
|----------------|---------|--------------------------------------|
| Symbol         | --      | Instrument to stream                 |
| Sample Percent | 100     | % of trades to emit (1-100)          |
| Port           | 8765    | TCP port to connect to               |
| DOM Levels     | 10      | Number of order book levels per side |

## Wire protocol

Newline-delimited JSON over TCP. Two message types:

**Trade:**
```json
{"type":"trade","symbol":"NQ","ts":"2026-05-27T07:08:28.288Z","price":30111.75,"size":1,"side":"buy"}
```

**DOM snapshot (throttled to ~10/sec):**
```json
{"type":"dom","symbol":"NQ","ts":"2026-05-27T07:08:28.288Z","bids":[{"price":30111.25,"size":3}],"asks":[{"price":30112.00,"size":5}]}
```

## Project layout

```
PythonBridgeQuantower/
  TradeStreamStrategy.cs    C# strategy (the producer)
  PythonBridgeQuantower.csproj
tui/
  tape.py                   Python TUI (the consumer)
captures/                   Auto-saved JSONL capture files
specs/                      Design specs
```

## Author

**Petr Moravsky** ([petr@structuredtrading.co](mailto:petr@structuredtrading.co)) -- futures trader and developer.

If python-bridge-quantower helped you connect Quantower to Python or served as a reference for your own development -- [star the repo](https://github.com/moravsky/python-bridge-quantower) and [leave a tip](https://ko-fi.com/moravsky).
