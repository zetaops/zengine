class ZengineError(Exception):
    """ pass """
    pass

class SuspiciousOperation(ZengineError):
    """The user did something suspicious"""
    pass

class SecurityInfringementAttempt(ZengineError):
    """Someone tried to do something nasty"""
    pass

class PermissionDenied(ZengineError):
    """The user did not have permission to do that"""
    pass


class ViewDoesNotExist(ZengineError):
    """The requested view does not exist"""
    pass


class FormValidationError(ZengineError):
    """ pass """
    pass


class ConfigurationError(ZengineError):
    """ pass """
    pass


class HTTPError(ZengineError):
    """Exception thrown for an unsuccessful HTTP request.

    Attributes:

    * ``code`` - HTTP error integer error code, e.g. 404.  Error code 599 is
      used when no HTTP response was received, e.g. for a timeout.
    """

    def __init__(self, code, message=None):
        self.code = code
        self.message = message
        super(HTTPError, self).__init__(code, message)

    def __str__(self):
        return "HTTP %d: %s" % (self.code, self.message)
