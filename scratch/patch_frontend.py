import re
with open('frontend/index.html', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace Addresses
new_vault = "0x2726c74D2e0A94Ec181Beb618569b10116415289"
content = content.replace("0x6B2Ec85Fb2c4CE051B71804e20aD8F2c03DADcB4", new_vault)
content = content.replace("0xC29688C7ca27c2826469D3F14D417562CcF5a3b5", new_vault)
content = content.replace("0xC296...a3b5", "0x2726...5289")

# Add UI for Queue
queue_html = """
<div class="mb-6 flex justify-between items-end">
<h2 class="text-xl font-bold text-white" data-i18n="vault_interface">Vault Interface</h2>
<div class="text-right">
<p class="text-xs text-slate-500 mb-1" data-i18n="your_balance">Your USDC Balance</p>
<p id="userBalanceDisplay" class="font-mono text-sm font-semibold">0.00</p>
</div>
</div>
<!-- Queue Display -->
<div id="queueDisplay" class="hidden mb-4 p-3 bg-blue-900/20 border border-blue-500/50 rounded-lg text-sm text-blue-300">
    <div class="flex items-center">
        <svg class="animate-spin -ml-1 mr-2 h-4 w-4 text-blue-400" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>
        <span>Withdrawal pending... <span id="queueAmount" class="font-bold">0.00</span> USDC will be available shortly.</span>
    </div>
</div>
"""
content = re.sub(r'<div class="mb-6 flex justify-between items-end">.*?</div>\s*</div>', queue_html, content, flags=re.DOTALL)

# Add ABI for withdrawal request
abi_addition = '"function withdrawalRequests(address) view returns (uint256 amount, uint256 timestamp)"'
if abi_addition not in content:
    content = content.replace('"function maxWithdraw(address owner) view returns (uint256)"', 
                              '"function maxWithdraw(address owner) view returns (uint256)",\n    ' + abi_addition)

# Add JS logic to fetch queue
js_addition = """
    try {
        const req = await vaultContract.withdrawalRequests(userAddress);
        const reqAmount = parseFloat(ethers.formatUnits(req.amount, 6));
        const queueDisplay = document.getElementById('queueDisplay');
        const queueAmount = document.getElementById('queueAmount');
        if (reqAmount > 0) {
            queueDisplay.classList.remove('hidden');
            queueAmount.innerText = reqAmount.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2});
        } else {
            queueDisplay.classList.add('hidden');
        }
    } catch(e) { console.log("Queue fetch err", e); }
"""
if "const req =" not in content:
    # Insert inside fetchUserBalances() right before `} catch (error) {`
    content = content.replace('} catch (error) {\n    console.error("Error fetching balances:", error);', js_addition + '\n  } catch (error) {\n    console.error("Error fetching balances:", error);')

with open('frontend/index.html', 'w', encoding='utf-8') as f:
    f.write(content)
print("Updated index.html!")
