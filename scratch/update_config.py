import re
with open('keeper/config.py', 'r') as f:
    content = f.read()

content = re.sub(r'VAULT_ADDRESS\s*=\s*\".*?\"', 'VAULT_ADDRESS = "0x2726c74D2e0A94Ec181Beb618569b10116415289"', content)
content = re.sub(r"VAULT_ADDRESS\s*=\s*'.*?'", 'VAULT_ADDRESS = "0x2726c74D2e0A94Ec181Beb618569b10116415289"', content)

with open('keeper/config.py', 'w') as f:
    f.write(content)
print("Updated config.py")
