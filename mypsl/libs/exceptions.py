

class Error(Exception):
    pass

class MyDBError(Error):
    pass

class SaltConfigError(Error):
    pass

class SaltClientError(Error):
    pass

class TooManyInstancesError(Error):
    pass

class NotificationError(Error):
    pass
