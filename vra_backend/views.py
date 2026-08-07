from django.shortcuts import render
from rest_framework.response import Response
from .serializers import (
    VRAArticuloSerializer, VRAProveedorSerializer, VRASolicitudOcSerializer, VRAOrdenCompraSerializer,
    VRADepartmentoSerializer, VRADocumentoEmbarqueSerializer, VRAEmbarqueSerializer, VRABodegaSerializer,
    ERPADMINUsuarioSerializer, VRAExistenciaBodegaSerializer
)
from .models import (
    VRAArticulo, VRAProveedor, VRASolicitudOc, VRAOrdenCompra, VRADepartamento, VRADocumentoEmbarque,
    VRAEmbarque, VRABodega, ERPADMINUsuario, VRAExistenciaBodega
)
from rest_framework import viewsets, views
from rest_framework.permissions import AllowAny
from django.db import connections


class ArticuloViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for listing and retrieving Articulo.
    This viewset provides read-only access to the Articulo in the system.
    """
    serializer_class = VRAArticuloSerializer
    queryset = VRAArticulo.objects.all()
    search_fields = ['ARTICULO', 'DESCRIPCION', 'CLASIFICACION_1']  # Allow searching by email, first name, and last name
    ordering_fields = ['ARTICULO', 'DESCRIPCION', 'CLASIFICACION_1']  # Allow ordering by these fields
    ordering = ['ARTICULO']

class VRAProveedorViewset(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for listing and retrieving Proveedor.
    This viewset provides read-only access to the Proveedor in the system.
    """
    serializer_class = VRAProveedorSerializer
    permission_classes = [AllowAny]
    queryset = VRAProveedor.objects.all()
    search_fields = ['PROVEEDOR', 'NOMBRE', 'E_MAIL', 'CONTACTO']  # Allow searching by email, first name, and last name
    ordering_fields = ['PROVEEDOR', 'NOMBRE', 'E_MAIL', 'CONTACTO']  # Allow ordering by these fields
    ordering = ['-RecordDate']


class VRASolicitudOcViewset(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for listing and retrieving Solicitud OC.
    This viewset provides read-only access to the Solicitud OC in the system.
    """
    permission_classes = [AllowAny]
    serializer_class = VRASolicitudOcSerializer
    queryset = VRASolicitudOc.objects.all()
    search_fields = ['SOLICITUD_OC']  # Allow searching by email, first name, and last name
    ordering_fields = ['SOLICITUD_OC']  # Allow ordering by these fields
    ordering = ['SOLICITUD_OC']

class VRAOrdenCompraViewset(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for listing and retrieving Orden Compra.
    This viewset provides read-only access to the Orden Compra in the system.
    """
    permission_classes = [AllowAny]
    serializer_class = VRAOrdenCompraSerializer
    queryset = VRAOrdenCompra.objects.all()
    search_fields = ['ORDEN_COMPRA', 'PROVEEDOR', 'BODEGA']  # Allow searching by email, first name, and last name
    ordering_fields = ['ORDEN_COMPRA', 'PROVEEDOR', 'BODEGA']  # Allow ordering by these fields
    ordering = ['-ORDEN_COMPRA']

class VRADepartmentoViewset(viewsets.ReadOnlyModelViewSet):

    permission_classes = [AllowAny]
    serializer_class = VRADepartmentoSerializer
    queryset = VRADepartamento.objects.all()


class VRADocumentoEmbarqueViewset(viewsets.ReadOnlyModelViewSet):

    permission_classes = [AllowAny]
    serializer_class = VRADocumentoEmbarqueSerializer
    queryset = VRADocumentoEmbarque.objects.all()
    ordering = ['-RecordDate']


class VRAEmbarqueViewset(viewsets.ReadOnlyModelViewSet):

    permission_classes = [AllowAny]
    serializer_class = VRAEmbarqueSerializer
    queryset = VRAEmbarque.objects.all()
    ordering = ['-RecordDate']


class VRABodegaViewset(viewsets.ReadOnlyModelViewSet):
    permission_classes = [AllowAny]
    serializer_class = VRABodegaSerializer
    queryset = VRABodega.objects.all()
    ordering = ['-RecordDate']


class ERPADMINUsuarioViewset(viewsets.ReadOnlyModelViewSet):
    permission_classes = [AllowAny]
    serializer_class = ERPADMINUsuarioSerializer
    queryset = ERPADMINUsuario.objects.filter(ACTIVO='S', TIPO='U').all()
    ordering = ['-RecordDate']

class ArticuloListView(views.APIView):

    def get(self, request):
        custom_join_sql = """
            SELECT eb."BODEGA",
                eb."ARTICULO",
                a."TIPO_COSTO",
                eb."CANT_DISPONIBLE",
                eb."CANT_RESERVADA",
                eb."CANT_NO_APROBADA",
                eb."CANT_VENCIDA",
                eb."CANT_REMITIDA",
                eb."COSTO_UNT_ESTANDAR_LOC",
                eb."COSTO_UNT_ESTANDAR_DOL",
                eb."COSTO_UNT_PROMEDIO_LOC",
                eb."COSTO_UNT_PROMEDIO_DOL"
             FROM [VRA].[EXISTENCIA_BODEGA] eb
             JOIN [VRA].[ARTICULO] a ON eb."ARTICULO" = a."ARTICULO"
        """
        with connections['mssql_db'].cursor() as cursor:
            cursor.execute(custom_join_sql)
            rows = cursor.fetchall()

        return Response(list(rows))