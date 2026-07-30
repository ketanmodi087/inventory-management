from rest_framework.routers import DefaultRouter
from django.urls import path, include
from . import views

router = DefaultRouter()
router.register("permissions", views.PermissionViewSet, basename="permission_readonly")
router.register("users", views.UserViewSet, basename="users_viewset")
router.register("groups", views.GroupViewSet, basename="group_readonly")
router.register("roles", views.RoleViewSet, basename="roles_viewset")
router.register("notifications", views.NotificationViewset, basename="notifications_viewset")


urlpatterns = [
    path("", include(router.urls)),
    path("me/", views.AuthUserDetailView.as_view(), name="auth_user_detail"),
]