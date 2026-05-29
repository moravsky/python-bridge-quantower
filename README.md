# python-bridge-quantower

Streams live trade prints and Level 2 order book data from Quantower into a
Python terminal UI over a ZeroMQ PUB/SUB socket with Protobuf-encoded
payloads. Shared schema lives in `proto/messages.proto`; both sides use
generated types.

https://github.com/user-attachments/assets/dc364044-a92d-4e19-bd40-35471f3ce35e

## What it does

- **C# Strategy** runs inside Quantower, subscribes to trades and L2 data,
  and publishes Protobuf-encoded messages on a ZeroMQ PUB socket bound to
  `tcp://127.0.0.1:<port>`. Topics are `trade` and `dom`.
- **Python TUI** connects as a SUB, subscribes to both topics, parses
  Protobuf based on topic, and renders a live scrolling trade tape and a
  DOM (depth of market) price ladder with proportional bars.

## Quick start

### Prerequisites

- Quantower v1.145.17 installed at `C:\Quantower` with a data feed
  connected (L2 data for DOM).
- Python 3.10+ with `pip` on PATH.
- .NET 10.0 SDK is only needed if you build from source -- see
  [.NET 10.0 SDK (Windows x64)](https://builds.dotnet.microsoft.com/dotnet/Sdk/10.0.300/dotnet-sdk-10.0.300-win-x64.exe).

### Install (prebuilt release, recommended)

1. **Download** the latest `python-bridge-quantower-<version>-qt1.145.17.zip`
   from [Releases](https://github.com/moravsky/python-bridge-quantower/releases).
   The `qt1.145.17` in the filename is the Quantower version it was built
   against -- it must match yours.

2. **Extract** the zip somewhere convenient (e.g. your home directory).
   You will get:

   ```
   PythonBridgeQuantower/   <-- this folder goes into Quantower
     PythonBridgeQuantower.dll
     PythonBridgeQuantower.deps.json
     PythonBridgeQuantower.pdb
   tui/
     tape.py
   requirements.txt
   README.md
   ```

3. **Install the strategy** in Quantower. Copy the entire
   `PythonBridgeQuantower/` folder (the one containing the .dll) into:

   ```
   C:\Quantower\Settings\Scripts\Strategies\
   ```

   Create the `Strategies` folder if it does not exist. The final path
   must be
   `C:\Quantower\Settings\Scripts\Strategies\PythonBridgeQuantower\PythonBridgeQuantower.dll`.

4. **Install Python dependencies.** Open PowerShell in the extracted
   folder (the one containing `requirements.txt`) and run:

   ```powershell
   pip install -r requirements.txt
   ```

5. **Start Quantower** (or restart it if it was already running -- it
   loads strategies from `Settings\Scripts\Strategies\` on startup).

### Install (build from source)

Requires the .NET 10 SDK linked in Prerequisites.

```powershell
git clone https://github.com/moravsky/python-bridge-quantower.git
cd python-bridge-quantower
pip install -r requirements.txt
dotnet build PythonBridgeQuantower/PythonBridgeQuantower.csproj -c Debug
.\deploy.ps1                     # deploys to C:\Quantower
.\deploy.ps1 -Dev                # deploys to C:\QuantowerDev
```

### Run

Either side can start first. The strategy binds the PUB socket; the
TUI connects as a SUB and waits. ZeroMQ holds the connection until
the other side is up.

1. **Add and run the strategy in Quantower.** Open Quantower's Strategy
   Manager, click the `+` to add a strategy, and pick **Trade Stream**
   from the list. Set the parameters:

   | Parameter      | Value                       |
   |----------------|-----------------------------|
   | Symbol         | the instrument to stream    |
   | Port           | 8765                        |
   | DOM Levels     | 10                          |
   | Sample Percent | 100                         |

   Click **Run**. The strategy log shows
   `Publishing on tcp://127.0.0.1:8765`.

2. **Start the TUI.** From the extracted folder (or repo root):

   ```powershell
   python tui/tape.py
   ```

   The title bar shows `Subscribing to tcp://127.0.0.1:8765`. As soon
   as messages arrive, the TUI shows the symbol, a live trade tape,
   and a DOM ladder. A capture file is saved automatically to
   `captures/` next to the `tui/` folder.

   Note: ZeroMQ PUB/SUB is fire-and-forget -- messages published
   before the TUI subscribes are dropped (this is normal ZMQ "slow
   joiner" behavior). The TUI captures everything it observes from
   the moment it subscribes onward.

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
| Port           | 8765    | TCP port the PUB socket binds to     |
| DOM Levels     | 10      | Number of order book levels per side |

## Wire protocol

ZeroMQ PUB/SUB over loopback TCP, with Protobuf-encoded payloads.
Strategy is the publisher (binds `tcp://127.0.0.1:<port>`); any
subscriber connects with a ZMQ SUB socket.

Each ZMQ message is two frames: a topic string (`trade` or `dom`) and
a Protobuf payload. The schema lives in `proto/messages.proto`. See
[ARCHITECTURE.md](ARCHITECTURE.md) for the schema dump, codegen
workflow, capture-file format, and design rationale.

### Minimal Python subscriber

If you want to write your own consumer instead of using the TUI:

```python
import zmq

from messages_pb2 import DomMessage, TradeMessage

ctx = zmq.Context()
sub = ctx.socket(zmq.SUB)
sub.connect("tcp://127.0.0.1:8765")
sub.setsockopt(zmq.SUBSCRIBE, b"")  # all topics; use b"trade" or b"dom" to filter

while True:
    topic_bytes, payload = sub.recv_multipart()
    topic = topic_bytes.decode()
    if topic == "trade":
        msg = TradeMessage()
    elif topic == "dom":
        msg = DomMessage()
    else:
        continue
    msg.ParseFromString(payload)
    print(topic, msg.symbol, msg.price if topic == "trade" else len(msg.bids))
```

## Project layout

```
proto/
  messages.proto            shared schema for the wire (single source of truth)
PythonBridgeQuantower/
  TradeStreamStrategy.cs    C# strategy (the producer)
  PythonBridgeQuantower.csproj   references Grpc.Tools for protoc-at-build
tui/
  tape.py                   Python TUI (the consumer)
  messages_pb2.py           generated by grpcio-tools from messages.proto
captures/                   Auto-saved JSONL capture files
specs/                      Design specs
```

## Author

**Petr Moravsky** ([petr@structuredtrading.co](mailto:petr@structuredtrading.co)) -- futures trader and developer.

If python-bridge-quantower helped you connect Quantower to Python or served as a reference for your own development -- [star the repo](https://github.com/moravsky/python-bridge-quantower) and [leave a tip](https://ko-fi.com/moravsky).
