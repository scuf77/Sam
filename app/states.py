from aiogram.fsm.state import StatesGroup, State


class CheckoutState(StatesGroup):
    full_name = State()
    phone = State()
    address = State()
    comment = State()


class PaymentState(StatesGroup):
    confirm = State()
