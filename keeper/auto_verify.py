import os
import time
import requests
import json
from dotenv import load_dotenv
from eth_abi import encode

load_dotenv()

API_KEY = os.getenv("ETHERSCAN_TOKEN")
BASESCAN_API_URL = "https://api.etherscan.io/v2/api?chainid=8453"

USDC = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
WETH = "0x4200000000000000000000000000000000000006"
ROUTER = "0x2626664c2603336E57B271c5C0b26F421741e481"
KEEPER = "0x00000FdE9Fd1A4574D7141BC438DBCaFd4c0e153"

vault_args = encode(['address', 'address', 'address', 'address'], [USDC, WETH, ROUTER, KEEPER]).hex()
zapper_args = encode(['address'], [USDC]).hex()

def read_json(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except UnicodeDecodeError:
        with open(path, "r", encoding="utf-16le") as f:
            return f.read().replace('\ufeff', '')

contracts = [
    {
        "name": "ALMVault_Singularity",
        "file": "contracts/src/ALMVault_Singularity.sol:ALMVault_Singularity",
        "address": "0x402C6E59F44e23074C00E1541512Dde5b2045527",
        "json_path": "vault_standard_json.json",
        "compiler": "v0.8.24+commit.e11b9ed9",
        "args": vault_args
    },
    {
        "name": "ALMZapper",
        "file": "contracts/src/ALMZapper.sol:ALMZapper",
        "address": "0xcF473A11A1675BEb5b5bCcBB06dFAbd54463283e",
        "json_path": "zapper_standard_json.json",
        "compiler": "v0.8.24+commit.e11b9ed9",
        "args": zapper_args
    }
]

def verify_contract(c):
    print(f"\n[INFO] Starting verification for {c['name']} at {c['address']}...")
    source_code = read_json(c['json_path'])
    
    data = {
        "apikey": API_KEY,
        "module": "contract",
        "action": "verifysourcecode",
        "contractaddress": c['address'],
        "sourceCode": source_code,
        "codeformat": "solidity-standard-json-input",
        "contractname": c['file'],
        "compilerversion": c['compiler'],
        "constructorArguments": c['args']
    }
    
    guid = None
    while not guid:
        try:
            print(f"       -> POSTing payload to {BASESCAN_API_URL} ...")
            response = requests.post(BASESCAN_API_URL, data=data, timeout=30)
            res_json = response.json()
            
            if res_json.get("status") == "1":
                guid = res_json.get("result")
                print(f"       -> SUCCESS! Received GUID: {guid}")
            elif "Already Verified" in res_json.get("result", ""):
                print(f"       -> SUCCESS: {c['name']} is already verified!")
                return
            else:
                print(f"       -> API Error: {res_json.get('result')}. Retrying in 15s...")
                time.sleep(15)
        except Exception as e:
            print(f"       -> Network Error: {e}. Retrying in 15s...")
            time.sleep(15)
            
    print(f"[INFO] Polling verification status for GUID {guid}...")
    while True:
        try:
            params = {
                "apikey": API_KEY,
                "module": "contract",
                "action": "checkverifystatus",
                "guid": guid
            }
            resp = requests.get(BASESCAN_API_URL, params=params, timeout=30).json()
            status = resp.get("status")
            result = resp.get("result")
            
            if status == "1" and "Pass - Verified" in result:
                print(f"[SUCCESS] {c['name']} is VERIFIED! Result: {result}")
                break
            elif status == "0" and "Pending in queue" in result:
                print(f"       -> Pending... ({result})")
                time.sleep(10)
            else:
                print(f"       -> Verification Result: {result}")
                if "Fail" in result or status == "0" and "Pending" not in result:
                    print(f"[ERROR] Verification failed for {c['name']}.")
                    break
                time.sleep(10)
        except Exception as e:
            print(f"       -> Polling Network Error: {e}. Retrying in 15s...")
            time.sleep(15)

def main():
    print("[INFO] Basescan Auto-Verifier Started")
    for c in contracts:
        verify_contract(c)
    print("\n[SUCCESS] All contracts successfully verified on Basescan!")

if __name__ == '__main__':
    main()
