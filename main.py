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
PRICE_FILE = "prices.json"
CHECK_TIMES = ["09:00", "13:00", "20:00"]

AVIASALES_1 = "https://www.aviasales.ru/search/MOW2206TBS03071"
AVIASALES_3 = "https://www.aviasales.ru/search/MOW2206TBS03073"
YANDEX_1 = "https://travel.yandex.ru/avia/search/result/?adult_seats=1&children_seats=0&fromId=c213&infant_seats=0&klass=economy&oneway=2&return_date=2026-07-03&toId=c10277&when=2026-06-20"
YANDEX_3 = "https://travel.yandex.ru/avia/search/result/?adult_seats=3&children_seats=0&fromId=c213&infant_seats=0&klass=economy&oneway=2&return_date=2026-07-03&toId=c10277&when=2026-06-20"
# ================================


def send_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, json={
            "chat_id": CHAT_ID,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True
        }, timeout=10)
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


def send_reminder():
    now = datetime.now().strftime("%H:%M")
    if now < "12:00":
        greet = "🌅 Доброе утро!"
    elif now < "18:00":
        greet = "☀️ Добрый день!"
    else:
        greet = "🌙 Добрый вечер!"

    prices = load_prices()
    last_info = ""
    if prices:
        last = prices[-1]
        last_info = f"\nПоследняя цена: <b>{last['price']:,} ₽</b> ({last['date']})"

    msg = f"""{greet} Время проверить цены на билеты!

✈️ <b>Москва → Тбилиси</b>
🗓 20 июня → 3 июля, 3 пассажира{last_info}

🔍 Открыть поиск:
- <a href="{AVIASALES_1}">Aviasales — 1 пассажир</a> (× 3)
- <a href="{AVIASALES_3}">Aviasales — 3 пассажира</a>
- <a href="{YANDEX_1}">Яндекс — 1 пассажир</a> (× 3)
- <a href="{YANDEX_3}">Яндекс — 3 пассажира</a>

💬 Напишите найденную цену цифрами, например: <b>95000</b>"""

    send_telegram(msg)
    print(f"[{now}] Напоминание отправлено")


def handle_updates():
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

                if text == "/start":
                    send_telegram(
                        "👋 Привет! Я слежу за ценами на билеты <b>Москва → Тбилиси</b>.\n\n"
                        "Буду присылать напоминания в <b>9:00, 13:00 и 20:00</b> со ссылками на поиск.\n\n"
                        "Когда найдёте цену — просто напишите число, например: <b>95000</b>\n\n"
                        "Команды:\n"
                        "/check — проверить цены прямо сейчас\n"
                        "/history — история записанных цен"
                    )

                elif text == "/check":
                    send_reminder()

                elif text == "/history":
                    prices = load_prices()
                    if not prices:
                        send_telegram("Пока нет записей.\n\nПроверьте цену и напишите мне число!")
                    else:
                        lines = ["📊 <b>История цен:</b>\n"]
                        for p in prices[-10:]:
                            lines.append(f"• {p['date']}: {p['price']:,} ₽")
                        if len(prices) >= 2:
                            diff = prices[-1]['price'] - prices[0]['price']
                            sign = "📉 -" if diff < 0 else "📈 +"
                            lines.append(f"\nС первой проверки: {sign}{abs(diff):,} ₽")
                        send_telegram("\n".join(lines))

                elif text.replace(" ", "").replace(",", "").isdigit():
                    price = int(text.replace(" ", "").replace(",", ""))
                    if 10000 < price < 500000:
                        prices = save_price(price)
                        if len(prices) >= 2:
                            prev = prices[-2]["price"]
                            diff = price - prev
                            if diff < 0:
                                trend = f"📉 Подешевело на <b>{abs(diff):,} ₽</b>!"
                            elif diff > 0:
                                trend = f"📈 Подорожало на <b>{diff:,} ₽</b>."
                            else:
                                trend = "➡️ Цена не изменилась."
                            reply = f"✅ Записала: <b>{price:,} ₽</b>\n{trend}\n\nВсего записей: {len(prices)}"
                        else:
                            reply = f"✅ Записала стартовую цену: <b>{price:,} ₽</b>\nБуду сравнивать со следующей проверкой!"
                        send_telegram(reply)
                    else:
                        send_telegram("⚠️ Введите полную сумму в рублях, например: <b>95000</b>")

        except Exception as e:
            print(f"Ошибка updates: {e}")
            time.sleep(5)


def schedule_loop():
    sent = set()
    while True:
        now = datetime.now().strftime("%H:%M")
        day = datetime.now().strftime("%d")
        key = f"{day}-{now}"
        if now in CHECK_TIMES and key not in sent:
            send_reminder()
            sent.add(key)
            if len(sent) > 20:
                sent = {key}
        time.sleep(30)


class PingHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is running!")
    def log_message(self, format, *args):
        pass


print("Бот запущен!")
send_telegram("✅ Бот запущен!\n\nБуду присылать ссылки в 9:00, 13:00 и 20:00.\nНапишите /check чтобы проверить прямо сейчас.")

threading.Thread(target=handle_updates, daemon=True).start()
threading.Thread(target=schedule_loop, daemon=True).start()

port = int(os.environ.get("PORT", 10000))
print(f"Сервер на порту {port}")
HTTPServer(("0.0.0.0", port), PingHandler).serve_forever()
