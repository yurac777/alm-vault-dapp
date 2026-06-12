import os
import sys
import time
from decimal import Decimal
import eth_abi
import eth_utils
from web3 import Web3

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import logging
from core import telegram_reporter
from keeper.connectors.base_rpc import BaseConnector

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("RealtimeTracker")

WETH_ADDRESS = "0x4200000000000000000000000000000000000006"
USDC_ADDRESS = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"
POOL_MANAGER = "0x000000000004444c5dc75cB358380D2e3dE08A90"

# Calculate PoolId
encoded = eth_abi.encode(
    ['address', 'address', 'uint24', 'int24', 'address'], 
    [WETH_ADDRESS, USDC_ADDRESS, 500, 10, ZERO_ADDRESS]
)
pool_id = eth_utils.keccak(encoded)

SWAP_EVENT_SIGNATURE = Web3.keccak(text="Swap(bytes32,address,int128,int128,uint160,uint128,int24,uint24)").hex()

def main():
    connector = BaseConnector()
    w3 = connector.w3
    
    print("========================================")
    print("   UNISWAP V4 REALTIME FEE TRACKER      ")
    print("========================================")
    print(f"Tracking PoolId: {pool_id.hex()}")
    
    # Safe block fetch with failover
    latest_block = None
    while latest_block is None:
        try:
            latest_block = w3.eth.block_number
        except Exception as e:
            print(f"Failed to get block number: {e}. Rotating RPC...")
            connector.rotate_rpc()
            w3 = connector.w3
            time.sleep(1)
    # Analyze last 5000 blocks (approx 2.5 hours on Base)
    start_block = latest_block - 5000
    print(f"Scanning blocks {start_block} to {latest_block}...")
    
    try:
        total_volume_usdc = 0.0
        total_volume_weth = 0.0
        total_swaps = 0
        
        # Pagination / Chunking logic (500 blocks per request)
        chunk_size = 500
        current_start = start_block
        
        while current_start <= latest_block:
            current_end = min(current_start + chunk_size - 1, latest_block)
            print(f"  -> Fetching logs for chunk: {current_start} to {current_end}...")
            
            # Simple retry mechanism for the chunk
            retries = 3
            chunk_logs = []
            while retries > 0:
                try:
                    chunk_logs = w3.eth.get_logs({
                        "fromBlock": current_start,
                        "toBlock": current_end,
                        "address": w3.to_checksum_address(POOL_MANAGER),
                        "topics": [SWAP_EVENT_SIGNATURE, pool_id.hex()]
                    })
                    break # Success
                except Exception as chunk_e:
                    retries -= 1
                    print(f"     [Warning] Chunk {current_start}-{current_end} failed: {chunk_e}. Retries left: {retries}")
                    if retries > 0:
                        print("     [Action] Switching RPC...")
                        connector.rotate_rpc()
                        w3 = connector.w3
                    else:
                        print("     [Error] Failed to fetch chunk after retries. Skipping.")
                    time.sleep(2)
            
            total_swaps += len(chunk_logs)
            
            for log in chunk_logs:
                # Parse unindexed data
                # amount0 (int128), amount1 (int128), sqrtPriceX96 (uint160), liquidity (uint128), tick (int24), fee (uint24)
                # Web3.py decode returns a tuple
                try:
                    data = bytes.fromhex(log['data'][2:])
                    decoded = eth_abi.decode(['int128', 'int128', 'uint160', 'uint128', 'int24', 'uint24'], data)
                    amount0 = decoded[0] # WETH
                    amount1 = decoded[1] # USDC
                    
                    # amount0 and amount1 represent deltas. One is positive, one is negative.
                    # Volume is the absolute amount traded
                    total_volume_weth += abs(amount0) / 10**18
                    total_volume_usdc += abs(amount1) / 10**6
                    
                except Exception as e:
                    error_msg = f"Ошибка декодирования лога в realtime_tracker: {e}"
                    logger.error(error_msg)
                    telegram_reporter.send_error_message(error_msg)
            
            # Anti-spam sleep
            time.sleep(0.5)
            current_start = current_end + 1
                
        print(f"\n[Volume] За последние 5000 блоков (~2.5 часа):")
        print(f"Total Swaps : {total_swaps}")
        print(f"WETH Volume : {total_volume_weth:.4f} WETH")
        print(f"USDC Volume : {total_volume_usdc:.2f} USDC")
        
        # Calculate fees (0.05% pool fee)
        fee_weth = total_volume_weth * 0.0005
        fee_usdc = total_volume_usdc * 0.0005
        
        # Наша доля ликвидности. В демо предполагаем, что мы единственные в узком тике (или ~50%)
        # Реалистично, рассчитаем потенциальную прибыль (Pool Fees)
        print(f"\n[Pool Fees Generated]")
        print(f"Собрано пулом: {fee_weth:.6f} WETH | {fee_usdc:.4f} USDC")
        
        # Estimate our share (assuming ~10% of active tick liquidity for our TVL size in demo)
        our_share = 0.10
        print(f"Наша прибыль (оценочно {our_share*100}% share):")
        print(f"-> {fee_weth * our_share:.6f} WETH | {fee_usdc * our_share:.4f} USDC")
        
    except Exception as e:
        print(f"Ошибка получения логов: {e}")

if __name__ == "__main__":
    main()
