import sys
import os
import subprocess
from dotenv import load_dotenv

sys.path.insert(0, 'keeper')
load_dotenv('keeper/.env')

RPC_URL = os.getenv("BASE_MAINNET_RPC", "https://base-mainnet.g.alchemy.com/v2/IvMTCy2p4_jk6PCd5-2Gu")
BASESCAN_API_KEY = os.getenv("ETHERSCAN_TOKEN")
if not BASESCAN_API_KEY:
    BASESCAN_API_KEY = os.getenv("BASESCAN_API_KEY")
if not BASESCAN_API_KEY:
    BASESCAN_API_KEY = os.getenv("POLYGONSCAN_TOKEN")

VAULT_ADDRESS = os.getenv("VAULT_ADDRESS")
ZAPPER_ADDRESS = os.getenv("ZAPPER_ADDRESS")

VAULT_ARGS = "000000000000000000000000833589fcd6edb6e08f4c7c32d4f71b54bda02913000000000000000000000000420000000000000000000000000000000000000600000000000000000000000000000fde9fd1a4574d7141bc438dbcafd4c0e153000000000000000000000000a238dd80c259a72e81d7e4664a9801593f98d1c500000000000000000000000003a520b32c04bf3beef7beb72e919cf822ed34f10000000000000000000000002d8a3c5677189723c4cb8873cfc9c8976fdf38ac00000000000000000000000051ea49d2c76ab826faed18dc0c3c16fc29cbd5d4"
ZAP_ARGS = "000000000000000000000000833589fcd6edb6e08f4c7c32d4f71b54bda02913000000000000000000000000402c6e59f44e23074c00e1541512dde5b204552700000000000000000000000000000fde9fd1a4574d7141bc438dbcafd4c0e153"

def verify_contract(name, address, constructor_args=""):
    print(f"Verifying {name} at {address}...")
    cmd = [
        "contracts\\foundry_bin\\forge.exe", "verify-contract",
        address,
        name,
        "--rpc-url", RPC_URL,
        "--etherscan-api-key", BASESCAN_API_KEY,
        "--compiler-version", "v0.8.24+commit.e11b9ed9",
        "--watch",
        "--verifier", "etherscan",
        "--verifier-url", "https://api.basescan.org/api"
    ]
    if constructor_args:
        cmd.extend(["--constructor-args", constructor_args])
        
    print(f"Command: {' '.join(cmd)}")
    
    max_retries = 5
    import time
    for attempt in range(max_retries):
        print(f"Attempt {attempt + 1}/{max_retries}...")
        result = subprocess.run(cmd, cwd="contracts", check=False, capture_output=True, text=True)
        print(result.stdout)
        if result.stderr:
            print(result.stderr)
        
        if result.returncode == 0 and "OK" in result.stdout or "already verified" in result.stdout.lower() or "successful" in result.stdout.lower():
            print(f"✅ {name} verified successfully!")
            return
        
        print("Verification failed or connection reset. Retrying in 10 seconds...")
        time.sleep(10)
        
    print(f"❌ Failed to verify {name} after {max_retries} attempts.")

if __name__ == "__main__":
    if not BASESCAN_API_KEY:
        print("Missing BASESCAN_API_KEY / ETHERSCAN_TOKEN")
        sys.exit(1)
        
    if VAULT_ADDRESS:
        verify_contract("src/ALMVault_Singularity.sol:ALMVault_Singularity", VAULT_ADDRESS, VAULT_ARGS)
    else:
        print("VAULT_ADDRESS not set")
        
    if ZAPPER_ADDRESS:
        verify_contract("src/ALMZapper.sol:ALMZapper", ZAPPER_ADDRESS, ZAP_ARGS)
    else:
        print("ZAPPER_ADDRESS not set")
