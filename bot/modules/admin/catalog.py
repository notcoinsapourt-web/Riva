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
    AdminProductSearchState,
    AdminProductState,
)
from bot.core.ui import button, edit_or_send, keyboard
from bot.database.models import User
from bot.modules.admin.common import protected_router
from bot.services.catalog import CatalogService
from bot.services.logs import ActivityLogService

router = protected_router("catalog")
ADMIN_PRODUCT_PAGE_SIZE = 8


@router.callback_query(AdminCallback.filter((F.section == "products") & (F.action == "list")))
async def products_list(callback: CallbackQuery, session: AsyncSession) -> None:
    service = CatalogService(session)
    categories = await service.categories(active_only=False)
    products = await service.products(active_only=False)
    grouped = {category.id: [] for category in categories}
    for product in products:
        grouped.setdefault(product.category_id, []).append(product)
    rows = []
    for category in categories:
        items = grouped.get(category.id, [])
        active_count = sum(item.is_active for item in items)
        rows.append(
            [
                button(
                    f"{category.emoji} {category.name} · {len(items)} ({active_count} فعال)",
                    callback_data=AdminCallback(
                        section="products", action="category", entity_id=category.id
                    ).pack(),
                    custom_emoji_id=category.custom_emoji_id,
                )
            ]
        )
    rows.extend(
        [
            [
                button(
                    "🔍 جستجوی محصول",
                    callback_data=AdminCallback(section="products", action="search").pack(),
                )
            ],
            [
                button(
                    "🟢 فعال‌ها",
                    callback_data=AdminCallback(section="products", action="active").pack(),
                ),
                button(
                    "⚫ غیرفعال‌ها",
                    callback_data=AdminCallback(section="products", action="inactive").pack(),
                ),
            ],
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
        + (
            f"تعداد کل: <b>{len(products)}</b>\n"
            f"فعال: <b>{sum(item.is_active for item in products)}</b> | "
            f"غیرفعال: <b>{sum(not item.is_active for item in products)}</b>\n\n"
            "ابتدا دسته‌بندی موردنظر را انتخاب کنید."
            if products
            else "هنوز محصولی ثبت نشده است."
        ),
        reply_markup=keyboard(*rows),
    )


def _admin_product_buttons(products: list, *, page: int) -> list[list]:
    return [
        [
            button(
                f"{item.emoji} {'🟢' if item.is_active else '⚫'} "
                f"{compact_text(item.name, 25)} | "
                f"{money(item.price)}",
                callback_data=AdminCallback(
                    section="products", action="detail", entity_id=item.id, page=page
                ).pack(),
                custom_emoji_id=item.custom_emoji_id,
            )
        ]
        for item in products
    ]


@router.callback_query(AdminCallback.filter((F.section == "products") & (F.action == "category")))
async def products_by_category(
    callback: CallbackQuery, callback_data: AdminCallback, session: AsyncSession
) -> None:
    service = CatalogService(session)
    category = await service.category(callback_data.entity_id, active_only=False)
    products = await service.products(category.id, active_only=False)
    page = max(0, callback_data.page)
    start = page * ADMIN_PRODUCT_PAGE_SIZE
    visible = products[start : start + ADMIN_PRODUCT_PAGE_SIZE]
    rows = _admin_product_buttons(visible, page=page)
    paging = []
    if page > 0:
        paging.append(
            button(
                "◀️ قبلی",
                callback_data=AdminCallback(
                    section="products", action="category", entity_id=category.id, page=page - 1
                ).pack(),
            )
        )
    if start + ADMIN_PRODUCT_PAGE_SIZE < len(products):
        paging.append(
            button(
                "بعدی ▶️",
                callback_data=AdminCallback(
                    section="products", action="category", entity_id=category.id, page=page + 1
                ).pack(),
            )
        )
    if paging:
        rows.append(paging)
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
                    "↩️ دسته‌های محصولات",
                    callback_data=AdminCallback(section="products", action="list").pack(),
                )
            ],
        ]
    )
    await edit_or_send(
        callback,
        f"<b>{h(category.emoji)} {h(category.name)}</b>\n\n"
        f"محصولات: <b>{len(products)}</b>\n"
        f"فعال: <b>{sum(item.is_active for item in products)}</b> | "
        f"غیرفعال: <b>{sum(not item.is_active for item in products)}</b>\n"
        f"صفحه: <b>{page + 1}</b>",
        reply_markup=keyboard(*rows),
    )


@router.callback_query(
    AdminCallback.filter((F.section == "products") & F.action.in_({"active", "inactive"}))
)
async def products_by_status(
    callback: CallbackQuery, callback_data: AdminCallback, session: AsyncSession
) -> None:
    enabled = callback_data.action == "active"
    products = [
        item
        for item in await CatalogService(session).products(active_only=False)
        if item.is_active is enabled
    ]
    page = max(0, callback_data.page)
    start = page * ADMIN_PRODUCT_PAGE_SIZE
    visible = products[start : start + ADMIN_PRODUCT_PAGE_SIZE]
    rows = _admin_product_buttons(visible, page=page)
    paging = []
    if page > 0:
        paging.append(
            button(
                "◀️ قبلی",
                callback_data=AdminCallback(
                    section="products", action=callback_data.action, page=page - 1
                ).pack(),
            )
        )
    if start + ADMIN_PRODUCT_PAGE_SIZE < len(products):
        paging.append(
            button(
                "بعدی ▶️",
                callback_data=AdminCallback(
                    section="products", action=callback_data.action, page=page + 1
                ).pack(),
            )
        )
    if paging:
        rows.append(paging)
    rows.append(
        [
            button(
                "↩️ مدیریت محصولات",
                callback_data=AdminCallback(section="products", action="list").pack(),
            )
        ]
    )
    await edit_or_send(
        callback,
        f"<b>{'🟢 محصولات فعال' if enabled else '⚫ محصولات غیرفعال'}</b>\n\n"
        f"تعداد: <b>{len(products)}</b>",
        reply_markup=keyboard(*rows),
    )


@router.callback_query(AdminCallback.filter((F.section == "products") & (F.action == "search")))
async def product_search_start(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminProductSearchState.query)
    await edit_or_send(
        callback,
        "<b>🔍 جستجوی محصول</b>\n\nبخشی از نام فارسی یا انگلیسی محصول را ارسال کنید.",
        reply_markup=keyboard(
            [
                button(
                    "لغو",
                    callback_data=AdminCallback(section="products", action="list").pack(),
                    style="danger",
                )
            ]
        ),
    )


@router.message(AdminProductSearchState.query, F.text)
async def product_search_result(message: Message, session: AsyncSession, state: FSMContext) -> None:
    products = await CatalogService(session).search_products(message.text)
    await state.clear()
    rows = _admin_product_buttons(products, page=0)
    rows.append(
        [
            button(
                "↩️ مدیریت محصولات",
                callback_data=AdminCallback(section="products", action="list").pack(),
            )
        ]
    )
    await message.answer(
        f"<b>نتیجه جستجو برای «{h(message.text)}»</b>\n\n"
        + (f"{len(products)} محصول پیدا شد." if products else "محصولی پیدا نشد."),
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
                "⬆️ بالاتر",
                callback_data=AdminCallback(
                    section="products", action="up", entity_id=product.id
                ).pack(),
            ),
            button(
                "⬇️ پایین‌تر",
                callback_data=AdminCallback(
                    section="products", action="down", entity_id=product.id
                ).pack(),
            ),
        ],
        [
            button(
                "🗂 انتقال به دسته دیگر",
                callback_data=AdminCallback(
                    section="products", action="move", entity_id=product.id
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
                "↩️ محصولات این دسته",
                callback_data=AdminCallback(
                    section="products",
                    action="category",
                    entity_id=product.category_id,
                    page=callback_data.page,
                ).pack(),
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


@router.callback_query(
    AdminCallback.filter((F.section == "products") & F.action.in_({"up", "down"}))
)
async def product_reorder(
    callback: CallbackQuery,
    callback_data: AdminCallback,
    session: AsyncSession,
    db_user: User,
) -> None:
    direction = -1 if callback_data.action == "up" else 1
    product = await CatalogService(session).reorder_product(callback_data.entity_id, direction)
    await ActivityLogService(session).record(
        "product.reordered",
        actor_user_id=db_user.id,
        entity_type="product",
        entity_id=product.id,
        details={"direction": callback_data.action},
    )
    await callback.answer("ترتیب محصول به‌روزرسانی شد.")
    await product_detail(
        callback,
        AdminCallback(section="products", action="detail", entity_id=product.id),
        session,
    )


@router.callback_query(AdminCallback.filter((F.section == "products") & (F.action == "move")))
async def product_move_start(
    callback: CallbackQuery, callback_data: AdminCallback, session: AsyncSession
) -> None:
    product = await CatalogService(session).product(callback_data.entity_id, active_only=False)
    categories = await CatalogService(session).categories(active_only=False)
    rows = [
        [
            button(
                f"{item.emoji} {item.name}",
                callback_data=AdminCallback(
                    section="products", action="moveto", entity_id=product.id, page=item.id
                ).pack(),
                custom_emoji_id=item.custom_emoji_id,
            )
        ]
        for item in categories
        if item.id != product.category_id
    ]
    rows.append(
        [
            button(
                "انصراف",
                callback_data=AdminCallback(
                    section="products", action="detail", entity_id=product.id
                ).pack(),
            )
        ]
    )
    await edit_or_send(
        callback,
        f"<b>🗂 انتقال «{h(product.name)}»</b>\n\nدسته مقصد را انتخاب کنید.",
        reply_markup=keyboard(*rows),
    )


@router.callback_query(AdminCallback.filter((F.section == "products") & (F.action == "moveto")))
async def product_move_finish(
    callback: CallbackQuery,
    callback_data: AdminCallback,
    session: AsyncSession,
    db_user: User,
) -> None:
    product = await CatalogService(session).move_product(
        callback_data.entity_id, callback_data.page
    )
    await ActivityLogService(session).record(
        "product.moved",
        actor_user_id=db_user.id,
        entity_type="product",
        entity_id=product.id,
        details={"category_id": product.category_id},
    )
    await callback.answer("محصول به دسته جدید منتقل شد.")
    await product_detail(
        callback,
        AdminCallback(section="products", action="detail", entity_id=product.id),
        session,
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
