import sys, os, subprocess
sys.path.insert(0, '../keeper')
import config

VAULT = config.VAULT_ADDRESS
forge_path = os.path.abspath(r'foundry_bin\forge.exe')

cmd = [
    forge_path, 'verify-contract',
    '--verifier', 'blockscout',
    '--verifier-url', 'https://base.blockscout.com/api/',
    '--num-of-optimizations', '200',
    '--compiler-version', 'v0.8.24+commit.e11b9ed9',
    '--constructor-args', '000000000000000000000000833589fcd6edb6e08f4c7c32d4f71b54bda02913000000000000000000000000420000000000000000000000000000000000000600000000000000000000000000000fde9fd1a4574d7141bc438dbcafd4c0e153000000000000000000000000a238dd80c259a72e81d7e4664a9801593f98d1c500000000000000000000000003a520b32c04bf3beef7beb72e919cf822ed34f10000000000000000000000002d8a3c5677189723c4cb8873cfc9c8976fdf38ac0000000000000000000000002cc0fc26ed4563a5ce5e8bdcfe1a2878676ae156',
    '--watch',
    VAULT,
    'src/ALMVaultV10.sol:ALMVaultV10'
]

print("Running verification:", " ".join(cmd))
res = subprocess.run(cmd, capture_output=True, text=True)
print("STDOUT:", res.stdout)
print("STDERR:", res.stderr)

if "GUID" in res.stdout or "OK" in res.stdout or "already verified" in res.stdout or "Success" in res.stdout:
    print("Verification Successful!")
else:
    print("Verification Failed.")
