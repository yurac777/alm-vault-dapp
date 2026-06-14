# Mathematical Foundation of ALMVault Protocol
*The First 100% On-Chain Synthetic Dollar on Base*

## 1. Mathematical Proof of Delta-Neutrality

The core objective of the ALMVault protocol is to maintain a delta-neutral position to issue the synthetic dollar, almUSD. 

Let the portfolio value $V_{\text{portfolio}}$ at time $t$ be defined as the sum of a concentrated liquidity position in Uniswap V3 ($V_{\text{uni}}$) and a short debt position in Aave V3 ($D_{\text{weth}}$):

$$V_{\text{portfolio}} = V_{\text{uni}} - D_{\text{weth}}$$

For an optimal delta-neutral state, the sensitivity of the portfolio to the underlying asset's price ($P$) must be zero:

$$\Delta_{\text{portfolio}} = \frac{\partial V_{\text{uni}}}{\partial P} - \frac{\partial D_{\text{weth}}}{\partial P} \approx 0$$

By carefully calibrating the Loan-to-Value (LTV) ratio on Aave and the bounds $[P_a, P_b]$ on Uniswap V3, the negative delta of the short position directly cancels out the positive delta of the LP position.

## 2. Leverage Optimization & Volatility Adaptation

To maximize capital efficiency without incurring liquidation risk, the protocol dynamically adjusts leverage based on market volatility, measured by the Average True Range (ATR).

The optimal Health Factor ($HF_{\text{target}}$) is defined as a function of the normalized ATR ($\sigma_{\text{ATR}}$):

$$HF_{\text{target}} = HF_{\text{min}} + \alpha \cdot \ln(1 + \beta \cdot \sigma_{\text{ATR}})$$

where $HF_{\text{min}}$ is the hard-coded safety threshold (e.g., 1.15), and $\alpha, \beta$ are risk-aversion parameters optimized via stochastic simulations.

## 3. Impermanent Loss (IL) Mitigation

Standard AMMs over $[0, \infty]$ suffer from significant Impermanent Loss (IL). By utilizing concentrated liquidity over a narrow range $[P_a, P_b]$ with continuous Auto-Sweep rebalancing, the effective IL is mitigated. 

The divergence loss is expressed as:

$$IL = 2 \frac{\sqrt{P_t}}{\sqrt{P_0} + P_t/\sqrt{P_0}} - 1$$

Through high-frequency rebalancing (where $\Delta t \to 0$), the accumulated fee generation $\int_0^T F_t dt$ significantly exceeds the instantaneous IL, yielding a strictly positive alpha.

## 4. Multi-Level On-Chain Referral Game Theory

To incentivize TVL growth, ALMVault employs a recursive geometric distribution of Performance and Deposit fees. Let the total fee generated be $F$. The distribution to referrer at level $k$ is given by:

$$R_k = F \cdot (1 - \gamma) \cdot \gamma^{k-1}$$

where $\gamma \in (0, 1)$ is the decay factor. The sum of the infinite series converges, ensuring economic sustainability and preventing sybil depletion of the treasury:

$$\sum_{k=1}^\infty R_k = F$$
