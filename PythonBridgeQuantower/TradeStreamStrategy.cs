using System;
using System.IO;
using System.Text.Json;
using TradingPlatform.BusinessLayer;

namespace PythonBridgeQuantower;

public class TradeStreamStrategy : Strategy, ICurrentSymbol
{
    [InputParameter("Symbol")]
    public Symbol CurrentSymbol { get; set; }

    [InputParameter("Sample Percent", sortIndex: 10, minimum: 1, maximum: 100, increment: 1, decimalPlaces: 0)]
    public int SamplePct { get; set; } = 100;

    private const string OutputDir = @"C:\Users\Lex\repos\python-bridge-quantower\captures";

    private StreamWriter _writer;
    private Random _rng = new();
    private int _count;

    public override string[] MonitoringConnectionsIds =>
        CurrentSymbol != null ? [CurrentSymbol.ConnectionId] : [];

    public TradeStreamStrategy()
    {
        Name = "Trade Stream";
        Description = "Streams trade prints to a JSONL file";
    }

    protected override void OnRun()
    {
        if (CurrentSymbol == null)
        {
            Log("No symbol selected", StrategyLoggingLevel.Error);
            Stop();
            return;
        }

        if (!Directory.Exists(OutputDir))
            Directory.CreateDirectory(OutputDir);
        var symbolName = CurrentSymbol.Name.Replace("/", "-").Replace("\\", "-");
        var filename = $"{symbolName}-{DateTime.Now:yyyy-MM-dd-HHmmss}.jsonl";
        var path = Path.Combine(OutputDir, filename);

        _writer = new StreamWriter(path, append: true) { AutoFlush = true };
        _count = 0;

        CurrentSymbol.NewLast += OnNewLast;
        Log($"Streaming to {path} (SamplePct={SamplePct})");
    }

    protected override void OnStop()
    {
        if (CurrentSymbol != null)
            CurrentSymbol.NewLast -= OnNewLast;

        _writer?.Dispose();
        _writer = null;

        Log($"Stopped after {_count} prints written");
    }

    private void OnNewLast(Symbol symbol, Last last)
    {
        if (SamplePct < 100 && _rng.Next(100) >= SamplePct)
            return;

        var side = last.AggressorFlag switch
        {
            AggressorFlag.Buy => "buy",
            AggressorFlag.Sell => "sell",
            _ => "unknown"
        };

        var line = JsonSerializer.Serialize(new
        {
            ts = last.Time.ToString("O"),
            price = last.Price,
            size = (int)last.Size,
            side
        });

        _writer?.WriteLine(line);
        _count++;
    }
}
