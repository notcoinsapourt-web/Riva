from aiogram.filters.callback_data import CallbackData


class NavCallback(CallbackData, prefix="n"):
    action: str


class CatalogCallback(CallbackData, prefix="c"):
    action: str
    entity_id: int = 0
    page: int = 0


class OrderCallback(CallbackData, prefix="o"):
    action: str
    order_id: int = 0
    page: int = 0


class TicketCallback(CallbackData, prefix="t"):
    action: str
    ticket_id: int = 0
    page: int = 0


class AdminCallback(CallbackData, prefix="a"):
    section: str
    action: str
    entity_id: int = 0
    page: int = 0


class ModuleCallback(CallbackData, prefix="m"):
    action: str
    name: str


class CouponCallback(CallbackData, prefix="coup"):
    action: str
    coupon_id: int = 0


class DepositCallback(CallbackData, prefix="dep"):
    action: str
    request_id: int = 0
    method: str = ""


class ChannelCallback(CallbackData, prefix="ch"):
    action: str
    channel_id: int = 0
