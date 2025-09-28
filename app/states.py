from aiogram.fsm.state import StatesGroup, State


class CheckoutState(StatesGroup):
    delivery_method = State()  # 'самовывоз' или 'доставка'
    delivery_date = State()    # выбор даты
    delivery_time = State()    # выбор времени
    full_name = State()
    phone = State()
    address = State()          # используется только если delivery_method == 'доставка'
    comment = State()


class PaymentState(StatesGroup):
    confirm = State()
