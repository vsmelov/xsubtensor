/**
 * Subscribe to new block headers (proves live chain + stable WS).
 *
 *   npm run new-heads
 *
 * Stops after NEW_HEADS_LIMIT blocks (default 5) or TIMEOUT_MS (default 60000).
 */

import { ApiPromise, WsProvider } from '@polkadot/api';

const WS_URL = process.env.WS_URL ?? 'ws://127.0.0.1:9944';
const LIMIT = Number(process.env.NEW_HEADS_LIMIT ?? 5);
const TIMEOUT_MS = Number(process.env.TIMEOUT_MS ?? 60000);

async function main() {
  console.log(`Subscribing to new heads on ${WS_URL} (stop after ${LIMIT} blocks)...`);

  const provider = new WsProvider(WS_URL);
  const api = await ApiPromise.create({ provider });

  const killTimer = setTimeout(async () => {
    console.error(`Timeout ${TIMEOUT_MS} ms — still waiting for ${LIMIT} new heads.`);
    await api.disconnect();
    process.exit(1);
  }, TIMEOUT_MS);

  let count = 0;
  const unsub = await api.rpc.chain.subscribeNewHeads((h) => {
    console.log(`  #${h.number.toString()} hash=${h.hash.toHex()}`);
    count += 1;
    if (count >= LIMIT) {
      clearTimeout(killTimer);
      unsub()
        .then(() => api.disconnect())
        .then(() => process.exit(0))
        .catch((e) => {
          console.error(e);
          process.exit(1);
        });
    }
  });
}

main().catch((e) => {
  console.error('FAILED:', e?.message ?? e);
  process.exit(1);
});
