from django.core.management import BaseCommand
from user_management.models import User
from vra_backend.models import ERPADMINUsuario
from django.db import IntegrityError


class Command(BaseCommand):
    help = 'Sync users from Softland to the local database'

    def handle(self, *args, **kwargs):
        try:
            softland_users = ERPADMINUsuario.objects.filter(TIPO='U', ACTIVO='S').all()
            for su in softland_users:
                try:
                    user, created = User.objects.update_or_create(
                        username=su.USUARIO,
                        defaults={
                            'first_name': " ".join(su.NOMBRE.split(' ')[:-1]),
                            'last_name': " ".join(su.NOMBRE.split(' ')[-1:]),
                            'email': '%s@virgiliorodriguez.com' % su.USUARIO if not su.CORREO_ELECTRONICO else su.CORREO_ELECTRONICO,
                            'is_active': True,
                        }
                    )
                    if created:
                        user.set_password('VRA@2025')
                        user.save()
                except IntegrityError as ie:
                    user, created = User.objects.update_or_create(
                        username=su.USUARIO,
                        defaults={
                            'first_name': " ".join(su.NOMBRE.split(' ')[:-1]),
                            'last_name': " ".join(su.NOMBRE.split(' ')[-1:]),
                            'email': '%s@virgiliorodriguez.com' % su.USUARIO,
                            'is_active': True,
                        }
                    )
                    if created:
                        user.set_password('VRA@2025')
                        user.save()
                    self.stderr.write(self.style.ERROR(f'Integrity error for user {su.USUARIO}: {ie}'))
            self.stdout.write(self.style.SUCCESS('Successfully synced users from Softland'))
        except Exception as e:
            self.stderr.write(self.style.ERROR(f'An unexpected error occurred: {e}'))