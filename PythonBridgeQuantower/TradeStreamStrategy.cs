using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Net.Sockets;
using System.Text.Json;
using TradingPlatform.BusinessLayer;

namespace PythonBridgeQuantower;

public class TradeStreamStrategy : Strategy, ICurrentSymbol
{
    [InputParameter("Symbol")]
    public Symbol CurrentSymbol { get; set; }

    [InputParameter("Sample Percent", sortIndex: 10, minimum: 1, maximum: 100, increment: 1, decimalPlaces: 0)]
    public int SamplePct { get; set; } = 100;

    [InputParameter("Port", sortIndex: 20, minimum: 1, maximum: 65535, increment: 1, decimalPlaces: 0)]
    public int Port { get; set; } = 8765;

    [InputParameter("DOM Levels", sortIndex: 30, minimum: 1, maximum: 50, increment: 1, decimalPlaces: 0)]
    public int DomLevels { get; set; } = 10;

    private TcpClient _client;
    private StreamWriter _writer;
    private Random _rng = new();
    private int _count;
    private long _lastDomTicks;

    public override string[] MonitoringConnectionsIds =>
        CurrentSymbol != null ? [CurrentSymbol.ConnectionId] : [];

    public TradeStreamStrategy()
    {
        Name = "Trade Stream";
        Description = "Streams trade prints and DOM over TCP socket";
    }

    protected override void OnRun()
    {
        if (CurrentSymbol == null)
        {
            Log("No symbol selected", StrategyLoggingLevel.Error);
            Stop();
            return;
        }

        try
        {
            _client = new TcpClient("127.0.0.1", Port);
            _writer = new StreamWriter(_client.GetStream()) { AutoFlush = true };
        }
        catch (SocketException ex)
        {
            Log($"Failed to connect to 127.0.0.1:{Port}: {ex.Message}", StrategyLoggingLevel.Error);
            Stop();
            return;
        }

        _count = 0;
        _lastDomTicks = 0;
        CurrentSymbol.NewLast += OnNewLast;
        CurrentSymbol.NewLevel2 += OnNewLevel2;
        Log($"Streaming to 127.0.0.1:{Port} (SamplePct={SamplePct}, DomLevels={DomLevels})");
    }

    protected override void OnStop()
    {
        if (CurrentSymbol != null)
        {
            CurrentSymbol.NewLast -= OnNewLast;
            CurrentSymbol.NewLevel2 -= OnNewLevel2;
        }

        _writer?.Dispose();
        _writer = null;
        _client?.Dispose();
        _client = null;

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
            type = "trade",
            symbol = symbol.Name,
            ts = last.Time.ToString("O"),
            price = last.Price,
            size = (int)last.Size,
            side
        });

        _writer?.WriteLine(line);
        _count++;
    }

    private void OnNewLevel2(Symbol symbol, Level2Quote level2, DOMQuote dom)
    {
        var now = Stopwatch.GetTimestamp();
        if (now - _lastDomTicks < Stopwatch.Frequency / 10)
            return;
        _lastDomTicks = now;

        var snapshot = symbol.DepthOfMarket.GetDepthOfMarketAggregatedCollections(
            new GetDepthOfMarketParameters
            {
                GetLevel2ItemsParameters = new GetLevel2ItemsParameters
                {
                    AggregateMethod = AggregateMethod.ByPriceLVL,
                    LevelsCount = DomLevels,
                    CalculateCumulative = false,
                    GetMBOItems = false
                }
            });

        var bids = snapshot.Bids?
            .Take(DomLevels)
            .Select(b => new { price = b.Price, size = (int)b.Size })
            .ToArray() ?? [];

        var asks = snapshot.Asks?
            .Take(DomLevels)
            .Select(a => new { price = a.Price, size = (int)a.Size })
            .ToArray() ?? [];

        var line = JsonSerializer.Serialize(new
        {
            type = "dom",
            symbol = symbol.Name,
            ts = DateTime.UtcNow.ToString("O"),
            bids,
            asks
        });

        _writer?.WriteLine(line);
    }
}
