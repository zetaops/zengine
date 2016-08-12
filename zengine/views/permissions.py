from zengine.views.crud import CrudView
from zengine import forms
from zengine.forms import fields
from zengine.lib.cache import Cache
from zengine.config import settings
from pyoko import ListNode
from pyoko.lib.utils import get_object_from_path
from collections import defaultdict

PermissionModel = get_object_from_path(settings.PERMISSION_MODEL)



class PermissionForm(forms.JsonForm):
    """Form used to edit the permissions of a role."""
    class Meta:
        title = 'Edit Permissions'
        exclude = ['Permissions']

    class Permissions(ListNode):
        perm_name = fields.String('Permission Name')

    save_edit = fields.Button("Save", cmd="finish")


class PermissionTree(object):
    def __init__(self):
        self._data = defaultdict(PermissionTree)
        self._permission = None

    def insert(self, permission):
        self._insert(permission, iter(filter(lambda s: s != '', permission.code.split('.'))))

    def _insert(self, permission, path):
        try:
            step = path.next()
            self._data[step]._insert(permission, path)
        except StopIteration:  # Last step
            self._permission = permission

    def serialize(self, path=''):
        return [pt._serialize('{}.{}'.format(path, p) if path else p) for p, pt in self._data.items()]

    def _serialize(self, path):
        if self._permission:
            code = self._permission.code or path
            name = self._permission.name or code
        else:
            code = name = path
        children = self.serialize(path)
        return {
            'id': code,
            'name': name,
            'children': children,
        }


class PermissionTreeCache(Cache):
    PREFIX = 'PERMTREE'
    # No key is set, we'll be only storing one object


class Permissions(CrudView):
    """View for editing permissions of roles."""

    def __init__(self, current=None):
        super(Permissions, self).__init__(current)
        self.object_form = PermissionForm(self.object, current=current)

    class Meta:
        model = 'Role'

    def edit_permissions(self):
        key = self.current.input['object_id']
        self.current.task_data['role_id'] = key
        # TODO: Add an extra view in case there was no cache, as in 'please wait calculating permissions'
        self.output['objects'] = self._permission_trees(PermissionModel.objects)
        self.form_out(PermissionForm())

    @staticmethod
    def _permission_trees(permissions):
        treecache = PermissionTreeCache()
        cached = treecache.get()
        if not cached:
            tree = PermissionTree()
            for permission in permissions:
                tree.insert(permission)
            result = tree.serialize()
            treecache.set(result)
            return result
        return cached

    @staticmethod
    def _traverse_permission(perm_tree, path):
        tree = perm_tree
        for step in reversed(path):
            tree = tree[step]
        return tree

    def apply_change(self):
        pass
