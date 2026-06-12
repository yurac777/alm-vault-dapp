import os
import requests
from dotenv import load_dotenv

load_dotenv()
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
USER_ID = os.getenv("TELEGRAM_USER_ID")

def send_message(text: str):
    if not BOT_TOKEN or not USER_ID:
        print("[TG] Ошибка: Не задан токен или ID пользователя Telegram в .env")
        return
        
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": USER_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
    except Exception as e:
        print(f"[TG] Ошибка отправки сообщения в Telegram: {e}")

def send_startup_message():
    text = "🚀 <b>Привет, Шеф!</b>\n\nКипер ALMVault успешно запущен в фоновом режиме на Base Mainnet! Готов печатать деньги. 💸"
    send_message(text)

def send_rebalance_message(tick_spacing: int, borrowed_usd: float, tx_hash: str):
    text = (
        "🔄 <b>Успешный Ребаланс (God-Tier)!</b>\n\n"
        f"🎯 Выбранный TickSpacing: <code>{tick_spacing}</code>\n"
        f"🏦 Взято в долг Aave: <code>${borrowed_usd:.2f}</code>\n"
        f"🔗 <a href='https://basescan.org/tx/{tx_hash}'>Транзакция в Basescan</a>"
    )
    send_message(text)

def send_pnl_report(net_worth: float, net_profit: float, gas_spent: float):
    text = (
        "📊 <b>Периодический Отчет PnL</b>\n\n"
        f"💰 Net Worth: <code>${net_worth:.4f}</code>\n"
        f"📈 Чистая Прибыль: <code>${net_profit:.4f}</code>\n"
        f"⛽️ Потрачено на газ: <code>${gas_spent:.4f}</code>\n\n"
        "Система работает штатно. 🛡️"
    )
    send_message(text)
    
def send_error_message(error_details: str):
    text = (
        "⚠️ <b>АЛАРМ: Ошибка Системы!</b>\n\n"
        f"<code>{error_details}</code>\n\n"
        "Пожалуйста, проверьте логи."
    )
    send_message(text)
