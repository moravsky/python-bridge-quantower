# Architecture

## Projects

```
PythonBridgeQuantower/
  PythonBridgeQuantower.csproj   -- Strategy, .NET 8.0, x64
  TradeStreamStrategy.cs         -- subscribes to trade prints, writes JSONL

tui/
  tape.py                        -- Python TUI, reads JSONL file or socket

captures/                        -- JSONL capture files (SYMBOL-DATE-TIME.jsonl)
specs/                           -- design specs and commit plans
```

## Data Flow

Phase 1 (file): Strategy -> JSONL file on disk
Phase 3 (socket): Strategy -> TCP socket -> TUI server

The strategy subscribes to `Symbol.NewLast` events. Each trade print is
mapped to the JSON contract (`ts`, `price`, `size`, `side`), serialized,
and written to either a file (Phase 1) or a TCP socket (Phase 3).

The TUI reads JSON lines from a file (Phase 2) or listens on a TCP socket
(Phase 3) and renders a scrolling time-and-sales tape.

## Wiring

- Strategy entry points: `OnRun` (subscribe + connect), `OnStop` (unsubscribe
  + close).
- Event subscription: `CurrentSymbol.NewLast += OnNewLast` in `OnRun`.
- Socket roles: TUI is the TCP server (binds/listens), strategy is the client
  (connects). Server must start first.
- No reconnection logic -- strategy logs an error and stops if the server is
  not reachable.

## Settings

Strategy `InputParameter`s exposed in Quantower UI:

| Name       | Type   | Default        | Purpose                     |
|------------|--------|----------------|-----------------------------|
| Symbol     | Symbol | (user picks)   | Instrument to stream        |
| SamplePct  | int    | 100            | % of trades to emit (1-100) |
| Port       | int    | 8765           | TCP port (Phase 3)          |

Output directory is hardcoded to `C:\Users\Lex\repos\python-bridge-quantower\captures`.

Python CLI args: `--port` for socket mode, positional file path for file mode.

## Decisions

- **Raw TCP over message queue or gRPC**: no external dependencies, localhost
  single-consumer, trivially debuggable with netcat/jq. gRPC would add
  protobuf deps on both sides for no benefit at this scale.
- **Newline-delimited JSON over binary framing**: human-readable, trivially
  parseable in both languages, capture files are plain text.
- **TUI as server, strategy as client**: the TUI is the stable long-running
  process during development; the strategy is toggled on/off in Quantower.
  "Start viewer, then start feed" is a simple mental model.
- **Sampling on producer only**: consumers process everything they receive.
  The producer's `SamplePct` controls volume at the source, keeping the
  consumer code simple.
- **File output in Phase 1, socket in Phase 3**: decouples C# and Python
  development. File output validates the API and produces real fixtures
  without any Python code running.
