/**
 * Local dev faucet: //Alice balance + signed transfers over Substrate RPC.
 *
 * Env: WS_URL, FAUCET_SEED, PORT, FAUCET_MAX_TAO_PER_TRANSFER, CORS_ORIGIN,
 *      SUBNET_MATH_PROBE_URL (optional proxy to subnet-math HTTP probe)
 */

import cors from 'cors';
import express from 'express';
import { ApiPromise, WsProvider } from '@polkadot/api';
import { Keyring } from '@polkadot/keyring';
import { BN } from '@polkadot/util';

const WS_URL = process.env.WS_URL ?? 'ws://127.0.0.1:9944';
const FAUCET_SEED = process.env.FAUCET_SEED ?? '//Alice';
const PORT = Number(process.env.PORT ?? 8090);
const MAX_TAO = Number(process.env.FAUCET_MAX_TAO_PER_TRANSFER ?? '1000000');
/** Comma-separated extra origins, e.g. http://localhost:5174 (defaults include Vite :5173) */
const CORS_EXTRA = process.env.CORS_ORIGIN ?? '';
const DECIMALS = 9;
const RAO_PER_TAO = 10n ** BigInt(DECIMALS);

/** Max blocks to walk back for `recent_events` (query override capped by env). */
const SNAPSHOT_MAX_EVENTS_DEPTH = Number(
  process.env.SNAPSHOT_MAX_EVENTS_DEPTH ?? '50',
);
const SNAPSHOT_MAX_EVENTS = Number(process.env.SNAPSHOT_MAX_EVENTS ?? '500');
/** Max blocks to scan for extrinsic list (`blocks_extrinsics_depth` query cap). */
const SNAPSHOT_MAX_BLOCKS_EXTRINSICS_DEPTH = Number(
  process.env.SNAPSHOT_MAX_BLOCKS_EXTRINSICS_DEPTH ?? '30',
);
/** Max extrinsic rows returned (`extrinsics_max` query cap). */
const SNAPSHOT_MAX_EXTRINSICS = Number(process.env.SNAPSHOT_MAX_EXTRINSICS ?? '800');
/** When query omits depth, scan this many recent blocks (use `events_depth=0` to disable). */
const DEFAULT_SNAPSHOT_EVENTS_DEPTH = 3;
const DEFAULT_SNAPSHOT_BLOCKS_EXTRINSICS_DEPTH = 3;
/** Optional: Python math-probe on same Docker network (subnet-math compose). Empty = proxy disabled. */
const SUBNET_MATH_PROBE_URL = (process.env.SUBNET_MATH_PROBE_URL ?? '').trim();

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

function codecToJson(v) {
  if (v == null) {
    return null;
  }
  if (typeof v.toJSON === 'function') {
    return v.toJSON();
  }
  if (Array.isArray(v)) {
    return v.map((x) => codecToJson(x));
  }
  return v;
}

/** Best-effort UTF-8 for metagraph name/symbol byte arrays from chain. */
function attachUtf8Fields(mgJson) {
  if (!mgJson || typeof mgJson !== 'object') {
    return mgJson;
  }
  const out = { ...mgJson };
  if (Array.isArray(out.name) && out.name.every((x) => typeof x === 'number')) {
    try {
      out.nameUtf8 = Buffer.from(out.name).toString('utf8');
    } catch {
      /* ignore */
    }
  }
  if (
    Array.isArray(out.symbol) &&
    out.symbol.every((x) => typeof x === 'number')
  ) {
    try {
      out.symbolUtf8 = Buffer.from(out.symbol).toString('utf8');
    } catch {
      /* ignore */
    }
  }
  return out;
}

/** Comma-separated list → Set of section names, or null = no filter. */
function parseSectionFilter(queryValue) {
  if (queryValue == null || queryValue === '') {
    return null;
  }
  const s = String(queryValue).trim();
  if (!s) {
    return null;
  }
  return new Set(s.split(',').map((x) => x.trim()).filter(Boolean));
}

async function fetchRecentEvents(api, headNum, depth, maxEvents, sectionFilter) {
  if (depth <= 0 || maxEvents <= 0) {
    return [];
  }
  const out = [];
  for (let d = 0; d < depth && out.length < maxEvents; d++) {
    const bn = headNum - d;
    if (bn < 0) {
      break;
    }
    const blockHash = await api.rpc.chain.getBlockHash(bn);
    const events = await api.query.system.events.at(blockHash);
    const blockHashHex = blockHash.toHex();
    for (const { event, phase } of events) {
      if (out.length >= maxEvents) {
        break;
      }
      if (sectionFilter?.size && !sectionFilter.has(event.section)) {
        continue;
      }
      out.push({
        blockNumber: bn,
        blockHash: blockHashHex,
        section: event.section,
        method: event.method,
        phase: phase.toHuman?.() ?? String(phase),
        data: event.data.toHuman?.() ?? codecToJson(event.data),
      });
    }
  }
  return out;
}

/**
 * Последние extrinsic по блокам (как «лог транзакций» для локального explorer).
 * sectionFilter: если задан — только extrinsic с method.section из набора.
 */
async function fetchRecentExtrinsics(
  api,
  headNum,
  depth,
  maxRows,
  sectionFilter,
) {
  if (depth <= 0 || maxRows <= 0) {
    return [];
  }
  const out = [];
  outer: for (let d = 0; d < depth; d++) {
    const bn = headNum - d;
    if (bn < 0) {
      break;
    }
    const blockHash = await api.rpc.chain.getBlockHash(bn);
    const signedBlock = await api.rpc.chain.getBlock(blockHash);
    const blockHashHex = blockHash.toHex();
    const { extrinsics } = signedBlock.block;
    for (let i = 0; i < extrinsics.length; i++) {
      if (out.length >= maxRows) {
        break outer;
      }
      const ex = extrinsics[i];
      const section = ex.method.section;
      const method = ex.method.method;
      if (sectionFilter?.size && !sectionFilter.has(section)) {
        continue;
      }
      let argsHuman = null;
      try {
        argsHuman = ex.method.toHuman?.() ?? null;
      } catch {
        argsHuman = { _error: 'toHuman failed' };
      }
      out.push({
        blockNumber: bn,
        blockHash: blockHashHex,
        extrinsicIndex: i,
        extrinsicHash: ex.hash.toHex(),
        isSigned: ex.isSigned,
        signer: ex.isSigned ? ex.signer?.toString() ?? null : null,
        section,
        method,
        args: argsHuman,
      });
    }
  }
  return out;
}

function metagraphNeuronCount(mg) {
  const n = mg?.numUids;
  if (Number.isFinite(n) && n >= 0) {
    return n;
  }
  if (Array.isArray(mg?.hotkeys)) {
    return mg.hotkeys.length;
  }
  return 0;
}

/**
 * Уплощённый «граф» для визуализации: сабнеты + нейроны (рёбра off-chain не в цепи).
 */
function buildNetworkGraphSummary(metagraphs) {
  if (!Array.isArray(metagraphs)) {
    return { subnets: [], neurons: [], edges: [] };
  }
  const subnets = [];
  const neurons = [];
  for (const mg of metagraphs) {
    if (!mg || typeof mg !== 'object') {
      continue;
    }
    const netuid = mg.netuid;
    subnets.push({
      netuid,
      nameUtf8: mg.nameUtf8 ?? null,
      symbolUtf8: mg.symbolUtf8 ?? null,
      numUids: metagraphNeuronCount(mg),
      tempo: mg.tempo ?? null,
      ownerColdkey: mg.ownerColdkey ?? null,
    });
    const n = metagraphNeuronCount(mg);
    for (let uid = 0; uid < n; uid++) {
      const ax = mg.axons?.[uid];
      neurons.push({
        netuid,
        uid,
        hotkey: mg.hotkeys?.[uid] ?? null,
        coldkey: mg.coldkeys?.[uid] ?? null,
        active: mg.active?.[uid] ?? null,
        validatorPermit: mg.validatorPermit?.[uid] ?? null,
        axonPort: ax?.port ?? null,
        axonIpPacked: ax?.ip ?? null,
        incentives: mg.incentives?.[uid] ?? null,
        dividends: mg.dividends?.[uid] ?? null,
        emission: mg.emission?.[uid] ?? null,
        totalStake: mg.totalStake?.[uid] ?? null,
      });
    }
  }
  return {
    subnets,
    neurons,
    edges: [],
    note:
      'On-chain edges for miner axon traffic are not stored; reward flow is reflected in emission/incentives/dividends per uid. Commit-reveal weights are not expanded here.',
  };
}

async function safeRuntimeCall(fn) {
  try {
    const v = await fn();
    return { ok: true, data: codecToJson(v) };
  } catch (e) {
    return { ok: false, error: e?.message ?? String(e) };
  }
}

async function buildNetworkSnapshot(api, query) {
  const depthRaw = Number(
    query.events_depth ?? String(DEFAULT_SNAPSHOT_EVENTS_DEPTH),
  );
  const depth = Math.min(
    Number.isFinite(depthRaw) ? Math.max(0, Math.floor(depthRaw)) : 0,
    SNAPSHOT_MAX_EVENTS_DEPTH,
  );
  const maxEvRaw = Number(query.events_max ?? String(SNAPSHOT_MAX_EVENTS));
  const maxEvents = Math.min(
    Number.isFinite(maxEvRaw) ? Math.max(0, Math.floor(maxEvRaw)) : 0,
    SNAPSHOT_MAX_EVENTS,
  );

  const extrDepthRaw = Number(
    query.blocks_extrinsics_depth ?? String(DEFAULT_SNAPSHOT_BLOCKS_EXTRINSICS_DEPTH),
  );
  const extrDepth = Math.min(
    Number.isFinite(extrDepthRaw) ? Math.max(0, Math.floor(extrDepthRaw)) : 0,
    SNAPSHOT_MAX_BLOCKS_EXTRINSICS_DEPTH,
  );
  const maxExtrRaw = Number(query.extrinsics_max ?? '200');
  const maxExtr = Math.min(
    Number.isFinite(maxExtrRaw) ? Math.max(0, Math.floor(maxExtrRaw)) : 0,
    SNAPSHOT_MAX_EXTRINSICS,
  );

  let eventSectionFilter = parseSectionFilter(query.events_filter);
  if (
    query.events_only_subtensor === '1' ||
    query.events_only_subtensor === 'true'
  ) {
    eventSectionFilter = new Set(['subtensorModule']);
  }
  const extrinsicSectionFilter = parseSectionFilter(query.extrinsics_filter);

  const [
    chainName,
    nodeName,
    nodeVersion,
    props,
    health,
    head,
    finalizedHead,
    totalNetworks,
    totalStake,
    issuance,
  ] = await Promise.all([
    api.rpc.system.chain(),
    api.rpc.system.name(),
    api.rpc.system.version(),
    api.rpc.system.properties(),
    api.rpc.system.health(),
    api.rpc.chain.getHeader(),
    api.rpc.chain.getFinalizedHead(),
    api.query.subtensorModule.totalNetworks(),
    api.query.subtensorModule.totalStake(),
    api.query.balances.totalIssuance(),
  ]);
  const finalizedHeader = await api.rpc.chain.getHeader(finalizedHead);
  const headNum = head.number.toNumber();

  const [
    metagraphsR,
    dynamicR,
    subnetsV2R,
    delegatesR,
    regCostR,
    events,
    extrinsics,
  ] = await Promise.all([
    safeRuntimeCall(() => api.call.subnetInfoRuntimeApi.getAllMetagraphs()),
    safeRuntimeCall(() => api.call.subnetInfoRuntimeApi.getAllDynamicInfo()),
    safeRuntimeCall(() => api.call.subnetInfoRuntimeApi.getSubnetsInfoV2()),
    safeRuntimeCall(() => api.call.delegateInfoRuntimeApi.getDelegates()),
    safeRuntimeCall(() =>
      api.call.subnetRegistrationRuntimeApi.getNetworkRegistrationCost(),
    ),
    fetchRecentEvents(api, headNum, depth, maxEvents, eventSectionFilter),
    fetchRecentExtrinsics(
      api,
      headNum,
      extrDepth,
      maxExtr,
      extrinsicSectionFilter,
    ),
  ]);

  let metagraphs =
    metagraphsR.ok && Array.isArray(metagraphsR.data)
      ? metagraphsR.data.map((m) => attachUtf8Fields(m))
      : metagraphsR.data;

  if (metagraphsR.ok && Array.isArray(metagraphs)) {
    metagraphs = metagraphs.filter(Boolean);
  }

  const networkGraph =
    metagraphsR.ok && Array.isArray(metagraphs)
      ? buildNetworkGraphSummary(metagraphs)
      : buildNetworkGraphSummary([]);

  return {
    ok: true,
    generated_at_ms: Date.now(),
    ws_url: WS_URL,
    snapshot_query: {
      events_depth: depth,
      events_max: maxEvents,
      events_filter: query.events_filter ?? null,
      events_only_subtensor: Boolean(
        query.events_only_subtensor === '1' ||
          query.events_only_subtensor === 'true',
      ),
      blocks_extrinsics_depth: extrDepth,
      extrinsics_max: maxExtr,
      extrinsics_filter: query.extrinsics_filter ?? null,
    },
    chain: {
      name: chainName.toString(),
      node: `${nodeName} ${nodeVersion}`,
      properties: codecToJson(props),
    },
    sync: codecToJson(health),
    head: {
      number: headNum,
      hash: head.hash.toHex(),
    },
    finalized: {
      number: finalizedHeader.number.toNumber(),
      hash: finalizedHead.toHex(),
    },
    subtensor: {
      total_networks: totalNetworks.toNumber?.() ?? Number(totalNetworks),
      total_stake: totalStake?.toString?.() ?? String(totalStake),
      total_issuance_balances: issuance?.toString?.() ?? String(issuance),
    },
    network_graph: networkGraph,
    runtime_calls: {
      getAllMetagraphs: metagraphsR.ok
        ? { ok: true, data: metagraphs }
        : metagraphsR,
      getAllDynamicInfo: dynamicR,
      getSubnetsInfoV2: subnetsV2R,
      getDelegates: delegatesR,
      getNetworkRegistrationCost: regCostR,
    },
    recent_events: {
      depth_blocks_requested: depth,
      max_events: maxEvents,
      count: events.length,
      events,
    },
    recent_extrinsics: {
      blocks_scanned_requested: extrDepth,
      max_rows: maxExtr,
      count: extrinsics.length,
      extrinsics,
    },
    limits: {
      SNAPSHOT_MAX_EVENTS_DEPTH,
      SNAPSHOT_MAX_EVENTS,
      SNAPSHOT_MAX_BLOCKS_EXTRINSICS_DEPTH,
      SNAPSHOT_MAX_EXTRINSICS,
    },
  };
}

function corsAllowedOrigins() {
  const defaults = [
    'http://localhost:5173',
    'http://127.0.0.1:5173',
    'http://localhost:3000',
    'http://127.0.0.1:3000',
    'http://localhost:8090',
    'http://127.0.0.1:8090',
  ];
  const extra = CORS_EXTRA.split(',')
    .map((s) => s.trim())
    .filter(Boolean);
  return [...new Set([...defaults, ...extra])];
}

async function start() {
  const app = express();
  const allowed = corsAllowedOrigins();
  app.use(
    cors({
      origin(origin, callback) {
        if (!origin) {
          callback(null, true);
          return;
        }
        if (allowed.includes(origin)) {
          callback(null, true);
          return;
        }
        callback(null, false);
      },
      credentials: true,
      methods: ['GET', 'POST', 'OPTIONS'],
      allowedHeaders: ['Content-Type', 'Authorization'],
    }),
  );
  app.use(express.json({ limit: '64kb' }));

  /**
   * Explorer-oriented snapshot: metagraphs, `network_graph`, optional
   * `recent_events` + `recent_extrinsics` (last blocks).
   *
   * Query:
   *   events_depth (default 3; 0 = off), events_max — system events per block walk.
   *   events_filter — comma sections, e.g. `subtensorModule,balances`
   *   events_only_subtensor=1 — shorthand filter subtensorModule only.
   *   blocks_extrinsics_depth (default 3; 0 = off), extrinsics_max — extrinsic log scan.
   *   extrinsics_filter — comma pallet sections for extrinsics.
   *
   * Docs: REQUEST_NET_GRAPH.md — snapshot + docs/network-snapshot*.json
   */
  app.get('/v1/network-snapshot', async (req, res) => {
    try {
      const api = await getApi();
      const snap = await buildNetworkSnapshot(api, req.query ?? {});
      res.json(snap);
    } catch (e) {
      res.status(503).json({
        ok: false,
        error: e?.message ?? String(e),
      });
    }
  });

  /**
   * Прокси к HTTP-сервису subnet-math (bittensor dendrite). Тело — JSON как у POST /v1/math-probe.
   * Док: REQUEST_TO_SUBNET.md
   */
  app.post('/v1/subnet-math-probe', async (req, res) => {
    if (!SUBNET_MATH_PROBE_URL) {
      res.status(503).json({
        ok: false,
        error:
          'SUBNET_MATH_PROBE_URL is not set; start math-probe (subnet-math compose) or set the env',
      });
      return;
    }
    const base = SUBNET_MATH_PROBE_URL.replace(/\/$/, '');
    const target = `${base}/v1/math-probe`;
    try {
      const r = await fetch(target, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Accept: 'application/json',
        },
        body: JSON.stringify(req.body && typeof req.body === 'object' ? req.body : {}),
      });
      const text = await r.text();
      const ct = r.headers.get('content-type') ?? '';
      if (ct.includes('application/json')) {
        try {
          res.status(r.status).json(JSON.parse(text));
        } catch {
          res.status(r.status).type('text').send(text);
        }
      } else {
        res.status(r.status).type('text').send(text);
      }
    } catch (e) {
      res.status(502).json({
        ok: false,
        error: e?.message ?? String(e),
        hint: `could not reach ${target}`,
      });
    }
  });

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

  // Do not await getApi() before listen: if the chain is still booting, the WS handshake
  // can block for a long time and the HTTP server never binds (host sees ECONNREFUSED).
  // RPC is connected lazily on first request via getApi().

  app.listen(PORT, '0.0.0.0', () => {
    // eslint-disable-next-line no-console
    console.log(
      JSON.stringify({
        msg: 'faucet listening',
        port: PORT,
        ws: WS_URL,
        routes: [
          'GET /health',
          'GET /v1/network-snapshot',
          'POST /v1/subnet-math-probe',
          'GET /v1/balance',
          'GET /v1/tx-status',
          'POST /v1/transfer',
        ],
        subnet_math_probe_url: SUBNET_MATH_PROBE_URL || null,
      }),
    );
  });
}

start().catch((e) => {
  console.error(e);
  process.exit(1);
});
