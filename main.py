import asyncio
import logging
import time
from typing import Dict, DefaultDict, List
from collections import defaultdict
from datetime import datetime, timedelta, date, time as dt_time

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery, Sticker
from aiogram.fsm.context import FSMContext
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from app.config import BOT_TOKEN, MANAGER_CHAT_ID, CARD_NUMBER
from app.catalog import CATALOG, get_cake_by_id
from app.keyboards import (
    main_menu_kb, catalog_kb, cake_card_kb, cart_kb,
    order_confirmation_kb, payment_confirm_kb,
    delivery_method_kb, dates_kb, time_slots_kb
)
from app.states import CheckoutState, PaymentState
from app.config import (
    BAKER_SCHEDULE_START_DATE, WORK_CYCLE_ON_DAYS, WORK_CYCLE_OFF_DAYS,
    WORKING_HOURS_START, WORKING_HOURS_END, SLOT_MINUTES,
    MIN_LEAD_HOURS, MAX_DAYS_AHEAD
)
from app.config import WELCOME_EFFECT_ID

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Память корзин пользователей: user_id -> {cake_id: qty}
CARTS: DefaultDict[int, Dict[str, int]] = defaultdict(dict)


def cart_total(user_id: int) -> int:
    total = 0
    for cake_id, qty in CARTS[user_id].items():
        cake = get_cake_by_id(cake_id)
        if cake:
            total += cake.price * qty
    return total


def cart_text(user_id: int) -> str:
    if not CARTS[user_id]:
        return "Ваша корзина пуста."
    lines = ["Ваша корзина:"]
    for cake_id, qty in CARTS[user_id].items():
        cake = get_cake_by_id(cake_id)
        if cake:
            lines.append(f"• {cake.name} × {qty} = {cake.price * qty}₽")
    lines.append(f"Итого: {cart_total(user_id)}₽")
    return "\n".join(lines)


# ==================== ВСПОМОГАТЕЛЬНОЕ: РАСПИСАНИЕ И СЛОТЫ ====================

def _parse_schedule_start() -> date:
    try:
        y, m, d = [int(x) for x in BAKER_SCHEDULE_START_DATE.split("-")]
        return date(y, m, d)
    except Exception:
        return date.today()


def is_working_day(day: date) -> bool:
    base = _parse_schedule_start()
    cycle = WORK_CYCLE_ON_DAYS + WORK_CYCLE_OFF_DAYS
    if cycle <= 0:
        return True
    delta = (day - base).days
    mod = delta % cycle
    return 0 <= mod < WORK_CYCLE_ON_DAYS


def generate_available_dates(now_dt: datetime) -> List[str]:
    dates: List[str] = []
    for i in range(MAX_DAYS_AHEAD + 1):
        d = (now_dt.date() + timedelta(days=i))
        if not is_working_day(d):
            continue
        # Проверка минимального времени: если день текущий, должен быть хотя бы MIN_LEAD_HOURS
        if i == 0:
            if now_dt + timedelta(hours=MIN_LEAD_HOURS) < datetime.combine(d, dt_time(hour=WORKING_HOURS_END)):
                dates.append(d.isoformat())
        else:
            dates.append(d.isoformat())
    return dates


def generate_time_slots_for_date(target_date_iso: str, now_dt: datetime) -> List[str]:
    try:
        y, m, d = [int(x) for x in target_date_iso.split("-")]
        target_date = date(y, m, d)
    except Exception:
        return []
    if not is_working_day(target_date):
        return []
    slots: List[str] = []
    start_dt = datetime.combine(target_date, dt_time(hour=WORKING_HOURS_START))
    end_dt = datetime.combine(target_date, dt_time(hour=WORKING_HOURS_END))
    step = timedelta(minutes=SLOT_MINUTES)
    cursor = start_dt
    min_dt = now_dt + timedelta(hours=MIN_LEAD_HOURS)
    while cursor + step <= end_dt:
        if cursor >= min_dt:
            slots.append(cursor.strftime("%H:%M"))
        cursor += step
    return slots


def format_date_ru(date_iso: str) -> str:
    try:
        y, m, d = [int(x) for x in date_iso.split("-")]
        return f"{d:02d}.{m:02d}.{y}"
    except Exception:
        return date_iso


def format_method_ru(method: str | None) -> str:
    if not method:
        return ""
    return "самовывоз" if method == "pickup" else "доставка"


async def cmd_start(message: Message, state: FSMContext):
    logger.info(f"Команда /start от пользователя {message.from_user.id}")
    await state.clear()
    
    # Отправляем приветственный стикер
    try:
        await message.answer_sticker(
            "CAACAgIAAxkBAAEPUWpou_GAnCdMdk0HEhGmGzuw1PBipgACBQADwDZPE_lqX5qCa011NgQ"
        )
    except:
        pass

    # Приветственный текст с цитатой и эмодзи 🎉, который автоматически вызывает эффект
    text = f"""
Привет, <b>{message.from_user.first_name}</b>! 👋 Рады видеть тебя в нашем боте 🥳🎉

<blockquote>🕒 График работы:
• Пн – Вс: Круглосуточно</blockquote>

🛒 Сумма заказа от 500 ₽  
🚚 Доставка — 200 ₽ (бесплатно от 2500 ₽)

📚 Помощь: Если возникли вопросы, напиши <b>"Помощь"</b>, и я буду рад помочь!  

👇 Выберите вариант ниже и начнём:
"""

    # Отправляем сообщение (эффект 🎉 сработает автоматически)
    await message.answer(
        text,
        reply_markup=main_menu_kb(message.from_user.id)
    )


# ... весь остальной код остаётся без изменений ...

async def main():
    logger.info("Запуск кулинарного бота...")
    
    if not MANAGER_CHAT_ID:
        logger.error("❌ КРИТИЧЕСКАЯ ОШИБКА: MANAGER_CHAT_ID не настроен!")
    else:
        logger.info(f"✅ MANAGER_CHAT_ID настроен: {MANAGER_CHAT_ID}")
    
    bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()

    dp.message.register(cmd_start, CommandStart())
    dp.message.register(cmd_basket, Command("basket"))
    dp.message.register(cmd_feedback, Command("feedback"))

    dp.message.register(show_catalog, F.text == "🍰 Каталог")
    dp.message.register(open_cart, F.text.startswith("🛒 Корзина"))
    dp.message.register(show_reviews, F.text == "⭐ Отзывы")

    dp.callback_query.register(open_cake_card, F.data.startswith("cake:"))
    dp.callback_query.register(add_to_cart, F.data.startswith("add:"))
    dp.callback_query.register(open_cart, F.data == "open:cart")
    dp.callback_query.register(clear_cart, F.data == "cart:clear")
    dp.callback_query.register(start_checkout, F.data == "cart:checkout")
    dp.callback_query.register(choose_delivery_method, F.data.startswith("delivery:"))
    dp.callback_query.register(choose_date, F.data.startswith("date:"))
    dp.callback_query.register(choose_time, F.data.startswith("time:"))
    dp.message.register(ask_phone, CheckoutState.full_name)
    dp.message.register(ask_address, CheckoutState.phone)
    dp.message.register(ask_comment, CheckoutState.address)
    dp.message.register(finish_checkout, CheckoutState.comment)
    dp.callback_query.register(back_handler, F.data.startswith("back:"))
    dp.callback_query.register(start_payment, F.data == "payment:start")
    dp.callback_query.register(process_payment_confirmation, F.data == "payment:confirm")
    dp.callback_query.register(cancel_payment, F.data == "payment:cancel")
    dp.callback_query.register(back_to_cart, F.data == "back:cart")

    logger.info("Бот успешно запущен и готов к работе!")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        logger.info("Инициализация кулинарного бота...")
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"Ошибка при запуске бота: {e}")
        raise
