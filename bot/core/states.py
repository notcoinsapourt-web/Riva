from aiogram.fsm.state import State, StatesGroup


class CheckoutState(StatesGroup):
    waiting_for_quantity = State()
    waiting_for_details = State()
    waiting_for_coupon = State()
    confirming = State()


class TicketCreateState(StatesGroup):
    subject = State()
    message = State()


class AdminCategoryState(StatesGroup):
    name = State()
    description = State()
    emoji = State()


class AdminProductState(StatesGroup):
    category = State()
    name = State()
    description = State()
    price = State()
    input_prompt = State()
    emoji = State()
    photo = State()


class AdminEditTextState(StatesGroup):
    value = State()


class AdminCouponState(StatesGroup):
    code = State()
    coupon_type = State()
    value = State()
    max_uses = State()
    expires_at = State()


class AdminBroadcastState(StatesGroup):
    content = State()
    confirm = State()


class AdminMessageState(StatesGroup):
    text = State()


class AdminWalletState(StatesGroup):
    user_id = State()
    amount = State()
    reason = State()


class AdminUserSearchState(StatesGroup):
    query = State()


class AdminCatalogEditState(StatesGroup):
    value = State()


class AdminSettingsEditState(StatesGroup):
    value = State()


class AdminModuleEditState(StatesGroup):
    value = State()


class AdminAccessState(StatesGroup):
    telegram_id = State()
