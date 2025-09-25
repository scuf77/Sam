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

    # Приветственный текст с цитатой и эффектом
    text = f"""
Привет, <b>{message.from_user.first_name}</b>! 👋 Рады видеть тебя в нашем боте 🥳

<blockquote>🕒 График работы:
• Пн – Вс: Круглосуточно</blockquote>

🛒 Сумма заказа от 500 ₽  
🚚 Доставка — 200 ₽ (бесплатно от 2500 ₽)

📚 Помощь: Если возникли вопросы, напиши <b>"Помощь"</b>, и я буду рад помочь!  

👇 Выберите вариант ниже и начнём:
"""

    # Отправляем с обязательным эффектом салюта (fireworks)
    try:
        await message.answer(
            text,
            reply_markup=main_menu_kb(message.from_user.id),
            message_effect_id="5046509860389126442"
        )
    except:
        # Падение эффекта — пробуем с эффектом из конфига (на случай отличий клиента)
        try:
            await message.answer(
                text,
                reply_markup=main_menu_kb(message.from_user.id),
                message_effect_id=WELCOME_EFFECT_ID
            )
        except:
            await message.answer(text, reply_markup=main_menu_kb(message.from_user.id))





async def show_catalog(message: Message | CallbackQuery):
    text = (
        "🍰 <b>Наш каталог тортов</b>\n\n"
        "✨ Выберите понравившийся торт и нажмите на него, чтобы увидеть фото и подробности!\n\n"
        "💡 Все торты готовятся из свежих ингредиентов по домашним рецептам."
    )
    if isinstance(message, Message):
        # Удаляем предыдущее сообщение (главное меню) при переходе в каталог
        try:
            await message.delete()
        except:
            pass
        # Отправляем новое сообщение с каталогом
        await message.answer(text, reply_markup=catalog_kb())
    else:
        # Удаляем предыдущее сообщение при переходе в каталог
        try:
            await message.message.delete()
        except:
            pass
        # Отправляем новое сообщение с каталогом
        await message.message.answer(text, reply_markup=catalog_kb())


async def open_cake_card(callback: CallbackQuery):
    cake_id = callback.data.split(":", 1)[1]
    cake = get_cake_by_id(cake_id)
    if not cake:
        await callback.answer("Товар не найден", show_alert=True)
        return
    
    # Формируем подпись к фото с полной информацией
    photo_caption = (
        f"🍰 <b>{cake.name}</b>\n\n"
        f"<blockquote>📝 {cake.description}\n\n"
        f"💰 Цена: {cake.price}₽</blockquote>\n\n"
        f"✨ Добавьте в корзину и оформите заказ!"
    )
    
    if callback.message:
        # Удаляем предыдущее сообщение (каталог) при открытии карточки торта
        try:
            await callback.message.delete()
        except:
            pass
        # Отправляем фото с полной информацией в подписи
        await callback.message.answer_photo(
            photo=cake.photo_url,
            caption=photo_caption,
            reply_markup=cake_card_kb(cake, callback.from_user.id)
        )
    await callback.answer()


async def add_to_cart(callback: CallbackQuery):
    cake_id = callback.data.split(":", 1)[1]
    cake = get_cake_by_id(cake_id)
    if not cake:
        await callback.answer("Товар не найден", show_alert=True)
        return
    
    user_id = callback.from_user.id
    current_qty = CARTS[user_id].get(cake_id, 0)
    new_qty = current_qty + 1
    CARTS[user_id][cake_id] = new_qty
    
    # Формируем сообщение с полной корзиной
    message_lines = [f"🎉 {cake.name} добавлен в корзину!"]
    message_lines.append("")
    message_lines.append("📦 Ваша корзина:")
    
    # Добавляем все товары из корзины
    for cart_cake_id, qty in CARTS[user_id].items():
        cart_cake = get_cake_by_id(cart_cake_id)
        if cart_cake:
            message_lines.append(f"• {cart_cake.name} × {qty} = {cart_cake.price * qty}₽")
    
    message_lines.append(f"💰 Итого: {cart_total(user_id)}₽")
    message_lines.append("")
    message_lines.append("💡 Откройте корзину, чтобы оформить заказ!")
    
    message = "\n".join(message_lines)
    await callback.answer(message, show_alert=True)
    
    # Обновляем кнопку, чтобы показать новое количество
    try:
        if callback.message:
            cake = get_cake_by_id(cake_id)
            if cake:
                # Обновляем клавиатуру для сообщения с фото
                await callback.message.edit_reply_markup(
                    reply_markup=cake_card_kb(cake, user_id)
                )
    except Exception as e:
        logger.error(f"Ошибка при обновлении кнопки: {e}")


async def open_cart(event: Message | CallbackQuery):
    user_id = event.from_user.id if isinstance(event, Message) else event.from_user.id
    text = cart_text(user_id)
    has_items = bool(CARTS[user_id])
    if isinstance(event, Message):
        # Удаляем предыдущее сообщение (главное меню) при открытии корзины
        try:
            await event.delete()
        except:
            pass
        # Отправляем новое сообщение с корзиной
        await event.answer(text, reply_markup=cart_kb(has_items))
    else:
        if event.message:
            # Удаляем предыдущее сообщение при открытии корзины
            try:
                await event.message.delete()
            except:
                pass
            # Отправляем новое сообщение с корзиной
            await event.message.answer(text, reply_markup=cart_kb(has_items))
        await event.answer()


async def clear_cart(callback: CallbackQuery):
    CARTS.pop(callback.from_user.id, None)
    await open_cart(callback)


async def start_checkout(callback: CallbackQuery, state: FSMContext):
    if not CARTS[callback.from_user.id]:
        await callback.answer("Корзина пуста", show_alert=True)
        return
    await state.set_state(CheckoutState.delivery_method)
    await callback.message.answer(
        "Выберите способ получения заказа:",
        reply_markup=delivery_method_kb()
    )
    await callback.answer()


async def choose_delivery_method(callback: CallbackQuery, state: FSMContext):
    method = callback.data.split(":", 1)[1]  # pickup | delivery
    await state.update_data(delivery_method=method)
    # Далее — выбор даты
    await state.set_state(CheckoutState.delivery_date)
    now_dt = datetime.now()
    dates = generate_available_dates(now_dt)
    if not dates:
        await callback.message.edit_text(
            "К сожалению, ближайшие слоты недоступны. Попробуйте позже.")
        await callback.answer()
        return
    await callback.message.edit_text(
        "Выберите дату получения заказа:", reply_markup=dates_kb(dates)
    )
    await callback.answer()


async def choose_date(callback: CallbackQuery, state: FSMContext):
    date_str = callback.data.split(":", 1)[1]
    await state.update_data(delivery_date=date_str)
    await state.set_state(CheckoutState.delivery_time)
    now_dt = datetime.now()
    slots = generate_time_slots_for_date(date_str, now_dt)
    if not slots:
        await callback.message.edit_text(
            "В выбранную дату нет доступных слотов. Выберите другую дату:",
            reply_markup=dates_kb(generate_available_dates(now_dt))
        )
        await callback.answer()
        return
    await callback.message.edit_text(
        f"Дата: {format_date_ru(date_str)}. Выберите время:",
        reply_markup=time_slots_kb(date_str, slots)
    )
    await callback.answer()


async def choose_time(callback: CallbackQuery, state: FSMContext):
    payload = callback.data.split(":", 1)[1]
    time_str, date_str = payload.split("|")
    await state.update_data(delivery_time=time_str, delivery_date=date_str)
    # Далее — ФИО
    await state.set_state(CheckoutState.full_name)
    await callback.message.edit_text("Введите ваше Имя:")
    await callback.answer()


async def ask_phone(message: Message, state: FSMContext):
    await state.update_data(full_name=message.text)
    await state.set_state(CheckoutState.phone)
    await message.answer("Введите ваш телефон (например, +7XXXXXXXXXX):")


async def ask_address(message: Message, state: FSMContext):
    await state.update_data(phone=message.text)
    data = await state.get_data()
    if data.get("delivery_method") == "delivery":
        await state.set_state(CheckoutState.address)
        await message.answer("Введите адрес доставки:")
    else:
        # Самовывоз — адрес не спрашиваем
        await state.set_state(CheckoutState.comment)
        await message.answer("Комментарий к заказу (или '-' если без комментария):")


async def ask_comment(message: Message, state: FSMContext):
    await state.update_data(address=message.text)
    await state.set_state(CheckoutState.comment)
    await message.answer("Комментарий к заказу (или '-' если без комментария):")


async def finish_checkout(message: Message, state: FSMContext):
    data = await state.get_data()
    comment = message.text if message.text != "-" else "без комментария"
    user_id = message.from_user.id

    # Сохраняем данные заказа в состоянии для последующей оплаты
    await state.update_data(
        full_name=data.get('full_name'),
        phone=data.get('phone'),
        address=data.get('address'),
        comment=comment
    )

    # Формируем сообщение подтверждения заказа
    user_order_lines = ["🆕 ЗАКАЗ ОФОРМЛЕН"]
    user_order_lines.append("")
    user_order_lines.append("📋 Содержимое:")
    
    # Добавляем содержимое корзины
    for cake_id, qty in CARTS[user_id].items():
        cake = get_cake_by_id(cake_id)
        if cake:
            user_order_lines.append(f"• {cake.name} × {qty} = {cake.price * qty}₽")
    
    user_order_lines.append(f"Итого: {cart_total(user_id)}₽")
    user_order_lines.append("")
    user_order_lines.append("👤 Данные:")
    user_order_lines.append(f"• Ваше имя: {data.get('full_name')}")
    user_order_lines.append(f"• Телефон: {data.get('phone')}")
    user_order_lines.append(f"• Способ: {format_method_ru(data.get('delivery_method'))}")
    user_order_lines.append(f"• Дата: {format_date_ru(data.get('delivery_date'))}")
    user_order_lines.append(f"• Время: {data.get('delivery_time')}")
    user_order_lines.append(f"• Адрес: {data.get('address', 'самовывоз')}")
    user_order_lines.append(f"• Комментарий: {comment}")
    user_order_lines.append("")
    user_order_lines.append("⏰ Время заказа: " + message.date.strftime("%d.%m.%Y %H:%M:%S"))
    user_order_lines.append("")
    user_order_lines.append("💳 Для завершения заказа нажмите кнопку 'Оплатить заказ' ниже.")
    
    user_order_text = "\n".join(user_order_lines)

    # Отправляем подтверждение заказа с кнопкой оплаты
    await message.answer(user_order_text, reply_markup=order_confirmation_kb())
    
    logger.info(f"Заказ пользователя {user_id} оформлен, ожидает оплаты")


async def back_handler(callback: CallbackQuery):
    action = callback.data.split(":", 1)[1]
    if action == "main":
        text = (
            "🏠 <b>Главное меню</b>\n\n"
            "🍰 <b>Каталог</b> - посмотреть наши торты\n"
            "🛒 <b>Корзина</b> - оформить заказ\n"
            "⭐ <b>Отзывы</b> - оставить отзыв или почитать отзывы\n\n"
            "⚡ <b>Быстрые команды:</b>\n"
            "• /start - перезапуск бота\n"
            "• /basket - открыть корзину\n"
            "• /feedback - оставить отзыв\n\n"
            "💡 Выберите действие с помощью кнопок ниже!"
        )
        # Удаляем старое сообщение
        try:
            await callback.message.delete()
        except:
            pass
        # Отправляем новое сообщение с главным меню
        await callback.message.answer(text, reply_markup=main_menu_kb(callback.from_user.id))
    elif action == "catalog":
        await show_catalog(callback)
    elif action == "cart":
        await open_cart(callback)
    elif action == "delivery":
        await callback.message.edit_text(
            "Выберите способ получения заказа:", reply_markup=delivery_method_kb()
        )
    elif action == "dates":
        now_dt = datetime.now()
        await callback.message.edit_text(
            "Выберите дату получения заказа:", reply_markup=dates_kb(generate_available_dates(now_dt))
        )
    await callback.answer()


# ==================== ОПЛАТА НА КАРТУ ====================

async def start_payment(callback: CallbackQuery, state: FSMContext):
    """Показывает реквизиты для оплаты"""
    user_id = callback.from_user.id
    
    # Проверяем, что у пользователя есть заказ
    if not CARTS[user_id]:
        await callback.answer("Корзина пуста", show_alert=True)
        return
    
    # Получаем данные заказа
    order_data = await state.get_data()
    
    payment_text = f"""💳 ОПЛАТА ЗАКАЗА

💰 Сумма к оплате: {cart_total(user_id)}₽

📱 Номер карты для оплаты:
{CARD_NUMBER}

📋 Содержимое заказа:
{chr(10).join([f"• {get_cake_by_id(cake_id).name} × {qty} = {get_cake_by_id(cake_id).price * qty}₽" for cake_id, qty in CARTS[user_id].items()])}

👤 Данные заказа:
• Имя: {order_data.get('full_name')}
• Телефон: {order_data.get('phone')}
• Способ: {format_method_ru(order_data.get('delivery_method'))}
• Дата: {format_date_ru(order_data.get('delivery_date'))}
• Время: {order_data.get('delivery_time')}
• Адрес: {order_data.get('address', 'самовывоз')}
• Комментарий: {order_data.get('comment', 'без комментария')}

⚠️ После перевода денег нажмите кнопку "Платёж выполнен" ниже."""
    
    await state.set_state(PaymentState.confirm)
    await callback.message.edit_text(payment_text, reply_markup=payment_confirm_kb())
    await callback.answer()


async def process_payment_confirmation(callback: CallbackQuery, state: FSMContext):
    """Обрабатывает подтверждение оплаты"""
    user_id = callback.from_user.id
    order_data = await state.get_data()
    
    # Формируем сообщение об успешной оплате
    success_text = f"""✅ ПЛАТЁЖ ПОДТВЕРЖДЁН!

💳 Заказ оплачен на сумму: {cart_total(user_id)}₽
📱 Карта получателя: {CARD_NUMBER}

🆕 ЗАКАЗ ПРИНЯТ И ОПЛАЧЕН

📋 Содержимое заказа:
{chr(10).join([f"• {get_cake_by_id(cake_id).name} × {qty} = {get_cake_by_id(cake_id).price * qty}₽" for cake_id, qty in CARTS[user_id].items()])}

👤 Данные:
• Имя: {order_data.get('full_name')}
• Телефон: {order_data.get('phone')}
• Способ: {format_method_ru(order_data.get('delivery_method'))}
• Дата: {format_date_ru(order_data.get('delivery_date'))}
• Время: {order_data.get('delivery_time')}
• Адрес: {order_data.get('address', 'самовывоз')}
• Комментарий: {order_data.get('comment', 'без комментария')}

⏰ Время заказа: {callback.message.date.strftime("%d.%m.%Y %H:%M:%S")}

✅ Ваш заказ принят и оплачен! Менеджер свяжется с вами в ближайшее время."""
    
    # Отправляем уведомление менеджеру
    if MANAGER_CHAT_ID:
        manager_text = f"""💳 ПЛАТЁЖ ПОДТВЕРЖДЁН!

🆕 НОВЫЙ ЗАКАЗ
==============================

📋 Содержимое заказа:
{chr(10).join([f"• {get_cake_by_id(cake_id).name} × {qty} = {get_cake_by_id(cake_id).price * qty}₽" for cake_id, qty in CARTS[user_id].items()])}
Итого: {cart_total(user_id)}₽

👤 Данные клиента:
• Имя: {order_data.get('full_name')}
• Телефон: {order_data.get('phone')}
• Способ: {order_data.get('delivery_method')}
• Дата: {order_data.get('delivery_date')}
• Время: {order_data.get('delivery_time')}
• Адрес: {order_data.get('address', 'самовывоз')}
• Комментарий: {order_data.get('comment', 'без комментария')}

👨‍💻 Информация о пользователе:
• Username: @{callback.from_user.username or 'без никнейма'}
• ID: {callback.from_user.id}
• Имя: {callback.from_user.first_name or 'не указано'}
• Фамилия: {callback.from_user.last_name or 'не указана'}

⏰ Время заказа: {callback.message.date.strftime("%d.%m.%Y %H:%M:%S")}
==============================

💰 СТАТУС: ПЛАТЁЖ ПОДТВЕРЖДЁН КЛИЕНТОМ
⚠️ ТРЕБУЕТСЯ ПРОВЕРКА ПЛАТЕЖА"""
        
        try:
            await callback.bot.send_message(MANAGER_CHAT_ID, manager_text)
            logger.info(f"Заказ с подтверждением платежа отправлен менеджеру {MANAGER_CHAT_ID}")
        except Exception as e:
            logger.error(f"Ошибка при отправке заказа: {e}")
    
    # Очищаем корзину и состояние
    CARTS.pop(user_id, None)
    await state.clear()
    
    # Отправляем подтверждение пользователю
    await callback.message.edit_text(success_text)
    
    # Отправляем стикер после оплаты
    try:
        await callback.message.answer_sticker("CAACAgIAAxkBAAEPUX1ou_UPzrbLgxAAAc6qcrkC74GQj70AAgEdAAJdjShIYFtNtyx1ELs2BA")
    except:
        pass
    
    # Отправляем сообщение с просьбой оставить отзыв
    review_text = """⭐ <b>Пожалуйста, оставьте отзыв о нашем заказе!</b>

Ваше мнение очень важно для нас и поможет другим клиентам сделать правильный выбор.

📝 <b>Оставить отзыв можно здесь:</b>
https://t.me/qwert1moment/2

💬 <b>Есть вопросы?</b> Общайтесь с другими клиентами:
https://t.me/+zdtovQ9SvMxjZTUy

🙏 Спасибо за ваш заказ!"""
    
    await callback.message.answer(review_text, disable_web_page_preview=True)
    await callback.answer()
    
    logger.info(f"Заказ пользователя {user_id} с подтверждением платежа")


async def cancel_payment(callback: CallbackQuery, state: FSMContext):
    """Отменяет процесс оплаты"""
    await state.clear()
    await callback.message.edit_text("❌ Оплата отменена. Заказ сохранен в корзине.")
    await callback.answer()


async def back_to_cart(callback: CallbackQuery, state: FSMContext):
    """Возвращает к корзине"""
    await state.clear()
    await open_cart(callback)


async def show_reviews(message: Message):
    """Показывает информацию об отзывах"""
    text = """⭐ <b>Отзывы наших клиентов</b>

Мы очень ценим мнение каждого клиента! Здесь вы можете:

📝 <b>Оставить свой отзыв</b> — поделитесь впечатлениями о заказе
⭐ <b>Почитать отзывы</b> — узнайте, что говорят другие клиенты

👇 <b>Нажмите на ссылку ниже, чтобы перейти к отзывам:</b>

https://t.me/qwert1moment/2

💬 <b>Есть вопросы?</b> Общайтесь с другими клиентами в нашем чате:
https://t.me/+zdtovQ9SvMxjZTUy

🙏 Спасибо за то, что выбираете нас!"""
    
    await message.answer(text, disable_web_page_preview=True)


async def cmd_basket(message: Message):
    """Команда /basket - открывает корзину"""
    await open_cart(message)


async def cmd_feedback(message: Message):
    """Команда /feedback - показывает информацию об отзывах"""
    await show_reviews(message)


async def main():
    logger.info("Запуск кулинарного бота...")
    
    # Проверяем критически важные настройки
    if not MANAGER_CHAT_ID:
        logger.error("❌ КРИТИЧЕСКАЯ ОШИБКА: MANAGER_CHAT_ID не настроен!")
        logger.error("❌ Заказы НЕ будут отправляться в чат менеджера!")
        logger.error("❌ Создайте файл .env с правильным MANAGER_CHAT_ID")
        logger.error("❌ Или установите переменную окружения MANAGER_CHAT_ID")
    else:
        logger.info(f"✅ MANAGER_CHAT_ID настроен: {MANAGER_CHAT_ID}")
    
    bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()

    # Команды
    dp.message.register(cmd_start, CommandStart())
    dp.message.register(cmd_basket, Command("basket"))
    dp.message.register(cmd_feedback, Command("feedback"))

    # Главное меню
    dp.message.register(show_catalog, F.text == "🍰 Каталог")
    dp.message.register(open_cart, F.text.startswith("🛒 Корзина"))
    dp.message.register(show_reviews, F.text == "⭐ Отзывы")

    # Каталог и карточки
    dp.callback_query.register(open_cake_card, F.data.startswith("cake:"))
    dp.callback_query.register(add_to_cart, F.data.startswith("add:"))

    # Корзина
    dp.callback_query.register(open_cart, F.data == "open:cart")
    dp.callback_query.register(clear_cart, F.data == "cart:clear")

    # Оформление
    dp.callback_query.register(start_checkout, F.data == "cart:checkout")
    dp.callback_query.register(choose_delivery_method, F.data.startswith("delivery:"))
    dp.callback_query.register(choose_date, F.data.startswith("date:"))
    dp.callback_query.register(choose_time, F.data.startswith("time:"))
    dp.message.register(ask_phone, CheckoutState.full_name)
    dp.message.register(ask_address, CheckoutState.phone)
    dp.message.register(ask_comment, CheckoutState.address)
    dp.message.register(finish_checkout, CheckoutState.comment)

    # Навигация
    dp.callback_query.register(back_handler, F.data.startswith("back:"))
    
    # Платежи
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
