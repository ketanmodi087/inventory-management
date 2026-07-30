import json
from asgiref.sync import async_to_sync
from channels.generic.websocket import AsyncWebsocketConsumer

class NotificationConsumer(AsyncWebsocketConsumer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user_id = None
        self.user_group_name = None

    async def connect(self):
        if self.scope["user"] and self.scope["user"].is_authenticated:
            self.user_id = self.scope["user"].id
            self.user_group_name = f"vra_user_{self.user_id}"

            await self.channel_layer.group_add(
                self.user_group_name,
                self.channel_name
            )
            await self.accept()
        else:
            await self.close()

    async def disconnect(self, close_code):
        if self.scope["user"] and self.scope["user"].is_authenticated:
            await self.channel_layer.group_discard(
                self.user_group_name,
                self.channel_name
            )

    async def send_notification(self, event):
        await self.send(text_data=json.dumps({
            'message': event.get('message', ''),
            'timestamp': event.get('timestamp', None),
            'title': event.get('title', ''),
            'alert_type': event.get('alert_type', ''),
            'notification_type': event.get('notification_type', ''),
            'is_read': event.get('is_read', False),
            'id': event.get('id', None),
            'recipient': event.get('recipient', None),
        }))


class SoftlandSyncAlertConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        await self.channel_layer.group_add(
            "SOFTLAND_SYNC_ALERT",
            self.channel_name
        )
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            "SOFTLAND_SYNC_ALERT",
            self.channel_name
        )

    async def task_notification(self, event):
        await self.send(text_data=json.dumps({
            'message': event.get('message', ''),
            'timestamp': event.get('timestamp', None),
            'alert_type': event.get('alert_type', 'info'),
        }))