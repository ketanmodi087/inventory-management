from rest_framework import permissions
from .models import User


class IMSViewSetPermissions(permissions.BasePermission):
    """
    Custom permission to check user permissions based on Django's
    model permissions (e.g., app_label.can_do_something_model).
    """

    def has_permission(self, request, view):
        if request.user and request.user.is_authenticated:
            if request.user.is_superuser:
                # Superusers have all permissions
                return True
            # For list views or actions not involving a specific object
            if view.action in ['list', 'create']:
                # Example: Allow list if user has 'view_mymodel' permission
                # Allow create if user has 'add_mymodel' permission
                if request.method == 'GET' and request.user.has_perm(f'{view.queryset.model._meta.app_label}.view_{view.queryset.model._meta.model_name}'):
                    return True
                if request.method == 'POST' and request.user.has_perm(f'{view.queryset.model._meta.app_label}.add_{view.queryset.model._meta.model_name}'):
                    return True
                return False
            return True # Defer to has_object_permission for detail views
        return False

    def has_object_permission(self, request, view, obj):
        # For detail views (retrieve, update, destroy)
        app_label = obj._meta.app_label
        model_name = obj._meta.model_name

        if request.method == 'GET':
            return request.user.has_perm(f'{app_label}.view_{model_name}')
        elif request.method == 'PUT' or request.method == 'PATCH':
            return request.user.has_perm(f'{app_label}.change_{model_name}')
        elif request.method == 'DELETE':
            return request.user.has_perm(f'{app_label}.delete_{model_name}')
        return False


class IsOwner(permissions.BasePermission):
    """
    Custom permission to only allow owners of an object to edit it.
    """

    def has_object_permission(self, request, view, obj):
        if hasattr(obj, 'user'):
            # If the object has a 'user' attribute, check if the request user is the owner
            return obj.user == request.user
        # If the object does not have a 'user' attribute, check if the request user
        if isinstance(obj, User):
            # If the object is a User instance, check if the request user is the same
            return obj == request.user
        return False