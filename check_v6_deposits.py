import sys; sys.path.insert(0, 'keeper')
from config import RPC_URL
from web3 import Web3
w3 = Web3(Web3.HTTPProvider(RPC_URL))
v6_addr = w3.to_checksum_address('0x75fd978542e082d455879A9301567438e71db9ec')
v6 = w3.eth.contract(address=v6_addr, abi=[{'anonymous': False, 'inputs': [{'indexed': True, 'internalType': 'address', 'name': 'sender', 'type': 'address'}, {'indexed': True, 'internalType': 'address', 'name': 'owner', 'type': 'address'}, {'indexed': False, 'internalType': 'uint256', 'name': 'assets', 'type': 'uint256'}, {'indexed': False, 'internalType': 'uint256', 'name': 'shares', 'type': 'uint256'}], 'name': 'Deposit', 'type': 'event'}])
logs = v6.events.Deposit.get_logs(fromBlock=47280000, toBlock='latest')
for log in logs:
    print(f"Deposit: assets={log['args']['assets']}, shares={log['args']['shares']}")
