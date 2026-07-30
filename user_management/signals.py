from django.db.models.signals import post_save
from django.dispatch import receiver
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from user_management.models import Notification

@receiver(post_save, sender=Notification)
def notification_created(sender, instance, created, **kwargs):
    if created:
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            'vra_user_{}'.format(instance.recipient.id),
            {
                "type": "send_notification",
                "message": instance.message,
                "timestamp": instance.timestamp.isoformat(),
                "title": instance.title,
                "alert_type": instance.alert_type,
                "notification_type": instance.notification_type.name if instance.notification_type else '',
                "is_read": instance.is_read,
                "id": instance.id,
                "recipient": instance.recipient.id,
            }
        )