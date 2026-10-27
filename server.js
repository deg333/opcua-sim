const express = require("express");
const { OPCUAServer, Variant, DataType, StatusCodes } = require("node-opcua");

const OPC_PORT = +process.env.OPC_PORT || 4840;
const WEB_PORT = +process.env.PORT || 3000;

const state = { running: true, speed: 60, intervalMs: 100, value: 0 }; // speed = deg/s

async function main() {
  const server = new OPCUAServer({
    port: OPC_PORT,
    resourcePath: "/UA/Simulator",
    buildInfo: { productName: "VirtualMasterSimulator", buildNumber: "1" },
  });
  await server.initialize();

  const addressSpace = server.engine.addressSpace;
  const ns = addressSpace.getOwnNamespace();
  const device = ns.addObject({ organizedBy: addressSpace.rootFolder.objects, browseName: "Simulator" });

  ns.addVariable({
    componentOf: device,
    nodeId: "s=virtualMaster",
    browseName: "virtualMaster",
    dataType: "Double",
    minimumSamplingInterval: 50,
    value: {
      get: () => new Variant({ dataType: DataType.Double, value: state.value }),
      // allow clients to write (e.g. to reset phase)
      set: (v) => {
        const n = Number(v.value);
        if (!Number.isFinite(n)) return StatusCodes.BadTypeMismatch;
        state.value = ((n % 360) + 360) % 360;
        return StatusCodes.Good;
      },
    },
  });

  let last = Date.now(), timer;
  const arm = () => {
    clearInterval(timer);
    last = Date.now();
    timer = setInterval(() => {
      const now = Date.now();
      if (state.running) state.value = (state.value + state.speed * (now - last) / 1000) % 360;
      if (state.value < 0) state.value += 360;
      last = now;
    }, state.intervalMs);
  };
  arm();

  await server.start();
  const endpoint = server.endpoints[0].endpointDescriptions()[0].endpointUrl;
  console.log(`OPC UA endpoint: ${endpoint}   node: ns=1;s=virtualMaster`);

  const app = express();
  app.use(express.json());
  app.use(express.static("public"));
  const view = () => ({ ...state, endpoint, nodeId: "ns=1;s=virtualMaster" });
  app.get("/api/state", (_, res) => res.json(view()));
  app.post("/api/config", (req, res) => {
    const { running, speed, intervalMs, value } = req.body;
    if (typeof running === "boolean") state.running = running;
    if (Number.isFinite(speed)) state.speed = Math.max(-3600, Math.min(3600, speed));
    if (Number.isFinite(value)) state.value = ((value % 360) + 360) % 360;
    if (Number.isFinite(intervalMs)) { state.intervalMs = Math.max(10, Math.min(5000, Math.round(intervalMs))); arm(); }
    res.json(view());
  });
  app.get("/api/stream", (req, res) => {
    res.set({ "Content-Type": "text/event-stream", "Cache-Control": "no-cache", Connection: "keep-alive" });
    const t = setInterval(() => res.write(`data: ${JSON.stringify({ v: state.value, t: Date.now(), running: state.running })}\n\n`), 50);
    req.on("close", () => clearInterval(t));
  });
  app.listen(WEB_PORT, () => console.log(`Web UI: http://localhost:${WEB_PORT}`));

  process.on("SIGINT", async () => { await server.shutdown(); process.exit(0); });
}
main().catch((e) => { console.error(e); process.exit(1); });
