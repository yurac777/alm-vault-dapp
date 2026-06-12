from web3 import Web3
from decimal import Decimal

try:
    from web3.middleware import ExtraDataToPOAMiddleware
except ImportError:
    from web3.middleware import geth_poa_middleware as ExtraDataToPOAMiddleware

RPC_POOL = [
    "https://base-mainnet.g.alchemy.com/v2/IvMTCy2p4_jk6PCd5-2Gu",
    "https://mainnet.base.org",
    "https://base-rpc.publicnode.com",
    "https://base.llamarpc.com",
    "https://base.meowrpc.com",
    "https://1rpc.io/base"
]

class BaseConnector:
    def __init__(self, rpc_url: str = None):
        self.current_rpc_index = 0
        if rpc_url and rpc_url not in RPC_POOL:
            RPC_POOL.insert(0, rpc_url)
            
        self._init_w3()
        
    def _init_w3(self):
        rpc_url = RPC_POOL[self.current_rpc_index]
        self.w3 = Web3(Web3.HTTPProvider(rpc_url, request_kwargs={'timeout': 30}))
        self.w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
        print(f"[BaseConnector] Инициализирован RPC: {rpc_url}")
        
    def rotate_rpc(self):
        self.current_rpc_index = (self.current_rpc_index + 1) % len(RPC_POOL)
        print(f"[BaseConnector] Ротация RPC. Новый индекс: {self.current_rpc_index}")
        self._init_w3()
        
    def is_connected(self) -> bool:
        """Проверяет подключение к RPC ноде."""
        return self.w3.is_connected()
        
    def get_latest_block_number(self) -> int:
        """Возвращает номер последнего блока."""
        return self.w3.eth.get_block('latest')['number']
        
    def get_balance(self, address: str) -> Decimal:
        """Возвращает баланс нативного ETH на кошельке в Decimal."""
        checksum_address = self.w3.to_checksum_address(address)
        balance_wei = self.w3.eth.get_balance(checksum_address)
        return Decimal(self.w3.from_wei(balance_wei, 'ether'))
        
    def get_optimal_gas_fee(self) -> dict:
        """
        Рассчитывает оптимальные комиссии для Type 2 (EIP-1559) транзакций.
        """
        latest_block = self.w3.eth.get_block('latest')
        
        # Base fee - базовая комиссия блока (сжигается)
        base_fee = latest_block.get('baseFeePerGas', 0)
        
        # Priority fee (чаевые майнеру/секвенсору)
        try:
            max_priority_fee = self.w3.eth.max_priority_fee
        except Exception:
            # Фолбэк, если публичная нода обрывает соединение или не поддерживает метод
            max_priority_fee = self.w3.to_wei('0.01', 'gwei')
        
        # Max fee = базовая комиссия + чаевые + буфер 15% на случай резкого всплеска
        max_fee_per_gas = int(base_fee * 1.15) + max_priority_fee
        
        return {
            'maxFeePerGas': max_fee_per_gas,
            'maxPriorityFeePerGas': max_priority_fee
        }
