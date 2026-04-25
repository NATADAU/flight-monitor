import os
import requests
import json
import time
import threading
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler

# ========== НАСТРОЙКИ ==========
TELEGRAM_TOKEN = "8661087329:AAH-iqUje-nzV8slPhF1XDekPXKB9uAJeSg"
CHAT_ID = "429893567"

DATE_THERE = "20250620"
DATE_BACK = "20250703"
PASSENGERS = 3

PRICE_FILE = "prices.json"
CHECK_TIMES = ["09:00", "13:00", "20:00"]
# ================================

AVIASALES_URL = f"https://www.aviasales.ru/search/MOW{DATE_THERE}TBS{DATE_BACK}{PASSENGERS}"
YANDEX_URL = f"https://travel.yandex.ru/avia/search/?fromId=c213&toId=c10313&when=2025-06-20&return=2025-07-03&adults={PASSENGERS}"
SKYSCANNER_URL = f"https://www.skyscanner.ru/transport/flights/mosc/tbla/250620/250703/?adults={PASSENGERS}"


def send_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True}, timeout=10)
    except Exception as e:
        print(f"Ошибка Telegram: {e}")


def load_prices():
    try:
        with open(PRICE_FILE) as f:
            return json.load(f)
    except:
        return []


def save_price(price):
    prices = load_prices()
    now = datetime.now().strftime("%d.%m %H:%M")
    prices.append({"price": price, "date": now})
    with open(PRICE_FILE, "w") as f:
        json.dump(prices, f)
    return prices


def get_last_price():
    prices = load_prices()
    if len(prices) >= 2:
        return prices[-2]["price"]
    return None


def send_check_reminder():
    now = datetime.now().strftime("%H:%M")
    greet = "🌅 Доброе утро!" if now < "12:00" else ("☀️ Добрый день!" if now < "18:00" else "🌙 Добрый вечер!")
    
    prices = load_prices()
    last = prices[-1] if prices else None
    last_info = f"\nПоследняя записанная цена: <b>{last['price']:,} ₽</b> ({last['date']})" if last else ""

    msg = f"""{greet} Время проверить цены на билеты!

✈️ <b>Москва → Тбилиси</b>
🗓 20 июня → 3 июля, {PASSENGERS} пассажира
{last_info}

🔍 Проверить сейчас:
• <a href="{AVIASALES_URL}">Aviasales</a>
• <a href="{YANDEX_URL}">Яндекс Путешествия</a>
• <a href="{SKYSCANNER_URL}">Skyscanner</a>

💬 Напишите мне цену которую нашли (только цифры, например: <b>95000</b>)"""

    send_telegram(msg)
    print(f"[{now}] Напоминание отправлено")


def handle_updates():
    """Получаем ответы пользователя и сохраняем цены"""
    offset = 0
    while True:
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates"
            r = requests.get(url, params={"offset": offset, "timeout": 30}, timeout=35)
            data = r.json()
            
            for update in data.get("result", []):
                offset = update["update_id"] + 1
                msg = update.get("message", {})
                text = msg.get("text", "").strip()
                chat_id = str(msg.get("chat", {}).get("id", ""))
                
                if chat_id != CHAT_ID:
                    continue
                    
                # Если пользователь прислал число — это цена
                if text.replace(" ", "").replace(",", "").isdigit():
                    price = int(text.replace(" ", "").replace(",", ""))
                    if 10000 < price < 500000:
                        prices = save_price(price)
                        last = get_last_price()
                        
                        if last:
                            diff = price - last
                            if diff < 0:
                                trend = f"📉 Подешевело на {abs(diff):,} ₽ с прошлой проверки!"
                            elif diff > 0:
                                trend = f"📈 Подорожало на {diff:,} ₽ с прошлой проверки."
                            else:
                                trend = "➡️ Цена не изменилась."
                            reply = f"✅ Записала: <b>{price:,} ₽</b>\n{trend}\n\nВсего записей: {len(prices)}"
                        else:
                            reply = f"✅ Записала стартовую цену: <b>{price:,} ₽</b>\nБуду сравнивать со следующей проверкой!"
                        
                        send_telegram(reply)
                    else:
                        send_telegram("Цена выглядит странно — введите полную сумму за 3 пассажира в рублях, например: 95000")
                        
                elif text == "/start":
                    send_telegram("Привет! Я слежу за ценами на билеты Москва → Тбилиси.\n\nПрисылаю напоминания в 9:00, 13:00 и 20:00.\nКогда проверите цену — просто напишите мне число, например: 95000")
                    
                elif text == "/history":
                    prices = load_prices()
                    if not prices:
                        send_telegram("Пока нет записей. Проверьте цену и напишите мне число!")
                    else:
                        lines = ["📊 <b>История цен:</b>\n"]
                        for p in prices[-10:]:
                            lines.append(f"• {p['date']}: {p['price']:,} ₽")
                        if len(prices) >= 2:
                            diff = prices[-1]['price'] - prices[0]['price']
                            lines.append(f"\nИзменение с первой проверки: {'📉 -' if diff < 0 else '📈 +'}{abs(diff):,} ₽")
                        send_telegram("\n".join(lines))

        except Exception as e:
            print(f"Ошибка получения обновлений: {e}")
            time.sleep(5)


def schedule_loop():
    """Проверяем расписание каждую минуту"""
    sent_today = set()
    while True:
        now = datetime.now().strftime("%H:%M")
        day = datetime.now().strftime("%d")
        key = f"{day}-{now}"
        
        if now in CHECK_TIMES and key not in sent_today:
            send_check_reminder()
            sent_today.add(key)
            # Очищаем старые записи
            if len(sent_today) > 10:
                sent_today = {key}
        
        time.sleep(30)


class PingHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is running!")
    def log_message(self, format, *args):
        pass


# Запуск
print("Бот запущен!")
send_telegram("✅ Бот запущен! Буду присылать напоминания в 9:00, 13:00 и 20:00.\n\nКоманды:\n/history — история цен\n\nПросто напишите число чтобы записать цену, например: 95000")

threading.Thread(target=handle_updates, daemon=True).start()
threading.Thread(target=schedule_loop, daemon=True).start()

port = int(os.environ.get("PORT", 10000))
print(f"Сервер на порту {port}")
HTTPServer(("0.0.0.0", port), PingHandler).serve_forever()
