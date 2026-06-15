import os
import json
from flask import Flask, request, jsonify, render_template_string
from web3 import Web3

app = Flask(__name__)

# Config
BASE_RPC = os.getenv("BASE_MAINNET_RPC", "https://mainnet.base.org")
w3 = Web3(Web3.HTTPProvider(BASE_RPC))

VAULT_ADDRESS = "0xYourVaultAddress" # Usually configured via env, assuming config.VAULT_ADDRESS
USDC_ADDRESS = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
DEPOSIT_AMOUNT = 100 * 10**6 # 100 USDC

# Try to load vault address from config if available (up one dir)
try:
    import sys
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    import keeper.config as config
    VAULT_ADDRESS = config.VAULT_ADDRESS
except:
    pass

def get_erc20_abi():
    return [
        {
            "constant": False,
            "inputs": [{"name": "spender", "type": "address"}, {"name": "amount", "type": "uint256"}],
            "name": "approve",
            "outputs": [{"name": "", "type": "bool"}],
            "payable": False,
            "stateMutability": "nonpayable",
            "type": "function"
        },
        {
            "constant": True,
            "inputs": [{"name": "account", "type": "address"}],
            "name": "balanceOf",
            "outputs": [{"name": "", "type": "uint256"}],
            "payable": False,
            "stateMutability": "view",
            "type": "function"
        }
    ]

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
        <meta property="fc:frame:image" content="https://api.placeholder.com/600x315/0f172a/10b981?text=ALMVault+Epoch+1:+3x+Points+Multiplier" />
        
        <meta property="fc:frame:button:1" content="Approve 100 USDC" />
        <meta property="fc:frame:button:1:action" content="tx" />
        <meta property="fc:frame:button:1:target" content="https://YOUR_DOMAIN/api/frame/tx/approve" />
        
        <meta property="fc:frame:button:2" content="Deposit 100 USDC" />
        <meta property="fc:frame:button:2:action" content="tx" />
        <meta property="fc:frame:button:2:target" content="https://YOUR_DOMAIN/api/frame/tx/deposit" />
      </head>
      <body>
        <h1>ALMVault Epoch 1</h1>
        <p>Deposit USDC directly from Farcaster.</p>
      </body>
    </html>
    """
    return html

@app.route('/api/frame/tx/approve', methods=['POST'])
def frame_tx_approve():
    erc20 = w3.eth.contract(address=USDC_ADDRESS, abi=get_erc20_abi())
    calldata = erc20.encodeABI(fn_name="approve", args=[VAULT_ADDRESS, DEPOSIT_AMOUNT])
    
    return jsonify({
        "chainId": "eip155:8453",
        "method": "eth_sendTransaction",
        "params": {
            "abi": get_erc20_abi(),
            "to": USDC_ADDRESS,
            "data": calldata,
            "value": "0"
        }
    })

@app.route('/api/frame/tx/deposit', methods=['POST'])
def frame_tx_deposit():
    # We need the user's address to set as the receiver.
    # In Farcaster vNext frames, the caller's address can be parsed from the trustedData message.
    # For this implementation, we will extract it if provided, or default to msg.sender in a wrapper if needed.
    # To keep it simple, we pass a dummy address if not found, but a real app verifies the signature.
    
    body = request.json or {}
    untrusted_data = body.get("untrustedData", {})
    # For a real implementation, you verify trustedData. Here we just take the custody address if passed.
    fid = untrusted_data.get("fid", 0)
    user_address = "0x0000000000000000000000000000000000000000" # Placeholder, requires Neynar API to map FID to address in prod.
    
    # Actually, in standard Farcaster tx frames, the user's connected wallet will execute the tx.
    # The 'deposit' function requires the 'receiver' address.
    # If we pass user_address=address(0), it might revert.
    # In Farcaster frame tx specs, we can't dynamically inject the executor's address unless they send it.
    # Wait, the spec says: "The user's connected wallet address is not available to the frame server."
    # Wait! As of February 2024, `untrustedData` contains `address` for `tx` action if the user connected a wallet.
    user_address = untrusted_data.get("address", "0x0000000000000000000000000000000000000000")
    
    vault = w3.eth.contract(address=VAULT_ADDRESS, abi=get_vault_abi())
    calldata = vault.encodeABI(fn_name="deposit", args=[DEPOSIT_AMOUNT, user_address])
    
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

# --- GALXE / LAYER3 QUEST API ---

@app.route('/verify_deposit', methods=['GET'])
def verify_deposit():
    address = request.args.get('address')
    if not address or not w3.is_address(address):
        return jsonify({"is_eligible": False, "error": "Invalid address"}), 400
        
    address = w3.to_checksum_address(address)
    try:
        erc20 = w3.eth.contract(address=VAULT_ADDRESS, abi=get_erc20_abi())
        bal = erc20.functions.balanceOf(address).call()
        is_eligible = bal > 0
        return jsonify({"is_eligible": is_eligible})
    except Exception as e:
        return jsonify({"is_eligible": False, "error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
