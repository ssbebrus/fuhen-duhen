class ProductNotFoundError(Exception):
    pass

class NotOwnerError(Exception):
    pass

class ProductHardBlockedError(Exception):
    pass

class ProductAlreadyDeletedError(Exception):
    pass

class ImageNotFoundError(Exception):
    pass

class InvalidUUIDError(Exception):
    pass
