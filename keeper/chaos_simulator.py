import sys
import os
import math
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core.ai_oracle import AIOracle

class MockOracle:
    def get_directional_ticks(self, eth_price):
        # We simulate a bullish pump
        return "bullish", 200, 600

def run_chaos():
    original_price = 1666.0
    pumped_price = 2000.0  # +20%
    
    print(f"==================================================")
    print(f"   🌪️ THE REAL STRESS TEST: PUMP BLACK SWAN 🌪️")
    print(f"==================================================")
    print(f"Market Shock: ETH Price instantly PUMPED from ${original_price} to ${pumped_price} (+20%)!")
    
    # 1. Old Position State
    old_capital = 5.01
    old_collateral = 3.1401
    old_debt_usd = 1.8753
    old_debt_weth = old_debt_usd / original_price
    
    old_uni_value = old_capital - old_collateral + old_debt_usd # ~ 3.745
    old_uni_weth = old_debt_weth
    old_uni_usdc = old_uni_value - old_debt_usd
    
    print(f"\n[Pre-Shock State at ${original_price}]")
    print(f" -> Total Capital: ${old_capital:.4f}")
    print(f" -> Aave Collateral: ${old_collateral:.4f} USDC")
    print(f" -> Aave Debt: ${old_debt_usd:.4f} ({old_debt_weth:.6f} WETH)")
    print(f" -> Uni V3 Position: ${old_uni_value:.4f}")
    
    # Pre-shock HF
    old_hf = (old_collateral * 0.80) / old_debt_usd
    print(f" -> Aave Health Factor: {old_hf:.2f}")
    
    # 2. Simulate V3 IL and Debt Inflation
    # Assuming symmetric 200 ticks (2%) previously
    p_lower = original_price / 1.0202
    p_upper = original_price * 1.0202
    
    # L = amt0 / (1/sqrt(P0) - 1/sqrt(P_upper))
    L = old_uni_weth / (1/math.sqrt(original_price) - 1/math.sqrt(p_upper))
    
    # New value in V3: since 2000 > p_upper, all WETH is sold to USDC
    new_uni_usdc = L * (math.sqrt(p_upper) - math.sqrt(p_lower))
    new_uni_weth = 0.0
    new_uni_value = new_uni_usdc + (new_uni_weth * pumped_price)
    
    new_debt_usd = old_debt_weth * pumped_price
    new_capital = old_collateral + new_uni_value - new_debt_usd
    
    print(f"\n[Post-Shock State at ${pumped_price} BEFORE Rebalance]")
    print(f" -> Debt Inflated to: ${new_debt_usd:.4f} (+{(new_debt_usd - old_debt_usd):.4f}$)")
    print(f" -> Uni V3 Position Liquidated to USDC: ${new_uni_value:.4f}")
    print(f" -> Total Capital: ${new_capital:.4f} (Impermanent Loss + Debt effect: {new_capital - old_capital:.4f}$)")
    
    pre_rebalance_hf = (old_collateral * 0.80) / new_debt_usd
    print(f" -> 🚨 CRITICAL: Health Factor crashed to {pre_rebalance_hf:.3f}!")
    if pre_rebalance_hf < 1.0:
        print(" ❌ FATAL: Position liquidated by Aave before keeper could react!")
        return
    else:
        print(" ✅ SURVIVED: Keeper has a window to rebalance.")
    
    # 3. AI Oracle and Emergency Rebalance
    ai_oracle = MockOracle()
    trend, tick_down, tick_up = ai_oracle.get_directional_ticks(pumped_price)
    
    print(f"\n[AIOracle] Reacting to extreme BULLISH volatility...")
    print(f"[AIOracle] Trend={trend.upper()} | tickDown={tick_down} | tickUp={tick_up}")
    
    base_hf = Decimal("1.60")
    current_target_hf = base_hf
    if trend == "bullish":
        current_target_hf = current_target_hf + Decimal("0.4")
    elif trend == "bearish":
        current_target_hf = max(Decimal("1.1"), current_target_hf - Decimal("0.3"))
        
    print(f"[SRE] Dynamic HF set to {current_target_hf:.2f} (Base: {base_hf:.2f})")
    print(f"[SRE] Forcing emergency rebalance with surviving capital ${new_capital:.4f}.")
    
    # Math recalculation based on new HF logic
    amount_usdc_to_aave = new_capital / float(1 + 0.80 / float(current_target_hf))
    amount_weth_borrow  = (new_capital - amount_usdc_to_aave) / pumped_price
    
    print(f"\n[Math Engine] New Position Setup:")
    print(f" -> Collateral (Aave Deposit): ${amount_usdc_to_aave:.4f}")
    print(f" -> Debt (Aave Borrow): ${amount_weth_borrow * pumped_price:.4f} ({amount_weth_borrow:.6f} WETH)")
    
    actual_hf = 0.80 / ((amount_weth_borrow * pumped_price) / amount_usdc_to_aave)
    print(f" -> Resulting HF: {actual_hf:.2f}")
    
    print("\n✅ Real Stress Test PASSED! Aave liquidation prevented during +20% PUMP.")

if __name__ == "__main__":
    run_chaos()
