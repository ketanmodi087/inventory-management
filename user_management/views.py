from .models import User, Role, Notification, NotificationType
from .serializers import PermissionSerializer, UserSerializer, GroupSerializer, RoleSerializer, NotificationSerializer
from django.contrib.auth.models import Permission, Group
from django.utils.translation import gettext_lazy as _
from rest_framework import viewsets, response, views, status
from rest_framework.pagination import PageNumberPagination
from rest_framework.decorators import action
from rest_framework_simplejwt.tokens import RefreshToken
from .permissions import IMSViewSetPermissions, IsOwner
from django.utils.text import slugify



class PermissionViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for listing and retrieving permissions.
    This viewset provides read-only access to the permissions in the system.
    It allows users to view the details of each permission without the ability to create, update, or delete them.
    """
    ordering = ['id']
    serializer_class = PermissionSerializer
    pagination_class = None
    def get_queryset(self):
        return Permission.objects.filter(content_type__app_label__icontains='management').all()


class UserViewSet(viewsets.ModelViewSet):
    """
    ViewSet for listing and retrieving users.
    This viewset provides read-only access to the users in the system.
    """
    ordering = ['id']
    serializer_class = UserSerializer
    queryset = User.objects.exclude(is_superuser=True).all()
    search_fields = ['email', 'first_name', 'last_name']  # Allow searching by email, first name, and last name
    ordering_fields = ['email', 'first_name', 'id']  # Allow ordering by these fields
    permission_classes = [IMSViewSetPermissions | IsOwner]  # Custom permission class to check user permissions


class RoleViewSet(viewsets.ModelViewSet):
    """
    ViewSet for listing and retrieving roles.
    This viewset provides read-only access to the roles in the system.
    """
    ordering = ['id']
    serializer_class = RoleSerializer
    pagination_class = None
    queryset = Role.objects.all()
    permission_classes = [IMSViewSetPermissions | IsOwner]  # Custom permission class to check user permissions


class GroupViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for listing and retrieving roles.
    This viewset provides read-only access to the roles in the system.
    """
    ordering = ['id']
    serializer_class = GroupSerializer
    pagination_class = None

    def get_queryset(self):
        return Group.objects.all()


class AuthUserDetailView(views.APIView):

    def get(self, request):
        if not request.user or not request.user.is_authenticated:
            return response.Response({"error": "Authentication credentials were not provided."},
                                     status=status.HTTP_401_UNAUTHORIZED)
        user = request.user
        user_data = {
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'full_name': user.get_full_name(),
            'last_login': user.last_login,
            'phone_number': user.phone_number,
            'groups': [slugify(group.name) for group in user.groups.all()],
            'role': user.role.name if user.role else None,
            'id': user.id,
            'is_superuser': user.is_superuser,
            'is_staff': user.is_staff,
            'date_joined': user.date_joined,
            'is_active': user.is_active,
        }
        return response.Response(user_data)


class LogoutView(views.APIView):
    """ View for logging out users by blacklisting their refresh tokens."""

    def post(self, request):
        try:
            refresh_token = request.data["refresh_token"]
            token = RefreshToken(refresh_token)
            token.blacklist()

            return response.Response(status=status.HTTP_205_RESET_CONTENT)
        except Exception as e:
            return response.Response(status=status.HTTP_400_BAD_REQUEST)

class NotificationViewset(viewsets.ViewSet):

    @action(detail=False, methods=['get'])
    def list_all(self, request):
        notifications = Notification.objects.filter(recipient=request.user).order_by('-id')
        paginator = PageNumberPagination()  #

        page = paginator.paginate_queryset(notifications, request)
        if page is not None:
            serializer = NotificationSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)
        return None

    @action(detail=False, methods=['get'])
    def get_unread_count(self, request):
        count = Notification.objects.filter(recipient=request.user, is_read=False).count()
        return response.Response({'unread_count': count})

    @action(detail=False, methods=['post'])
    def mark_all_read(self, request):
        Notification.objects.filter(recipient=request.user, is_read=False).update(is_read=True)
        return response.Response({'message': 'success'})

    @action(detail=True, methods=['patch'])
    def mark_read(self, request, pk=None):
        try:
            notification = Notification.objects.get(pk=pk, recipient=request.user)
            notification.is_read = True
            notification.save()
            return response.Response({'message': 'success'})
        except Notification.DoesNotExist:
            return response.Response({'error': 'Notification not found'}, status=status.HTTP_404_NOT_FOUND)