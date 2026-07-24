import django_filters
from .models import SolicitudOc, OrdenCompra, Embarque, AuditTransInv, LowStockView

class SolicitudOcFilter(django_filters.FilterSet):
    FECHA_REQUERIDA = django_filters.DateFromToRangeFilter(field_name='FECHA_REQUERIDA__date')

    class Meta:
        model = SolicitudOc
        fields = ['FECHA_REQUERIDA', 'ESTADO', 'USUARIO', 'PRIORIDAD', 'DEPARTAMENTO']


class OrdenCompraFilter(django_filters.FilterSet):
    FECHA_HORA = django_filters.DateFromToRangeFilter(field_name='FECHA_HORA__date')

    class Meta:
        model = OrdenCompra
        fields = ['ESTADO', 'USUARIO', 'PRIORIDAD', 'DEPARTAMENTO', 'FECHA_HORA']

class EmbarqueFilter(django_filters.FilterSet):
    FECHA_EMBARQUE = django_filters.DateFromToRangeFilter(field_name='FECHA_EMBARQUE__date')

    class Meta:
        model = Embarque
        fields = ['ESTADO', 'PROVEEDOR', 'FECHA_EMBARQUE', 'CRM']


class AuditTransInvFilter(django_filters.FilterSet):
    FECHA_HORA = django_filters.DateFromToRangeFilter(field_name='FECHA_HORA__date')

    class Meta:
        model = AuditTransInv
        fields = ['APLICACION', 'USUARIO', 'ASIENTO', 'MODULO_ORIGEN', 'FECHA_HORA']


class LowStockFilter(django_filters.FilterSet):
    availability_perc = django_filters.RangeFilter()

    class Meta:
        model = LowStockView
        fields = ['ARTICULO', 'PO_ESTADO', 'SHIP_ESTADO', 'PROVEEDOR', 'availability_perc']