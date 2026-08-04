# db_routers.py
class MSSQLRouter:
    route_app_labels = {'VRA', 'vra_backend'}

    def db_for_read(self, model, **hints):
        if model._meta.app_label in self.route_app_labels:
            return 'mssql_db'
        return None

    def db_for_write(self, model, **hints):
        # Prevent writes to models in VRA
        if model._meta.app_label in self.route_app_labels:
            return 'mssql_db'  # Directs writes to mssql_db, but consider if you want to explicitly prevent them.
        return None

    def allow_relation(self, obj1, obj2, **hints):
        # Allow relations between models within the same database
        if (obj1._meta.app_label in self.route_app_labels or
                obj2._meta.app_label in self.route_app_labels):
            return True
        return None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        if app_label in self.route_app_labels:
            return False
        return None