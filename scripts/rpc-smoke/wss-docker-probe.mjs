/**
 * wss://subtensor-rpc-wss:3443 from the same Docker network (Caddy → localnet:9944).
 * docker run --rm --network xsubtensor_default -v "%CD%":/app -w /app -e NODE_TLS_REJECT_UNAUTHORIZED=0 node:22-alpine sh -c "npm i ws@8 --silent && node wss-docker-probe.mjs"
 */
process.env.NODE_TLS_REJECT_UNAUTHORIZED = "0";
import { WebSocket } from "ws";

const url = process.env.WSS_URL || "wss://subtensor-rpc-wss:3443";
const ws = new WebSocket(url);
ws.on("open", () => {
  console.log("OPEN", url);
  ws.close();
});
ws.on("error", (e) => console.log("ERR", e.message));
ws.on("close", (c) => console.log("CLOSE", c));
setTimeout(() => process.exit(0), 8000);
