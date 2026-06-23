import os
import json
from flask import Flask, request, jsonify
from web3 import Web3

app = Flask(__name__)

# Config
BASE_RPC = os.getenv("BASE_MAINNET_RPC", "https://mainnet.base.org")
w3 = Web3(Web3.HTTPProvider(BASE_RPC))

VAULT_ADDRESS = "0xYourVaultAddress" # Usually configured via env
USDC_ADDRESS = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
DEPOSIT_AMOUNT = 100 * 10**6 # 100 USDC

def get_vault_abi():
    return [
        {
            "inputs": [{"internalType": "uint256", "name": "assets", "type": "uint256"}, {"internalType": "address", "name": "receiver", "type": "address"}],
            "name": "deposit",
            "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
            "stateMutability": "nonpayable",
            "type": "function"
        }
    ]

# --- FARCASTER FRAMES ---

@app.route('/api/frame', methods=['GET', 'POST'])
def frame_home():
    html = f"""
    <!DOCTYPE html>
    <html>
      <head>
        <meta property="fc:frame" content="vNext" />
        <meta property="fc:frame:image" content="https://api.placeholder.com/600x315/0f172a/10b981?text=Mint+almUSD" />
        
        <meta property="fc:frame:button:1" content="Mint almUSD (Deposit 100 USDC)" />
        <meta property="fc:frame:button:1:action" content="tx" />
        <meta property="fc:frame:button:1:target" content="https://YOUR_DOMAIN/api/frame/tx/deposit" />
      </head>
      <body>
        <h1>ALMVault</h1>
        <p>Deposit USDC directly from Farcaster.</p>
      </body>
    </html>
    """
    return html

@app.route('/api/frame/tx/deposit', methods=['POST'])
def frame_tx_deposit():
    body = request.json or {}
    untrusted_data = body.get("untrustedData", {})
    user_address = untrusted_data.get("address", "0x0000000000000000000000000000000000000000")
    
    vault = w3.eth.contract(address=VAULT_ADDRESS, abi=get_vault_abi())
    calldata = vault.encode_abi("deposit", args=[DEPOSIT_AMOUNT, user_address])
    
    return jsonify({
        "chainId": "eip155:8453",
        "method": "eth_sendTransaction",
        "params": {
            "abi": get_vault_abi(),
            "to": VAULT_ADDRESS,
            "data": calldata,
            "value": "0"
        }
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
