__author__ = 'Evren Esat Ozkan'

# def basic_view(name):
#     def wrapper(func):
#         from pyoko.conf import settings
#         settings.VIEW_METHODS[name] = func
#         return func
#
# class basic_view(object):
#
#     def __call__(self, cls):
#         class Wrapped(cls):
#             classattr = self.arg
#             def new_method(self, value):
#                 return value * 2
#         return Wrapped
