# Commit 2 -- TUI file reader (Phase 2)

## What this commit delivers
A Python TUI that reads a JSONL capture file and renders a scrolling trade
tape using `rich.Live`. This is the primary dev loop -- iterate against a
captured file, Quantower stays closed.

## Usage
```
python tui/tape.py captures/NQ-2026-05-26-143201.jsonl
python tui/tape.py captures/NQ-2026-05-26-143201.jsonl --delay 0.05
```

## Files
- `tui/tape.py` -- the TUI
- `requirements.txt` -- `rich`

## TUI design

### Header
`SYMBOL | 1234 prints | 45.2 msgs/sec`

Symbol is parsed from the capture filename (everything before the date
portion). msgs/sec is total prints / elapsed wall time.

### Table
| Time         | Price    | Size | Side |
|--------------|----------|------|------|
| 14:32:01.123 | 21050.25 |    3 | buy  |

- Time: HH:MM:SS.fff extracted from the ISO-8601 `ts` field
- Price: formatted to 2 decimal places
- Size: integer
- Side: green for buy, red for sell, dim for unknown

### Tape depth
Terminal height minus header/border rows. Oldest prints roll off the top
as new ones arrive. Adapts to window size at startup.

### File mode behavior
Lines are read one at a time and rendered progressively via `rich.Live`.
`--delay N` adds a sleep between lines (default 0, fast as possible).
After the file is consumed, the final tape stays on screen.

## Verification
1. Create a small test JSONL file with a few lines matching the contract
2. `python tui/tape.py test.jsonl` -- should render a colored tape
3. `python tui/tape.py test.jsonl --delay 0.5` -- should scroll visibly
