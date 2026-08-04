# Example of a simplified JWT authentication middleware for Channels
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import AccessToken
from catalog_management.models import ApiAccessLog


@database_sync_to_async
def get_user(token):
    try:
        access_token = AccessToken(token)
        user_id = access_token['user_id']
        User = get_user_model()
        return User.objects.get(id=user_id)
    except Exception:
        return None


class JWTAuthMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        query_string = scope.get('query_string', b'').decode('utf-8')
        query_params = dict(qp.split('=') for qp in query_string.split('&') if '=' in qp)
        token = query_params.get('token')
        scope['user'] = None
        if token:
            user = await get_user(token)
            if user:
                scope['user'] = user

        return await self.app(scope, receive, send)


class ApiLoggingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        if request.user.is_authenticated and request.user.id != 1:
            ApiAccessLog.objects.create(
                user=request.user,
                endpoint=request.path,
                method=request.method,
                response_code=response.status_code
            )

        return response