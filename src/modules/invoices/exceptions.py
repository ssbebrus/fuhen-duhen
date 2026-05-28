class InvoiceItemMissingError(Exception):
    pass

class SkuNotFoundError(Exception):
    pass

class NotOwnerError(Exception):
    pass

class InvalidProductStatusError(Exception):
    pass

class InvalidQuantityError(Exception):
    pass

class InvoiceNotFoundError(Exception):
    pass

class InvoiceAlreadyProcessedError(Exception):
    pass

class InvoiceItemNotFoundError(Exception):
    pass
