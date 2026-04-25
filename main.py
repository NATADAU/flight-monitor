import requests
import json
import time
import schedule
from datetime import datetime

# ========== НАСТРОЙКИ ==========
TELEGRAM_TOKEN = "8661087329:AAH-iqUje-nzV8slPhF1XDekPXKB9uAJeSg"   # вставьте ваш токен от BotFather
CHAT_ID = "429893567"

# Маршрут
ORIGIN = "MOW"
DESTINATION = "TBS"
DATE_THERE = "2025-06-20"
DATE_BACK = "2025-07-03"

# Порог — присылать уведомление если цена на 3 человек НИЖЕ этой суммы
PRICE_ALERT_THRESHOLD = 95000  # ₽ на троих туда-обратно

# Файл для хранения последней известной цены
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
    """Получаем цену через Aviasales API (публичный поиск)"""
    url = "https://api.travelpayouts.com/v1/prices/cheap"
    params = {
        "origin": ORIGIN,
        "destination": DESTINATION,
        "depart_date": DATE_THERE,
        "return_date": DATE_BACK,
        "currency": "rub",
        "token": "ba31807a9b745a310fa9b25beddd5b6f"  # бесплатный токен на aviasales.ru/developers
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
        print("Не удалось получить цены")
        return

    last = load_last_price()
    last_p3 = last.get("price_3", 0)

    # Формируем сообщение
    msg_lines = [
        f"✈️ <b>Москва → Тбилиси</b>",
        f"🗓 Туда: 20 июня | Обратно: 3 июля",
        f"🕐 Проверено: {now}",
        f"",
        f"👤 1 пассажир:  <b>{price_1:,} ₽</b>",
        f"👥 2 пассажира: <b>{price_2:,} ₽</b> ({price_2//2:,} ₽/чел)",
        f"👨‍👩‍👧 3 пассажира: <b>{price_3:,} ₽</b> ({price_3//3:,} ₽/чел)",
    ]

    # Выгоднее — вместе или по одному?
    price_3x1 = price_1 * 3
    if price_3x1 < price_3:
        savings = price_3 - price_3x1
        msg_lines.append(f"")
        msg_lines.append(f"💡 Выгоднее 3 отдельных билета: {price_3x1:,} ₽")
        msg_lines.append(f"   Экономия: {savings:,} ₽")

    # Уведомление о снижении цены
    alerts = []
    if last_p3 and price_3 < last_p3:
        diff = last_p3 - price_3
        alerts.append(f"📉 Цена упала на {diff:,} ₽ по сравнению с прошлой проверкой!")
    if price_3 < PRICE_ALERT_THRESHOLD:
        alerts.append(f"🔥 Цена ниже вашего порога {PRICE_ALERT_THRESHOLD:,} ₽ — самое время покупать!")

    if alerts:
        msg_lines = alerts + [""] + msg_lines

    send_telegram("\n".join(msg_lines))

    save_last_price({
        "price_1": price_1,
        "price_2": price_2,
        "price_3": price_3,
        "checked_at": now
    })
    print(f"Готово. Цена на 3: {price_3:,} ₽")


# Запуск по расписанию — каждые 6 часов
schedule.every(6).hours.do(check_prices)
schedule.every().day.at("09:00").do(check_prices)  # всегда в 9 утра

print("Бот запущен! Первая проверка через несколько секунд...")
check_prices()  # сразу при старте

while True:
    schedule.run_pending()
    time.sleep(60)
