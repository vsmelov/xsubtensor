/**
 * Local dev faucet: //Alice balance + signed transfers over Substrate RPC.
 *
 * Env: WS_URL, FAUCET_SEED, PORT, FAUCET_MAX_TAO_PER_TRANSFER
 */

import express from 'express';
import { ApiPromise, WsProvider } from '@polkadot/api';
import { Keyring } from '@polkadot/keyring';
import { BN } from '@polkadot/util';

const WS_URL = process.env.WS_URL ?? 'ws://127.0.0.1:9944';
const FAUCET_SEED = process.env.FAUCET_SEED ?? '//Alice';
const PORT = Number(process.env.PORT ?? 8090);
const MAX_TAO = Number(process.env.FAUCET_MAX_TAO_PER_TRANSFER ?? '1000000');
const DECIMALS = 9;
const RAO_PER_TAO = 10n ** BigInt(DECIMALS);

let apiPromise;
let faucetPair;

function taoStringToRao(s) {
  const t = String(s).trim();
  if (!/^\d+(\.\d+)?$/.test(t)) {
    throw new Error('amount_tao must be a decimal string like "1" or "0.5"');
  }
  const [whole, frac = ''] = t.split('.');
  const fracPadded = (frac + '0'.repeat(DECIMALS)).slice(0, DECIMALS);
  const w = BigInt(whole || '0');
  const f = BigInt(fracPadded || '0');
  return w * RAO_PER_TAO + f;
}

function raoStringToBigInt(s) {
  const x = String(s).trim();
  if (!/^\d+$/.test(x)) {
    throw new Error('amount_rao must be a non-negative integer string');
  }
  return BigInt(x);
}

async function getApi() {
  if (apiPromise) {
    return apiPromise;
  }
  const provider = new WsProvider(WS_URL);
  apiPromise = await ApiPromise.create({ provider });
  return apiPromise;
}

function getFaucetPair(api) {
  if (faucetPair) {
    return faucetPair;
  }
  const ss58 = api.registry.chainSS58 ?? 42;
  const keyring = new Keyring({ type: 'sr25519', ss58Format: ss58 });
  faucetPair = keyring.addFromUri(FAUCET_SEED);
  return faucetPair;
}

async function start() {
  const app = express();
  app.use(express.json({ limit: '32kb' }));

  app.get('/health', async (_req, res) => {
    try {
      const api = await getApi();
      const header = await api.rpc.chain.getHeader();
      res.json({
        ok: true,
        ws: WS_URL,
        head: header.number.toString(),
      });
    } catch (e) {
      res.status(503).json({
        ok: false,
        error: e?.message ?? String(e),
      });
    }
  });

  /**
   * Lookup inclusion / success by block + extrinsic hash (same info you get from chain RPC).
   * Query: block_hash, extrinsic_hash (0x...)
   */
  app.get('/v1/tx-status', async (req, res) => {
    try {
      const blockHash = req.query.block_hash;
      const extrinsicHash = req.query.extrinsic_hash;
      if (!blockHash || !extrinsicHash) {
        res.status(400).json({
          error:
            'query params block_hash and extrinsic_hash are required (hex 0x... )',
        });
        return;
      }
      const want = String(extrinsicHash).toLowerCase();
      const api = await getApi();
      const signedBlock = await api.rpc.chain.getBlock(blockHash);
      let extrinsicIndex = -1;
      for (let i = 0; i < signedBlock.block.extrinsics.length; i++) {
        const h = signedBlock.block.extrinsics[i].hash.toHex().toLowerCase();
        if (h === want) {
          extrinsicIndex = i;
          break;
        }
      }
      if (extrinsicIndex === -1) {
        res.status(404).json({
          error: 'extrinsic hash not found in this block',
          block_hash: String(blockHash),
        });
        return;
      }

      const apiAt = await api.at(blockHash);
      const allEvents = await apiAt.query.system.events();
      let dispatchSuccess = true;
      for (const { event, phase } of allEvents) {
        if (
          !phase.isApplyExtrinsic ||
          !phase.asApplyExtrinsic.eq(extrinsicIndex)
        ) {
          continue;
        }
        if (event.section === 'system' && event.method === 'ExtrinsicFailed') {
          dispatchSuccess = false;
        }
        if (event.section === 'system' && event.method === 'ExtrinsicSuccess') {
          dispatchSuccess = true;
        }
      }

      const head = await api.rpc.chain.getHeader(blockHash);
      const finalizedHead = await api.rpc.chain.getFinalizedHead();
      const finalizedHdr = await api.rpc.chain.getHeader(finalizedHead);
      const finalizedHint =
        finalizedHdr.number.toNumber() >= head.number.toNumber();

      res.json({
        extrinsic_hash: signedBlock.block.extrinsics[extrinsicIndex].hash.toHex(),
        block_hash: String(blockHash),
        block_number: head.number.toNumber(),
        extrinsic_index: extrinsicIndex,
        dispatch_success: dispatchSuccess,
        finalized_head_block_number: finalizedHdr.number.toNumber(),
        finalized_hint: finalizedHint,
      });
    } catch (e) {
      res.status(500).json({ error: e?.message ?? String(e) });
    }
  });

  app.get('/v1/balance', async (_req, res) => {
    try {
      const api = await getApi();
      const pair = getFaucetPair(api);
      const { data } = await api.query.system.account(pair.address);
      const free = data.free.toBigInt();
      const freeTao = Number(free) / Number(RAO_PER_TAO);
      res.json({
        ss58: pair.address,
        seed_hint: FAUCET_SEED.startsWith('//') ? 'dev URI' : 'custom',
        free_rao: free.toString(),
        free_tao: freeTao.toFixed(9),
      });
    } catch (e) {
      res.status(500).json({ error: e?.message ?? String(e) });
    }
  });

  app.post('/v1/transfer', async (req, res) => {
    try {
      const { dest, amount_rao, amount_tao } = req.body ?? {};
      if (!dest || typeof dest !== 'string') {
        res.status(400).json({ error: 'body.dest (ss58 address) is required' });
        return;
      }
      let amount;
      if (amount_rao != null && amount_tao != null) {
        res
          .status(400)
          .json({ error: 'use either amount_rao or amount_tao, not both' });
        return;
      }
      if (amount_rao != null) {
        amount = raoStringToBigInt(amount_rao);
      } else if (amount_tao != null) {
        amount = taoStringToRao(amount_tao);
      } else {
        res
          .status(400)
          .json({ error: 'provide amount_rao (integer string) or amount_tao (decimal string)' });
        return;
      }
      if (amount <= 0n) {
        res.status(400).json({ error: 'amount must be positive' });
        return;
      }

      const maxRao = taoStringToRao(String(MAX_TAO));
      if (amount > maxRao) {
        res.status(400).json({
          error: `amount exceeds FAUCET_MAX_TAO_PER_TRANSFER (${MAX_TAO} TAO)`,
        });
        return;
      }

      const api = await getApi();
      const pair = getFaucetPair(api);

      const tx = api.tx.balances.transferKeepAlive(
        dest,
        new BN(amount.toString()),
      );

      const inclusion = await new Promise((resolve, reject) => {
        tx.signAndSend(pair, async (result) => {
          const { status, dispatchError } = result;
          if (dispatchError) {
            if (dispatchError.isModule) {
              const meta = api.registry.findMetaError(dispatchError.asModule);
              reject(
                new Error(
                  `${meta.section}.${meta.name}: ${meta.docs.join(' ')}`,
                ),
              );
            } else {
              reject(new Error(dispatchError.toString()));
            }
            return;
          }
          if (status.isInBlock) {
            const blockHash = status.asInBlock;
            const extrinsicHash =
              result.txHash?.toHex?.() ??
              result.tx?.hash?.toHex?.() ??
              null;
            const header = await api.rpc.chain.getHeader(blockHash);
            resolve({
              extrinsic_hash: extrinsicHash,
              block_hash: blockHash.toHex(),
              block_number: header.number.toNumber(),
              status: 'in_block',
            });
          }
        }).catch(reject);
      });

      if (!inclusion.extrinsic_hash) {
        res.status(500).json({
          error: 'node did not return extrinsic hash (txHash)',
        });
        return;
      }

      res.json({
        ok: true,
        ...inclusion,
        hash: inclusion.extrinsic_hash,
        from: pair.address,
        dest,
        amount_rao: amount.toString(),
      });
    } catch (e) {
      res.status(500).json({ error: e?.message ?? String(e) });
    }
  });

  await getApi();

  app.listen(PORT, '0.0.0.0', () => {
    // eslint-disable-next-line no-console
    console.log(
      JSON.stringify({
        msg: 'faucet listening',
        port: PORT,
        ws: WS_URL,
        routes: [
          'GET /health',
          'GET /v1/balance',
          'GET /v1/tx-status',
          'POST /v1/transfer',
        ],
      }),
    );
  });
}

start().catch((e) => {
  console.error(e);
  process.exit(1);
});
