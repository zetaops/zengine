from falcon.errors import *



class SuspiciousOperation(Exception):
    """The user did something suspicious"""


class SuspiciousMultipartForm(SuspiciousOperation):
    """Suspect MIME request in multipart form data"""
    pass


class SuspiciousFileOperation(SuspiciousOperation):
    """A Suspicious filesystem operation was attempted"""
    pass


class DisallowedHost(SuspiciousOperation):
    """HTTP_HOST header contains invalid value"""
    pass


class PermissionDenied(Exception):
    """The user did not have permission to do that"""
    pass


class ViewDoesNotExist(Exception):
    """The requested view does not exist"""
    pass

class ZengineError(Exception):
    pass
