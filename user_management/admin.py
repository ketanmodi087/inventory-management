from django.contrib import admin
from .models import User, Role, NotificationType
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.forms import BaseUserCreationForm, UserChangeForm
from django.core.exceptions import ValidationError


class CustomUserChangeForm(UserChangeForm):
    """Custom form for changing user details, using email as the username."""

    class Meta(UserChangeForm.Meta):
        model = User
        fields = "__all__"
        labels = {
            "groups": _("Groups"),
            "first_name": _("First Name"),
            "last_name": _("Last Name"),
            "phone_number": _("Phone Number"),
            "email": _("Email Address"),
            "role": _("Role"),
        }

    def clean_email(self):
        """Ensure that the email is unique and not already in use."""
        email = self.cleaned_data.get("email")
        if email and self._meta.model.objects.filter(email__iexact=email).exclude(pk=self.instance.pk).exists():
            self._update_errors(
                ValidationError(
                    {
                        "email": self.instance.unique_error_message(
                            self._meta.model, ["email"]
                        )
                    }
                )
            )
        else:
            return email


# class CustomUserCreationForm(BaseUserCreationForm):
#     """Custom form for creating new users with email as the username."""
#
#     class Meta(BaseUserCreationForm.Meta):
#         model = User
#         fields = ("email",)
#
#     def clean_email(self):
#         """Ensure that the email is unique and not already in use."""
#         email = self.cleaned_data.get("email")
#         if email and self._meta.model.objects.filter(email__iexact=email).exists():
#             self._update_errors(
#                 ValidationError(
#                     {
#                         "email": self.instance.unique_error_message(
#                             self._meta.model, ["email"]
#                         )
#                     }
#                 )
#             )
#         else:
#             return email
#
#     def save(self, commit=True):
#         user = super().save(commit=False)
#         user.set_password(self.cleaned_data["password1"])
#         if commit:
#             user.save()
#         return user


# class AdminUserCreationForm(SetUnusablePasswordMixin, CustomUserCreationForm):
#
#     usable_password = SetUnusablePasswordMixin.create_usable_password_field()
#
#     def __init__(self, *args, **kwargs):
#         super().__init__(*args, **kwargs)
#         self.fields["password1"].required = False
#         self.fields["password2"].required = False


class UserAdmin(BaseUserAdmin):
    form = CustomUserChangeForm
    # add_form = AdminUserCreationForm
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        (_("Personal info"), {"fields": ("first_name", "last_name", "phone_number")}),
        (
            _("Permissions"),
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "role",
                ),
            },
        ),
        (_("Important dates"), {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "usable_password", "password1", "password2"),
            },
        ),
    )
    list_display = ("email", "first_name", "last_name", "is_staff", "role")
    list_filter = ("is_staff", "is_superuser", "is_active", "groups")
    search_fields = ("first_name", "last_name", "email")
    ordering = ("email",)
    filter_horizontal = ('groups',)


admin.site.register(User, UserAdmin)
admin.site.register(Role)
admin.site.register(NotificationType)
