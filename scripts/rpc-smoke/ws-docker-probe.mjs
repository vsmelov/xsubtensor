/**
 * Probe WebSocket from another Docker container on the same network:
 * docker run --rm --network xsubtensor_default -v "%CD%":/app -w /app node:22-alpine sh -c "npm i ws@8 --silent && node ws-docker-probe.mjs"
 */
import { WebSocket } from 'ws';

const url = process.env.WS_URL || 'ws://subtensor-localnet:9944';
const ws = new WebSocket(url);
ws.on('open', () => {
  console.log('OPEN', url);
  ws.close();
});
ws.on('error', (e) => console.log('ERR', e.message));
ws.on('close', (c) => console.log('CLOSE code', c));
setTimeout(() => process.exit(0), 8000);
