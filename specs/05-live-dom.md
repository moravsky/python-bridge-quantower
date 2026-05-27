# Live DOM (Depth of Market) Price Ladder

## Goal
Add a live Level 2 order book display to the TUI. Price ladder layout:
bids (size) on the left, price center, asks (size) on the right. 10 levels
each side by default.

## Wire protocol

Multiplex on the existing TCP socket by adding a `type` field to all messages.

**Trade (existing contract, add `type`):**
```json
{"type":"trade","ts":"2026-05-27T07:08:28.288","price":30111.75,"size":1,"side":"buy"}
```

**DOM snapshot (new):**
```json
{"type":"dom","ts":"2026-05-27T07:08:28.288","bids":[{"price":30111.25,"size":3},{"price":30111.00,"size":8}],"asks":[{"price":30112.00,"size":5},{"price":30112.25,"size":8}]}
```

Bids array sorted descending by price (best bid first). Asks array sorted
ascending by price (best ask first).

Backward compatibility: messages without a `type` field are treated as trades.
Existing capture files still work in file mode (no DOM, just tape).

## C# strategy changes

- Subscribe to `Symbol.NewLevel2` in `OnRun`, unsubscribe in `OnStop`
- In the `NewLevel2` callback, throttle to ~10 snapshots/sec (skip if <100ms
  since last send)
- When due: call `symbol.DepthOfMarket.GetDepthOfMarketAggregatedCollections()`
  to get the current aggregated book -- no need to maintain our own book state
- Take top N bids and asks from the result
- Serialize as a `type: "dom"` JSON line and write to the socket
- Add `type: "trade"` to existing trade messages

**New InputParameter:** `DomLevels` (int, default 10) -- number of levels
per side to send.

**API details (from QuantowerRef):**
- Subscribe: `CurrentSymbol.NewLevel2 += handler`
- Delegate: `void Level2Handler(Symbol symbol, Level2Quote level2, DOMQuote dom)`
- Snapshot fetch: `symbol.DepthOfMarket.GetDepthOfMarketAggregatedCollections(params)`
- Returns `Level2Item[]` arrays for Asks and Bids, each with `Price` and `Size`
- Use `LevelsCount` parameter to limit depth

## TUI changes

Socket mode renders a split layout -- tape on top, DOM ladder below:

```
              MNQ  |  305 prints  |  9.7 msgs/sec
+----------+----------+----------+
| Bids     |  Price   |    Asks  |
+----------+----------+----------+
|          | 30112.25 |        8 |
|          | 30112.00 |        5 |   <-- best ask (highlighted)
|        3 | 30111.25 |          |   <-- best bid (highlighted)
|        8 | 30111.00 |          |
|        7 | 30110.75 |          |
+----------+----------+----------+

+----------+----------+----------+----------+
| Time     |    Price |     Size |   Side   |
+----------+----------+----------+----------+
| 07:08:29 | 30110.50 |        1 |   sell   |
| ...      |          |          |          |
```

- Best bid row: cyan/teal background or highlight
- Best ask row: orange/red background or highlight
- DOM updates in place (not scrolling -- it's a fixed grid that refreshes)
- Tape scrolls as before below the DOM
- Parse `type` field: route `"dom"` messages to ladder, `"trade"` to tape
- File mode: tape only (no DOM data in captures)

### Keyboard controls
Toggle panels live without restarting:
- `d` -- toggle DOM panel on/off
- `t` -- toggle tape panel on/off
- Both start enabled in socket mode

When one panel is hidden, the other expands to fill the terminal. When both
are visible, they split the space. A footer legend shows available keys:
`d - DOM  |  t - Trades`

### Tech
Switch from `rich` to `textual` (built on `rich`) for cross-platform key
handling and reactive layout. Update `requirements.txt` accordingly.
`textual` is the only added dependency -- it bundles `rich`.

## Non-goals for V0
- No cumulative size column
- No last-trade marker on the ladder
- No bid/ask imbalance highlighting
- No configurable levels from TUI side (controlled by C# `DomLevels` param)
- No spread display in header

## Verification
1. `dotnet build` succeeds
2. Start TUI in socket mode, start strategy in Quantower
3. DOM ladder shows 10 levels each side, updating live
4. Tape continues scrolling below the DOM
5. Best bid/ask rows are visually distinct
6. File mode still works (tape only, no DOM)
