using System;
using System.Diagnostics;
using System.Linq;
using Google.Protobuf;
using NetMQ;
using NetMQ.Sockets;
using PythonBridgeQuantower.Proto;
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

    private PublisherSocket _pub;
    private Random _rng = new();
    private int _count;
    private long _lastDomTicks;

    public override string[] MonitoringConnectionsIds =>
        CurrentSymbol != null ? [CurrentSymbol.ConnectionId] : [];

    public TradeStreamStrategy()
    {
        Name = "Trade Stream";
        Description = "Publishes trade prints and DOM over a ZeroMQ PUB socket (Protobuf payloads)";
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
            _pub = new PublisherSocket();
            _pub.Bind($"tcp://127.0.0.1:{Port}");
        }
        catch (Exception ex)
        {
            Log($"Failed to bind PUB socket on 127.0.0.1:{Port}: {ex.Message}", StrategyLoggingLevel.Error);
            Stop();
            return;
        }

        _count = 0;
        _lastDomTicks = 0;
        CurrentSymbol.NewLast += OnNewLast;
        CurrentSymbol.NewLevel2 += OnNewLevel2;
        Log($"Publishing on tcp://127.0.0.1:{Port} (SamplePct={SamplePct}, DomLevels={DomLevels})");
    }

    protected override void OnStop()
    {
        if (CurrentSymbol != null)
        {
            CurrentSymbol.NewLast -= OnNewLast;
            CurrentSymbol.NewLevel2 -= OnNewLevel2;
        }

        _pub?.Dispose();
        _pub = null;

        Log($"Stopped after {_count} prints published");
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

        var msg = new TradeMessage
        {
            Symbol = symbol.Name,
            Ts = last.Time.ToString("O"),
            Price = last.Price,
            Size = (int)last.Size,
            Side = side
        };

        Publish("trade", msg.ToByteArray());
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

        var msg = new DomMessage
        {
            Symbol = symbol.Name,
            Ts = DateTime.UtcNow.ToString("O")
        };

        if (snapshot.Bids != null)
        {
            foreach (var b in snapshot.Bids.Take(DomLevels))
                msg.Bids.Add(new DomLevel { Price = b.Price, Size = (int)b.Size });
        }
        if (snapshot.Asks != null)
        {
            foreach (var a in snapshot.Asks.Take(DomLevels))
                msg.Asks.Add(new DomLevel { Price = a.Price, Size = (int)a.Size });
        }

        Publish("dom", msg.ToByteArray());
    }

    private void Publish(string topic, byte[] payload)
    {
        _pub?.SendMoreFrame(topic).SendFrame(payload);
    }
}
