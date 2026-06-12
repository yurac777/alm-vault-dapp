import requests
import re
import statistics
from openai import OpenAI
import httpx
import logging

class AIOracle:
    def __init__(self, base_url='http://127.0.0.1:8045/v1', api_key='sk-58f78301dfd44875947d82d0a1fdf046', model='gemini-pro-agent'):
        self.client = OpenAI(
            base_url=base_url,
            api_key=api_key,
            http_client=httpx.Client(timeout=30.0)
        )
        self.model = model
    
    def get_eth_24h_klines(self):
        """Получает последние 24 часовые свечи ETH/USDT с Binance и рассчитывает ATR/SMA."""
        try:
            url = 'https://api.binance.com/api/v3/klines?symbol=ETHUSDT&interval=1h&limit=24'
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            summary = []
            close_prices = []
            true_ranges = []
            prev_close = None
            
            for kline in data:
                open_price = float(kline[1])
                high_price = float(kline[2])
                low_price = float(kline[3])
                close_price = float(kline[4])
                
                summary.append(f"O:{open_price:.2f} H:{high_price:.2f} L:{low_price:.2f} C:{close_price:.2f}")
                close_prices.append(close_price)
                
                # ATR Calculation (True Range)
                if prev_close is not None:
                    tr = max(high_price - low_price, abs(high_price - prev_close), abs(low_price - prev_close))
                    true_ranges.append(tr)
                prev_close = close_price
                
            atr = sum(true_ranges) / len(true_ranges) if true_ranges else 0.0
            sma = sum(close_prices) / len(close_prices) if close_prices else 0.0
            
            return "\n".join(summary), close_prices, atr, sma
        except Exception as e:
            logging.error(f"Ошибка получения данных Binance: {e}")
            return "Нет данных", [], 0.0, 0.0

    def get_directional_ticks(self, current_price: float) -> tuple:
        klines_text, close_prices, atr, sma = self.get_eth_24h_klines()
        
        if len(close_prices) == 0:
            return "neutral", 200, 200
            
        current_close = close_prices[-1]
        
        # Determine trend based on SMA
        if current_close > sma * 1.002:
            trend = "bullish"
            tick_down_delta = 200
            tick_up_delta = 600
        elif current_close < sma * 0.998:
            trend = "bearish"
            tick_down_delta = 600
            tick_up_delta = 200
        else:
            trend = "neutral"
            tick_down_delta = 200
            tick_up_delta = 200
            
        return trend, tick_down_delta, tick_up_delta
