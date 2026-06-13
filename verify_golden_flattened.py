import requests, os, time

api_key = '119KN47TI7YNX97TJZYXXI413ZPR7IVWXF'
contract_address = '0x1d7f402A789a1e06Eac3E161d0AEdbEcf8090964'

with open('contracts/flat.sol', 'r') as f:
    source_code = f.read()

# Filter out duplicate SPDX-License-Identifiers that forge flatten might leave
lines = source_code.split('\n')
filtered = []
spdx_found = False
for line in lines:
    if 'SPDX-License-Identifier' in line:
        if not spdx_found:
            filtered.append(line)
            spdx_found = True
        else:
            continue
    else:
        filtered.append(line)
source_code = '\n'.join(filtered)

data = {
    'apikey': api_key,
    'module': 'contract',
    'action': 'verifysourcecode',
    'contractaddress': contract_address,
    'sourceCode': source_code,
    'codeformat': '1', # flattened
    'contractname': 'ALMVault',
    'compilerversion': 'v0.8.24+commit.e11b9ed9',
    'optimizationUsed': '1',
    'runs': 200,
    'chainid': '8453',
}

print('Submitting to Basescan API...')
response = requests.post('https://api.basescan.org/v2/api', data=data)
print(response.text)

res = response.json()
if res.get('status') == '1':
    guid = res['result']
    print('GUID:', guid)
    while True:
        time.sleep(5)
        check = requests.get('https://api.basescan.org/api', params={
            'apikey': api_key,
            'module': 'contract',
            'action': 'checkverifystatus',
            'guid': guid
        }).json()
        print('Status:', check.get('result'))
        if check.get('result') == 'Pass - Verified' or check.get('result') == 'Already Verified':
            print('VERIFICATION SUCCESSFUL!')
            break
        elif check.get('status') == '0' and check.get('result') != 'Pending in queue':
            print('FAILED!')
            break
else:
    print('Failed to submit:', res)
