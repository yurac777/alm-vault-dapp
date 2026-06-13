import requests
import json

api_key = "119KN47TI7YNX97TJZYXXI413ZPR7IVWXF"
# V10 Contract Address since config has it
contract_address = "0x9a45aC52cDDe7e0865F2b39BABAE486188Cc88c7"

with open("contracts/ALMVaultV10_flattened.sol", "r") as f:
    source_code = f.read()

payload = {
    "apikey": api_key,
    "module": "contract",
    "action": "verifysourcecode",
    "contractaddress": contract_address,
    "sourceCode": source_code,
    "codeformat": "1",
    "contractname": "ALMVaultV10",
    "compilerversion": "v0.8.24+commit.e11b9ed9",
    "optimizationUsed": 1,
    "runs": 200,
    "evmversion": "cancun",
    "licenseType": 3
}

print(f"=== PHYSICAL VERIFICATION: {contract_address} ===")
try:
    response = requests.post("https://api.basescan.org/api", data=payload)
    print("RAW STATUS CODE:", response.status_code)
    try:
        resp_json = response.json()
        print("RAW JSON RESPONSE:")
        print(json.dumps(resp_json, indent=2))
        
        if resp_json.get("status") == "1":
            print(f"GUID: {resp_json.get('result')}")
    except ValueError:
        print("RAW TEXT RESPONSE:")
        print(response.text)
except Exception as e:
    print(f"REQUEST ERROR: {e}")
