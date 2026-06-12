import requests, time

rpcs = [
    'https://base.llamarpc.com',
    'https://base.drpc.org',
    '1rpc.io/base',
    'https://base-rpc.publicnode.com',
]
payload = {'jsonrpc': '2.0', 'method': 'eth_blockNumber', 'params': [], 'id': 1}
best = None
for rpc in rpcs:
    url = rpc if rpc.startswith('http') else 'https://' + rpc
    try:
        t0 = time.time()
        r = requests.post(url, json=payload, timeout=6)
        ms = int((time.time()-t0)*1000)
        block = int(r.json()['result'], 16)
        print(f'OK {ms}ms - {url} -> block {block}')
        if best is None:
            best = url
    except Exception as e:
        print(f'FAIL - {url}: {e}')

print()
print('BEST RPC:', best)
