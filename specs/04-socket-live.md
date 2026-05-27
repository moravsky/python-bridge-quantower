# Commit 3 -- Socket on both sides (Phase 3)

## What this commit delivers
Live streaming from Quantower to the Python TUI over TCP. The C# strategy
connects as a client, the TUI listens as a server. The TUI logs every
received line to a capture file as a byproduct.

## C# strategy changes
- Remove file output (OutputDir constant, StreamWriter to file)
- Add `Port` InputParameter (default 8765)
- `OnRun`: connect to `127.0.0.1:Port` via `TcpClient`; if it fails, log
  error and stop. Wrap the NetworkStream in a StreamWriter.
- `OnStop`: dispose writer, dispose TcpClient
- Callback unchanged -- still writes to `_writer`

## Python TUI changes
- `file` arg becomes optional
- Add `--port` (default 8765) and `--symbol` (default "LIVE") flags
- File mode: `python tui/tape.py captures/MNQ-2026-05-26.jsonl` (unchanged)
- Socket mode: `python tui/tape.py --port 8765`
  - Binds and listens on 127.0.0.1:port
  - Accepts one connection
  - Reads newline-delimited JSON, renders tape
  - Logs every line to `captures/SYMBOL-DATE-TIME.jsonl`

## Usage
```
# Terminal 1: start TUI server
python tui/tape.py --port 8765 --symbol MNQ

# Terminal 2 (or Quantower): strategy connects automatically
```

## Verification
1. `dotnet build` succeeds
2. Start TUI in socket mode, start strategy in Quantower (live or replay)
3. Tape scrolls with live prints
4. Capture file appears in `captures/` with the received data
5. Ctrl+C the TUI, confirm clean shutdown
