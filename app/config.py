import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")

# ID чата для заказов (ваша частная беседа)
MANAGER_CHAT_ID_RAW = os.getenv("MANAGER_CHAT_ID")
MANAGER_CHAT_ID = int(MANAGER_CHAT_ID_RAW) if MANAGER_CHAT_ID_RAW not in (None, "") else None

# Настройки уведомлений
ENABLE_ORDER_NOTIFICATIONS = os.getenv("ENABLE_ORDER_NOTIFICATIONS", "true").lower() == "true"
ORDER_NOTIFICATION_TEMPLATE = os.getenv("ORDER_NOTIFICATION_TEMPLATE", "default")

# Настройки оплаты на карту
CARD_NUMBER = "2202 2080 9748 5529"  # Номер карты для оплаты
ENABLE_CARD_PAYMENTS = True  # Всегда включено

if not BOT_TOKEN:
    raise RuntimeError("Не задан токен бота. Укажите BOT_TOKEN в .env или переменных окружения.")

# Логируем настройки при запуске
print(f"Конфигурация загружена:")
print(f"- BOT_TOKEN: {'*' * len(BOT_TOKEN) if BOT_TOKEN else 'НЕ ЗАДАН'}")
print(f"- MANAGER_CHAT_ID: {MANAGER_CHAT_ID or 'НЕ ЗАДАН'}")
print(f"- Уведомления о заказах: {'ВКЛЮЧЕНЫ' if ENABLE_ORDER_NOTIFICATIONS else 'ОТКЛЮЧЕНЫ'}")
print(f"- Оплата на карту: {'ВКЛЮЧЕНА' if ENABLE_CARD_PAYMENTS else 'ОТКЛЮЧЕНА'}")
print(f"- Номер карты: {CARD_NUMBER}")
