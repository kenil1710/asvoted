// Probes candidate public RPCs: chain id, finalized tag, batch of 10, an old
// tx + receipt by hash, eth_call at the finalized block and at an old block.
const C = {
  ethereum: { id: 1, tx: "0x5c306081ffda317547e42d245603e5ba08a0ee9386255bfe2e17b98dfa2bf159", old: "0xe4e1c0", tok: "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
    rpcs: ["https://ethereum-rpc.publicnode.com", "https://eth.llamarpc.com", "https://eth.drpc.org", "https://eth-pokt.nodies.app", "https://1rpc.io/eth", "https://rpc.mevblocker.io", "https://eth.merkle.io", "https://cloudflare-eth.com", "https://ethereum.publicnode.com", "https://rpc.flashbots.net", "https://eth-mainnet.public.blastapi.io", "https://gateway.tenderly.co/public/mainnet", "https://mainnet.gateway.tenderly.co"] },
  arbitrum: { id: 42161, tok: "0x912CE59144191C1204E64559FE8253a0e49E6548", old: "0x8000000",
    rpcs: ["https://arb1.arbitrum.io/rpc", "https://arbitrum-one-rpc.publicnode.com", "https://arbitrum.drpc.org", "https://arb-pokt.nodies.app", "https://1rpc.io/arb", "https://arbitrum.llamarpc.com", "https://arbitrum-one.public.blastapi.io", "https://arbitrum.gateway.tenderly.co"] },
  optimism: { id: 10, tok: "0x4200000000000000000000000000000000000042", old: "0x6000000",
    rpcs: ["https://mainnet.optimism.io", "https://optimism-rpc.publicnode.com", "https://optimism.drpc.org", "https://op-pokt.nodies.app", "https://1rpc.io/op", "https://optimism.llamarpc.com", "https://optimism-mainnet.public.blastapi.io", "https://optimism.gateway.tenderly.co"] },
  base: { id: 8453, tok: "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913", old: "0x1000000",
    rpcs: ["https://mainnet.base.org", "https://base-rpc.publicnode.com", "https://base.drpc.org", "https://base-pokt.nodies.app", "https://1rpc.io/base", "https://base.llamarpc.com", "https://base-mainnet.public.blastapi.io", "https://base.gateway.tenderly.co"] },
  polygon: { id: 137, tok: "0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359", old: "0x3000000",
    rpcs: ["https://polygon-rpc.com", "https://polygon-bor-rpc.publicnode.com", "https://polygon.drpc.org", "https://poly.api.pocket.network", "https://1rpc.io/matic", "https://polygon.llamarpc.com", "https://polygon-mainnet.public.blastapi.io", "https://polygon.gateway.tenderly.co"] },
};
const only = process.argv[2];
async function post(url, body) {
  const t = Date.now();
  try {
    const r = await fetch(url, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body), signal: AbortSignal.timeout(15000) });
    const txt = await r.text();
    let j = null; try { j = JSON.parse(txt); } catch {}
    return { status: r.status, j, txt: txt.slice(0, 120), ms: Date.now() - t };
  } catch (e) { return { status: -1, txt: String(e.message).slice(0, 80) }; }
}
for (const [name, c] of Object.entries(C)) {
  if (only && only !== name) continue;
  for (const url of c.rpcs) {
    const fin = await post(url, { jsonrpc: "2.0", id: 1, method: "eth_getBlockByNumber", params: ["finalized", false] });
    const fb = fin.j?.result?.number;
    const batch = [];
    for (let i = 0; i < 10; i++) batch.push({ jsonrpc: "2.0", id: i, method: i === 0 ? "eth_chainId" : "eth_call", params: i === 0 ? [] : [{ to: c.tok, data: "0x313ce567" }, fb ?? "latest"] });
    const b = await post(url, batch);
    const bok = Array.isArray(b.j) && b.j.length === 10 && b.j.every((x) => x.result);
    const arch = await post(url, { jsonrpc: "2.0", id: 1, method: "eth_call", params: [{ to: c.tok, data: "0x313ce567" }, c.old] });
    let tx = "-";
    if (c.tx) {
      const t = await post(url, [{ jsonrpc: "2.0", id: 0, method: "eth_getTransactionByHash", params: [c.tx] }, { jsonrpc: "2.0", id: 1, method: "eth_getTransactionReceipt", params: [c.tx] }]);
      tx = Array.isArray(t.j) && t.j.every((x) => x.result) ? "old-tx OK" : "old-tx FAIL " + (t.txt || "").slice(0, 60);
    }
    console.log(`${name.padEnd(9)} ${url.padEnd(48)} fin=${fb ? parseInt(fb, 16) : "NO " + fin.status + " " + (fin.txt || "").slice(0, 50)} batch10=${bok ? "OK" : "NO " + b.status + " " + (b.txt || "").slice(0, 50)} archive=${arch.j?.result ? "OK" : "NO " + (arch.j?.error?.message ?? arch.txt ?? "").slice(0, 40)} ${tx} ${fin.ms}ms`);
  }
}
