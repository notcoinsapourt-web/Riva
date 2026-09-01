from __future__ import annotations

from aiogram import Bot, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.core.callbacks import AdminCallback
from bot.core.emojis import (
    extract_custom_emoji_id,
    valid_custom_emoji_id,
    validate_custom_emoji,
    verify_custom_emoji_button_access,
)
from bot.core.formatting import compact_text, h, money
from bot.core.states import (
    AdminCatalogEditState,
    AdminCategoryState,
    AdminProductState,
)
from bot.core.ui import button, edit_or_send, keyboard
from bot.database.models import User
from bot.modules.admin.common import protected_router
from bot.services.catalog import CatalogService
from bot.services.logs import ActivityLogService

router = protected_router("catalog")


@router.callback_query(AdminCallback.filter((F.section == "products") & (F.action == "list")))
async def products_list(callback: CallbackQuery, session: AsyncSession) -> None:
    products = await CatalogService(session).products(active_only=False)
    rows = [
        [
            button(
                f"{'🟢' if item.is_active else '⚫'} {compact_text(item.name, 24)}"
                f" • {money(item.price)}",
                callback_data=AdminCallback(
                    section="products", action="detail", entity_id=item.id
                ).pack(),
            )
        ]
        for item in products[:30]
    ]
    rows.extend(
        [
            [
                button(
                    "➕ افزودن محصول",
                    callback_data=AdminCallback(section="products", action="add").pack(),
                    style="success",
                )
            ],
            [
                button(
                    "↩️ پنل مدیریت",
                    callback_data=AdminCallback(section="dashboard", action="show").pack(),
                )
            ],
        ]
    )
    await edit_or_send(
        callback,
        "<b>💎 مدیریت محصولات</b>\n\n"
        + ("محصول موردنظر را انتخاب کنید." if products else "هنوز محصولی ثبت نشده است."),
        reply_markup=keyboard(*rows),
    )


@router.callback_query(AdminCallback.filter((F.section == "products") & (F.action == "detail")))
async def product_detail(
    callback: CallbackQuery, callback_data: AdminCallback, session: AsyncSession
) -> None:
    product = await CatalogService(session).product(callback_data.entity_id, active_only=False)
    rows = [
        [
            button(
                "⏸ غیرفعال‌سازی" if product.is_active else "▶️ فعال‌سازی",
                callback_data=AdminCallback(
                    section="products", action="toggle", entity_id=product.id
                ).pack(),
                style="danger" if product.is_active else "success",
            )
        ],
        [
            button(
                "✏️ نام",
                callback_data=AdminCallback(
                    section="products", action="edit_name", entity_id=product.id
                ).pack(),
            ),
            button(
                "💰 قیمت",
                callback_data=AdminCallback(
                    section="products", action="edit_price", entity_id=product.id
                ).pack(),
            ),
        ],
        [
            button(
                "📝 توضیحات",
                callback_data=AdminCallback(
                    section="products", action="edit_description", entity_id=product.id
                ).pack(),
            ),
            button(
                "📋 ورودی سفارش",
                callback_data=AdminCallback(
                    section="products", action="edit_input_prompt", entity_id=product.id
                ).pack(),
            ),
        ],
        [
            button(
                "😀 ایموجی",
                callback_data=AdminCallback(
                    section="products", action="edit_emoji", entity_id=product.id
                ).pack(),
            ),
            button(
                "🖼 عکس",
                callback_data=AdminCallback(
                    section="products", action="edit_photo", entity_id=product.id
                ).pack(),
            ),
        ],
        [
            button(
                "💠 Custom Emoji",
                callback_data=AdminCallback(
                    section="products",
                    action="edit_custom_emoji_id",
                    entity_id=product.id,
                ).pack(),
            )
        ],
        [
            button(
                "🗑 حذف محصول",
                callback_data=AdminCallback(
                    section="products", action="delete", entity_id=product.id
                ).pack(),
                style="danger",
            )
        ],
        [
            button(
                "↩️ محصولات",
                callback_data=AdminCallback(section="products", action="list").pack(),
            )
        ],
    ]
    await edit_or_send(
        callback,
        f"<b>{h(product.emoji)} {h(product.name)}</b>\n\n"
        f"دسته: {h(product.category.name)}\n"
        f"قیمت: <b>{money(product.price)}</b>\n"
        f"وضعیت: {'🟢 فعال' if product.is_active else '⚫ غیرفعال'}\n"
        f"عکس: {'✅' if product.photo_file_id else '—'}\n\n"
        f"{h(product.description)}\n\n"
        f"<b>درخواست اطلاعات:</b> {h(product.input_prompt)}",
        reply_markup=keyboard(*rows),
    )


@router.callback_query(AdminCallback.filter((F.section == "products") & (F.action == "toggle")))
async def product_toggle(
    callback: CallbackQuery,
    callback_data: AdminCallback,
    session: AsyncSession,
    db_user: User,
) -> None:
    product = await CatalogService(session).product(callback_data.entity_id, active_only=False)
    enabled = not product.is_active
    await CatalogService(session).update_product(product.id, is_active=enabled)
    await ActivityLogService(session).record(
        "product.toggled",
        actor_user_id=db_user.id,
        entity_type="product",
        entity_id=product.id,
        details={"enabled": enabled},
    )
    await product_detail(
        callback,
        AdminCallback(section="products", action="detail", entity_id=product.id),
        session,
    )


@router.callback_query(AdminCallback.filter((F.section == "products") & (F.action == "delete")))
async def product_delete_confirm(
    callback: CallbackQuery, callback_data: AdminCallback, session: AsyncSession
) -> None:
    product = await CatalogService(session).product(callback_data.entity_id, active_only=False)
    await edit_or_send(
        callback,
        f"<b>حذف «{h(product.name)}»؟</b>\n\n"
        "این محصول از فروشگاه حذف می‌شود؛ سوابق سفارش‌ها حفظ خواهند شد.",
        reply_markup=keyboard(
            [
                button(
                    "بله، حذف شود",
                    callback_data=AdminCallback(
                        section="products", action="delete_confirm", entity_id=product.id
                    ).pack(),
                    style="danger",
                )
            ],
            [
                button(
                    "انصراف",
                    callback_data=AdminCallback(
                        section="products", action="detail", entity_id=product.id
                    ).pack(),
                )
            ],
        ),
    )


@router.callback_query(
    AdminCallback.filter((F.section == "products") & (F.action == "delete_confirm"))
)
async def product_delete(
    callback: CallbackQuery,
    callback_data: AdminCallback,
    session: AsyncSession,
    db_user: User,
) -> None:
    await CatalogService(session).delete_product(callback_data.entity_id)
    await ActivityLogService(session).record(
        "product.deleted",
        actor_user_id=db_user.id,
        entity_type="product",
        entity_id=callback_data.entity_id,
    )
    await products_list(callback, session)


@router.callback_query(
    AdminCallback.filter((F.section == "products") & F.action.startswith("edit_"))
)
async def product_edit_prompt(
    callback: CallbackQuery, callback_data: AdminCallback, state: FSMContext
) -> None:
    field = callback_data.action.removeprefix("edit_")
    prompts = {
        "name": "نام جدید را ارسال کنید.",
        "price": "قیمت جدید را به تومان و فقط با عدد ارسال کنید.",
        "description": "توضیحات جدید را ارسال کنید.",
        "input_prompt": "متن درخواست اطلاعات از مشتری را ارسال کنید.",
        "emoji": "ایموجی جدید را ارسال کنید.",
        "custom_emoji_id": (
            "ایموجی Premium متحرک را مستقیماً ارسال کنید یا Custom Emoji ID را بفرستید؛ "
            "برای حذف عدد 0 را ارسال کنید."
        ),
        "photo": "عکس جدید را ارسال کنید؛ برای حذف عکس کلمه «حذف» را بفرستید.",
    }
    if field not in prompts:
        return
    await state.set_state(AdminCatalogEditState.value)
    await state.set_data({"scope": "product", "entity_id": callback_data.entity_id, "field": field})
    await edit_or_send(callback, f"<b>ویرایش محصول</b>\n\n{prompts[field]}")


@router.callback_query(AdminCallback.filter((F.section == "products") & (F.action == "add")))
async def product_add_start(
    callback: CallbackQuery, session: AsyncSession, state: FSMContext
) -> None:
    categories = await CatalogService(session).categories(active_only=False)
    if not categories:
        await callback.answer("ابتدا یک دسته‌بندی بسازید.", show_alert=True)
        return
    await state.set_state(AdminProductState.category)
    await edit_or_send(
        callback,
        "<b>➕ محصول جدید</b>\n\nدسته‌بندی محصول را انتخاب کنید.",
        reply_markup=keyboard(
            *[
                [
                    button(
                        f"{item.emoji} {item.name}",
                        callback_data=AdminCallback(
                            section="products", action="choosecat", entity_id=item.id
                        ).pack(),
                    )
                ]
                for item in categories
            ]
        ),
    )


@router.callback_query(
    AdminProductState.category,
    AdminCallback.filter((F.section == "products") & (F.action == "choosecat")),
)
async def product_add_category(
    callback: CallbackQuery, callback_data: AdminCallback, state: FSMContext
) -> None:
    await state.update_data(category_id=callback_data.entity_id)
    await state.set_state(AdminProductState.name)
    await edit_or_send(callback, "نام محصول را ارسال کنید.")


@router.message(AdminProductState.name, F.text)
async def product_add_name(message: Message, state: FSMContext) -> None:
    await state.update_data(name=message.text.strip())
    await state.set_state(AdminProductState.description)
    await message.answer("توضیحات کامل محصول را ارسال کنید.")


@router.message(AdminProductState.description, F.text)
async def product_add_description(message: Message, state: FSMContext) -> None:
    await state.update_data(description=message.text.strip())
    await state.set_state(AdminProductState.price)
    await message.answer("قیمت محصول را به تومان و فقط با عدد ارسال کنید.")


@router.message(AdminProductState.price, F.text)
async def product_add_price(message: Message, state: FSMContext) -> None:
    raw = message.text.replace(",", "").strip()
    if not raw.isdigit():
        await message.answer("قیمت نامعتبر است؛ فقط عدد ارسال کنید.")
        return
    await state.update_data(price=int(raw))
    await state.set_state(AdminProductState.input_prompt)
    await message.answer("برای انجام سفارش چه اطلاعاتی از مشتری لازم است؟")


@router.message(AdminProductState.input_prompt, F.text)
async def product_add_input(message: Message, state: FSMContext) -> None:
    await state.update_data(input_prompt=message.text.strip())
    await state.set_state(AdminProductState.emoji)
    await message.answer("یک ایموجی برای محصول ارسال کنید.")


@router.message(AdminProductState.emoji, F.text)
async def product_add_emoji(message: Message, state: FSMContext) -> None:
    await state.update_data(emoji=message.text.strip())
    await state.set_state(AdminProductState.photo)
    await message.answer("عکس محصول را ارسال کنید یا /skip بفرستید.")


@router.message(AdminProductState.photo, F.photo | F.text)
async def product_add_photo(
    message: Message,
    session: AsyncSession,
    db_user: User,
    state: FSMContext,
) -> None:
    if message.text and message.text.lower() != "/skip":
        await message.answer("یک عکس بفرستید یا /skip را ارسال کنید.")
        return
    data = await state.get_data()
    photo_id = message.photo[-1].file_id if message.photo else None
    product = await CatalogService(session).create_product(
        category_id=int(data["category_id"]),
        name=str(data["name"]),
        description=str(data["description"]),
        price=int(data["price"]),
        input_prompt=str(data["input_prompt"]),
        emoji=str(data["emoji"]),
        photo_file_id=photo_id,
    )
    await ActivityLogService(session).record(
        "product.created",
        actor_user_id=db_user.id,
        entity_type="product",
        entity_id=product.id,
    )
    await state.clear()
    await message.answer(
        f"✅ محصول «{h(product.name)}» ساخته شد.",
        reply_markup=keyboard(
            [
                button(
                    "مشاهده محصول",
                    callback_data=AdminCallback(
                        section="products", action="detail", entity_id=product.id
                    ).pack(),
                )
            ]
        ),
    )


@router.callback_query(AdminCallback.filter((F.section == "categories") & (F.action == "list")))
async def categories_list(callback: CallbackQuery, session: AsyncSession) -> None:
    categories = await CatalogService(session).categories(active_only=False)
    rows = [
        [
            button(
                f"{'🟢' if item.is_active else '⚫'} {item.emoji} {item.name}",
                callback_data=AdminCallback(
                    section="categories", action="detail", entity_id=item.id
                ).pack(),
            )
        ]
        for item in categories
    ]
    rows.extend(
        [
            [
                button(
                    "➕ افزودن دسته",
                    callback_data=AdminCallback(section="categories", action="add").pack(),
                    style="success",
                )
            ],
            [
                button(
                    "↩️ پنل مدیریت",
                    callback_data=AdminCallback(section="dashboard", action="show").pack(),
                )
            ],
        ]
    )
    await edit_or_send(callback, "<b>🗂 مدیریت دسته‌بندی‌ها</b>", reply_markup=keyboard(*rows))


@router.callback_query(AdminCallback.filter((F.section == "categories") & (F.action == "detail")))
async def category_detail(
    callback: CallbackQuery, callback_data: AdminCallback, session: AsyncSession
) -> None:
    category = await CatalogService(session).category(callback_data.entity_id, active_only=False)
    products = await CatalogService(session).products(category.id, active_only=False)
    await edit_or_send(
        callback,
        f"<b>{h(category.emoji)} {h(category.name)}</b>\n\n"
        f"{h(category.description or '')}\n\n"
        f"محصولات: <b>{len(products)}</b>\n"
        f"وضعیت: {'🟢 فعال' if category.is_active else '⚫ غیرفعال'}",
        reply_markup=keyboard(
            [
                button(
                    "⏸ غیرفعال‌سازی" if category.is_active else "▶️ فعال‌سازی",
                    callback_data=AdminCallback(
                        section="categories", action="toggle", entity_id=category.id
                    ).pack(),
                )
            ],
            [
                button(
                    "✏️ نام",
                    callback_data=AdminCallback(
                        section="categories", action="edit_name", entity_id=category.id
                    ).pack(),
                ),
                button(
                    "📝 توضیحات",
                    callback_data=AdminCallback(
                        section="categories", action="edit_description", entity_id=category.id
                    ).pack(),
                ),
                button(
                    "😀 ایموجی",
                    callback_data=AdminCallback(
                        section="categories", action="edit_emoji", entity_id=category.id
                    ).pack(),
                ),
            ],
            [
                button(
                    "🗑 حذف دسته",
                    callback_data=AdminCallback(
                        section="categories", action="delete", entity_id=category.id
                    ).pack(),
                    style="danger",
                )
            ],
            [
                button(
                    "💠 Custom Emoji",
                    callback_data=AdminCallback(
                        section="categories",
                        action="edit_custom_emoji_id",
                        entity_id=category.id,
                    ).pack(),
                )
            ],
            [
                button(
                    "↩️ دسته‌بندی‌ها",
                    callback_data=AdminCallback(section="categories", action="list").pack(),
                )
            ],
        ),
    )


@router.callback_query(AdminCallback.filter((F.section == "categories") & (F.action == "toggle")))
async def category_toggle(
    callback: CallbackQuery, callback_data: AdminCallback, session: AsyncSession
) -> None:
    category = await CatalogService(session).category(callback_data.entity_id, active_only=False)
    await CatalogService(session).update_category(category.id, is_active=not category.is_active)
    await category_detail(
        callback,
        AdminCallback(section="categories", action="detail", entity_id=category.id),
        session,
    )


@router.callback_query(AdminCallback.filter((F.section == "categories") & (F.action == "add")))
async def category_add(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminCategoryState.name)
    await edit_or_send(callback, "<b>➕ دسته‌بندی جدید</b>\n\nنام دسته را ارسال کنید.")


@router.message(AdminCategoryState.name, F.text)
async def category_add_name(message: Message, state: FSMContext) -> None:
    await state.update_data(name=message.text.strip())
    await state.set_state(AdminCategoryState.description)
    await message.answer("توضیحات دسته را ارسال کنید.")


@router.message(AdminCategoryState.description, F.text)
async def category_add_description(message: Message, state: FSMContext) -> None:
    await state.update_data(description=message.text.strip())
    await state.set_state(AdminCategoryState.emoji)
    await message.answer("یک ایموجی برای دسته ارسال کنید.")


@router.message(AdminCategoryState.emoji, F.text)
async def category_add_emoji(
    message: Message, session: AsyncSession, db_user: User, state: FSMContext
) -> None:
    data = await state.get_data()
    category = await CatalogService(session).create_category(
        str(data["name"]), str(data["description"]), message.text.strip()
    )
    await ActivityLogService(session).record(
        "category.created",
        actor_user_id=db_user.id,
        entity_type="category",
        entity_id=category.id,
    )
    await state.clear()
    await message.answer(
        f"✅ دسته «{h(category.name)}» ساخته شد.",
        reply_markup=keyboard(
            [
                button(
                    "دسته‌بندی‌ها",
                    callback_data=AdminCallback(section="categories", action="list").pack(),
                )
            ]
        ),
    )


@router.callback_query(
    AdminCallback.filter((F.section == "categories") & F.action.startswith("edit_"))
)
async def category_edit_prompt(
    callback: CallbackQuery, callback_data: AdminCallback, state: FSMContext
) -> None:
    field = callback_data.action.removeprefix("edit_")
    if field not in {"name", "description", "emoji", "custom_emoji_id"}:
        return
    await state.set_state(AdminCatalogEditState.value)
    await state.set_data(
        {"scope": "category", "entity_id": callback_data.entity_id, "field": field}
    )
    prompt = (
        "ایموجی Premium متحرک را ارسال کنید یا Custom Emoji ID را بفرستید؛ "
        "برای حذف عدد 0 را ارسال کنید."
        if field == "custom_emoji_id"
        else "مقدار جدید را ارسال کنید."
    )
    await edit_or_send(callback, prompt)


@router.callback_query(AdminCallback.filter((F.section == "categories") & (F.action == "delete")))
async def category_delete(
    callback: CallbackQuery, callback_data: AdminCallback, session: AsyncSession
) -> None:
    await CatalogService(session).delete_category(callback_data.entity_id)
    await categories_list(callback, session)


@router.message(AdminCatalogEditState.value, F.photo | F.text)
async def catalog_edit_value(
    message: Message,
    bot: Bot,
    session: AsyncSession,
    db_user: User,
    state: FSMContext,
) -> None:
    data = await state.get_data()
    scope = str(data["scope"])
    entity_id = int(data["entity_id"])
    field = str(data["field"])
    if field == "photo":
        if message.photo:
            value: object = message.photo[-1].file_id
        elif message.text and message.text.strip() == "حذف":
            value = None
        else:
            await message.answer("لطفاً عکس بفرستید یا کلمه «حذف» را ارسال کنید.")
            return
        field = "photo_file_id"
    elif field == "price":
        raw = (message.text or "").replace(",", "").strip()
        if not raw.isdigit():
            await message.answer("قیمت نامعتبر است؛ فقط عدد ارسال کنید.")
            return
        value = int(raw)
    else:
        value = (message.text or "").strip()
        if field == "custom_emoji_id":
            if value == "0":
                value = None
            else:
                emoji_id = extract_custom_emoji_id(message) or valid_custom_emoji_id(value)
                if emoji_id is None or not await validate_custom_emoji(bot, emoji_id):
                    await message.answer(
                        "این ایموجی Premium معتبر نیست. خود ایموجی متحرک را از تلگرام "
                        "ارسال کنید یا یک ID عددی معتبر بفرستید."
                    )
                    return
                if not await verify_custom_emoji_button_access(bot, message.chat.id, emoji_id):
                    await message.answer(
                        "⚠️ تلگرام این ایموجی را برای دکمه‌های این ربات نپذیرفت و تغییر "
                        "ذخیره نشد.\n\nمالک همین ربات در BotFather باید اشتراک Premium فعال "
                        "داشته باشد؛ یا برای ربات Additional Username از Fragment تهیه شده باشد."
                    )
                    return
                value = emoji_id
    if scope == "product":
        item = await CatalogService(session).update_product(entity_id, **{field: value})
        section = "products"
    else:
        item = await CatalogService(session).update_category(entity_id, **{field: value})
        section = "categories"
    await ActivityLogService(session).record(
        f"{scope}.updated",
        actor_user_id=db_user.id,
        entity_type=scope,
        entity_id=entity_id,
        details={"field": field},
    )
    await state.clear()
    await message.answer(
        "✅ تغییر ذخیره شد.",
        reply_markup=keyboard(
            [
                button(
                    "مشاهده",
                    callback_data=AdminCallback(
                        section=section, action="detail", entity_id=item.id
                    ).pack(),
                )
            ]
        ),
    )
