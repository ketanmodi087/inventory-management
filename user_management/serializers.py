from django.shortcuts import get_object_or_404

from .models import User, Role, NotificationType, Notification
from rest_framework import serializers
from django.contrib.auth.models import Permission, Group
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework.exceptions import AuthenticationFailed
from django.utils.translation import gettext_lazy as _
from django.utils.text import slugify


class IMSTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        user = self.user
        if not user.is_active:
            raise AuthenticationFailed(_("User account is inactive."), code="user_inactive")
        return data


class PermissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Permission
        fields = ['id', 'name', 'codename']


class GroupSerializer(serializers.ModelSerializer):
    permissions = PermissionSerializer(many=True, read_only=True)
    code = serializers.SerializerMethodField()

    class Meta:
        model = Group
        fields = ['id', 'name', 'permissions', 'code']

    def get_code(self, obj):
        return slugify(obj.name)  # Generate a slug from the group name


class RoleSerializer(serializers.ModelSerializer):
    groups = serializers.SlugRelatedField(
                many=True,
                slug_field='name',  # Field to use for representation
                queryset=Group.objects.all()
            )

    class Meta:
        model = Role
        fields = ['id', 'name', 'code', 'description', 'groups']
        extra_kwargs = {
            'id': {'read_only': True},
            'name': {'error_messages': {'unique': "A role with that name already exists."}},
        }

    def update(self, instance, validated_data):
        groups = validated_data.pop('groups', None)
        if groups is not None:
            instance.groups.set(groups)
            for user in instance.users.all():
                user.groups.set(groups)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance


class UserSerializer(serializers.ModelSerializer):
    groups = serializers.SlugRelatedField(
                many=True,
                slug_field='name', # Field to use for representation
                read_only=True
            )
    role = serializers.SlugRelatedField(
                queryset=Role.objects.all(),
                slug_field='name',  # Field to use for representation
                error_messages={'does_not_exist': _("Role does not exist.")}
            )
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'email', 'role', 'first_name', 'last_name', 'is_active', 'groups', 'phone_number', 'full_name', 'password', 'username']
        extra_kwargs = {
            'id': {'read_only': True},
            'full_name': {'read_only': True},
            'groups': {'read_only': True},
            'role': {'required': True},
            'email': {'error_messages': {'unique': _("A user with that email already exists.")}},
            'password': {'write_only': True, 'min_length': 8, 'style': {'input_type': 'password'}, 'required': False},
        }

    def get_full_name(self, obj):
        return obj.get_full_name()

    def create(self, validated_data):
        role = validated_data.pop('role', None)
        if role:
            role_obj = get_object_or_404(Role, name=role)
            validated_data['role'] = role_obj
            groups = role_obj.groups.all()
        else:
            validated_data['role'] = None
            groups = []
        password = validated_data.pop('password', None)
        user = User(**validated_data)
        if password:
            user.set_password(password)
        user.save()
        user.groups.set(groups)
        return user

    def update(self, instance, validated_data):
        role = validated_data.pop('role', None)
        if role:
            role_obj = get_object_or_404(Role, name=role)
            validated_data['role'] = role_obj
            groups = role_obj.groups.all()
            # Update groups
            instance.groups.set(groups)
        else:
            validated_data['role'] = None
            instance.groups.clear()  # Clear groups if no role is provided
        password = validated_data.pop('password', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if password:
            instance.set_password(password)
        instance.save()
        return instance


class NotificationTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationType
        fields = ['id', 'name']

class NotificationSerializer(serializers.ModelSerializer):
    notification_type = NotificationTypeSerializer(read_only=True)
    class Meta:
        model = Notification
        fields = ['id', 'title', 'message', 'notification_type', 'alert_type', 'is_read', 'timestamp']
        read_only_fields = ['id', 'timestamp']