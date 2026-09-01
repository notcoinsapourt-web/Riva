from __future__ import annotations

from aiogram import Bot, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.core.callbacks import AdminCallback, ModuleCallback
from bot.core.emojis import (
    extract_custom_emoji_id,
    valid_custom_emoji_id,
    validate_custom_emoji,
    verify_custom_emoji_button_access,
)
from bot.core.formatting import h
from bot.core.states import (
    AdminModuleEditState,
    AdminPaymentMethodState,
    AdminSettingsEditState,
)
from bot.core.ui import button, edit_or_send, keyboard
from bot.database.models import User
from bot.modules.admin.common import protected_router
from bot.services.logs import ActivityLogService
from bot.services.settings import SettingsService

router = protected_router("settings")

EDITABLE_SETTINGS = {
    "shop_name": ("نام فروشگاه", "str"),
    "welcome_text": ("متن خوش‌آمد", "str"),
    "support_username": ("نام کاربری پشتیبانی", "str"),
    "referral_reward": ("پاداش دعوت", "int"),
    "maintenance_mode": ("حالت تعمیرات (true/false)", "bool"),
}

WALLET_SETTINGS = {
    "wallet_card_enabled": ("کارت‌به‌کارت فعال (true/false)", "bool"),
    "wallet_card_number": ("شماره کارت", "str"),
    "wallet_card_holder": ("نام صاحب کارت", "str"),
    "wallet_card_text": ("متن راهنمای کارت", "html"),
    "wallet_crypto_enabled": ("ارز دیجیتال فعال (true/false)", "bool"),
    "wallet_crypto_network": ("شبکه ارز دیجیتال", "str"),
    "wallet_crypto_address": ("آدرس ارز دیجیتال", "str"),
    "wallet_crypto_text": ("متن راهنمای ارز دیجیتال", "html"),
}


@router.callback_query(AdminCallback.filter((F.section == "settings") & (F.action == "list")))
async def settings_list(callback: CallbackQuery, session: AsyncSession) -> None:
    service = SettingsService(session)
    lines = []
    rows = []
    for index, (key, (label, _)) in enumerate(EDITABLE_SETTINGS.items(), start=1):
        value = await service.get(key)
        lines.append(f"{index}. <b>{h(label)}:</b> <code>{h(value or '—')}</code>")
        rows.append(
            [
                button(
                    f"✏️ {label}",
                    callback_data=AdminCallback(section="settings", action=f"edit_{index}").pack(),
                )
            ]
        )
    rows.append(
        [
            button(
                "💳 تنظیمات شارژ دستی",
                callback_data=AdminCallback(section="settings", action="wallet").pack(),
                style="success",
            )
        ]
    )
    rows.append(
        [
            button(
                "↩️ پنل مدیریت",
                callback_data=AdminCallback(section="dashboard", action="show").pack(),
            )
        ]
    )
    await edit_or_send(
        callback,
        "<b>⚙️ تنظیمات فروشگاه</b>\n\n" + "\n".join(lines),
        reply_markup=keyboard(*rows),
    )


@router.callback_query(AdminCallback.filter((F.section == "settings") & (F.action == "wallet")))
async def wallet_settings(callback: CallbackQuery, session: AsyncSession) -> None:
    service = SettingsService(session)
    card_number = await service.get("wallet_card_number")
    card_enabled = await service.get_bool("wallet_card_enabled")
    crypto_address = await service.get("wallet_crypto_address")
    crypto_enabled = await service.get_bool("wallet_crypto_enabled")
    await edit_or_send(
        callback,
        "<b>💳 روش‌های شارژ دستی</b>\n\n"
        f"کارت‌به‌کارت: <b>{'🟢 فعال' if card_enabled else '⚫ غیرفعال'}</b>\n"
        f"شماره کارت: <code>{h(card_number or 'تنظیم نشده')}</code>\n\n"
        f"ارز دیجیتال: <b>{'🟢 فعال' if crypto_enabled else '⚫ غیرفعال'}</b>\n"
        f"آدرس: <code>{h(crypto_address or 'تنظیم نشده')}</code>\n\n"
        "روش پرداخت را با دکمه‌های زیر اضافه یا ویرایش کنید.",
        reply_markup=keyboard(
            [
                button(
                    "➕ افزودن/ویرایش کارت",
                    callback_data=AdminCallback(section="settings", action="add_card").pack(),
                    style="success",
                ),
                button(
                    "فعال/غیرفعال کارت",
                    callback_data=AdminCallback(section="settings", action="toggle_card").pack(),
                ),
            ],
            [
                button(
                    "➕ افزودن/ویرایش ارز",
                    callback_data=AdminCallback(section="settings", action="add_crypto").pack(),
                    style="success",
                ),
                button(
                    "فعال/غیرفعال ارز",
                    callback_data=AdminCallback(section="settings", action="toggle_crypto").pack(),
                ),
            ],
            [
                button(
                    "↩️ تنظیمات",
                    callback_data=AdminCallback(section="settings", action="list").pack(),
                )
            ],
        ),
    )


@router.callback_query(
    AdminCallback.filter((F.section == "settings") & F.action.in_({"toggle_card", "toggle_crypto"}))
)
async def wallet_method_toggle(
    callback: CallbackQuery, callback_data: AdminCallback, session: AsyncSession
) -> None:
    method = callback_data.action.removeprefix("toggle_")
    settings = SettingsService(session)
    key = f"wallet_{method}_enabled"
    await settings.set(key, not await settings.get_bool(key), value_type="bool")
    await wallet_settings(callback, session)


@router.callback_query(AdminCallback.filter((F.section == "settings") & (F.action == "add_card")))
async def card_setup_start(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminPaymentMethodState.card_number)
    await edit_or_send(callback, "شماره کارت را فقط به صورت عدد ارسال کنید.")


@router.message(AdminPaymentMethodState.card_number, F.text)
async def card_number(message: Message, state: FSMContext) -> None:
    number = message.text.replace(" ", "").replace("-", "").strip()
    if not number.isdigit() or not 12 <= len(number) <= 24:
        await message.answer("شماره کارت معتبر نیست؛ دوباره ارسال کنید.")
        return
    await state.update_data(card_number=number)
    await state.set_state(AdminPaymentMethodState.card_holder)
    await message.answer("نام صاحب کارت را ارسال کنید.")


@router.message(AdminPaymentMethodState.card_holder, F.text)
async def card_holder(message: Message, state: FSMContext) -> None:
    await state.update_data(card_holder=message.text.strip())
    await state.set_state(AdminPaymentMethodState.card_text)
    await message.answer(
        "متن دلخواه راهنمای کارت‌به‌کارت را ارسال کنید. ایموجی Premium داخل متن حفظ می‌شود."
    )


@router.message(AdminPaymentMethodState.card_text, F.text)
async def card_text(message: Message, session: AsyncSession, state: FSMContext) -> None:
    data = await state.get_data()
    settings = SettingsService(session)
    await settings.set("wallet_card_number", data["card_number"])
    await settings.set("wallet_card_holder", data["card_holder"])
    await settings.set("wallet_card_text", message.html_text.strip())
    await settings.set("wallet_card_enabled", True, value_type="bool")
    await state.clear()
    await message.answer(
        "✅ کارت‌به‌کارت ذخیره و فعال شد.",
        reply_markup=keyboard(
            [
                button(
                    "روش‌های شارژ",
                    callback_data=AdminCallback(section="settings", action="wallet").pack(),
                )
            ]
        ),
    )


@router.callback_query(AdminCallback.filter((F.section == "settings") & (F.action == "add_crypto")))
async def crypto_setup_start(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminPaymentMethodState.crypto_network)
    await edit_or_send(callback, "نام شبکه ارز دیجیتال را ارسال کنید؛ مثال: <code>TRC20</code>")


@router.message(AdminPaymentMethodState.crypto_network, F.text)
async def crypto_network(message: Message, state: FSMContext) -> None:
    await state.update_data(crypto_network=message.text.strip())
    await state.set_state(AdminPaymentMethodState.crypto_address)
    await message.answer("آدرس کیف پول ارز دیجیتال را ارسال کنید.")


@router.message(AdminPaymentMethodState.crypto_address, F.text)
async def crypto_address(message: Message, state: FSMContext) -> None:
    address = message.text.strip()
    if len(address) < 10:
        await message.answer("آدرس واردشده معتبر نیست؛ دوباره ارسال کنید.")
        return
    await state.update_data(crypto_address=address)
    await state.set_state(AdminPaymentMethodState.crypto_text)
    await message.answer(
        "متن دلخواه راهنمای پرداخت ارزی را ارسال کنید. ایموجی Premium داخل متن حفظ می‌شود."
    )


@router.message(AdminPaymentMethodState.crypto_text, F.text)
async def crypto_text(message: Message, session: AsyncSession, state: FSMContext) -> None:
    data = await state.get_data()
    settings = SettingsService(session)
    await settings.set("wallet_crypto_network", data["crypto_network"])
    await settings.set("wallet_crypto_address", data["crypto_address"])
    await settings.set("wallet_crypto_text", message.html_text.strip())
    await settings.set("wallet_crypto_enabled", True, value_type="bool")
    await state.clear()
    await message.answer(
        "✅ پرداخت ارز دیجیتال ذخیره و فعال شد.",
        reply_markup=keyboard(
            [
                button(
                    "روش‌های شارژ",
                    callback_data=AdminCallback(section="settings", action="wallet").pack(),
                )
            ]
        ),
    )


@router.callback_query(
    AdminCallback.filter(
        (F.section == "settings") & (F.action.startswith("edit_") | F.action.startswith("wedit_"))
    )
)
async def setting_edit_start(
    callback: CallbackQuery, callback_data: AdminCallback, state: FSMContext
) -> None:
    wallet_edit = callback_data.action.startswith("wedit_")
    index = int(callback_data.action.removeprefix("wedit_" if wallet_edit else "edit_")) - 1
    try:
        source = WALLET_SETTINGS if wallet_edit else EDITABLE_SETTINGS
        key, (label, value_type) = list(source.items())[index]
    except (IndexError, ValueError):
        await callback.answer("تنظیم نامعتبر است.", show_alert=True)
        return
    await state.set_state(AdminSettingsEditState.value)
    await state.set_data({"setting_key": key, "value_type": value_type})
    await edit_or_send(callback, f"مقدار جدید «<b>{h(label)}</b>» را ارسال کنید.")


@router.message(AdminSettingsEditState.value, F.text)
async def setting_edit_value(
    message: Message,
    session: AsyncSession,
    db_user: User,
    state: FSMContext,
) -> None:
    data = await state.get_data()
    key = str(data["setting_key"])
    value_type = str(data["value_type"])
    value = (
        message.html_text.strip()
        if value_type == "html" or key == "welcome_text"
        else message.text.strip()
    )
    if value_type == "int" and not value.replace(",", "").isdigit():
        await message.answer("مقدار باید عدد باشد.")
        return
    if value_type == "bool" and value.lower() not in {"true", "false", "1", "0"}:
        await message.answer("فقط true یا false ارسال کنید.")
        return
    if value_type == "int":
        value = value.replace(",", "")
    await SettingsService(session).set(
        key, value, value_type="str" if value_type == "html" else value_type
    )
    await ActivityLogService(session).record(
        "setting.updated",
        actor_user_id=db_user.id,
        entity_type="setting",
        entity_id=key,
    )
    await state.clear()
    await message.answer(
        "✅ تنظیم ذخیره شد.",
        reply_markup=keyboard(
            [
                button(
                    "تنظیمات",
                    callback_data=AdminCallback(section="settings", action="list").pack(),
                )
            ]
        ),
    )


@router.callback_query(AdminCallback.filter((F.section == "modules") & (F.action == "list")))
async def modules_list(callback: CallbackQuery, session: AsyncSession) -> None:
    modules = await SettingsService(session).modules()
    rows = [
        [
            button(
                f"{'🟢' if item.is_enabled else '⚫'} {item.emoji or ''} {item.display_name}",
                callback_data=ModuleCallback(action="detail", name=item.name).pack(),
            )
        ]
        for item in modules
    ]
    rows.append(
        [
            button(
                "↩️ پنل مدیریت",
                callback_data=AdminCallback(section="dashboard", action="show").pack(),
            )
        ]
    )
    await edit_or_send(
        callback,
        "<b>🧩 مدیریت ماژول‌ها</b>\n\n"
        "فعال‌سازی، ترتیب منو، متن دکمه و Custom Emoji از این بخش قابل تغییر است.",
        reply_markup=keyboard(*rows),
    )


@router.callback_query(ModuleCallback.filter(F.action == "detail"))
async def module_detail(
    callback: CallbackQuery, callback_data: ModuleCallback, session: AsyncSession
) -> None:
    service = SettingsService(session)
    module = next(item for item in await service.modules() if item.name == callback_data.name)
    has_content = bool(await service.get(f"module_content_{module.name}"))
    await edit_or_send(
        callback,
        f"<b>🧩 {h(module.display_name)}</b>\n\n"
        f"نام فنی: <code>{h(module.name)}</code>\n"
        f"وضعیت: {'🟢 فعال' if module.is_enabled else '⚫ غیرفعال'}\n"
        f"دکمه: {h(module.menu_text or 'بدون دکمه')}\n"
        f"ایموجی: {h(module.emoji or '—')}\n"
        f"Custom Emoji ID: <code>{h(module.custom_emoji_id or '—')}</code>\n"
        f"متن بخش: {'✅ تنظیم شده' if has_content else 'پیش‌فرض'}\n"
        f"ترتیب: {module.sort_order}",
        reply_markup=keyboard(
            [
                button(
                    "غیرفعال‌سازی" if module.is_enabled else "فعال‌سازی",
                    callback_data=ModuleCallback(action="toggle", name=module.name).pack(),
                    style="danger" if module.is_enabled else "success",
                )
            ],
            [
                button(
                    "⬆️ بالاتر", callback_data=ModuleCallback(action="up", name=module.name).pack()
                ),
                button(
                    "⬇️ پایین‌تر",
                    callback_data=ModuleCallback(action="down", name=module.name).pack(),
                ),
            ],
            [
                button(
                    "✏️ متن دکمه",
                    callback_data=ModuleCallback(action="edit_text", name=module.name).pack(),
                ),
                button(
                    "😀 ایموجی",
                    callback_data=ModuleCallback(action="edit_emoji", name=module.name).pack(),
                ),
            ],
            [
                button(
                    "💠 Custom Emoji",
                    callback_data=ModuleCallback(action="edit_custom", name=module.name).pack(),
                ),
                button(
                    "📝 متن بخش",
                    callback_data=ModuleCallback(action="edit_content", name=module.name).pack(),
                ),
            ],
            [
                button(
                    "↩️ ماژول‌ها",
                    callback_data=AdminCallback(section="modules", action="list").pack(),
                )
            ],
        ),
    )


@router.callback_query(ModuleCallback.filter(F.action.in_({"toggle", "up", "down"})))
async def module_action(
    callback: CallbackQuery,
    callback_data: ModuleCallback,
    session: AsyncSession,
    db_user: User,
) -> None:
    service = SettingsService(session)
    if callback_data.action == "toggle":
        await service.toggle_module(callback_data.name)
    else:
        await service.move_module(callback_data.name, -1 if callback_data.action == "up" else 1)
    await ActivityLogService(session).record(
        f"module.{callback_data.action}",
        actor_user_id=db_user.id,
        entity_type="module",
        entity_id=callback_data.name,
    )
    await module_detail(callback, ModuleCallback(action="detail", name=callback_data.name), session)


@router.callback_query(ModuleCallback.filter(F.action.startswith("edit_")))
async def module_edit_start(
    callback: CallbackQuery, callback_data: ModuleCallback, state: FSMContext
) -> None:
    field = callback_data.action.removeprefix("edit_")
    if field not in {"text", "emoji", "custom", "content"}:
        return
    await state.set_state(AdminModuleEditState.value)
    await state.set_data({"module_name": callback_data.name, "field": field})
    prompt = {
        "text": "متن جدید دکمه را ارسال کنید.",
        "emoji": "ایموجی جدید را ارسال کنید؛ برای حذف عدد 0 را بفرستید.",
        "custom": (
            "ایموجی Premium متحرک را مستقیماً ارسال کنید یا Custom Emoji ID را بفرستید؛ "
            "برای حذف عدد 0 را ارسال کنید."
        ),
        "content": (
            "متن یا توضیح این بخش را ارسال کنید. ایموجی Premium داخل پیام نیز حفظ می‌شود؛ "
            "برای بازگرداندن متن پیش‌فرض عدد 0 را بفرستید."
        ),
    }[field]
    await edit_or_send(callback, prompt)


@router.message(AdminModuleEditState.value, F.text)
async def module_edit_value(
    message: Message,
    bot: Bot,
    session: AsyncSession,
    db_user: User,
    state: FSMContext,
) -> None:
    data = await state.get_data()
    name = str(data["module_name"])
    field = str(data["field"])
    value = message.text.strip()
    kwargs: dict[str, str | None]
    if field == "content":
        await SettingsService(session).set(
            f"module_content_{name}",
            "" if value == "0" else message.html_text.strip(),
            description=f"متن قابل تنظیم ماژول {name}",
        )
        kwargs = {}
    elif field == "text":
        kwargs = {"menu_text": value}
    elif field == "emoji":
        kwargs = {"emoji": "" if value == "0" else value}
    else:
        if value == "0":
            kwargs = {"custom_emoji_id": ""}
        else:
            emoji_id = extract_custom_emoji_id(message) or valid_custom_emoji_id(value)
            if emoji_id is None or not await validate_custom_emoji(bot, emoji_id):
                await message.answer(
                    "این ایموجی Premium معتبر نیست. خود ایموجی متحرک را ارسال کنید "
                    "یا یک ID عددی معتبر بفرستید."
                )
                return
            if not await verify_custom_emoji_button_access(bot, message.chat.id, emoji_id):
                await message.answer(
                    "⚠️ تلگرام این ایموجی را برای دکمه‌های این ربات نپذیرفت و تغییر "
                    "ذخیره نشد.\n\nمالک همین ربات در BotFather باید اشتراک Premium فعال "
                    "داشته باشد؛ یا برای ربات Additional Username از Fragment تهیه شده باشد."
                )
                return
            kwargs = {"custom_emoji_id": emoji_id}
    if kwargs:
        await SettingsService(session).update_module_ui(name, **kwargs)
    await ActivityLogService(session).record(
        "module.ui_updated",
        actor_user_id=db_user.id,
        entity_type="module",
        entity_id=name,
        details={"field": field},
    )
    await state.clear()
    await message.answer(
        "✅ ظاهر ماژول ذخیره شد.",
        reply_markup=keyboard(
            [
                button(
                    "مشاهده ماژول",
                    callback_data=ModuleCallback(action="detail", name=name).pack(),
                )
            ]
        ),
    )
