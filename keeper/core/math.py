import math
from decimal import Decimal, getcontext

# Устанавливаем достаточную точность для вычислений с токенами
getcontext().prec = 50

# ==========================================
# AAVE MATH
# ==========================================

def calculate_health_factor(collateral_usd: Decimal, debt_usd: Decimal, liquidation_threshold: Decimal) -> Decimal:
    """
    Рассчитывает Health Factor для позиции в Aave.
    HF < 1.0 означает, что позиция может быть ликвидирована.
    """
    if debt_usd == Decimal("0"):
        return Decimal('inf')
    return (collateral_usd * liquidation_threshold) / debt_usd


# ==========================================
# UNISWAP V3/V4 TICK & PRICE MATH
# ==========================================

def tick_to_price(tick: int, decimals0: int, decimals1: int) -> Decimal:
    """
    Рассчитывает человекочитаемую цену token0 в единицах token1 из тика.
    """
    raw_price = Decimal('1.0001') ** tick
    adjusted_price = raw_price * (Decimal(10) ** (decimals0 - decimals1))
    return adjusted_price


def price_to_tick(price: Decimal, decimals0: int, decimals1: int) -> int:
    """
    Рассчитывает тик на основе человекочитаемой цены.
    """
    raw_price = price / (Decimal(10) ** (decimals0 - decimals1))
    tick = math.log(float(raw_price)) / math.log(1.0001)
    return round(tick)


def get_closest_usable_tick(tick: int, tick_spacing: int, lower: bool) -> int:
    """
    Выравнивает тик до ближайшего значения, кратного tick_spacing.
    lower=True — округление вниз (для нижней границы).
    lower=False — округление вверх (для верхней).
    """
    rounded = (tick // tick_spacing) * tick_spacing
    if not lower and tick % tick_spacing != 0:
        rounded += tick_spacing
    return rounded


def tick_to_sqrt_ratio_x96(tick: int) -> int:
    """
    Конвертирует тик в sqrtPriceX96 — формат Uniswap V3/V4 Q64.96 fixed-point.
    Формула: sqrt(1.0001^tick) * 2^96
    """
    sqrt_price = math.sqrt(1.0001 ** tick)
    return int(sqrt_price * (2 ** 96))


def get_liquidity_for_amounts(
    sqrt_price_x96: int,
    tick_lower: int,
    tick_upper: int,
    amount0: int,
    amount1: int
) -> int:
    """
    Рассчитывает максимально возможную ликвидность L по стандартным формулам
    Uniswap V3 Whitepaper (§6.29-6.30).

    В паре WETH/USDC (token0=WETH, token1=USDC):
      - amount0 = кол-во WETH в wei (18 decimals)
      - amount1 = кол-во USDC в минимальных единицах (6 decimals)

    :param sqrt_price_x96:  Текущая цена пула в Q64.96.
    :param tick_lower:      Нижняя граница диапазона.
    :param tick_upper:      Верхняя граница диапазона.
    :param amount0:         Кол-во token0 (wei).
    :param amount1:         Кол-во token1 (минимальные единицы).
    :return:                Ликвидность L (целое число).
    """
    Q96 = 2 ** 96

    sqrt_ratio_a = tick_to_sqrt_ratio_x96(tick_lower)
    sqrt_ratio_b = tick_to_sqrt_ratio_x96(tick_upper)

    # Гарантируем порядок a < b
    if sqrt_ratio_a > sqrt_ratio_b:
        sqrt_ratio_a, sqrt_ratio_b = sqrt_ratio_b, sqrt_ratio_a

    if sqrt_price_x96 <= sqrt_ratio_a:
        # Цена НИЖЕ диапазона: вся ликвидность в token0
        # L = amount0 * (sqrtA * sqrtB) / (sqrtB - sqrtA)
        numerator = amount0 * sqrt_ratio_a * sqrt_ratio_b // Q96
        denominator = sqrt_ratio_b - sqrt_ratio_a
        liquidity = numerator // denominator

    elif sqrt_price_x96 >= sqrt_ratio_b:
        # Цена ВЫШЕ диапазона: вся ликвидность в token1
        # L = amount1 * Q96 / (sqrtB - sqrtA)
        liquidity = amount1 * Q96 // (sqrt_ratio_b - sqrt_ratio_a)

    else:
        # Цена ВНУТРИ диапазона: минимум из двух ограничений
        # L0 = amount0 * sqrtPrice * sqrtB / (sqrtB - sqrtPrice)
        num0 = amount0 * sqrt_price_x96 * sqrt_ratio_b // Q96
        den0 = sqrt_ratio_b - sqrt_price_x96
        l0 = num0 // den0

        # L1 = amount1 * Q96 / (sqrtPrice - sqrtA)
        l1 = amount1 * Q96 // (sqrt_price_x96 - sqrt_ratio_a)

        liquidity = min(l0, l1)

    return int(liquidity)


# ==========================================
# LEVERAGE MATH
# ==========================================

def calculate_borrow_amount(initial_capital_usd: Decimal, target_ltv: Decimal) -> Decimal:
    """
    Рассчитывает целевой долг на основе стартового капитала и желаемого LTV.
    """
    return initial_capital_usd * target_ltv

def get_amounts_for_liquidity(sqrt_price_x96: int, tick_lower: int, tick_upper: int, liquidity: int) -> tuple:
    """
    Вычисляет количество token0 и token1, заблокированных в позиции V3.
    Возвращает (amount0, amount1).
    """
    Q96 = 2 ** 96
    sqrt_ratio_a = tick_to_sqrt_ratio_x96(tick_lower)
    sqrt_ratio_b = tick_to_sqrt_ratio_x96(tick_upper)
    
    if sqrt_ratio_a > sqrt_ratio_b:
        sqrt_ratio_a, sqrt_ratio_b = sqrt_ratio_b, sqrt_ratio_a

    if sqrt_price_x96 <= sqrt_ratio_a:
        amount0 = liquidity * Q96 * (sqrt_ratio_b - sqrt_ratio_a) // (sqrt_ratio_a * sqrt_ratio_b)
        amount1 = 0
    elif sqrt_price_x96 >= sqrt_ratio_b:
        amount0 = 0
        amount1 = liquidity * (sqrt_ratio_b - sqrt_ratio_a) // Q96
    else:
        amount0 = liquidity * Q96 * (sqrt_ratio_b - sqrt_price_x96) // (sqrt_price_x96 * sqrt_ratio_b)
        amount1 = liquidity * (sqrt_price_x96 - sqrt_ratio_a) // Q96
        
    return amount0, amount1
