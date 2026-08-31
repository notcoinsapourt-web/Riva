class PersianShopError(Exception):
    """Expected business error safe to display to the user."""


class NotFoundError(PersianShopError):
    pass


class ValidationError(PersianShopError):
    pass


class InsufficientBalanceError(PersianShopError):
    pass


class ModuleDisabledError(PersianShopError):
    pass


class PaymentDisabledError(PersianShopError):
    pass


class PermissionDeniedError(PersianShopError):
    pass
