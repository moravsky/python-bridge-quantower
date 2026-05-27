# Commit 1 -- Project scaffold + C# pump to file (Phase 1)

## What this commit delivers
The project skeleton (via `init-quantower`) plus a working C# strategy that subscribes to trade prints and writes them as newline-delimited JSON to a local file. No socket, no Python yet.

## Files

### Scaffolded by `init-quantower`
- `.sln`, `.gitignore`, `deploy.ps1`, `AGENTS.md`, `CLAUDE.md`, `LICENSE`
- `PythonBridgeQuantower/PythonBridgeQuantower.csproj`

### Implemented
- `PythonBridgeQuantower/TradeStreamStrategy.cs` -- the pump
- `captures/.gitkeep` -- output directory for JSONL files

## TradeStreamStrategy

### InputParameters
| Name        | Type   | Default                                                     | Description                          |
|-------------|--------|-------------------------------------------------------------|--------------------------------------|
| Symbol      | Symbol | (user picks in UI)                                          | Instrument to stream                 |
| SamplePct   | int    | 100                                                         | % of trades to emit (1-100)          |

Output directory is hardcoded to `C:\Users\Lex\repos\python-bridge-quantower\captures`.

### API mapping (verified from QuantowerRef)
| Quantower field         | JSON field | Mapping                                          |
|-------------------------|------------|--------------------------------------------------|
| `Last.Time`             | `ts`       | `DateTime` -> ISO-8601 string via `ToString("O")`|
| `Last.Price`            | `price`    | `double` -> number                               |
| `Last.Size`             | `size`     | `double` -> cast to `int`                        |
| `Last.AggressorFlag`    | `side`     | `Buy`->`"buy"`, `Sell`->`"sell"`, else->`"unknown"`|

### Lifecycle
- **`OnRun`**: open `StreamWriter` to `OutputDir/SYMBOL-DATE-TIME.jsonl` (append), subscribe `CurrentSymbol.NewLast`
- **`OnStop`**: unsubscribe, flush, dispose writer
- **Callback**: roll `Random.Next(100) < SamplePct` -> map fields -> `JsonSerializer.Serialize` -> `WriteLine` + `Flush`

## Verification
1. `dotnet build` succeeds
2. `.\deploy.ps1` deploys to Quantower
3. Run strategy on a symbol (live or Quantower replay) with SamplePct=10
4. Confirm `.jsonl` file appears in `captures/` with valid lines matching the contract:
   ```json
   {"ts":"2026-05-26T14:32:01.1234560","price":21050.25,"size":3,"side":"buy"}
   ```
