

class DotDict(dict):
    """
    A dict object that support dot notation for item access.

    Slower that pure dict.
    """
    def __getattr__(self, attr):
        return self.get(attr, None)

    __setattr__ = dict.__setitem__
    __delattr__ = dict.__delitem__


def date_to_solr(d):
    """ converts DD-MM-YYYY to YYYY-MM-DDT00:00:00Z"""
    return "{y}-{m}-{day}T00:00:00Z".format(day=d[:2], m=d[3:5], y=d[6:]) if d else d

def solr_to_date(d):
    """ converts YYYY-MM-DDT00:00:00Z to DD-MM-YYYY """
    return "{day}:{m}:{y}".format(y=d[:4], m=d[5:7], day=d[8:10]) if d else d

def solr_to_year(d):
    """ converts YYYY-MM-DDT00:00:00Z to DD-MM-YYYY """
    return d[:4]
