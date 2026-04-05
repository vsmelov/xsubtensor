/**
 * Smoke test: connect over WebSocket, print chain info and //Alice balance.
 *
 *   cd scripts/rpc-smoke && npm install && npm run check
 *
 * Env:
 *   WS_URL     (default ws://127.0.0.1:9944)
 *   TIMEOUT_MS (default 15000)
 */

import { ApiPromise, WsProvider } from '@polkadot/api';
import { Keyring } from '@polkadot/keyring';
import { formatBalance } from '@polkadot/util';

const WS_URL = process.env.WS_URL ?? 'ws://127.0.0.1:9944';
const TIMEOUT_MS = Number(process.env.TIMEOUT_MS ?? 15000);

function withTimeout(promise, ms, label) {
  return Promise.race([
    promise,
    new Promise((_, reject) =>
      setTimeout(
        () =>
          reject(
            new Error(
              `${label}: no response in ${ms}ms for ${WS_URL}. ` +
                'Start Docker localnet (see RUN_LOCAL.md) or fix the URL/port.',
            ),
          ),
        ms,
      ),
    ),
  ]);
}

async function main() {
  console.log(`Connecting to ${WS_URL} (timeout ${TIMEOUT_MS} ms)...`);

  const provider = new WsProvider(WS_URL);
  let api;
  try {
    api = await withTimeout(ApiPromise.create({ provider }), TIMEOUT_MS, 'ApiPromise.create');
  } catch (e) {
    await provider.disconnect?.().catch(() => {});
    const msg = e?.message ?? String(e);
    console.error('FAILED:', msg);
    if (/1006|Abnormal|disconnected|ECONNREFUSED/i.test(msg)) {
      console.error(
        'Hint: WebSocket closed abnormally or refused — often nothing listening, wrong port, or Docker not publishing 9944.',
      );
    }
    process.exit(1);
  }

  try {
    const [chain, name, version, header] = await Promise.all([
      api.rpc.system.chain(),
      api.rpc.system.name(),
      api.rpc.system.version(),
      api.rpc.chain.getHeader(),
    ]);

    const ss58 = api.registry.chainSS58 ?? 42;
    const decimals = api.registry.chainDecimals?.[0] ?? 9;
    const unit = api.registry.chainTokens?.[0]?.toString?.() ?? 'TAO';

    formatBalance.setDefaults({ decimals, unit });

    const keyring = new Keyring({ type: 'sr25519', ss58Format: ss58 });
    const alice = keyring.addFromUri('//Alice');
    const { data } = await api.query.system.account(alice.address);
    const free = data.free;

    console.log('');
    console.log('OK — WebSocket RPC is reachable');
    console.log(`  chain:        ${chain}`);
    console.log(`  node:         ${name} ${version}`);
    console.log(`  ss58Format:   ${ss58}`);
    console.log(`  head:         #${header.number.toString()} (${header.hash.toHex()})`);
    console.log(`  //Alice:      ${alice.address}`);
    console.log(`  free balance: ${formatBalance(free)} (raw: ${free.toString()})`);
    console.log('');
  } finally {
    await api.disconnect();
  }
}

main().catch((e) => {
  console.error('FAILED:', e?.message ?? e);
  process.exit(1);
});
