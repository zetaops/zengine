from zengine.views.base import BaseView
from zengine import forms
from zengine.forms import fields
from zengine.lib.cache import Cache
from zengine.config import settings
from pyoko import ListNode
from pyoko.lib.utils import get_object_from_path
from collections import defaultdict

PermissionModel = get_object_from_path(settings.PERMISSION_MODEL)
RoleModel = get_object_from_path(settings.ROLE_MODEL)



class PermissionForm(forms.JsonForm):
    """Form used to edit the permissions of a role."""
    class Meta:
        title = 'Edit Permissions'
        exclude = ['Permissions']

    class Permissions(ListNode):
        perm_name = fields.String('Permission Name')

    save_edit = fields.Button("Save", cmd="finish")


class PermissionTreeBuilder(object):
    """A class to help permission trees to be built out of permission objects.

    The permission trees built by this class will be in the form of

    {
        'id': 'workflow',
        'name': 'Workflow Name',
        'checked': True,
        'children': {
            'task': {
                'id': 'workflow.task',
                'name' 'Task Name',
                'checked': False,
                'children': {}
            }
        }
    }

    Note that these permission trees are NOT sent to the UI in this form.
    An additional formatting step is performed before sending these trees,
    see `Permissions.edit_permissions` to see the actual trees that are
    sent to the UI.

    To build a permission tree, create an instance of this class, and call
    the `insert` method to insert all permissions into the permission tree.
    The order of the insertions is not important.
    Missing permissions will be automatically created, for example only
    inserting `workflow.task` will create a permission tree similar to the
    example above, minus the human readable task name. Inserting the
    `workflow` later will allow you to get the human readable name for
    that permission as well.
    """
    def __init__(self):
        self._data = defaultdict(PermissionTreeBuilder)
        self._permission = None

    def insert(self, permission):
        # Insert the permission, skipping empty steps, such that inserting workflow..task
        # will make the task to be inserted under the workflow.
        self._insert(permission, iter(filter(lambda s: s != '', permission.code.split('.'))))

    def _insert(self, permission, path):
        try:
            step = path.next()
            self._data[step]._insert(permission, path)
        except StopIteration:  # Last step
            self._permission = permission

    def serialize(self, path=''):

        def do_serialize(newstep, subtree):
            newpath = '{}.{}'.format(path, newstep) if path else newstep
            return newstep, subtree._serialize(newpath)

        return dict(do_serialize(p, pt) for p, pt in self._data.items())

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
            'checked': False,
        }


class PermissionTreeCache(Cache):
    PREFIX = 'PERMTREE'
    # No key is set, we'll be only storing one object


class Permissions(BaseView):
    """View for editing permissions of roles."""

    def __init__(self, current=None):
        super(Permissions, self).__init__(current)

    def edit_permissions(self):
        """Creates the view used to edit permissions.

        To create the view, data in the following format is passed to the UI
        in the objects field:

        .. code-block:: python
            {
                "type": "tree-toggle",
                "action": "set_permission",
                "tree": [
                    {
                        "checked": true,
                        "name": "Workflow 1 Name",
                        "id": "workflow1",
                        "children":
                            [
                                {
                                    "checked": true,
                                    "name": "Task 1 Name",
                                    "id": "workflow1..task1",
                                    "children": []
                                },
                                {
                                    "checked": false,
                                    "id": "workflow1..task2",
                                    "name": "Task 2 Name",
                                    "children": []
                                }
                            ]
                    },
                    {
                        "checked": true,
                        "name": "Workflow 2 Name",
                        "id": "workflow2",
                        "children": [
                            {
                                "checked": true,
                                "name": "Workflow 2 Lane 1 Name",
                                "id": "workflow2.lane1",
                                "children": [
                                    {
                                        "checked": true,
                                        "name": "Workflow 2 Task 1 Name",
                                        "id": "workflow2.lane1.task1",
                                        "children": []
                                    },
                                    {
                                        "checked": false,
                                        "name": "Workflow 2 Task 2 Name",
                                        "id": "workflow2.lane1.task2",
                                        "children": []
                                    }
                                ]
                            }
                        ]
                    }
                ]
            }

        "type" field denotes that the object is a tree view which has elements that can be toggled.
        "action" field is the

        "name" field is the human readable name.
        "id" field is used to make requests to the backend.
        "checked" field shows whether the role has the permission or not.
        "children" field is the sub-permissions of the permission.
        """
        # Get the role that was selected in the CRUD view
        key = self.current.input['object_id']
        self.current.task_data['role_id'] = key
        role = RoleModel.objects.get(key=key)
        # Get the cached permission tree, or build a new one if there is none cached
        # TODO: Add an extra view in case there was no cache, as in 'please wait calculating permissions'
        permission_tree = self._permission_trees(PermissionModel.objects)
        # Apply the selected role to the permission tree, setting the 'checked' field
        # of the permission the role has
        role_tree = self._apply_role_tree(permission_tree, role)
        # Apply final formatting, and output the tree to the UI
        self.output['objects'] = [
            {
                'type': 'tree-toggle',
                'action': 'apply_change',
                'trees': self._format_tree_output(role_tree),
            },
        ]
        self.form_out(PermissionForm())

    @staticmethod
    def _permission_trees(permissions):
        """Get the cached permission tree, or build a new one if necessary."""
        treecache = PermissionTreeCache()
        cached = treecache.get()
        if not cached:
            tree = PermissionTreeBuilder()
            for permission in permissions:
                tree.insert(permission)
            result = tree.serialize()
            treecache.set(result)
            return result
        return cached

    def _apply_role_tree(self, perm_tree, role):
        """In permission tree, sets `'checked': True` for the permissions that the role has."""
        role_permissions = role.get_permissions()
        for perm in role_permissions:
            self._traverse_tree(perm_tree, perm)['checked'] = True
        return perm_tree

    @staticmethod
    def _traverse_tree(tree, path):
        """Traverses the permission tree, returning the permission at given permission path."""
        path_steps = (step for step in path.split('.') if step != '')
        # Special handling for first step, because the first step isn't under 'objects'
        first_step = path_steps.next()
        subtree = tree[first_step]

        for step in path_steps:
            subtree = subtree['children'][step]
        return subtree

    def _format_tree_output(self, tree):
        """Format the tree to be sent to the UI.

        Internally, 'children' of each permission is a dictionary to allow
        easier searches, but we will be sending them to the UI as a list,
        in order to make it possible to control the order in which the children
        appear.
        """
        return [self._format_subtree(subtree) for subtree in tree.values()]

    def _format_subtree(self, subtree):
        """Recursively format all subtrees."""
        subtree['children'] = list(subtree['children'].values())
        for child in subtree['children']:
            self._format_subtree(child)
        return subtree

    def apply_change(self):
        """Applies changes to the permissions of the role.

        To make a change to the permission of the role, a request
        in the following format should be sent:

        .. code-block:: python
            {
                'change':
                    {
                        'id': 'workflow2.lane1.task1',
                        'checked': false
                    },
            }

        The 'id' field of the change is the id of the tree element
        that was sent to the UI (see `Permissions.edit_permissions`).
        'checked' field is the new state of the element.
        """
        changes = self.input['change']
        key = self.current.task_data['role_id']
        role = RoleModel.objects.get(key=key)
        for change in changes:
            permission = PermissionModel.objects.get(code=change['id'])
            if change['checked'] is True:
                role.add_permission(permission)
            else:
                role.remove_permission(permission)
        role.save()
