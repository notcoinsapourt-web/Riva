from aiogram import Router

from bot.modules.admin import (
    admins,
    broadcast,
    catalog,
    channels,
    coupons,
    dashboard,
    deposits,
    messages,
    orders,
    report_emojis,
    settings,
    tickets,
    users,
    web_store,
    website_control,
)

router = Router(name="admin")
router.include_routers(
    dashboard.router,
    deposits.router,
    channels.router,
    admins.router,
    orders.router,
    web_store.router,
    website_control.router,
    catalog.router,
    users.router,
    coupons.router,
    broadcast.router,
    settings.router,
    report_emojis.router,
    tickets.router,
    messages.router,
)
