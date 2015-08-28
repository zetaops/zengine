import importlib

__author__ = 'Evren Esat Ozkan'


class DotDict(dict):
    def __getattr__(self, attr):
        return self.get(attr, None)

    __setattr__ = dict.__setitem__
    __delattr__ = dict.__delitem__


def get_object_from_path(path):
    path = path.split('.')
    module_path = '.'.join(path[:-1])
    class_name = path[-1]
    module = importlib.import_module(module_path)
    return getattr(module, class_name)
