# Build: Quantower → Socket → Python TUI (live trade tape)

## Goal
A minimal sample (a few hours of work) that streams **trades** out of Quantower into a Python **TUI** over a localhost socket. The TUI draws a live, scrolling time-&-sales tape. That's the whole thing.

Three pieces:
1. **Quantower C# Strategy** — subscribes to a symbol's trade prints, serializes each one to JSON, writes it to a file (Phase 1) then to a socket (Phase 3). Computes nothing. It's a dumb pump.
2. **The wire** — localhost TCP, newline-delimited JSON. Python is the server (binds/listens/accepts); the strategy connects as a client.
3. **Python TUI** — reads JSON lines from a file (Phase 2) or from a socket (Phase 3), renders a scrolling tape (time, price, size, colored by aggressor side).

## Build order

**Phase 0 — Design the message contract.** You design the JSON shape; the API just tells you what's available to put in it. One genuine unknown — whether aggressor side is on the print — gets resolved in Phase 1. Everything else (`ts`, `price`, `size`) you can commit to now. Schema below.

**Phase 1 — C# pump to file + verify the API.** A headless `Strategy` with `OnRun`/`OnStop`, no strategy metrics for V0. In `OnRun`: subscribe to the symbol's trade prints; in the callback, apply the sample rate and, for each print, roll a random check against the sample percentage — if it passes, map Quantower's fields into the frozen JSON schema and write the line to a local JSONL file. In `OnStop`: unsubscribe and close cleanly. No socket yet — just file output to get real data and confirm the API shape. Use Quantower's replay feature to generate captures without waiting for live market hours.

`InputParameter`s: `SamplePct` (default `100` — percentage of trades to emit, 1–100). During early development, set `SamplePct` to 5 or 10 to keep the stream manageable on a liquid symbol; set to 100 for the full feed. Sampling is strictly a producer concern — consumers process everything they receive.

**Phase 2 — TUI against the capture file (primary dev loop).** The TUI reads a JSONL capture file directly and renders the scrolling tape — time, price, size, green for buy / red for sell / neutral for unknown — with a small header showing the symbol and a simple running `msgs/sec` counter (total messages ÷ elapsed time). The tape fills the terminal height minus the header rows, adapting to window size. No socket, no server — just `python tui/tape.py captures/NQ-2026-05-26-143201.jsonl`. Iterate here against the Phase 1 capture; Quantower stays closed.

**Phase 3 — Socket on both sides, live end to end.** Add socket code to both sides:
- **C# strategy**: in `OnRun`, attempt to connect to the Python server as a TCP client; if the connection fails, log an error and stop — do not retry. The callback now writes to the socket instead of (or in addition to) a file.
- **TUI server mode**: the TUI listens on a socket, reads JSON lines, and renders the same tape. Logs every received line verbatim to a capture file under `captures/` (e.g. `captures/NQ-2026-05-26-143201.jsonl`), so capture is a byproduct of the live server — not a separate tool.

The TUI can't tell live from file — both are the same JSON contract. Confirm the tape tracks Quantower's own time-&-sales. Use Quantower's replay feature to test without live market.

`InputParameter`s (added in this phase): `Port` (default `8765`).

## The message contract
One JSON object per line, UTF-8, newline-framed:
```json
{"type": "trade", "symbol": "MNQ", "ts": "2026-05-26T14:32:01.123456", "price": 21050.25, "size": 3, "side": "buy"}
```
- `type` — `"trade"` (required; enables multiplexing with future message types)
- `symbol` — instrument name as reported by Quantower
- `ts` — ISO-8601 string, the print's event time
- `price` — number
- `size` — integer (contracts)
- `side` — `"buy"` | `"sell"` | `"unknown"` (aggressor side; `"unknown"` when the source can't determine it)

Every producer conforms to this; the TUI only ever parses this. Freeze it after Phase 1.

## Tech stack
- **Python:** `textual` (includes `rich`) for the TUI, stdlib `socket` and `json`. `--port` CLI arg for socket mode (default `8765`).
- **C#:** .NET, `TradingPlatform.BusinessLayer`, `System.Net.Sockets`, `System.Text.Json`. No NuGet beyond what Quantower ships + built-in JSON. Reference assemblies from `repos/QuantowerRef`. Use the `init-quantower` skill to scaffold the strategy project.
- Socket: `127.0.0.1`, configurable port (default `8765`), TCP, newline-framed. The TUI is the server and starts first; the strategy is the client.

## Verify, don't guess (Phase 1)
Quantower's API surface shifts between versions, so confirm against the **actual installed Quantower assemblies** in `repos/QuantowerRef`, not from memory:
- The exact way to subscribe to trade prints (the `Last` quote type) and the precise field names/types on the trade event payload.
- Whether **aggressor side** (buy vs sell) is present on the print. If it is, map it to `side`. If it is **not**, set `side` to `"unknown"` — do not fabricate or infer it (inferring would require L2, which is out of scope). The TUI handles `"unknown"` with a neutral color, so the contract holds either way.

If a Quantower API detail can't be confirmed, flag it explicitly rather than guessing a method name.

## Non-goals — do NOT build these
- No Level 2 / DOM / order book.
- No volume profile, POC/VAH/VAL.
- No historical bars / `GetHistory`.
- No bidirectional commands, symbol switching, or request/response — the producer only pushes.
- No ML / PyTorch.
- No strategy metrics in V0.
- No separate replay client — Quantower's built-in replay feature serves this purpose.
- Single symbol, single client, no reconnection logic beyond clean connect/disconnect, no GUI beyond the terminal.

Keep it minimal. If a piece feels like it's growing into a framework, it's out of scope.

## Code style
- The TUI rendering and the `msgs/sec` header are deliberate program output — that's the product, not debug output. Separately: do not add logging/print statements for debugging; rely on a debugger with breakpoints.
- C#: use regular comments, not XML doc comments. Comment only where it adds context.
- If any unit tests are written, no `// Arrange // Act // Assert` scaffolding comments — only comments that add real context.

## Suggested layout
```
quantower/TradeStreamStrategy.cs   # Phase 1+3 — the pump (file, then socket)
captures/                          # captured .jsonl files
tui/tape.py                        # Phase 2+3 — file reader, then socket server
README.md                          # usage: file mode and socket mode
```

## Future hook (out of scope, do not build)
ML/PyTorch would later attach as *another consumer of the same socket stream* — its own process, never touching Quantower's data thread. Nothing in this build should preclude that, but build none of it now.
