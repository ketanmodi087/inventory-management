from django.db import models
from django.contrib.auth.models import AbstractUser, Group
from django.utils.translation import gettext_lazy as _
from .managers import UserManager
from django.utils.text import slugify


class Role(models.Model):
    """
    Model representing a role in the system.
    Roles can be assigned to users to define their permissions and access levels.
    """
    name = models.CharField(max_length=100, unique=True, verbose_name=_("role name"))
    description = models.TextField(blank=True, null=True, verbose_name=_("description"))
    code = models.CharField(
        max_length=50,
        verbose_name=_("role code"),
        help_text=_("Unique code for the role, used for identification."),
        error_messages={
            'unique': _("A role with that code already exists."),
            'blank': _("Role code cannot be blank."),
            'null': _("Role code cannot be null.")
        },
        null=True,
        blank=True,
        default=''  # Default value can be set as needed,
    )
    groups = models.ManyToManyField(
        Group,
        blank=True,
        related_name='roles',
        verbose_name=_("groups"),
        help_text=_("Groups associated with this role."),
    )

    def save(self, *args, **kwargs):
        if not self.code or self.code == "":  # Check if code is not set or still the placeholder
            self.code = slugify(self.name)
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = _("role")
        verbose_name_plural = _("roles")

    def __str__(self):
        return self.name


class User(AbstractUser):
    """
    Custom user model that extends the default Django user model.
    This model uses email as the unique identifier instead of username.
    """
    email = models.EmailField(unique=True, blank=False, null=False, error_messages={
        'unique': _("A user with that email already exists."),
        'blank': _("Email field cannot be blank."),
        'null': _("Email field cannot be null.")
    })
    phone_number = models.CharField(
        max_length=15,
        blank=True,
        null=True,
        verbose_name=_("phone number"),
        help_text=_("Optional phone number for the user."),
    )
    role = models.ForeignKey(
        Role,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='users',
        verbose_name=_("role"),
        help_text=_("Role assigned to the user."),
    )
    username = models.CharField(
        _("username"),
        max_length=150,
        null=True,
        default=None,
        unique=True,
        error_messages={
            "unique": _("A user with that username already exists."),
        },
    )
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    objects = UserManager()

    def get_full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    def __str__(self):
        return self.email


class NotificationType(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name=_("notification type name"))

    class Meta:
        verbose_name = _("notification type")
        verbose_name_plural = _("notification types")

    def __str__(self):
        return self.name


class Notification(models.Model):
    class NotificationAlertType(models.TextChoices):
        SUCCESS = 'SUCCESS', _('success')
        INFO = 'INFO', _('info')
        WARNING = 'WARNING', _('warning')
        ERROR = 'ERROR', _('error')

    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    title = models.CharField(max_length=100)
    message = models.CharField(max_length=255)
    notification_type = models.ForeignKey(NotificationType, on_delete=models.SET_NULL, null=True, blank=True)
    alert_type = models.CharField(max_length=50, choices=NotificationAlertType.choices, default='info')
    is_read = models.BooleanField(default=False)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Notification for {self.recipient.first_name}: {self.message[:50]}..."
