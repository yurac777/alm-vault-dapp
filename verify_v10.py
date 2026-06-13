import requests, os, time, json
from dotenv import load_dotenv

load_dotenv(dotenv_path="keeper/.env")
vault_address = os.getenv("VAULT_ADDRESS")

# We must use Standard JSON for verification with viaIR
BUILD_DIR = "contracts/out/build-info"
standard_json = None
for f in os.listdir(BUILD_DIR):
    if f.endswith(".json"):
        with open(os.path.join(BUILD_DIR, f), "r", encoding="utf-8") as bf:
            data = json.load(bf)
            if "input" in data:
                standard_json = data["input"]
                break

if not standard_json:
    print("Could not find standard JSON input.")
    exit(1)

source_code = json.dumps(standard_json)

url = "https://api.etherscan.io/v2/api"
BASESCAN_KEY = "119KN47TI7YNX97TJZYXXI413ZPR7IVWXF"

data = {
    "apikey":          BASESCAN_KEY,
    "chainid":         "8453",
    "module":          "contract",
    "action":          "verifysourcecode",
    "contractaddress": vault_address,
    "sourceCode":      source_code,
    "codeformat":      "3",  # 3 = Standard JSON
    "contractname":    "src/ALMVault.sol:ALMVault",
    "compilerversion": "v0.8.24+commit.e11b9ed9",
    "optimizationUsed": "1",
    "runs": "200"
}

print(f"Verifying {vault_address} on Basescan via Single File with viaIR...")
resp = requests.post(url, data=data, params={"chainid": "8453"}, timeout=60)
res_json = resp.json()
print("Response:", res_json)

if res_json.get("status") == "1":
    guid = res_json["result"]
    for i in range(15):
        time.sleep(5)
        check = requests.get(url, params={"chainid":"8453", "apikey":BASESCAN_KEY, "module":"contract", "action":"checkverifystatus", "guid":guid})
        result_msg = check.json().get("result")
        print(f"[{i+1}] {result_msg}")
        if result_msg == "Pass - Verified":
            print(f"SUCCESS: https://basescan.org/address/{vault_address}#code")
            break
