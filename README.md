# OPC UA Sawtooth Simulator

A small OPC UA server with a web UI. It publishes a sawtooth angle (0–360°) on `virtualMaster`, with its speed set by a second tag, `cpm`.

## Tags

Namespace URI `urn:opcua-sim` (namespace index 2 on this server).

| Tag | NodeId | Type | Description |
|---|---|---|---|
| `cpm` | `ns=2;s=cpm` | Double, writable | Cycles per minute. Default 10. |
| `virtualMaster` | `ns=2;s=virtualMaster` | Double, writable | Sawtooth from 0 up to just under 360, then wraps to 0. |

`virtualMaster` climbs 360° per cycle, so it advances `360 × cpm / 60` degrees per second. For example, `cpm = 10` gives 60°/s, one full sweep every 6 seconds. Writing `virtualMaster` from a client sets the phase.

## Run

Requires Python 3.9+.

```
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python server.py
```

- OPC UA endpoint: `opc.tcp://localhost:4840/UA/Simulator`
- Web UI: http://localhost:3000

Ports can be changed with the `OPC_PORT` and `PORT` environment variables.

## Web UI

Shows the live `virtualMaster` value with a scrolling 10-second graph. Controls:

- **cpm**: writes the `cpm` tag.
- **Update interval (ms)**: how often the simulation steps (10–5000, default 100).
- **Set value (0–359)**: jumps the sawtooth to a given angle.
- **Pause / Resume**: freezes the sawtooth.

The web UI and OPC UA clients write to the same tags, so a change in one shows up in the other.

## Web API

- `GET /api/state`: current state, endpoint and node IDs.
- `POST /api/config`: JSON body with any of `cpm`, `value`, `intervalMs`, `running`.
- `GET /api/stream`: server-sent events with the live value.

## Security

The server accepts anonymous connections with no encryption. Use it on a trusted network only.
