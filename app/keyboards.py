from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from .catalog import CATALOG, Cake


def main_menu_kb(user_id: int = None) -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.button(text="🍰 Каталог")
    
    # Показываем количество товаров в корзине
    if user_id is not None:
        try:
            from main import CARTS
            cart_items = sum(CARTS.get(user_id, {}).values())
            if cart_items > 0:
                button_text = f"🛒 Корзина ({cart_items})"
            else:
                button_text = "🛒 Корзина"
        except:
            button_text = "🛒 Корзина"
    else:
        button_text = "🛒 Корзина"
    
    builder.button(text=button_text)
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True)


def catalog_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for cake in CATALOG:
        builder.button(text=f"{cake.name} — {cake.price}₽", callback_data=f"cake:{cake.id}")
    builder.adjust(1)
    builder.button(text="⬅️ Назад", callback_data="back:main")
    return builder.as_markup()


def cake_card_kb(cake: Cake, user_id: int = None) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    
    # Показываем количество в корзине, если пользователь указан
    if user_id is not None:
        from .catalog import get_cake_by_id
        # Импортируем здесь, чтобы избежать циклических импортов
        current_qty = 0
        try:
            # Получаем количество из корзины пользователя
            from main import CARTS
            current_qty = CARTS.get(user_id, {}).get(cake.id, 0)
        except:
            pass
        
        if current_qty > 0:
            button_text = f"➕ В корзину ({current_qty})"
        else:
            button_text = "➕ В корзину"
    else:
        button_text = "➕ В корзину"
    
    builder.button(text=button_text, callback_data=f"add:{cake.id}")
    builder.button(text="⬅️ К каталогу", callback_data="back:catalog")
    builder.button(text="🛒 Открыть корзину", callback_data="open:cart")
    builder.adjust(1)
    return builder.as_markup()


def cart_kb(has_items: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if has_items:
        builder.button(text="🧹 Очистить", callback_data="cart:clear")
        builder.button(text="✅ Оформить заказ", callback_data="cart:checkout")
    builder.button(text="⬅️ К каталогу", callback_data="back:catalog")
    return builder.as_markup()


def order_confirmation_kb() -> InlineKeyboardMarkup:
    """Клавиатура подтверждения заказа с кнопкой оплаты"""
    builder = InlineKeyboardBuilder()
    builder.button(text="💳 Оплатить заказ", callback_data="payment:start")
    builder.button(text="⬅️ Назад к корзине", callback_data="back:cart")
    builder.adjust(1)
    return builder.as_markup()


def payment_confirm_kb() -> InlineKeyboardMarkup:
    """Клавиатура подтверждения оплаты"""
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Платёж выполнен", callback_data="payment:confirm")
    builder.button(text="❌ Отменить", callback_data="payment:cancel")
    builder.adjust(1)
    return builder.as_markup()
