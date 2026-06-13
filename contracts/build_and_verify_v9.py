"""
build_and_verify_v7.py
======================
Build Standard JSON Input from compiled artifacts and submit to Basescan.
Standard JSON Input is the ONLY format that properly supports viaIR via API.
"""
import json
import os
import time
import requests

VAULT_ADDRESS = "0x5BE2DA950F8F15588bb0B670e9b8c3f538aE8E5d"
BASESCAN_KEY  = "119KN47TI7YNX97TJZYXXI413ZPR7IVWXF"
CONTRACTS_DIR = os.path.dirname(os.path.abspath(__file__))
ARTIFACT_PATH = os.path.join(CONTRACTS_DIR, "out", "ALMVaultV9.sol", "ALMVaultV9.json")


def build_standard_json():
    """Reconstruct Standard JSON Input from compiled artifact + source files on disk."""
    with open(ARTIFACT_PATH, "r", encoding="utf-8") as f:
        art = json.load(f)

    meta = art["metadata"]
    compiler_version = meta["compiler"]["version"]
    print(f"Compiler from artifact: {compiler_version}")

    # Read each source file from disk
    sources = {}
    missing = []
    for src_path in meta["sources"]:
        disk_path = os.path.join(CONTRACTS_DIR, src_path)
        if os.path.exists(disk_path):
            with open(disk_path, "r", encoding="utf-8") as f:
                sources[src_path] = {"content": f.read()}
        else:
            missing.append(src_path)

    if missing:
        print(f"[WARN] Missing source files: {missing}")

    print(f"Loaded {len(sources)}/{len(meta['sources'])} source files")

    # Build Standard JSON Input
    std_json = {
        "language": "Solidity",
        "sources": sources,
        "settings": {
            "remappings": [
                "openzeppelin-contracts/=lib/openzeppelin-contracts/"
            ],
            "optimizer": {
                "enabled": True,
                "runs": 200
            },
            "viaIR": True,
            "evmVersion": "cancun",
            "outputSelection": {
                "*": {
                    "*": ["abi", "evm.bytecode", "evm.deployedBytecode", "evm.methodIdentifiers", "metadata"],
                    "": ["ast"]
                }
            }
        }
    }

    return std_json, compiler_version


def verify(std_json, compiler_version):
    """Submit Standard JSON Input to Etherscan V2 API for Base Mainnet."""
    url    = "https://api.etherscan.io/v2/api"
    params = {"chainid": "8453"}

    source_code = json.dumps(std_json)

    # Etherscan wants the compiler version in the format: v0.8.24+commit.e11b9ed9
    # The artifact may report: 0.8.34+commit.80d5c536 — use that exact version
    if not compiler_version.startswith("v"):
        compiler_version = "v" + compiler_version
    print(f"Using compiler: {compiler_version}")

    data = {
        "apikey":          BASESCAN_KEY,
        "module":          "contract",
        "action":          "verifysourcecode",
        "contractaddress": VAULT_ADDRESS,
        "sourceCode":      source_code,
        "codeformat":      "solidity-standard-json-input",
        "contractname":    "src/ALMVaultV9.sol:ALMVaultV9",
        "compilerversion": compiler_version,
        "licenseType":     "3",  # MIT
    }

    print(f"\nSubmitting Standard JSON Input ({len(source_code):,} bytes)...")
    resp     = requests.post(url, data=data, params=params, timeout=120)
    res_json = resp.json()
    print(f"Response: {resp.text[:300]}")

    if res_json.get("status") != "1":
        print(f"[ERROR] Submission failed: {resp.text}")
        return False

    guid = res_json["result"]
    print(f"GUID: {guid}")
    print("Polling verification status...")

    for i in range(25):
        time.sleep(6)
        check = requests.get(url, params={
            **params,
            "apikey": BASESCAN_KEY,
            "module": "contract",
            "action": "checkverifystatus",
            "guid":   guid,
        }, timeout=30)
        result = check.json().get("result", "")
        msg    = check.json().get("message", "")
        print(f"  [{i+1:02d}] {result}")

        if result == "Pass - Verified":
            print(f"\n[SUCCESS] ALMVaultV9 VERIFIED!")
            print(f"  https://basescan.org/address/{VAULT_ADDRESS}#code")
            return True

        if "Fail" in result or ("NOTOK" in msg and "Pending" not in result):
            print(f"[FAIL] {check.text}")
            return False

    print("[TIMEOUT] Verification polling timed out after 150s.")
    return False


def main():
    print("=" * 60)
    print("  ALMVaultV9 — Standard JSON Verification")
    print(f"  Contract: {VAULT_ADDRESS}")
    print("=" * 60)

    std_json, compiler_version = build_standard_json()
    verify(std_json, compiler_version)


if __name__ == "__main__":
    main()
