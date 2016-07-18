
class SuspiciousOperation(Exception):
    """The user did something suspicious"""




class PermissionDenied(Exception):
    """The user did not have permission to do that"""
    pass


class ViewDoesNotExist(Exception):
    """The requested view does not exist"""
    pass

class ZengineError(Exception):
    """ pass """
    pass

class FormValidationError(ZengineError):
    """ pass """
    pass

class HTTPError(Exception):
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
