class SkuNotFoundError(Exception):
    pass

class ProductNotFoundError(Exception):
    pass

class NotOwnerError(Exception):
    pass

class SkuHardBlockedError(Exception):
    pass

class SkuHasReservesError(Exception):
    pass

class ImageNotFoundError(Exception):
    pass
