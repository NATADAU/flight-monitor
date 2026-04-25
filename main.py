import os
import requests
import json
import time
import schedule
import threading
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler

# ========== НАСТРОЙКИ ==========
TELEGRAM_TOKEN = "8661087329:AAH-iqUje-nzV8slPhF1XDekPXKB9uAJeSg"
CHAT_ID = "429893567"

ORIGIN = "MOW"
DESTINATION = "TBS"
DATE_THERE = "2025-06-20"
DATE_BACK = "2025-07-03"

PRICE_ALERT_THRESHOLD = 95000
PRICE_FILE = "last_price.json"
# ================================


def send_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"})


def load_last_price():
    try:
        with open(PRICE_FILE) as f:
            return json.load(f)
    except:
        return {}


def save_last_price(data):
    with open(PRICE_FILE, "w") as f:
        json.dump(data, f)


def get_price(passengers=1):
    url = "https://api.travelpayouts.com/v1/prices/cheap"
    params = {
        "origin": ORIGIN,
        "destination": DESTINATION,
        "depart_date": DATE_THERE,
        "return_date": DATE_BACK,
        "currency": "rub",
        "token": "ba31807a9b745a310fa9b25beddd5b6f"
    }
    try:
        r = requests.get(url, params=params, timeout=15)
        data = r.json()
        if data.get("data") and data["data"].get(DESTINATION):
            price_one = list(data["data"][DESTINATION].values())[0].get("price", 0)
            return price_one * passengers
    except Exception as e:
        print(f"Ошибка API: {e}")
    return None


def check_prices():
    now = datetime.now().strftime("%d.%m %H:%M")
    print(f"[{now}] Проверяю цены...")
    price_1 = get_price(1)
    price_2 = get_price(2)
    price_3 = get_price(3)
    if not price_1:
        send_telegram("Не удалось получить цены. Проверьте токен Aviasales.")
        return
    last = load_last_price()
    last_p3 = last.get("price_3", 0)
    msg_lines = [
        f"✈️ <b>Москва → Тбилиси</b>",
        f"🗓 Туда: 20 июня | Обратно: 3 июля",
        f"🕐 Проверено: {now}",
        f"",
        f"👤 1 пассажир:  <b>{price_1:,} ₽</b>",
        f"👥 2 пассажира: <b>{price_2:,} ₽</b> ({price_2//2:,} ₽/чел)",
        f"👨‍👩‍👧 3 пассажира: <b>{price_3:,} ₽</b> ({price_3//3:,} ₽/чел)",
    ]
    price_3x1 = price_1 * 3
    if price_3x1 < price_3:
        savings = price_3 - price_3x1
        msg_lines.append(f"")
        msg_lines.append(f"💡 Выгоднее 3 отдельных билета: {price_3x1:,} ₽")
        msg_lines.append(f"   Экономия: {savings:,} ₽")
    alerts = []
    if last_p3 and price_3 < last_p3:
        diff = last_p3 - price_3
        alerts.append(f"📉 Цена упала на {diff:,} ₽!")
    if price_3 < PRICE_ALERT_THRESHOLD:
        alerts.append(f"🔥 Цена ниже {PRICE_ALERT_THRESHOLD:,} ₽ — пора покупать!")
    if alerts:
        msg_lines = alerts + [""] + msg_lines
    send_telegram("\n".join(msg_lines))
    save_last_price({"price_1": price_1, "price_2": price_2, "price_3": price_3, "checked_at": now})
    print(f"Готово. Цена на 3: {price_3:,} ₽")


schedule.every(6).hours.do(check_prices)
schedule.every().day.at("09:00").do(check_prices)


class PingHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is running!")
    def log_message(self, format, *args):
        pass


def run_bot():
    print("Бот запущен!")
    send_telegram("Привет! Бот работает и начинает мониторинг цен.")
    check_prices()
    while True:
        schedule.run_pending()
        time.sleep(60)


threading.Thread(target=run_bot, daemon=True).start()
port = int(os.environ.get("PORT", 10000))
print(f"Сервер на порту {port}")
HTTPServer(("0.0.0.0", port), PingHandler).serve_forever()
