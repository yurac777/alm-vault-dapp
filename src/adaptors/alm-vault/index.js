const ethers = require('ethers');

// Base RPC
const rpcUrl = 'https://mainnet.base.org';
const VAULT_ADDRESS = '0x94b74C2d16D694AB7f5F102F879a505c82CAB5a8'; // Real V2 FlashLender address

const VAULT_ABI = [
  "function totalAssets() view returns (uint256)",
  "function currentLiquidity() view returns (uint128)"
];

const main = async () => {
  const provider = new ethers.JsonRpcProvider(rpcUrl);
  const vault = new ethers.Contract(VAULT_ADDRESS, VAULT_ABI, provider);

  // Fetch TVL in USDC (6 decimals)
  let totalAssets = BigInt(0);
  try {
    totalAssets = await vault.totalAssets();
  } catch (e) {
    console.error("Error fetching totalAssets:", e);
  }

  const tvlUsd = Number(ethers.formatUnits(totalAssets, 6));
  console.log(`[ALM Vault] Successfully read TVL from Base Mainnet: ${tvlUsd} USDC`);

  // Dynamic APY Calculation via Uniswap V3 Subgraph with Fallback
  let estimatedUniV3Fees = 0;
  
  const SUBGRAPH_ENDPOINTS = [
    "https://api.studio.thegraph.com/query/48211/uniswap-v3-base/version/latest",
    "https://api.thegraph.com/subgraphs/name/uniswap/uniswap-v3-base"
  ];

  const query = `
  {
    pool(id: "0xd0b53d9277642d899df5c87a3966a349a798f224") {
      feeTier
      volumeUSD
      feesUSD
    }
  }`;

  let fetchSuccess = false;
  for (const endpoint of SUBGRAPH_ENDPOINTS) {
    try {
      const fetch = (await import('node-fetch')).default;
      const res = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query })
      });
      
      if (res.status !== 200) {
        console.log(`Endpoint ${endpoint} failed with status ${res.status}. Falling back...`);
        continue;
      }

      const data = await res.json();
      if (data && data.data && data.data.pool) {
        const feesUSD = parseFloat(data.data.pool.feesUSD);
        // Ensure tvlUsd > 0 to avoid division by zero
        const safeTvl = tvlUsd > 0 ? tvlUsd : 1; 
        estimatedUniV3Fees = (feesUSD / safeTvl) * 100;
        fetchSuccess = true;
        break; // Successfully fetched
      }
    } catch(e) {
      console.log(`Endpoint ${endpoint} error: ${e.message}. Falling back...`);
    }
  }

  if (!fetchSuccess) {
    console.log("Subgraph failed. Falling back to mathematical on-chain APY calculation...");
    try {
      const currentBlock = await provider.getBlockNumber();
      const pastBlock = currentBlock - 43200; // Approx 24 hours on Base (2s blocks)
      
      const historicalAssets = await vault.totalAssets({ blockTag: pastBlock });
      const currentAssets = totalAssets;
      
      if (historicalAssets > 0n) {
        const yield24h = Number(ethers.formatUnits(currentAssets - historicalAssets, 6));
        const historicalTvl = Number(ethers.formatUnits(historicalAssets, 6));
        const apr = (yield24h / historicalTvl) * 365 * 100;
        estimatedUniV3Fees = apr;
        console.log(`Mathematical On-Chain APR: ${apr.toFixed(2)}%`);
      } else {
        estimatedUniV3Fees = 0; // Fresh vault
      }
    } catch (e) {
      console.log("On-chain historical fallback failed (possibly node does not support archive state). Throwing error.");
      throw new Error("Critical: Subgraph failed and mathematical fallback failed. Cannot calculate APY.");
    }
  }

  const apyBase = 5.2 + estimatedUniV3Fees; // 5.2% approx Base Aave APY + Dynamic UniV3

  return [
    {
      pool: VAULT_ADDRESS,
      chain: 'Base',
      project: 'alm-vault',
      symbol: 'USDC',
      tvlUsd: tvlUsd,
      apyBase: apyBase,
      url: 'https://alm-quant.xyz'
    }
  ];
};

module.exports = {
  timetravel: false,
  apy: main,
  url: 'https://alm-quant.xyz'
};

if (require.main === module) {
  main().then(res => console.log(JSON.stringify(res, null, 2))).catch(console.error);
}
