"""OPC UA sawtooth simulator with a small web UI.

Tags (namespace "urn:opcua-sim"):
  cpm           Double, writable - cycles per minute
  virtualMaster Double, read-only to the sim loop - sawtooth 0..360, climbs 360 degrees per cycle
                (so it advances 360 * cpm / 60 degrees per second). Writable to set the phase.
"""
import asyncio
import json
import os

from aiohttp import web
from asyncua import Server, ua

OPC_PORT = int(os.environ.get("OPC_PORT", 4840))
WEB_PORT = int(os.environ.get("PORT", 3000))
NS_URI = "urn:opcua-sim"

state = {"running": True, "intervalMs": 100}


async def main():
    server = Server()
    await server.init()
    server.set_endpoint(f"opc.tcp://0.0.0.0:{OPC_PORT}/UA/Simulator")
    server.set_server_name("VirtualMasterSimulator")
    idx = await server.register_namespace(NS_URI)

    device = await server.nodes.objects.add_object(idx, "Simulator")
    cpm = await device.add_variable(ua.NodeId("cpm", idx), "cpm", 10.0, ua.VariantType.Double)
    master = await device.add_variable(ua.NodeId("virtualMaster", idx), "virtualMaster", 0.0, ua.VariantType.Double)
    await cpm.set_writable()
    await master.set_writable()

    endpoint = f"opc.tcp://localhost:{OPC_PORT}/UA/Simulator"
    ids = {"cpm": cpm.nodeid.to_string(), "virtualMaster": master.nodeid.to_string()}

    # cache so web handlers don't hit the address space on every SSE tick
    cache = {"cpm": 10.0, "value": 0.0}

    async def sim_loop():
        loop = asyncio.get_running_loop()
        last = loop.time()
        while True:
            await asyncio.sleep(state["intervalMs"] / 1000)
            now = loop.time()
            dt, last = now - last, now
            cache["cpm"] = max(0.0, float(await cpm.read_value()))   # tag is the source of truth
            value = float(await master.read_value()) % 360
            if state["running"]:
                value = (value + 360.0 * cache["cpm"] / 60.0 * dt) % 360
            cache["value"] = value
            await master.write_value(ua.Variant(value, ua.VariantType.Double))

    def view():
        return {**state, "cpm": cache["cpm"], "value": cache["value"], "endpoint": endpoint, "nodeIds": ids}

    async def get_state(_):
        return web.json_response(view())

    async def post_config(req):
        b = await req.json()
        if isinstance(b.get("running"), bool):
            state["running"] = b["running"]
        if isinstance(b.get("intervalMs"), (int, float)):
            state["intervalMs"] = int(max(10, min(5000, b["intervalMs"])))
        if isinstance(b.get("cpm"), (int, float)):
            cache["cpm"] = max(0.0, min(6000.0, float(b["cpm"])))
            await cpm.write_value(ua.Variant(cache["cpm"], ua.VariantType.Double))
        if isinstance(b.get("value"), (int, float)):
            cache["value"] = float(b["value"]) % 360
            await master.write_value(ua.Variant(cache["value"], ua.VariantType.Double))
        return web.json_response(view())

    async def stream(req):
        resp = web.StreamResponse(headers={"Content-Type": "text/event-stream", "Cache-Control": "no-cache"})
        await resp.prepare(req)
        loop = asyncio.get_running_loop()
        try:
            while True:
                msg = {"v": cache["value"], "t": int(loop.time() * 1000), "cpm": cache["cpm"], "running": state["running"]}
                await resp.write(f"data: {json.dumps(msg)}\n\n".encode())
                await asyncio.sleep(0.05)
        except (ConnectionResetError, asyncio.CancelledError):
            pass
        return resp

    public = os.path.join(os.path.dirname(os.path.abspath(__file__)), "public")
    app = web.Application()
    app.add_routes([
        web.get("/api/state", get_state),
        web.post("/api/config", post_config),
        web.get("/api/stream", stream),
        web.get("/", lambda _: web.FileResponse(os.path.join(public, "index.html"))),
    ])
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", WEB_PORT).start()

    async with server:
        print(f"OPC UA endpoint: {endpoint}")
        print(f"Nodes: {ids}")
        print(f"Web UI: http://localhost:{WEB_PORT}")
        await sim_loop()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
