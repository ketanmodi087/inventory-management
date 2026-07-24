from dateutil.relativedelta import relativedelta
from django.db import connection, transaction
from django.db.models import (
    Q, F, Sum, ExpressionWrapper, OuterRef, Subquery, FloatField, Value, DecimalField,
    Count, Max, Func, Case, When, CharField, IntegerField
)
from decimal import Decimal
from django.contrib.postgres.aggregates import ArrayAgg
from django.db.models.functions import Coalesce, ExtractDay, Now, TruncMonth
from rest_framework.exceptions import NotFound, ValidationError
from .serializers import (
    ArticuloDetailSerializer, ItemMasterSerializer, SolicitudOcDetailSerializer, ArticuloSearchSerializer,
    SolicitudOcSerializer, DepartamentoSerializer, OrdenCompraDetailSerializer, ProveedorSearchSerializer,
    OrdenCompraSerializer, EmbarqueSerializer, DocumentoEmbarqueSerializer, ArticuloProveedorDetailSerializer,
    EmbarqueDetailSerializer, ProveedorSerializer, AuditTransInvDetailSerializer, AuditTransInvSerializer,
    LowStockViewSerializer, OrdenCompraRequestSerializer, ProveedorDetailSerializer, CuentaContableSerializer,
    CentroCostoSerializer, EmbarqueRequestSerializer, ExistenciaLoteSerializer, ConversionRateRequestSerializer,
    ArticuloProveedorRequestSerializer, SolicitudCompraRequestSerializer, LocalizacionSerializer,
    PaqueteInventarioSerializer, ConsecutivoCiSerializer, DocumentoInvSerializer, DocumentoInvDetailSerializer,
    StockTransferRequestSerializer, EmailFormSerializer, EmailFormAttachmentsSerializer, InventoryAuditViewSerializer,
    InventoryAuditDetailViewSerializer, CycleCountBatchSerializer, CycleCountTaskSerializer, ArticuloSerializer,
    CycleCountTaskStatusSerializer, SarimaForecastSerializer, ProphetForecastSerializer, HoltWintersForecastSerializer,
    AgingInventorySummarySerializer, SPDispatchHeaderSerializer, SPReturnHeaderSerializer,
    SPDispatchItemActionSerializer, SPReturnItemActionSerializer, StandaloneArticuloSerializer
)
from .models import (
    Articulo, ItemMasterView, SolicitudOc, Departamento, OrdenCompra, Embarque, DocumentoEmbarque, Proveedor,
    AuditTransInv, ArticuloProveedor, LowStockView, ExistenciaLote, GlobalesCo, Bodega,
    ResponSeguimiento, MonedaHist, Localizacion, PaqueteInventario, ConsecutivoCi, DocumentoInv, InventoryAuditView,
    ItemsSalesHistory, ExistenciaBodega, Clasificacion, ArticuloCompra, CycleCountBatch, CycleCountTask,
    LineaDocInv, ProphetForecast, SarimaForecast, HoltWintersForecast, ProphetForecastView, SarimaForecastView,
    HoltWintersForecastView, OrdenCompraLinea, TransaccionInv, Factura, ABCValueView, ABCUsageView, AjusteConfig,
    CentroCosto, CuentaContable, AgingInventorySummary, ItemLeadDaysView, SPDispatchHeader, SPReturnHeader,
    SPReturnItem, SPDispatchItem, ArticuloCuenta, Impuesto
)
from user_management.models import Role
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import viewsets, status, views
from .filters import SolicitudOcFilter, OrdenCompraFilter, EmbarqueFilter, AuditTransInvFilter, LowStockFilter
from .atomic import (
    create_purchase_order, create_shipment, update_purchase_order, update_em_shipment, create_purchase_request,
    update_purchase_request, create_location, approve_purchase_request, approve_purchase_order, approve_shipment,
    disapprove_shipment, disapprove_purchase_request, disapprove_purchase_order, cancel_purchase_request,
    cancel_purchase_order, cancel_shipment, create_inter_inv_stock_transfer, approve_inter_inv_stock_transfer,
    apply_inter_inv_stock_transfer, disapprove_inter_inv_stock_transfer, cancel_inter_inv_stock_transfer,
    update_inter_inv_stock_transfer, create_stock_transfer_adjustment, apply_stock_transfer_adjustment
)
from vra_backend.models import VRAConsecutivoCi, VRAGlobalesCo, VRAExistenciaLote
from django.conf import settings
from django.core.mail import send_mail, EmailMultiAlternatives
from django.utils.html import strip_tags
from datetime import datetime, timedelta, date
from IMS.utility import get_forecast_reviews, send_applied_stocktransfer_alert
import qrcode
import os
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm, inch
from reportlab.lib.enums import TA_CENTER
from io import BytesIO
import barcode
from barcode.writer import ImageWriter
from PIL import Image as PILImage
import boto3
import uuid
from email.message import EmailMessage




class ArticuloViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for retrieving Articulo.
    This viewset provides read-only access to the Articulo in the system.
    """
    serializer_class = ArticuloDetailSerializer
    queryset = Articulo.objects.all()


class PaqueteInventarioViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for retrieving PaqueteInventario.
    This viewset provides read-only access to the PaqueteInventario in the system.
    """
    serializer_class = PaqueteInventarioSerializer
    queryset = PaqueteInventario.objects.all()
    ordering = ['-CreateDate']


class ConsecutivoCiViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for retrieving ConsecutivoCi.
    This viewset provides read-only access to the ConsecutivoCi in the system.
    """
    serializer_class = ConsecutivoCiSerializer
    queryset = ConsecutivoCi.objects.all()
    ordering = ['-CreateDate']


class DocumentoInvViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for retrieving DocumentoInv.
    This viewset provides read-only access to the DocumentoInv in the system.
    """
    serializer_class = DocumentoInvSerializer
    queryset = DocumentoInv.objects.all()
    search_fields = ['DOCUMENTO_INV', 'REFERENCIA', 'PAQUETE_INVENTARIO']
    ordering = ['-CreateDate']


class DocumentoInvDetailViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for retrieving DocumentoInv.
    This viewset provides read-only access to the DocumentoInv in the system.
    """
    serializer_class = DocumentoInvDetailSerializer
    queryset = DocumentoInv.objects.all()
    lookup_field = 'DOCUMENTO_INV'
    ordering = ['-CreateDate']


class StokTransferViewset(viewsets.ViewSet):
    @action(detail=False, methods=['get'])
    def search_articulos(self, request):
        items = Articulo.objects.filter(Q(ARTICULO__icontains=request.query_params.get('search', '')) | Q(
            DESCRIPCION__icontains=request.query_params.get('search', '')))[:25]
        serializer = ArticuloSearchSerializer(items, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def consecutivo_ci(self, request):
        items = ConsecutivoCi.objects.filter(CONSECUTIVO="TRASPASO").all()
        serializer = ConsecutivoCiSerializer(items, many=True)
        items = PaqueteInventario.objects.order_by('-FECHA_ULT_ACCESO').all()
        paquetes = PaqueteInventarioSerializer(items, many=True)
        return Response({'consecutivo': serializer.data, 'paquetes': paquetes.data})

    @action(detail=False, methods=['get'])
    def search_localizacion(self, request):
        if not request.query_params.get('search', None):
            queryset = ExistenciaLote.objects.filter(
                ARTICULO=request.query_params.get('articulo', ''), BODEGA=request.query_params.get('bodega', 'A001'))
            existencia = ExistenciaLoteSerializer(queryset, many=True).data
            return Response(existencia)
        items = Localizacion.objects.filter(LOCALIZACION__icontains=request.query_params.get('search', ''),
                                            BODEGA=request.query_params.get('bodega', 'A001'))[:10]
        serializer = LocalizacionSerializer(items, many=True)
        locations = serializer.data
        return Response(locations)

    @action(detail=False, methods=['post'])
    def create_stock_transfer(self, request):
        serializer = StockTransferRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        if serializer.data['CONSECUTIVO'] != 'TRASPASO':
            return Response({"error": "Operation not allowed."}, status=status.HTTP_400_BAD_REQUEST)
        consecutivo_ci = VRAConsecutivoCi.objects.filter(CONSECUTIVO="TRASPASO").first()
        if serializer.data['DOCUMENTO_INV'] != consecutivo_ci.SIGUIENTE_CONSEC:
            return Response({"error": "Invalid DOCUMENTO_INV."}, status=status.HTTP_400_BAD_REQUEST)
        lineas = serializer.data['lineas']
        for line in lineas:
            existencia_lote = ExistenciaLote.objects.filter(
                ARTICULO=line['ARTICULO'], BODEGA=line['BODEGA'], LOCALIZACION=line['LOCALIZACION'], LOTE='ND').first()
            if float(existencia_lote.CANT_DISPONIBLE) < float(line['CANTIDAD']):
                return Response(
                    {"error": f"Insufficient stock for article {line['ARTICULO']} in location {line['LOCALIZACION']}."},
                    status=status.HTTP_400_BAD_REQUEST)
        try:
            create_inter_inv_stock_transfer(serializer.validated_data,
                                            request.user.username if request.user.username else 'DEVELOPER')
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        return Response({"message": "Stock Transfer created successfully."}, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['put'])
    def update_stock_transfer(self, request):
        serializer = StockTransferRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        documento_inv = serializer.data.get('DOCUMENTO_INV')
        if serializer.data['CONSECUTIVO'] != 'TRASPASO':
            return Response({"error": "Operation not allowed."}, status=status.HTTP_400_BAD_REQUEST)
        documento = DocumentoInv.objects.filter(DOCUMENTO_INV=documento_inv).first()
        if documento and documento.APROBADO == 'S':
            return Response({"error": "Stock Transfer can not be updated.."},
                            status=status.HTTP_400_BAD_REQUEST)
        try:
            update_inter_inv_stock_transfer(documento_inv, serializer.validated_data,
                                            request.user.username if request.user.username else 'DEVELOPER')
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        return Response({"message": "Stock Transfer updated successfully."}, status=status.HTTP_200_OK)

    @action(detail=False, methods=['patch'])
    def approve_stock_transfer(self, request):
        documento_inv = request.data.get('DOCUMENTO_INV', None)
        if not documento_inv:
            return Response({"error": "DOCUMENTO_INV is required."}, status=status.HTTP_400_BAD_REQUEST)
        documento = DocumentoInv.objects.filter(DOCUMENTO_INV=documento_inv).first()
        if not documento:
            return Response({"error": "Stock Transfer not found."}, status=status.HTTP_404_NOT_FOUND)
        if documento.CONSECUTIVO != 'TRASPASO':
            return Response({"error": "Operation not allowed."}, status=status.HTTP_400_BAD_REQUEST)
        if documento and documento.APROBADO == 'S':
            return Response({"error": "Transfer already approved."},
                            status=status.HTTP_400_BAD_REQUEST)
        try:
            approve_inter_inv_stock_transfer(documento_inv,
                                             request.user.username if request.user.username else 'DEVELOPER')
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        return Response({"message": "Stock Transfer approved successfully."}, status=status.HTTP_200_OK)

    @action(detail=False, methods=['patch'])
    def disapprove_stock_transfer(self, request):
        documento_inv = request.data.get('DOCUMENTO_INV', None)
        if not documento_inv:
            return Response({"error": "DOCUMENTO_INV is required."}, status=status.HTTP_400_BAD_REQUEST)
        documento = DocumentoInv.objects.filter(DOCUMENTO_INV=documento_inv).first()
        if not documento:
            return Response({"error": "Stock Transfer not found."}, status=status.HTTP_404_NOT_FOUND)
        if documento.CONSECUTIVO != 'TRASPASO':
            return Response({"error": "Operation not allowed."}, status=status.HTTP_400_BAD_REQUEST)
        if documento and documento.APROBADO != 'S':
            return Response({"error": "Stock Transfer is not approved yet."},
                            status=status.HTTP_400_BAD_REQUEST)
        try:
            disapprove_inter_inv_stock_transfer(documento_inv)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        return Response({"message": "Stock Transfer disapproved successfully."}, status=status.HTTP_200_OK)

    @action(detail=False, methods=['patch'])
    def cancel_stock_transfer(self, request):
        documento_inv = request.data.get('DOCUMENTO_INV', None)
        if not documento_inv:
            return Response({"error": "DOCUMENTO_INV is required."}, status=status.HTTP_400_BAD_REQUEST)
        documento = DocumentoInv.objects.filter(DOCUMENTO_INV=documento_inv).first()
        if not documento:
            return Response({"error": "Stock Transfer not found."}, status=status.HTTP_404_NOT_FOUND)
        if documento.CONSECUTIVO != 'TRASPASO':
            return Response({"error": "Operation not allowed."}, status=status.HTTP_400_BAD_REQUEST)
        if documento and documento.APROBADO == 'S':
            return Response({"error": "Approved Stock Transfer cannot be canceled."},
                            status=status.HTTP_400_BAD_REQUEST)
        try:
            cancel_inter_inv_stock_transfer(documento_inv,
                                            request.user.username if request.user.username else 'DEVELOPER')
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        return Response({"message": "Stock Transfer canceled successfully."}, status=status.HTTP_200_OK)

    @action(detail=False, methods=['patch'])
    def apply_stock_transfer(self, request):
        documento_inv = request.data.get('DOCUMENTO_INV', None)
        if not documento_inv:
            return Response({"error": "DOCUMENTO_INV is required."}, status=status.HTTP_400_BAD_REQUEST)
        documento = DocumentoInv.objects.filter(DOCUMENTO_INV=documento_inv).first()
        if not documento:
            return Response({"error": "Stock Transfer not found."}, status=status.HTTP_404_NOT_FOUND)
        if documento.CONSECUTIVO != 'TRASPASO':
            return Response({"error": "Operation not allowed."}, status=status.HTTP_400_BAD_REQUEST)
        if documento and documento.APROBADO != 'S':
            return Response({"error": "Transfer is not approved yet."},
                            status=status.HTTP_400_BAD_REQUEST)
        lineas = LineaDocInv.objects.filter(DOCUMENTO_INV=documento_inv)
        for line in lineas:
            existencia_lote = ExistenciaLote.objects.filter(
                ARTICULO=line.ARTICULO, BODEGA=line.BODEGA, LOCALIZACION=line.LOCALIZACION, LOTE='ND').first()
            if float(existencia_lote.CANT_DISPONIBLE) < float(line.CANTIDAD):
                return Response(
                    {"error": f"Insufficient stock for article {line.ARTICULO} in location {line.LOCALIZACION}."},
                    status=status.HTTP_400_BAD_REQUEST)
        try:
            apply_inter_inv_stock_transfer(documento_inv,
                                           request.user.username if request.user.username else 'DEVELOPER')
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        return Response({"message": "Stock Transfer applied successfully."}, status=status.HTTP_200_OK)


class SolicitudCompraViewset(viewsets.ViewSet):

    @action(detail=False, methods=['get'])
    def search_articulos(self, request):
        # query = SearchQuery(request.query_params.get('search', ''))
        # search_vector = SearchVector('ARTICULO')
        # items = Articulo.objects.annotate(
        #     search=search_vector,
        #     rank=SearchRank(search_vector, query)
        # ).filter(search=query).order_by('-rank')[:10]
        items = Articulo.objects.filter(Q(ARTICULO__icontains=request.query_params.get('search', '')) | Q(
            DESCRIPCION__icontains=request.query_params.get('search', '')))[:25]
        serializer = ArticuloSearchSerializer(items, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def list_centro_costo(self, request):
        items = CentroCosto.objects.order_by('CENTRO_COSTO')
        serializer = CentroCostoSerializer(items, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def list_cuenta_contable(self, request):
        items = CuentaContable.objects.order_by('CUENTA_CONTABLE')
        serializer = CuentaContableSerializer(items, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def list_departments(self, request):
        items = Departamento.objects.filter(ACTIVO="S")
        serializer = DepartamentoSerializer(items, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['post'])
    def submit_request(self, request):
        serializer = SolicitudCompraRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        department = Departamento.objects.filter(DEPARTAMENTO=serializer.data['DEPARTAMENTO'], ACTIVO='S').first()
        if not department:
            return Response({"error": "Invalid Department."}, status=status.HTTP_400_BAD_REQUEST)
        vra_globals = VRAGlobalesCo.objects.first()
        index = int(vra_globals.ULT_SOLICITUD[2:])
        new_order = 'SC' + str(index + 1).zfill(len(vra_globals.ULT_SOLICITUD[2:]))
        if serializer.data['SOLICITUD_OC'] == new_order:
            try:
                serializer.validated_data['USUARIO'] = request.user.username if request.user.username else 'DEVELOPER'
                serializer.validated_data[
                    'CreatedBy'] = 'CO/%s' % request.user.username if request.user.username else 'CO/DEVELOPER'
                serializer.validated_data[
                    'UpdatedBy'] = 'CO/%s' % request.user.username if request.user.username else 'CO/DEVELOPER'
                create_purchase_request(serializer.validated_data)
            except Exception as e:
                return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            return Response({"message": "Purchase Request submitted successfully."}, status=status.HTTP_201_CREATED)
        else:
            return Response({"error": "Invalid Purchase Request."}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['put'])
    def update_request(self, request):
        serializer = SolicitudCompraRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        solicitud_oc = serializer.data.get('SOLICITUD_OC')
        update_fields = {key: value for key, value in serializer.validated_data.items() if key != 'SOLICITUD_OC'}
        try:
            update_fields['UpdatedBy'] = 'CO/%s' % request.user.username if request.user.username else 'CO/DEVELOPER'
            update_purchase_request(solicitud_oc, update_fields)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        return Response({"message": "Purchase Request updated successfully."}, status=status.HTTP_200_OK)

    @action(detail=False, methods=['patch'])
    def approve_request(self, request):
        solicitud_oc = request.data.get('SOLICITUD_OC', None)
        if not solicitud_oc:
            return Response({"error": "SOLICITUD_OC is required."}, status=status.HTTP_400_BAD_REQUEST)
        solicitude = SolicitudOc.objects.filter(SOLICITUD_OC=solicitud_oc).first()
        if solicitude and solicitude.ESTADO != 'A':
            return Response({"error": "Only requests in Planeada state can be approved."},
                            status=status.HTTP_400_BAD_REQUEST)
        try:
            approve_purchase_request(solicitud_oc, request.user.username if request.user.username else 'DEVELOPER')
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        return Response({"message": "Purchase Request approved successfully."}, status=status.HTTP_200_OK)

    @action(detail=False, methods=['patch'])
    def disapprove_request(self, request):
        solicitud_oc = request.data.get('SOLICITUD_OC', None)
        if not solicitud_oc:
            return Response({"error": "SOLICITUD_OC is required."}, status=status.HTTP_400_BAD_REQUEST)
        solicitude = SolicitudOc.objects.filter(SOLICITUD_OC=solicitud_oc).first()
        if solicitude and solicitude.ESTADO != 'E':
            return Response({"error": "Only requests in No Asignada state can be disapproved."},
                            status=status.HTTP_400_BAD_REQUEST)
        try:
            disapprove_purchase_request(solicitud_oc)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        return Response({"message": "Purchase Request disapproved successfully."}, status=status.HTTP_200_OK)

    @action(detail=False, methods=['patch'])
    def cancel_request(self, request):
        solicitud_oc = request.data.get('SOLICITUD_OC', None)
        comment = request.data.get('COMMENT', '')
        if not solicitud_oc:
            return Response({"error": "SOLICITUD_OC is required."}, status=status.HTTP_400_BAD_REQUEST)
        solicitude = SolicitudOc.objects.filter(SOLICITUD_OC=solicitud_oc).first()
        if solicitude and solicitude.ESTADO != 'A':
            return Response({"error": "Only requests in Planeada state can be cancelled."},
                            status=status.HTTP_400_BAD_REQUEST)
        try:
            cancel_purchase_request(solicitud_oc, request.user.username if request.user.username else 'DEVELOPER',
                                    comment)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        return Response({"message": "Purchase Request canceled successfully."}, status=status.HTTP_200_OK)


class PurchaseOrderViewset(viewsets.ViewSet):
    @action(detail=False, methods=['get'])
    def articulo_proveedor(self, request):
        serializer = ArticuloProveedorRequestSerializer(data=request.query_params)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        items = ArticuloProveedor.objects.filter(ARTICULO=serializer.data['articulo'],
                                                 PROVEEDOR=serializer.data['proveedor']).all()
        serializer = ArticuloProveedorDetailSerializer(items, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def responsible_seguimiento(self, request):
        return Response(ResponSeguimiento.objects.values('RESPON_SEGUIMIENTO', 'ESTADO', 'EMPLEADO'))

    @action(detail=False, methods=['get'])
    def search_articulos(self, request):
        # query = SearchQuery(request.query_params.get('search', ''))
        # search_vector = SearchVector('ARTICULO')
        # items = Articulo.objects.annotate(
        #     search=search_vector,
        #     rank=SearchRank(search_vector, query)
        # ).filter(search=query).order_by('-rank')[:10]
        items = Articulo.objects.filter(Q(ARTICULO__icontains=request.query_params.get('search', '')) | Q(
            DESCRIPCION__icontains=request.query_params.get('search', '')))[:25]
        serializer = ArticuloSearchSerializer(items, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def list_centro_costo(self, request):
        items = CentroCosto.objects.order_by('CENTRO_COSTO')
        serializer = CentroCostoSerializer(items, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def list_cuenta_contable(self, request):
        items = CuentaContable.objects.order_by('CUENTA_CONTABLE')
        serializer = CuentaContableSerializer(items, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def conversion_rate(self, request):
        serializer = ConversionRateRequestSerializer(data=request.query_params)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        montos = MonedaHist.objects.filter(MONEDA=serializer.data['moneda'],
                                           FECHA__date__lte=serializer.data['fecha']).order_by('-FECHA')[:1]
        if not montos.exists():
            return Response({"error": "No conversion rate found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(montos.values('MONEDA', 'MONTO', 'FECHA'))

    @action(detail=False, methods=['get'])
    def search_proveedors(self, request):
        # query = SearchQuery(request.query_params.get('search', ''))
        # search_vector = SearchVector('PROVEEDOR')
        # results = Proveedor.objects.annotate(
        #     search=sea
        #     rch_vector,
        #     rank=SearchRank(search_vector, query)
        # ).filter(search=query).order_by('-rank')[:10]
        items = Proveedor.objects.filter(Q(PROVEEDOR__icontains=request.query_params.get('search', '')) | Q(
            NOMBRE__icontains=request.query_params.get('search', '')))[:10]
        serializer = ProveedorSearchSerializer(items, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['post'])
    def submit_order(self, request):
        serializer = OrdenCompraRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        vra_globals = VRAGlobalesCo.objects.first()
        index = int(vra_globals.ULT_ORDEN_COMPRA[2:])
        new_order = 'OC' + str(index + 1).zfill(len(vra_globals.ULT_ORDEN_COMPRA[2:]))
        if serializer.data['ORDEN_COMPRA'] == new_order:
            try:
                create_purchase_order(serializer.validated_data)
            except Exception as e:
                return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            return Response({"message": "Order submitted successfully."}, status=status.HTTP_201_CREATED)
        else:
            return Response({"error": "Invalid Purchase Order."}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['put'])
    def update_order(self, request):
        serializer = OrdenCompraRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        orden_compra = serializer.data.get('ORDEN_COMPRA')
        update_fields = {key: value for key, value in serializer.validated_data.items() if key != 'ORDEN_COMPRA'}
        try:
            update_purchase_order(orden_compra, update_fields)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        return Response({"message": "Order updated successfully."}, status=status.HTTP_200_OK)

    @action(detail=False, methods=['patch'])
    def approve_order(self, request):
        orden_compra = request.data.get('ORDEN_COMPRA', None)
        if not orden_compra:
            return Response({"error": "ORDEN_COMPRA is required."}, status=status.HTTP_400_BAD_REQUEST)
        orden = OrdenCompra.objects.filter(ORDEN_COMPRA=orden_compra).first()
        if orden and orden.ESTADO != 'A':
            return Response({"error": "Only orders in Planeada state can be approved."},
                            status=status.HTTP_400_BAD_REQUEST)
        if orden and orden.RESPON_SEGUIMIENTO != request.user.username:
            return Response({"error": "You are not authorized to approve this order."},
                            status=status.HTTP_403_FORBIDDEN)
        try:
            approve_purchase_order(orden_compra, request.user.username if request.user.username else 'DEVELOPER')
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        return Response({"message": "Purchase Order approved successfully."}, status=status.HTTP_200_OK)

    @action(detail=False, methods=['patch'])
    def disapprove_order(self, request):
        orden_compra = request.data.get('ORDEN_COMPRA', None)
        if not orden_compra:
            return Response({"error": "ORDEN_COMPRA is required."}, status=status.HTTP_400_BAD_REQUEST)
        orden = OrdenCompra.objects.filter(ORDEN_COMPRA=orden_compra).first()
        if orden and orden.ESTADO != 'E':
            return Response({"error": "Only orders in Tránsito state can be disapproved."},
                            status=status.HTTP_400_BAD_REQUEST)
        try:
            disapprove_purchase_order(orden_compra, request.user.username if request.user.username else 'DEVELOPER')
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        return Response({"message": "Purchase Order disapproved successfully."}, status=status.HTTP_200_OK)

    @action(detail=False, methods=['patch'])
    def cancel_order(self, request):
        orden_compra = request.data.get('ORDEN_COMPRA', None)
        if not orden_compra:
            return Response({"error": "ORDEN_COMPRA is required."}, status=status.HTTP_400_BAD_REQUEST)
        orden = OrdenCompra.objects.filter(ORDEN_COMPRA=orden_compra).first()
        if orden and orden.ESTADO != 'A':
            return Response({"error": "Only orders in Planeada state can be cancelled."},
                            status=status.HTTP_400_BAD_REQUEST)
        try:
            cancel_purchase_order(orden_compra, request.user.username if request.user.username else 'DEVELOPER')
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        return Response({"message": "Purchase Order canceled successfully."}, status=status.HTTP_200_OK)


    @action(detail=False, methods=['get'])
    def generate_sticker_4x2_pdf(self, request):
        orden_compra = request.query_params.get('ORDEN_COMPRA', None)
        if not orden_compra:
            return Response({"error": "ORDEN_COMPRA is required."}, status=status.HTTP_400_BAD_REQUEST)
        articulo = request.query_params.get('ARTICULO', None)
        if not articulo:
            return Response({"error": "ARTICULO is required."}, status=status.HTTP_400_BAD_REQUEST)
        articulo_object = Articulo.objects.filter(ARTICULO=articulo).first()
        purchase_order = OrdenCompra.objects.filter(ORDEN_COMPRA=orden_compra).first()
        if not purchase_order:
            return Response({"error": "Invalid ORDEN_COMPRA."}, status=status.HTTP_400_BAD_REQUEST)
        if not articulo_object:
            return Response({"error": "Invalid ARTICULO."}, status=status.HTTP_400_BAD_REQUEST)
        articulo_compra = ArticuloProveedor.objects.filter(PROVEEDOR=purchase_order.PROVEEDOR,
                                                           ARTICULO=articulo).first()
        # if image already exists, return the existing one
        if os.path.exists(
                os.path.join(settings.BASE_DIR, 'static', 'qrcodes', f'{orden_compra}_{articulo}_4x2.pdf')):
            return Response(
                {"qrcode": settings.FRONTEND_URL + '/static/qrcodes/' + f'{orden_compra}_{articulo}_4x2.pdf'})
        # -------------------------
        #  INPUT DATA
        # -------------------------
        company_name = "VIRGILIO RODRIGUEZ & ASOCIADOS, S.R.L."
        phone = "Tel.: 809-578-7775"
        website = "www.virgiloorodriguez.com"

        qr_text = orden_compra
        item_number = articulo
        item_name = articulo_object.DESCRIPCION
        reference = articulo_compra.CODIGO_CATALOGO if articulo_compra else ''
        barcode_value = item_number

        # -------------------------
        #  PAGE SIZE → 4 × 2 inch
        # -------------------------
        PAGE_WIDTH = 4 * inch
        PAGE_HEIGHT = 2 * inch
        PAGE_SIZE = (PAGE_WIDTH, PAGE_HEIGHT)

        # -------------------------
        #  STYLES
        # -------------------------
        styles = getSampleStyleSheet()
        center_normal = ParagraphStyle(
            "center_normal",
            parent=styles["Normal"],
            alignment=TA_CENTER,
            leading=10,
            fontSize=7
        )
        center_bold = ParagraphStyle(
            "center_bold",
            parent=styles["Normal"],
            alignment=TA_CENTER,
            leading=11,
            fontSize=8,
            spaceAfter=2,
        )
        company_style = ParagraphStyle(
            "company",
            parent=styles["Normal"],
            alignment=TA_CENTER,
            leading=8,
            fontSize=7,
        )

        # -------------------------
        #  GENERATE HIGH-RES QR
        #  (No scaling → perfect crisp)
        # -------------------------
        qr = qrcode.QRCode(
            version=4,
            box_size=8,  # generates ~32mm QR which fits well
            border=1,
        )
        qr.add_data(qr_text)
        qr.make()

        qr_img_pil = qr.make_image(fill_color="black", back_color="white").convert("RGB")
        qr_buf = BytesIO()
        qr_img_pil.save(qr_buf, format="PNG")
        qr_buf.seek(0)

        qr_img = Image(qr_buf)
        qr_img.hAlign = "CENTER"

        # QR exact physical size (≈32mm)
        qr_img.drawWidth = 13 * mm
        qr_img.drawHeight = 13 * mm

        # ================================
        # 1. Generate base barcode (600 DPI)
        # ================================
        writer = ImageWriter()
        writer.set_options({
            "module_width": 0.32,  # you can increase this to make barcode longer
            "module_height": 11,  # exact height in mm
            "quiet_zone": 1,
            "font_size": 0,
            "dpi": 600,
        })

        bc_buf = BytesIO()
        barcode_obj = barcode.get("code128", barcode_value, writer=writer)
        barcode_obj.write(bc_buf)
        bc_buf.seek(0)

        # ================================
        # 2. Resize barcode with PIL, NOT REPORTLAB
        #    (This avoids stretching/blur)
        # ================================
        barcode_pil = PILImage.open(bc_buf)

        final_width_mm = 40  # choose width that fits your layout
        final_height_mm = 16  # exact height

        # convert mm → pixels (at 300 DPI)
        dpi = 300
        px_w = int(final_width_mm / 25.4 * dpi)
        px_h = int(final_height_mm / 25.4 * dpi)

        barcode_resized = barcode_pil.resize((px_w, px_h), PILImage.LANCZOS)

        # Save resized barcode back to BytesIO
        barcode_final = BytesIO()
        barcode_resized.save(barcode_final, format="PNG")
        barcode_final.seek(0)

        # ================================
        # 3. Use ReportLab Image at EXACT SIZE (NO SCALING)
        # ================================
        barcode_img = Image(barcode_final)
        barcode_img.drawWidth = final_width_mm * mm
        barcode_img.drawHeight = final_height_mm * mm

        # -------------------------
        #  PDF RESPONSE
        # -------------------------
        save_path = os.path.join(settings.BASE_DIR, 'static', 'qrcodes',
                                 f'{orden_compra}_{articulo}_4x2.pdf')
        os.makedirs(os.path.dirname(save_path), exist_ok=True)

        doc = SimpleDocTemplate(
            save_path,
            pagesize=PAGE_SIZE,
            leftMargin=6,
            rightMargin=6,
            topMargin=6,
            bottomMargin=6,
        )

        flow = []

        # -----------------------------
        #  COMPANY HEADER
        # -----------------------------
        flow.append(Paragraph(f"<b>{company_name}</b>", company_style))
        flow.append(Paragraph(phone, company_style))
        flow.append(Paragraph(website, company_style))
        flow.append(Spacer(1, 6))

        # -----------------------------
        #  ITEM TITLE / REF
        # -----------------------------
        flow.append(Paragraph(f"<b>{item_name}</b>", center_bold))
        flow.append(Paragraph(f"<b>REF: {reference}</b>", center_normal))
        flow.append(Spacer(1, 6))

        # -----------------------------
        #  BARCODE + QR SIDE BY SIDE
        # -----------------------------
        table = Table(
            [["", barcode_img, qr_img]],
            colWidths=[PAGE_WIDTH * 0.24, PAGE_WIDTH * 0.50, PAGE_WIDTH * 0.26],
        )

        table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("LEFTPADDING", (0, 0), (-1, -1), 2),
            ("RIGHTPADDING", (0, 0), (-1, -1), 2),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ]))

        flow.append(table)

        doc.build(flow)
        return Response(
            {"qrcode": settings.FRONTEND_URL + '/static/qrcodes/' + f'{orden_compra}_{articulo}_4x2.pdf'})

    @action(detail=False, methods=['get'])
    def generate_sticker_2x1_pdf(self, request):
        orden_compra = request.query_params.get('ORDEN_COMPRA')
        articulo = request.query_params.get('ARTICULO')

        if not orden_compra or not articulo:
            return Response({"error": "ORDEN_COMPRA and ARTICULO are required."},
                            status=status.HTTP_400_BAD_REQUEST)

        articulo_object = Articulo.objects.filter(ARTICULO=articulo).first()
        purchase_order = OrdenCompra.objects.filter(ORDEN_COMPRA=orden_compra).first()

        if not purchase_order:
            return Response({"error": "Invalid ORDEN_COMPRA."}, status=400)
        if not articulo_object:
            return Response({"error": "Invalid ARTICULO."}, status=400)

        articulo_compra = ArticuloProveedor.objects.filter(
            PROVEEDOR=purchase_order.PROVEEDOR,
            ARTICULO=articulo
        ).first()

        # If already generated
        save_path = os.path.join(
            settings.BASE_DIR,
            'static', 'qrcodes',
            f'{orden_compra}_{articulo}_2x1.pdf'
        )
        if os.path.exists(save_path):
            return Response({"qrcode": settings.FRONTEND_URL + '/static/qrcodes/' +
                                       f'{orden_compra}_{articulo}_2x1.pdf'})

        # -------------------------
        #  INPUT DATA
        # -------------------------
        item_name = articulo_object.DESCRIPCION[:28]  # short text for 2x1 label
        reference = articulo_compra.CODIGO_CATALOGO if articulo_compra else ''
        barcode_value = articulo
        qr_text = orden_compra

        # -------------------------
        #  PAGE SIZE → 2 × 1 inch
        # -------------------------
        PAGE_WIDTH = 2 * inch
        PAGE_HEIGHT = 1 * inch
        PAGE_SIZE = (PAGE_WIDTH, PAGE_HEIGHT)

        # -------------------------
        #  STYLES
        # -------------------------
        styles = getSampleStyleSheet()
        small_center = ParagraphStyle(
            "small_center",
            parent=styles["Normal"],
            alignment=TA_CENTER,
            fontSize=5.5,
            leading=6
        )
        small_bold = ParagraphStyle(
            "small_bold",
            parent=styles["Normal"],
            alignment=TA_CENTER,
            fontSize=6,
            leading=7
        )

        # -------------------------
        #  QR (small for 2x1 label)
        # -------------------------
        qr = qrcode.QRCode(version=2, box_size=4, border=1)
        qr.add_data(qr_text)
        qr.make()

        qr_img_pil = qr.make_image(fill_color="black", back_color="white").convert("RGB")
        qr_buf = BytesIO()
        qr_img_pil.save(qr_buf, format="PNG")
        qr_buf.seek(0)

        qr_img = Image(qr_buf)
        qr_img.drawWidth = 9 * mm
        qr_img.drawHeight = 9 * mm

        # -------------------------
        #  BARCODE (600 DPI, crisp)
        # -------------------------
        writer = ImageWriter()
        writer.set_options({
            "module_width": 0.30,  # good width for 2-inch label
            "module_height": 7,  # smaller height for compact label
            "quiet_zone": 0.8,
            "font_size": 0,
            "dpi": 600
        })

        bc_buf = BytesIO()
        barcode_obj = barcode.get("code128", barcode_value, writer=writer)
        barcode_obj.write(bc_buf)
        bc_buf.seek(0)

        barcode_pil = PILImage.open(bc_buf).convert("RGB")

        # Resize in PIL (exact size for 2-inch label)
        final_width_mm = 20  # fits 2-inch width with margins
        final_height_mm = 8

        dpi = 300
        px_w = int(final_width_mm / 25.4 * dpi)
        px_h = int(final_height_mm / 25.4 * dpi)

        bc_resized = barcode_pil.resize((px_w, px_h), PILImage.LANCZOS)

        barcode_final = BytesIO()
        bc_resized.save(barcode_final, format="PNG")
        barcode_final.seek(0)

        barcode_img = Image(barcode_final)
        barcode_img.drawWidth = final_width_mm * mm
        barcode_img.drawHeight = final_height_mm * mm

        # -------------------------
        #  BUILD PDF
        # -------------------------
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        doc = SimpleDocTemplate(
            save_path,
            pagesize=PAGE_SIZE,
            leftMargin=2,
            rightMargin=2,
            topMargin=2,
            bottomMargin=2,
        )

        flow = []

        # Item Name
        flow.append(Paragraph(f"<b>{item_name}</b>", small_bold))

        # REF
        flow.append(Paragraph(f"REF: {reference}", small_center))
        flow.append(Spacer(1, 2))

        # Layout: Barcode left, QR right
        table = Table(
            [["", barcode_img, qr_img]],
            colWidths=[PAGE_WIDTH * 0.15, PAGE_WIDTH * 0.35, PAGE_WIDTH * 0.50],
        )

        table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("LEFTPADDING", (0, 0), (-1, -1), 1),
            ("RIGHTPADDING", (0, 0), (-1, -1), 1),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ]))

        flow.append(table)

        doc.build(flow)

        return Response({
            "qrcode": settings.FRONTEND_URL + '/static/qrcodes/' +
                      f'{orden_compra}_{articulo}_2x1.pdf'
        })


class ShipmentViewset(viewsets.ViewSet):
    @action(detail=False, methods=['get'])
    def search_articulos(self, request):
        items = Articulo.objects.filter(Q(ARTICULO__icontains=request.query_params.get('search', '')) | Q(
            DESCRIPCION__icontains=request.query_params.get('search', '')))[:25]
        serializer = ArticuloSearchSerializer(items, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def search_proveedors(self, request):
        items = Proveedor.objects.filter(Q(PROVEEDOR__icontains=request.query_params.get('search', '')) | Q(
            NOMBRE__icontains=request.query_params.get('search', '')))[:10]
        serializer = ProveedorSearchSerializer(items, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def search_ordenes_compra(self, request):
        items = OrdenCompra.objects.filter(ESTADO='E', PROVEEDOR=request.query_params.get('proveedor', '')).values(
            'ORDEN_COMPRA', 'PROVEEDOR', 'ESTADO').distinct()
        return Response(items)

    @action(detail=False, methods=['get'])
    def get_existencia_lote(self, request):
        queryset = ExistenciaLote.objects.filter(ARTICULO=request.query_params.get('articulo', ''))
        serializer = ExistenciaLoteSerializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def search_localizacion(self, request):
        if not request.query_params.get('search', None):
            queryset = ExistenciaLote.objects.filter(ARTICULO=request.query_params.get('articulo', ''),
                                                     BODEGA=request.query_params.get('bodega', 'A001'))
            existencia = ExistenciaLoteSerializer(queryset, many=True).data
            # existencia_locs = [ext['LOCALIZACION'] for ext in existencia]
            # for idx, loc in enumerate(locations):
            #     if loc['LOCALIZACION'] in existencia_locs:
            #         del locations[idx]
            return Response(existencia)
        items = Localizacion.objects.filter(LOCALIZACION__icontains=request.query_params.get('search', ''),
                                            BODEGA=request.query_params.get('bodega', 'A001'))[:10]
        serializer = LocalizacionSerializer(items, many=True)
        locations = serializer.data
        return Response(locations)

    @action(detail=False, methods=['post'])
    def add_new_location(self, request):
        serializer = LocalizacionSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        try:
            items = Localizacion.objects.filter(LOCALIZACION=serializer.data['LOCALIZACION'],
                                                BODEGA=serializer.data['BODEGA'])
            if items.exists():
                return Response({"message": "Location already exists."})
            data_dict = dict(serializer.validated_data)
            data_dict.update(
                {'VOLUMEN': 0.0, 'PESO_MAXIMO': 0.0, 'DESCRIPCION': data_dict['LOCALIZACION'], 'NoteExistsFlag': False})
            create_location(data_dict)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        return Response({"message": "Location created successfully."}, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['post'])
    def submit_shipment(self, request):
        serializer = EmbarqueRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        vra_globals = VRAGlobalesCo.objects.first()
        index = int(vra_globals.ULT_EMBARQUE[2:])
        new_order = 'EM' + str(index + 1).zfill(len(vra_globals.ULT_EMBARQUE[2:]))
        crm_index = int(vra_globals.ULT_CRM[3:])
        new_crm = 'CRM' + str(crm_index + 1).zfill(len(vra_globals.ULT_CRM[3:]))
        if serializer.data['EMBARQUE'] == new_order and serializer.data['CRM'] == new_crm:
            try:
                serializer.validated_data[
                    'USUARIO_CREADO'] = request.user.username if request.user.username else 'DEVELOPER'
                create_shipment(serializer.validated_data)
            except Exception as e:
                return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            return Response({"message": "Shipment submitted successfully."}, status=status.HTTP_201_CREATED)
        else:
            return Response({"error": "Invalid Shipment."}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['put'])
    def update_shipment(self, request):
        serializer = EmbarqueRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        embarque = serializer.data.get('EMBARQUE')
        update_fields = {key: value for key, value in serializer.validated_data.items() if key != 'EMBARQUE'}
        try:
            update_em_shipment(embarque, update_fields)
            return Response({"message": "Shipment updated successfully."}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['patch'])
    def approve_shipment(self, request):
        embarque = request.data.get('EMBARQUE', None)
        if not embarque:
            return Response({"error": "EMBARQUE is required."}, status=status.HTTP_400_BAD_REQUEST)
        shipment = Embarque.objects.filter(EMBARQUE=embarque).first()
        if shipment and shipment.ESTADO != 'P':
            return Response({"error": "Only shipments in Planeado state can be approved."},
                            status=status.HTTP_400_BAD_REQUEST)
        try:
            approve_shipment(embarque)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        return Response({"message": "Shipment approved successfully."}, status=status.HTTP_200_OK)

    @action(detail=False, methods=['patch'])
    def disapprove_shipment(self, request):
        embarque = request.data.get('EMBARQUE', None)
        if not embarque:
            return Response({"error": "EMBARQUE is required."}, status=status.HTTP_400_BAD_REQUEST)
        shipment = Embarque.objects.filter(EMBARQUE=embarque).first()
        if shipment and shipment.ESTADO != 'T':
            return Response({"error": "Only shipments in Tránsito state can be disapproved."},
                            status=status.HTTP_400_BAD_REQUEST)
        try:
            disapprove_shipment(embarque)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        return Response({"message": "Shipment disapproved successfully."}, status=status.HTTP_200_OK)

    @action(detail=False, methods=['patch'])
    def cancel_shipment(self, request):
        embarque = request.data.get('EMBARQUE', None)
        if not embarque:
            return Response({"error": "EMBARQUE is required."}, status=status.HTTP_400_BAD_REQUEST)
        shipment = Embarque.objects.filter(EMBARQUE=embarque).first()
        if shipment and shipment.ESTADO != 'P':
            return Response({"error": "Only shipments in Planeado state can be cancelled."},
                            status=status.HTTP_400_BAD_REQUEST)
        try:
            cancel_shipment(embarque)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        return Response({"message": "Shipment canceled successfully."}, status=status.HTTP_200_OK)


class ItemMasterViewset(viewsets.ReadOnlyModelViewSet):
    serializer_class = ItemMasterSerializer
    queryset = ItemMasterView.objects.all()
    filterset_fields = ['BODEGA', 'category', 'brand', 'implemento']
    search_fields = ['ARTICULO', 'BODEGA', 'DESCRIPCION', 'category', 'brand', 'implemento']
    ordering_fields = '__all__'
    ordering = ['-CANT_DISPONIBLE']

    @action(detail=False, methods=['get'])
    def filters(self, request):
        categories = ItemMasterView.objects.values_list('category', flat=True).distinct().order_by('category')
        brands = ItemMasterView.objects.values_list('brand', flat=True).distinct().order_by('brand')
        implementos = ItemMasterView.objects.values_list('implemento', flat=True).distinct().order_by('implemento')
        return Response({
            'categories': categories,
            'brands': brands,
            'implementos': implementos
        })


class AgingInvViewset(viewsets.ReadOnlyModelViewSet):
    serializer_class = AgingInventorySummarySerializer
    queryset = AgingInventorySummary.objects.all()
    filterset_fields = ['BODEGA', 'category', 'brand', 'implemento', 'aging_bucket']
    search_fields = ['ARTICULO', 'BODEGA', 'descripcion', 'category', 'brand', 'implemento']
    ordering_fields = '__all__'
    ordering = ['-total_value']


class LowStockViewset(viewsets.ReadOnlyModelViewSet):
    serializer_class = LowStockViewSerializer
    queryset = LowStockView.objects.order_by(F('LAST_TRANSACTION').desc(nulls_last=True))
    search_fields = ['ARTICULO', 'DESCRIPCION', 'ORDEN_COMPRA', 'EMBARQUE', 'UNIDAD_ALMACEN', 'PROVEEDOR',
                     'PROVEEDOR_NOMBRE']
    ordering_fields = '__all__'
    filterset_class = LowStockFilter
    ordering = ['-CANT_TRANSITO']


class InventoryAuditViewset(viewsets.ReadOnlyModelViewSet):
    serializer_class = InventoryAuditViewSerializer
    queryset = InventoryAuditView.objects.all()
    filterset_fields = ['BODEGA']
    search_fields = ['ARTICULO', 'BODEGA']
    ordering_fields = '__all__'
    ordering = ['diff_disponible']


class InventoryAuditDetailViewset(viewsets.ReadOnlyModelViewSet):
    serializer_class = InventoryAuditDetailViewSerializer
    queryset = InventoryAuditView.objects.all()
    lookup_fields = ['articulo', 'bodega']

    def get_object(self):
        articulo = self.kwargs.get('articulo', None)
        bodega = self.kwargs.get('bodega', None)
        try:
            return self.queryset.get(ARTICULO=articulo, BODEGA=bodega)
        except InventoryAuditView.DoesNotExist:
            raise NotFound(detail="The requested object does not exist.")


class SolicitudeViewset(viewsets.ReadOnlyModelViewSet):
    serializer_class = SolicitudOcSerializer
    queryset = SolicitudOc.objects.all()
    search_fields = ['SOLICITUD_OC', 'ESTADO', 'USUARIO', 'PRIORIDAD', 'AUTORIZADA_POR', 'DEPARTAMENTO']
    ordering_fields = '__all__'
    ordering = ['-RecordDate']
    filterset_class = SolicitudOcFilter

    def filter_queryset(self, queryset):
        search = self.request.query_params.get('search', '')
        queryset = super().filter_queryset(queryset)
        if not len(queryset):
            if search:
                departments = Departamento.objects.filter(DESCRIPCION__icontains=search).values_list('DEPARTAMENTO',
                                                                                                     flat=True)
                queryset |= self.queryset.filter(DEPARTAMENTO__in=departments)
        return queryset


class SolicitudeDetailViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for retrieving Solicitud Oc.
    This viewset provides read-only access to the Solicitud Oc in the system.
    """
    serializer_class = SolicitudOcDetailSerializer
    queryset = SolicitudOc.objects.all()


class DepartamentoViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for retrieving Solicitud Oc.
    This viewset provides read-only access to the Solicitud Oc in the system.
    """
    serializer_class = DepartamentoSerializer
    queryset = Departamento.objects.all()
    pagination_class = None
    ordering = ['-CreateDate']


class OrdenCompraViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = OrdenCompraSerializer
    queryset = OrdenCompra.objects.all()
    search_fields = ['ORDEN_COMPRA', 'PROVEEDOR']
    ordering_fields = '__all__'
    ordering = ['-RecordDate']
    filterset_class = OrdenCompraFilter

    def filter_queryset(self, queryset):
        search = self.request.query_params.get('search', '')
        queryset = super().filter_queryset(queryset)
        if not len(queryset):
            if search:
                suppliers = Proveedor.objects.filter(NOMBRE__icontains=search).values_list('PROVEEDOR',
                                                                                           flat=True)
                queryset |= self.queryset.filter(PROVEEDOR__in=suppliers)
        return queryset


class OrdenCompraDetailViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for Orden Compra (Purchase Order).
    """
    serializer_class = OrdenCompraDetailSerializer
    queryset = OrdenCompra.objects.all()


class EmbarqueViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = EmbarqueSerializer
    queryset = Embarque.objects.all()
    filterset_fields = ['ESTADO', 'PROVEEDOR', 'FECHA_EMBARQUE', 'CRM']
    search_fields = ['EMBARQUE', 'PROVEEDOR', 'USUARIO_CREADO', 'CRM']
    ordering_fields = '__all__'
    ordering = ['-RecordDate']
    filterset_class = EmbarqueFilter

    def filter_queryset(self, queryset):
        search = self.request.query_params.get('search', '')
        queryset = super().filter_queryset(queryset)
        if not len(queryset):
            if search:
                suppliers = Proveedor.objects.filter(NOMBRE__icontains=search).values_list('PROVEEDOR',
                                                                                           flat=True)
                queryset |= self.queryset.filter(PROVEEDOR__in=suppliers)
        return queryset


class EmbarqueDetailViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for retrieving Embarque.
    This viewset provides read-only access to the Embarque in the system.
    """
    serializer_class = EmbarqueDetailSerializer
    queryset = Embarque.objects.all()


class DocumentoEmbarqueViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for retrieving DocumentoEmbarque.
    This viewset provides read-only access to the DocumentoEmbarque in the system.
    """
    serializer_class = DocumentoEmbarqueSerializer
    queryset = DocumentoEmbarque.objects.all()
    lookup_field = 'DOCUMENTO'


class ProveedorViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for retrieving Proveedor.
    This viewset provides read-only access to the Proveedor in the system.
    """
    serializer_class = ProveedorSerializer
    queryset = Proveedor.objects.all()
    filterset_fields = ['PAIS', 'NOMBRE']
    search_fields = ['PROVEEDOR', 'TELEFONO1', 'TELEFONO2', 'NOMBRE', 'DIRECCION', 'E_MAIL']
    ordering_fields = '__all__'
    ordering = ['-RecordDate']


class ProveedorDetailViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for retrieving Proveedor.
    This viewset provides read-only access to the Proveedor in the system.
    """
    serializer_class = ProveedorDetailSerializer
    queryset = Proveedor.objects.all()


class AuditTransInvViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = AuditTransInvSerializer
    queryset = AuditTransInv.objects.all()
    search_fields = ['AUDIT_TRANS_INV', 'APLICACION', 'USUARIO', 'ASIENTO', 'REFERENCIA', 'MODULO_ORIGEN']
    ordering_fields = '__all__'
    ordering = ['-AUDIT_TRANS_INV']
    filterset_class = AuditTransInvFilter


class AuditTransInvDetailViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for retrieving AuditTransInv.
    This viewset provides read-only access to the AuditTransInv in the system.
    """
    serializer_class = AuditTransInvDetailSerializer
    queryset = AuditTransInv.objects.all()


class GlobalesViewset(viewsets.ViewSet):

    @action(detail=False, methods=['get'])
    def oc(self, request):
        globale = GlobalesCo.objects.values()[0]
        index = int(globale['ULT_ORDEN_COMPRA'][2:])
        new_order = 'OC' + str(index + 1).zfill(len(globale['ULT_ORDEN_COMPRA'][2:]))
        bodega = Bodega.objects.values('BODEGA', 'NOMBRE')
        return Response({'new_order': new_order, 'bodega': bodega, 'globale': globale})

    @action(detail=False, methods=['get'])
    def em(self, request):
        globale = GlobalesCo.objects.values()[0]
        index = int(globale['ULT_EMBARQUE'][2:])
        new_order = 'EM' + str(index + 1).zfill(len(globale['ULT_ORDEN_COMPRA'][2:]))
        bodega = Bodega.objects.values('BODEGA', 'NOMBRE')
        index = int(globale['ULT_CRM'][3:])
        new_crm = 'CRM' + str(index + 1).zfill(len(globale['ULT_CRM'][3:]))
        return Response({'new_shipment': new_order, 'new_crm': new_crm, 'bodega': bodega, 'globale': globale})

    @action(detail=False, methods=['get'])
    def sc(self, request):
        globale = GlobalesCo.objects.values()[0]
        index = int(globale['ULT_SOLICITUD'][2:])
        new_order = 'SC' + str(index + 1).zfill(len(globale['ULT_SOLICITUD'][2:]))
        bodega = Bodega.objects.values('BODEGA', 'NOMBRE')
        return Response({'new_solicitud': new_order, 'bodega': bodega, 'globale': globale})


class EmailFormView(viewsets.ViewSet):

    @action(detail=False, methods=['post'])
    def pr_email(self, request):
        serializer = EmailFormSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        subject = serializer.validated_data.get('subject')
        html_content = serializer.validated_data.get('html_content')
        recipient_email = serializer.validated_data.get('email')
        plain_message = strip_tags(html_content)
        try:
            send_mail(subject, plain_message, settings.DEFAULT_FROM_EMAIL,
                      [recipient_email, 'Virgiliorm@virgiliorodriguez.com'], html_message=html_content)
            return Response({"detail": "Email sent successfully."}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"detail": f"Error sending email: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def po_email(self, request):
        serializer = EmailFormAttachmentsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        subject = serializer.validated_data.get('subject')
        html_content = serializer.validated_data.get('html_content')
        recipient_email = serializer.validated_data.get('email')
        plain_message = strip_tags(html_content)
        try:
            msg = EmailMessage()
            msg["Subject"] = subject
            msg["From"] = settings.DEFAULT_FROM_EMAIL
            msg["To"] = [recipient_email, 'Virgiliorm@virgiliorodriguez.com']
            msg.set_content(plain_message)
            msg.add_alternative(html_content, subtype="html")
            # Attach file
            for _, file in request.FILES.items():
                file_data = file.read()

                msg.add_attachment(
                    file_data,
                    maintype="application",
                    subtype="octet-stream",
                    filename=file.name,
                )

            client = boto3.client(
                "sesv2",
                region_name=settings.AWS_REGION_NAME,
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            )

            response = client.send_email(
                FromEmailAddress=settings.DEFAULT_FROM_EMAIL,
                Destination={"ToAddresses": ['pratik.patel@kanhasoft.com', 'jenish@kanhasoft.com']},
                Content={
                    "Raw": {
                        "Data": msg.as_bytes()
                    }
                },
            )
            # original
            # msg = EmailMultiAlternatives(subject, plain_message, settings.DEFAULT_FROM_EMAIL,
            #                              ['pratik.patel@kanhasoft.com', 'jenish@kanhasoft.com'])
            # msg.attach_alternative(html_content, "text/html")
            # for filename, uploaded_file in request.FILES.items():
            #     msg.attach(uploaded_file.name, uploaded_file.read(), uploaded_file.content_type)
            # msg.send()
            return Response({"detail": "Email sent successfully.", "aws_response": response}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"detail": f"Error sending email: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class TopSellingForecastView(viewsets.ViewSet):
    """
    Returns Top 10 most selling products with 6-month forecast.
    """

    @action(detail=False, methods=['get'])
    def prophet(self, request):
        if request.query_params.get('articulo', None):
            articulo = request.query_params.get('articulo')
            current_month = datetime.now().replace(day=1)
            forecast = ProphetForecast.objects.filter(article=articulo, forecast_month__gte=current_month).order_by('forecast_month')
            existing = ExistenciaBodega.objects.filter(ARTICULO=articulo).aggregate(total=Sum('CANT_DISPONIBLE'))
            existing_stock = existing['total'] if existing['total'] else 0
            return Response({
                "articulo": articulo,
                "forecast": ProphetForecastSerializer(forecast, many=True).data,
                "review": get_forecast_reviews(existing_stock,
                                               sum(forecast.values_list('forecast_quantity', flat=True)))
            })
        # Step 1: Fetch top 10 products from MV
        top_products = (
            ItemsSalesHistory.objects
            .values("ARTICULO")
            .annotate(total_sales=Sum("SALES_AMOUNT"), total_sold=Sum("Y"))
            .order_by("-total_sold", "-total_sales")[:10]
        )
        # Step 2: Add forecast for each product
        response_data = []

        for item in top_products:
            articulo = item["ARTICULO"]
            current_month = datetime.now().replace(day=1)
            forecast = ProphetForecast.objects.filter(article=articulo, forecast_month__gte=current_month).order_by('forecast_month')
            existing = ExistenciaBodega.objects.filter(ARTICULO=articulo).aggregate(total=Sum('CANT_DISPONIBLE'))
            existing_stock = existing['total'] if existing['total'] else 0
            response_data.append({
                "articulo": articulo,
                "forecast": ProphetForecastSerializer(forecast, many=True).data,
                "review": get_forecast_reviews(existing_stock,
                                               sum(forecast.values_list('forecast_quantity', flat=True)))
            })

        return Response(response_data)

    @action(detail=False, methods=['get'])
    def sarima(self, request):
        if request.query_params.get('articulo', None):
            articulo = request.query_params.get('articulo')
            existing = ExistenciaBodega.objects.filter(ARTICULO=articulo).aggregate(total=Sum('CANT_DISPONIBLE'))
            existing_stock = existing['total'] if existing['total'] else 0
            current_month = datetime.now().replace(day=1)
            forecast = SarimaForecast.objects.filter(article=articulo, forecast_month__gte=current_month).order_by('forecast_month')
            return Response({"articulo": articulo,
                             "forecast": SarimaForecastSerializer(forecast, many=True).data,
                             "review": get_forecast_reviews(
                                 existing_stock,
                                 sum(forecast.values_list('forecast_quantity', flat=True)))})
        top10 = (
            ItemsSalesHistory.objects
            .values("ARTICULO")
            .annotate(total_sales=Sum("SALES_AMOUNT"), total_sold=Sum("Y"))
            .order_by("-total_sold")[:10]
        )

        results = []

        for item in top10:
            articulo = item["ARTICULO"]
            existing = ExistenciaBodega.objects.filter(ARTICULO=articulo).aggregate(total=Sum('CANT_DISPONIBLE'))
            existing_stock = existing['total'] if existing['total'] else 0
            current_month = datetime.now().replace(day=1)
            forecast = SarimaForecast.objects.filter(article=articulo, forecast_month__gte=current_month).order_by('forecast_month')
            results.append({
                "articulo": articulo,
                "forecast": SarimaForecastSerializer(forecast, many=True).data,
                "review": get_forecast_reviews(existing_stock,
                                               sum(forecast.values_list('forecast_quantity', flat=True)))
            })

        return Response(results)

    @action(detail=False, methods=['get'])
    def holt_winters(self, request):
        if request.query_params.get('articulo', None):
            articulo = request.query_params.get('articulo', None)
            current_month = datetime.now().replace(day=1)
            existing = ExistenciaBodega.objects.filter(ARTICULO=articulo).aggregate(total=Sum('CANT_DISPONIBLE'))
            existing_stock = existing['total'] if existing['total'] else 0
            forecast = HoltWintersForecast.objects.filter(article=articulo, forecast_month__gte=current_month).order_by('forecast_month')
            return Response({
                "articulo": articulo,
                "forecast": HoltWintersForecastSerializer(forecast, many=True).data,
                "review": get_forecast_reviews(existing_stock,
                                               sum(forecast.values_list('forecast_quantity', flat=True)))
            })
        top10 = (
            ItemsSalesHistory.objects
            .values("ARTICULO")
            .annotate(total_sales=Sum("SALES_AMOUNT"), total_sold=Sum("Y"))
            .order_by("-total_sold")[:10]
        )

        results = []

        for item in top10:
            articulo = item["ARTICULO"]
            existing = ExistenciaBodega.objects.filter(ARTICULO=articulo).aggregate(total=Sum('CANT_DISPONIBLE'))
            existing_stock = existing['total'] if existing['total'] else 0
            current_month = datetime.now().replace(day=1)
            forecast = HoltWintersForecast.objects.filter(article=articulo, forecast_month__gte=current_month).order_by('forecast_month')
            results.append({
                "articulo": articulo,
                "forecast": HoltWintersForecastSerializer(forecast, many=True).data,
                "review": get_forecast_reviews(existing_stock,
                                               sum(forecast.values_list('forecast_quantity', flat=True)))
            })

        return Response(results)


class StockSummaryViewset(viewsets.ViewSet):

    @action(detail=False, methods=['get'])
    def cat_summary(self, request):
        category_summary = (
            ItemMasterView
            .objects
            .annotate(
                CATEGORY=F('category')
            )
            .values("BODEGA", "CATEGORY", "UNIDAD_ALMACEN")
            .annotate(
                total_qty=Sum("CANT_DISPONIBLE"),
                total_value=Sum(
                    ExpressionWrapper(
                        F("CANT_DISPONIBLE") * F("COSTO_UNT_PROMEDIO_LOC"),
                        output_field=FloatField()
                    )
                )
            )
            .filter(total_qty__gt=0)
            .order_by("BODEGA", "CATEGORY", "UNIDAD_ALMACEN")
        )
        return Response(category_summary)

    @action(detail=False, methods=['get'])
    def brand_summary(self, request):
        brand_summary = (
            ItemMasterView
            .objects
            .annotate(
                CATEGORY=F('brand')
            )
            .values("BODEGA", "CATEGORY", "UNIDAD_ALMACEN")
            .annotate(
                total_qty=Sum("CANT_DISPONIBLE"),
                total_value=Sum(
                    ExpressionWrapper(
                        F("CANT_DISPONIBLE") * F("COSTO_UNT_PROMEDIO_LOC"),
                        output_field=FloatField()
                    )
                )
            )
            .filter(total_qty__gt=0)
            .order_by("BODEGA", "CATEGORY", "UNIDAD_ALMACEN")
        )
        return Response(brand_summary)

    @action(detail=False, methods=['get'])
    def implemento_summary(self, request):
        implemento_summary = (
            ItemMasterView
            .objects
            .annotate(
                CATEGORY=F('implemento')
            )
            .values("BODEGA", "CATEGORY", "UNIDAD_ALMACEN")
            .annotate(
                total_qty=Sum("CANT_DISPONIBLE"),
                total_value=Sum(
                    ExpressionWrapper(
                        F("CANT_DISPONIBLE") * F("COSTO_UNT_PROMEDIO_LOC"),
                        output_field=FloatField()
                    )
                )
            )
            .filter(total_qty__gt=0)
            .order_by("BODEGA", "CATEGORY", "UNIDAD_ALMACEN")
        )
        return Response(implemento_summary)


class InvValuationReportViewset(viewsets.ViewSet):

    @action(detail=False, methods=['get'])
    def valuation_report(self, request):
        locations_subquery = (
            ExistenciaLote.objects
            .filter(
                BODEGA=OuterRef("BODEGA"),
                ARTICULO=OuterRef("ARTICULO"),
            ).filter(Q(CANT_DISPONIBLE__gt=0) | Q(CANT_RESERVADA__gt=0))
            .values("BODEGA", "ARTICULO")
            .annotate(
                locations=ArrayAgg("LOCALIZACION", distinct=True)
            )
            .values("locations")[:1]
        )
        item_queryset = (
            ItemMasterView.objects
            .annotate(
                locations=Subquery(locations_subquery),
                total_value_loc=ExpressionWrapper(
                    F("CANT_DISPONIBLE") * F("COSTO_UNT_PROMEDIO_LOC"),
                    output_field=FloatField()
                ),
                total_value_dol=ExpressionWrapper(
                    F("CANT_DISPONIBLE") * F("COSTO_UNT_PROMEDIO_DOL"),
                    output_field=FloatField()
                )
            )
            .filter(CANT_DISPONIBLE__gt=0)
            .values('ARTICULO', 'DESCRIPCION', 'BODEGA', 'CANT_DISPONIBLE', 'COSTO_UNT_PROMEDIO_LOC', 'total_value_loc',
                    'category', 'brand', 'implemento', 'COSTO_UNT_PROMEDIO_DOL', 'total_value_dol', 'UNIDAD_ALMACEN',
                    'locations')
            .order_by('BODEGA', 'ARTICULO')
        )
        return Response(item_queryset)

    @action(detail=False, methods=['get'])
    def valuation_summary(self, request):
        valuation_summary = (
            ItemMasterView.objects
            .annotate(
                total_value_loc=ExpressionWrapper(
                    F("CANT_DISPONIBLE") * F("COSTO_UNT_PROMEDIO_LOC"),
                    output_field=FloatField()
                ),
                total_value_dol=ExpressionWrapper(
                    F("CANT_DISPONIBLE") * F("COSTO_UNT_PROMEDIO_DOL"),
                    output_field=FloatField()
                )
            )
            .filter(CANT_DISPONIBLE__gt=0)
            .values('BODEGA', 'UNIDAD_ALMACEN')
            .annotate(
                total_qty=Sum('CANT_DISPONIBLE'),
                total_value_loc=Sum('total_value_loc'),
                total_value_dol=Sum('total_value_dol')
            )
            .order_by('BODEGA')
        )
        return Response(valuation_summary)


class ConsumptionSummary(viewsets.ViewSet):

    @action(detail=False, methods=['get'])
    def cat_summary(self, request):
        category_subquery = Subquery(
            Articulo.objects.filter(
                ARTICULO=OuterRef("ARTICULO")
            )
            .annotate(
                CATEGORY=Coalesce(Subquery(Clasificacion.objects.filter(
                    CLASIFICACION=OuterRef("CLASIFICACION_2")
                ).values('DESCRIPCION')[:1]
                                           ), Value('Otros'))
            )
            .values("CATEGORY")[:1]
        )
        end_date = request.query_params.get('end_date', None)
        if end_date:
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
        else:
            end_date = date.today().replace(day=1) - timedelta(days=1)
        start_date = request.query_params.get('start_date', None)
        if start_date:
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        else:
            start_date = end_date.replace(day=1) - relativedelta(months=11)
        sales = (
            ItemsSalesHistory.objects
            .filter(DS__range=(start_date, end_date))
            .annotate(
                month=TruncMonth("DS"),
                category=category_subquery
            )
            .values("category", "month")
            .annotate(
                qty=Sum("Y"),
                value=Sum("SALES_AMOUNT")
            )
            .order_by("category", "month")
        )
        return Response(sales)

    @action(detail=False, methods=['get'])
    def brand_summary(self, request):
        category_subquery = Subquery(
            Articulo.objects.filter(
                ARTICULO=OuterRef("ARTICULO")
            )
            .annotate(
                CATEGORY=Coalesce(Subquery(Clasificacion.objects.filter(
                    CLASIFICACION=OuterRef("CLASIFICACION_5")
                ).values('DESCRIPCION')[:1]
                                           ), Value('Otros'))
            )
            .values("CATEGORY")[:1]
        )
        end_date = request.query_params.get('end_date', None)
        if end_date:
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
        else:
            end_date = date.today().replace(day=1) - timedelta(days=1)
        start_date = request.query_params.get('start_date', None)
        if start_date:
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        else:
            start_date = end_date.replace(day=1) - relativedelta(months=11)
        sales = (
            ItemsSalesHistory.objects
            .filter(DS__range=(start_date, end_date))
            .annotate(
                month=TruncMonth("DS"),
                category=category_subquery
            )
            .values("category", "month")
            .annotate(
                qty=Sum("Y"),
                value=Sum("SALES_AMOUNT")
            )
            .order_by("category", "month")
        )
        return Response(sales)

    @action(detail=False, methods=['get'])
    def implemento_summary(self, request):
        category_subquery = Subquery(
            Articulo.objects.filter(
                ARTICULO=OuterRef("ARTICULO")
            )
            .annotate(
                CATEGORY=Coalesce(Subquery(Clasificacion.objects.filter(
                    CLASIFICACION=OuterRef("CLASIFICACION_1")
                ).values('DESCRIPCION')[:1]
                                           ), Value('Otros'))
            )
            .values("CATEGORY")[:1]
        )
        end_date = request.query_params.get('end_date', None)
        if end_date:
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
        else:
            end_date = date.today().replace(day=1) - timedelta(days=1)
        start_date = request.query_params.get('start_date', None)
        if start_date:
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        else:
            start_date = end_date.replace(day=1) - relativedelta(months=11)
        sales = (
            ItemsSalesHistory.objects
            .filter(DS__range=(start_date, end_date))
            .annotate(
                month=TruncMonth("DS"),
                category=category_subquery
            )
            .values("category", "month")
            .annotate(
                qty=Sum("Y"),
                value=Sum("SALES_AMOUNT")
            )
            .order_by("category", "month")
        )
        return Response(sales)


class AgingSummaryViewset(viewsets.ViewSet):

    @action(detail=False, methods=['get'])
    def cat_summary(self, request):
        aging_summary = (
            AgingInventorySummary
            .objects
            .annotate(
                CATEGORY=F('implemento')
            )
            .values("BODEGA", "CATEGORY", "aging_bucket")
            .annotate(
                total_qty=Sum("total_qty"),
                total_articles=Count("ARTICULO", distinct=True),
                total_value=Sum("total_value"),
            )
            .order_by("-total_value")
        )
        return Response(aging_summary)

    @action(detail=False, methods=['get'])
    def brand_summary(self, request):
        aging_summary = (
            AgingInventorySummary
            .objects
            .annotate(
                CATEGORY=F('brand')
            )
            .values("BODEGA", "CATEGORY", "aging_bucket")
            .annotate(
                total_qty=Sum("total_qty"),
                total_articles=Count("ARTICULO", distinct=True),
                total_value=Sum("total_value"),
            )
            .order_by("-total_value")
        )
        return Response(aging_summary)

    @action(detail=False, methods=['get'])
    def implemento_summary(self, request):
        aging_summary = (
            AgingInventorySummary
            .objects
            .annotate(
                CATEGORY=F('implemento')
            )
            .values("BODEGA", "CATEGORY", "aging_bucket")
            .annotate(
                total_qty=Sum("total_qty"),
                total_articles=Count("ARTICULO", distinct=True),
                total_value=Sum("total_value"),
            )
            .order_by("-total_value")
        )
        return Response(aging_summary)


class OverstockViewset(viewsets.ViewSet):

    @action(detail=False, methods=['get'])
    def prophet_summary(self, request):
        descripcion_subquery = Subquery(
            Articulo.objects.filter(
                ARTICULO=OuterRef("ARTICULO")
            )
            .values("DESCRIPCION")[:1]
        )
        overstocks = (ProphetForecastView.objects
                      .annotate(description=descripcion_subquery)
                      .filter(available_perc__gte=2)
                      .values().order_by('-overstock_value'))
        return Response(overstocks)

    @action(detail=False, methods=['get'])
    def sarima_summary(self, request):
        descripcion_subquery = Subquery(
            Articulo.objects.filter(
                ARTICULO=OuterRef("ARTICULO")
            )
            .values("DESCRIPCION")[:1]
        )
        overstocks = (SarimaForecastView.objects
                      .annotate(description=descripcion_subquery)
                      .filter(available_perc__gte=2)
                      .values().order_by('-overstock_value'))
        return Response(overstocks)

    @action(detail=False, methods=['get'])
    def holt_winters_summary(self, request):
        descripcion_subquery = Subquery(
            Articulo.objects.filter(
                ARTICULO=OuterRef("ARTICULO")
            )
            .values("DESCRIPCION")[:1]
        )
        overstocks = (HoltWintersForecastView
                      .objects
                      .annotate(description=descripcion_subquery)
                      .filter(available_perc__gte=2)
                      .values().order_by('-overstock_value'))
        return Response(overstocks)


class ROPViewset(viewsets.ViewSet):

    @action(detail=False, methods=['get'])
    def prophet_summary(self, request):
        descripcion_subquery = Subquery(
            Articulo.objects.filter(
                ARTICULO=OuterRef("ARTICULO")
            )
            .values("DESCRIPCION")[:1]
        )
        overstocks = (ProphetForecastView
                      .objects
                      .annotate(description=descripcion_subquery)
                      .filter(available_perc__lt=1, total_forecast__gte=1)
                      .values().order_by('available_perc', '-total_forecast'))
        return Response(overstocks)

    @action(detail=False, methods=['get'])
    def sarima_summary(self, request):
        descripcion_subquery = Subquery(
            Articulo.objects.filter(
                ARTICULO=OuterRef("ARTICULO")
            )
            .values("DESCRIPCION")[:1]
        )
        overstocks = (SarimaForecastView
                      .objects
                      .annotate(description=descripcion_subquery)
                      .filter(available_perc__lt=1, total_forecast__gte=1)
                      .values().order_by('available_perc', '-total_forecast'))
        return Response(overstocks)

    @action(detail=False, methods=['get'])
    def holt_winters_summary(self, request):
        descripcion_subquery = Subquery(
            Articulo.objects.filter(
                ARTICULO=OuterRef("ARTICULO")
            )
            .values("DESCRIPCION")[:1]
        )
        overstocks = (HoltWintersForecastView
                      .objects
                      .annotate(description=descripcion_subquery)
                      .filter(available_perc__lt=1, total_forecast__gte=1)
                      .values().order_by('available_perc', '-total_forecast'))
        return Response(overstocks)


class RopReportViewset(viewsets.ViewSet):

    @action(detail=False, methods=['get'])
    def prophet_summary(self, request):
        forecast_subquery = Subquery(
            ProphetForecastView.objects.filter(
                ARTICULO=OuterRef("ARTICULO")
            )
            .values("total_forecast")[:1]
        )
        rop_report = (
            ItemLeadDaysView
            .objects
            .annotate(
                total_forecast=ExpressionWrapper(
                    Func(
                        Coalesce(forecast_subquery, Value(Decimal("0.0"))),
                        Value(Decimal("0.0")),
                        function="GREATEST"
                    ),
                    output_field=DecimalField(max_digits=20, decimal_places=4)
                )
            )
            .annotate(
                avg_daily_demand=ExpressionWrapper(
                    F("total_forecast") / Value(Decimal("183.0")),
                    output_field=DecimalField(max_digits=12, decimal_places=4)
                ),
            )
            .annotate(
                lead_time_demand=ExpressionWrapper(
                    F("avg_daily_demand") * Coalesce(F("LEAD_TIME_DAYS"), Value(0)),
                    output_field=DecimalField(max_digits=16, decimal_places=4)
                ),
                safety_stock_fc=ExpressionWrapper(
                    F("lead_time_demand") * Value(0.20),
                    output_field=DecimalField(max_digits=14, decimal_places=4)
                ),
                safety_stock=Coalesce(
                    F("EXISTENCIA_MINIMA"),
                    Value(Decimal("0.0"))
                ),
                reorder_qty=ExpressionWrapper(
                    Func(
                        Coalesce(
                            F('lead_time_demand') + F('safety_stock') - Coalesce(F("total_qty"), Value(Decimal("0.0"))),
                            Value(Decimal("0.0"))
                        ),
                        Value(Decimal("0.0")),
                        function='GREATEST'
                    ),
                    output_field=DecimalField(max_digits=20, decimal_places=4)
                ),
            )
            .annotate(
                inventory_status=Case(
                    #  Critical: Stock < Lead Time Demand
                    When(
                        total_qty__lt=F("lead_time_demand"),
                        then=Value("CRITICAL")
                    ),

                    #  Warning: Stock < Safety Stock
                    When(
                        total_qty__lt=F("safety_stock"),
                        then=Value("WARNING")
                    ),

                    #  Overstock: Stock > Forecast × 2
                    When(
                        total_qty__gt=ExpressionWrapper(
                            F("total_forecast") * Value(Decimal("2.0")),
                            output_field=DecimalField(max_digits=20, decimal_places=4)
                        ),
                        then=Value("OVERSTOCK")
                    ),

                    #  Healthy
                    default=Value("HEALTHY"),
                    output_field=CharField()
                )
            )
            .values(
                "ARTICULO",
                "total_forecast",
                "avg_daily_demand",
                "LEAD_TIME_DAYS",
                "lead_time_demand",
                "safety_stock",
                "safety_stock_fc",
                "total_qty",
                "reorder_qty",
                "inventory_status",
                "PROVEEDOR",
                "PROVEEDOR_NOMBRE",
                "PROVEEDOR_PAIS",
                "CANT_RESERVADA",
                "CANT_DISPONIBLE",
                "CANT_TRANSITO",
            ).order_by("-total_forecast"))
        return Response(rop_report)

    @action(detail=False, methods=['get'])
    def sarima_summary(self, request):
        forecast_subquery = Subquery(
            SarimaForecastView.objects.filter(
                ARTICULO=OuterRef("ARTICULO")
            )
            .values("total_forecast")[:1]
        )
        rop_report = (
            ItemLeadDaysView
            .objects
            .annotate(
                total_forecast=ExpressionWrapper(
                    Func(
                        Coalesce(forecast_subquery, Value(Decimal("0.0"))),
                        Value(Decimal("0.0")),
                        function="GREATEST"
                    ),
                    output_field=DecimalField(max_digits=20, decimal_places=4)
                )
            )
            .annotate(
                avg_daily_demand=ExpressionWrapper(
                    F("total_forecast") / Value(Decimal("183.0")),
                    output_field=DecimalField(max_digits=12, decimal_places=4)
                ),
            )
            .annotate(
                lead_time_demand=ExpressionWrapper(
                    F("avg_daily_demand") * Coalesce(F("LEAD_TIME_DAYS"), Value(0)),
                    output_field=DecimalField(max_digits=16, decimal_places=4)
                ),
                safety_stock_fc=ExpressionWrapper(
                    F("lead_time_demand") * Value(0.20),
                    output_field=DecimalField(max_digits=14, decimal_places=4)
                ),
                safety_stock=Coalesce(
                    F("EXISTENCIA_MINIMA"),
                    Value(Decimal("0.0"))
                ),
                reorder_qty=ExpressionWrapper(
                    Func(
                        Coalesce(
                            F('lead_time_demand') + F('safety_stock') - Coalesce(F("total_qty"), Value(Decimal("0.0"))),
                            Value(Decimal("0.0"))
                        ),
                        Value(Decimal("0.0")),
                        function='GREATEST'
                    ),
                    output_field=DecimalField(max_digits=20, decimal_places=4)
                ),
            )
            .annotate(
                inventory_status=Case(
                    #  Critical: Stock < Lead Time Demand
                    When(
                        total_qty__lt=F("lead_time_demand"),
                        then=Value("CRITICAL")
                    ),

                    #  Warning: Stock < Safety Stock
                    When(
                        total_qty__lt=F("safety_stock"),
                        then=Value("WARNING")
                    ),

                    #  Overstock: Stock > Forecast × 2
                    When(
                        total_qty__gt=ExpressionWrapper(
                            F("total_forecast") * Value(Decimal("2.0")),
                            output_field=DecimalField(max_digits=20, decimal_places=4)
                        ),
                        then=Value("OVERSTOCK")
                    ),

                    #  Healthy
                    default=Value("HEALTHY"),
                    output_field=CharField()
                )
            )
            .values(
                "ARTICULO",
                "total_forecast",
                "avg_daily_demand",
                "LEAD_TIME_DAYS",
                "lead_time_demand",
                "safety_stock",
                "safety_stock_fc",
                "total_qty",
                "reorder_qty",
                "inventory_status",
                "PROVEEDOR",
                "PROVEEDOR_NOMBRE",
                "PROVEEDOR_PAIS",
                "CANT_RESERVADA",
                "CANT_DISPONIBLE",
                "CANT_TRANSITO",
            ).order_by("-total_forecast"))
        return Response(rop_report)

    @action(detail=False, methods=['get'])
    def holt_winters_summary(self, request):
        forecast_subquery = Subquery(
            HoltWintersForecastView.objects.filter(
                ARTICULO=OuterRef("ARTICULO")
            )
            .values("total_forecast")[:1]
        )
        rop_report = (
            ItemLeadDaysView
            .objects
            .annotate(
                total_forecast=ExpressionWrapper(
                    Func(
                        Coalesce(forecast_subquery, Value(Decimal("0.0"))),
                        Value(Decimal("0.0")),
                        function="GREATEST"
                    ),
                    output_field=DecimalField(max_digits=20, decimal_places=4)
                )
            )
            .annotate(
                avg_daily_demand=ExpressionWrapper(
                    F("total_forecast") / Value(Decimal("183.0")),
                    output_field=DecimalField(max_digits=12, decimal_places=4)
                ),
            )
            .annotate(
                lead_time_demand=ExpressionWrapper(
                    F("avg_daily_demand") * Coalesce(F("LEAD_TIME_DAYS"), Value(0)),
                    output_field=DecimalField(max_digits=16, decimal_places=4)
                ),
                safety_stock_fc=ExpressionWrapper(
                    F("lead_time_demand") * Value(0.20),
                    output_field=DecimalField(max_digits=14, decimal_places=4)
                ),
                safety_stock=Coalesce(
                    F("EXISTENCIA_MINIMA"),
                    Value(Decimal("0.0"))
                ),
                reorder_qty=ExpressionWrapper(
                    Func(
                        Coalesce(
                            F('lead_time_demand') + F('safety_stock') - Coalesce(F("total_qty"), Value(Decimal("0.0"))),
                            Value(Decimal("0.0"))
                        ),
                        Value(Decimal("0.0")),
                        function='GREATEST'
                    ),
                    output_field=DecimalField(max_digits=20, decimal_places=4)
                ),
            )
            .annotate(
                inventory_status=Case(
                    #  Critical: Stock < Lead Time Demand
                    When(
                        total_qty__lt=F("lead_time_demand"),
                        then=Value("CRITICAL")
                    ),

                    #  Warning: Stock < Safety Stock
                    When(
                        total_qty__lt=F("safety_stock"),
                        then=Value("WARNING")
                    ),

                    #  Overstock: Stock > Forecast × 2
                    When(
                        total_qty__gt=ExpressionWrapper(
                            F("total_forecast") * Value(Decimal("2.0")),
                            output_field=DecimalField(max_digits=20, decimal_places=4)
                        ),
                        then=Value("OVERSTOCK")
                    ),

                    #  Healthy
                    default=Value("HEALTHY"),
                    output_field=CharField()
                )
            )
            .values(
                "ARTICULO",
                "total_forecast",
                "avg_daily_demand",
                "LEAD_TIME_DAYS",
                "lead_time_demand",
                "safety_stock",
                "safety_stock_fc",
                "total_qty",
                "reorder_qty",
                "inventory_status",
                "PROVEEDOR",
                "PROVEEDOR_NOMBRE",
                "PROVEEDOR_PAIS",
                "CANT_RESERVADA",
                "CANT_DISPONIBLE",
                "CANT_TRANSITO",
            ).order_by("-total_forecast"))
        return Response(rop_report)


class WarehouseActivity(viewsets.ViewSet):

    @action(detail=False, methods=['get'])
    def top_moving_items(self, request):
        descripcion_subquery = Subquery(
            Articulo.objects.filter(
                ARTICULO=OuterRef("ARTICULO")
            )
            .values("DESCRIPCION")[:1]
        )
        top_moving = (
            ItemsSalesHistory.objects
            .filter(DS__range=(date.today() - timedelta(days=180), date.today()))
            .annotate(description=descripcion_subquery, frequency=Count('DS', distinct=True))
            .values('ARTICULO', 'description', 'frequency')
            .annotate(total_sold=Sum('Y'), total_sold_value=Sum('SALES_AMOUNT'))
            .order_by('-total_sold', '-frequency')[:100]
        )
        top_moving_by_value = (
            ItemsSalesHistory.objects
            .filter(DS__range=(date.today() - timedelta(days=180), date.today()))
            .annotate(description=descripcion_subquery, frequency=Count('DS', distinct=True))
            .values('ARTICULO', 'description', 'frequency')
            .annotate(total_sold_value=Sum('SALES_AMOUNT'), total_sold=Sum('Y'))
            .order_by('-total_sold_value', '-frequency')[:100]
        )
        return Response({'by_qty': top_moving, 'by_value': top_moving_by_value})

    @action(detail=False, methods=['get'])
    def slow_moving_items(self, request):
        descripcion_subquery = Subquery(
            Articulo.objects.filter(
                ARTICULO=OuterRef("ARTICULO")
            )
            .values("DESCRIPCION")[:1]
        )

        slow_moving = (
            ItemsSalesHistory.objects
            .filter(DS__range=(date.today() - timedelta(days=180), date.today()))
            .annotate(description=descripcion_subquery, last_moved_days=ExtractDay(Now() - Max('DS')))
            .values('ARTICULO', 'description', 'last_moved_days')
            .annotate(total_sold=Sum('Y'))
            .order_by('-last_moved_days')[:100]
        )
        return Response(slow_moving)

    @action(detail=False, methods=['get'])
    def recent_purchases(self, request):
        descripcion_subquery = Subquery(
            Articulo.objects.filter(
                ARTICULO=OuterRef("ARTICULO")
            )
            .values("DESCRIPCION")[:1]
        )

        recent_purchases = (
            TransaccionInv.objects
            .filter(AJUSTE_CONFIG="~OO~", FECHA_HORA_TRANSAC__range=(date.today() - timedelta(days=180), date.today()))
            .annotate(description=descripcion_subquery,
                      last_received_days=ExtractDay(Now() - Max('FECHA_HORA_TRANSAC')))
            .values('ARTICULO', 'description', 'last_received_days')
            .annotate(total_received=Sum('CANTIDAD'))
            .order_by('last_received_days')[:50]
        )
        return Response(recent_purchases)

    @action(detail=False, methods=['get'])
    def open_purchase_orders(self, request):
        po_subquery = Subquery(
            OrdenCompra.objects.filter(
                ORDEN_COMPRA=OuterRef("ORDEN_COMPRA")
            ).values("PROVEEDOR")[:1]
        )
        open_pos = (
            OrdenCompraLinea.objects
            .filter(ESTADO__in=['A'])
            .annotate(
                descripcion=Subquery(
                    Articulo.objects.filter(
                        ARTICULO=OuterRef("ARTICULO")
                    ).values("DESCRIPCION")[:1]
                ),
                supplier=po_subquery
            )
            .values('ORDEN_COMPRA', 'ARTICULO', 'descripcion', 'supplier')
            .annotate(
                qty_ordered=Sum('CANTIDAD_ORDENADA')
            )
            .order_by('-qty_ordered')[:50]
        )
        return Response(open_pos)

    @action(detail=False, methods=['get'])
    def statistics(self, request):
        total_items = Articulo.objects.exclude(TIPO__in=('V', 'F', 'O', 'L')).count()
        total_orders = Factura.objects.filter(
            FECHA_HORA__range=(date.today() - timedelta(days=180), date.today()),
            TIPO_DOCUMENTO='F'
        ).count()
        shipment_transit = OrdenCompra.objects.filter(
            ESTADO='E',
            FECHA_HORA__range=(date.today() - timedelta(days=180), date.today())
        ).count()
        total_revenue = ItemsSalesHistory.objects.filter(
            DS__range=(date.today() - timedelta(days=180), date.today())
        ).aggregate(Sum('SALES_AMOUNT'))['SALES_AMOUNT__sum']
        return Response({
            "total_items": total_items,
            "total_orders": total_orders,
            "shipment_transit": shipment_transit,
            "total_revenue": total_revenue,
        })


class CycleCountBatchViewSet(viewsets.ModelViewSet):
    queryset = CycleCountBatch.objects.all().order_by('-id')
    serializer_class = CycleCountBatchSerializer

    @action(detail=True, methods=['get'])
    def tasks(self, request, pk=None):
        """Fetch all tasks for a specific batch."""
        batch = self.get_object()
        tasks = CycleCountTask.objects.filter(batch=batch)
        serializer = CycleCountTaskSerializer(tasks, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def consecutivo_ci(self, request):
        items = ConsecutivoCi.objects.filter(CONSECUTIVO="FISICO").all()
        serializer = ConsecutivoCiSerializer(items, many=True)
        items = PaqueteInventario.objects.order_by('-FECHA_ULT_ACCESO').all()
        paquetes = PaqueteInventarioSerializer(items, many=True)
        return Response({'consecutivo': serializer.data, 'paquetes': paquetes.data})

    @action(detail=False, methods=['get'])
    def existencia_lote(self, request):
        articulo = request.query_params.get('articulo', None)
        bodega = request.query_params.get('bodega', None)
        if not articulo or not bodega:
            return Response({"error": "Both 'articulo' and 'bodega' parameters are required."},
                            status=status.HTTP_400_BAD_REQUEST)
        existencia = VRAExistenciaLote.objects.filter(ARTICULO=articulo, BODEGA=bodega).all()
        existencia = ExistenciaLoteSerializer(existencia, many=True).data
        return Response({"articulo": articulo, "bodega": bodega, "existencia": existencia})

    @action(detail=True, methods=['get'])
    def apply_batch(self, request, pk=None):
        """Apply the cycle count batch."""
        try:
            batch = CycleCountBatch.objects.prefetch_related('tasks').get(id=pk)
            incomplete_tasks = batch.tasks.filter(~Q(status__in=('APPROVED', 'ADJUSTED')))
            approved_tasks = batch.tasks.filter(status='APPROVED')
            if incomplete_tasks.exists():
                return Response({"error": "All tasks must be approved before applying the batch."},
                                status=status.HTTP_400_BAD_REQUEST)
            batch.status = 'COMPLETED'
            serialized_data = self.get_serializer(batch).data
            tasks = CycleCountTaskSerializer(approved_tasks, many=True).data
            item = VRAConsecutivoCi.objects.filter(CONSECUTIVO="FISICO").first()
            serialized_data["document_number"] = item.SIGUIENTE_CONSEC
            create_stock_transfer_adjustment(
                serialized_data, tasks,
                request.user.username if request.user.username else 'DEVELOPER'
            )
            # apply_stock_transfer_adjustment(
            #     serialized_data["document_number"],
            #     request.user.username if request.user.username else 'DEVELOPER'
            # )
            approved_tasks.update(status='ADJUSTED', reviewed_by=request.user, reviewed_at=datetime.now())
            batch.save()
            wm_role = Role.objects.filter(code='warehouse-manager').first()
            admin_role = Role.objects.filter(code='admin').first()
            users_to_notify = set()
            if wm_role:
                users_to_notify.update(wm_role.users.all())
            if admin_role:
                users_to_notify.update(admin_role.users.all())
            send_applied_stocktransfer_alert([batch], users_to_notify)
            return Response({"message": "Cycle count batch applied successfully."}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class CycleCountTaskViewSet(viewsets.ModelViewSet):
    queryset = CycleCountTask.objects.all().order_by('-id')
    serializer_class = CycleCountTaskSerializer

    @action(detail=True, methods=['patch'])
    def update_status(self, request, pk=None):
        task = self.get_object()
        serializer = CycleCountTaskStatusSerializer(
            task,
            data=request.data,
            partial=True
        )

        if serializer.is_valid():
            state = serializer.validated_data.get('status')
            if state == 'APPROVED':
                serializer.save(reviewed_by=request.user, reviewed_at=datetime.now())
            else:
                serializer.save()
            return Response({
                "message": "Status updated successfully",
                "status": serializer.data["status"]
            })

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ABCAnalysisViewset(viewsets.ViewSet):

    @action(detail=False, methods=['get'])
    def value(self, request):
        article_discription_subquery = Subquery(
            Articulo.objects.filter(
                ARTICULO=OuterRef("ARTICULO")
            )
            .values("DESCRIPCION")[:1]
        )
        results = (
            ABCValueView
            .objects
            .annotate(descripcion=article_discription_subquery)
            .values()
        )
        return Response(results)

    @action(detail=False, methods=['get'])
    def usage(self, request):
        article_discription_subquery = Subquery(
            Articulo.objects.filter(
                ARTICULO=OuterRef("ARTICULO")
            )
            .values("DESCRIPCION")[:1]
        )
        results = (
            ABCUsageView
            .objects
            .annotate(descripcion=article_discription_subquery)
            .values()
        )
        return Response(results)


class DepartmentUsageReportViewset(viewsets.ViewSet):

    @action(detail=False, methods=['get'])
    def usage(self, request):
        end_date = request.query_params.get('end_date', None)
        if end_date:
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
        else:
            end_date = date.today().replace(day=1) - timedelta(days=1)
        start_date = request.query_params.get('start_date', None)
        if start_date:
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        else:
            start_date = end_date.replace(day=1) - relativedelta(months=11)
        usage_report = (
            TransaccionInv.objects
            .filter(CENTRO_COSTO__isnull=False, FECHA_HORA_TRANSAC__range=(start_date, end_date))
            .values('CENTRO_COSTO', 'CUENTA_CONTABLE', 'AJUSTE_CONFIG').annotate(
                total_qty=Sum('CANTIDAD'),
                total_value=Sum('COSTO_TOT_FISC_LOC'),
                centro_cost_desc=Subquery(
                    CentroCosto.objects.filter(CENTRO_COSTO=OuterRef('CENTRO_COSTO'))
                    .values('DESCRIPCION')[:1]
                ),
                cuenta_contable_desc=Subquery(
                    CuentaContable.objects.filter(CUENTA_CONTABLE=OuterRef('CUENTA_CONTABLE'))
                    .values('DESCRIPCION')[:1]
                ),
                ajuste_desc=Subquery(
                    AjusteConfig.objects.filter(AJUSTE_CONFIG=OuterRef('AJUSTE_CONFIG'))
                    .values('DESCRIPCION')[:1]
                )
            )
            .order_by('-total_value')
        )
        return Response(usage_report)


class PurchaseSummaryViewset(viewsets.ViewSet):

    @action(detail=False, methods=['get'])
    def supplier(self, request):
        end_date = request.query_params.get('end_date', None)
        if end_date:
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
        else:
            end_date = date.today().replace(day=1) - timedelta(days=1)
        start_date = request.query_params.get('start_date', None)
        if start_date:
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        else:
            start_date = end_date.replace(day=1) - relativedelta(months=11)
        purchase_summary = (
            TransaccionInv.objects
            .filter(AJUSTE_CONFIG='~OO~', FECHA_HORA_TRANSAC__range=(start_date, end_date))
            .annotate(
                PROVEEDOR=Embarque.objects.filter(AUDIT_TRANS_INV=OuterRef('AUDIT_TRANS_INV'))
                .values('PROVEEDOR')[:1]
            )
            .values('PROVEEDOR')
            .filter(PROVEEDOR__isnull=False)
            .annotate(
                total_qty=Sum('CANTIDAD'),
                total_value=Sum('COSTO_TOT_FISC_LOC'),
                suplier_name=Proveedor.objects.filter(PROVEEDOR=OuterRef('PROVEEDOR'))
                .values('NOMBRE')[:1]
            )
            .order_by('-total_value')
        )

        return Response(purchase_summary)


class SPDispatchViewSet(viewsets.ModelViewSet):
    queryset = SPDispatchHeader.objects.all().prefetch_related('items')
    serializer_class = SPDispatchHeaderSerializer
    ordering = ['-created_at']

    def get_queryset(self):
        # Optional: Filter by Project/Cost Center for the Dashboard
        project = self.request.query_params.get('project')
        if project:
            return self.queryset.filter(centro_costo=project)
        return self.queryset

class SPReturnViewSet(viewsets.ModelViewSet):
    queryset = SPReturnHeader.objects.all().prefetch_related('returned_items')
    serializer_class = SPReturnHeaderSerializer
    ordering = ['-created_at']


class SPDispatchItemViewSet(viewsets.ModelViewSet):
    queryset = SPDispatchItem.objects.all()
    serializer_class = SPDispatchItemActionSerializer

    def perform_destroy(self, instance):
        # Logic: Prevent deletion if a return has already been processed for this item
        if SPReturnItem.objects.filter(dispatch_item=instance).exists():
            raise ValidationError(
                "Cannot delete this item because a return record exists for it."
            )
        instance.delete()


class SPReturnItemViewSet(viewsets.ModelViewSet):
    queryset = SPReturnItem.objects.all()
    serializer_class = SPReturnItemActionSerializer

    def perform_update(self, serializer):
        # Ensure updated return quantity doesn't exceed original dispatch
        instance = self.get_object()
        new_quantity = serializer.validated_data.get('quantity_returned', instance.quantity_returned)

        if new_quantity > instance.dispatch_item.quantity:
            raise ValidationError("Return quantity exceeds original dispatch quantity.")

        serializer.save()


class StandaloneInventoryDashboardView(viewsets.ViewSet):
    """
    View to fetch the Standalone Inventory Dashboard data.
    Filters for types F, V, O, and L with detailed accounting and brand info.
    """

    @action(detail=False, methods=['get'])
    def items(self, request):
        query = """
        SELECT 
            a."ARTICULO" AS "Item Code",
            a."DESCRIPCION" AS "Item Name",
            CASE a."TIPO"
                WHEN 'F' THEN 'Phantom (Assembly)'
                WHEN 'V' THEN 'Service'
                WHEN 'O' THEN 'Other / Miscellaneous'
                WHEN 'L' THEN 'Labor'
                ELSE 'Unknown Type'
            END AS "Item Type",
            d."DESCRIPCION" AS "Origin",
            c."DESCRIPCION" AS "Family",
            b."DESCRIPCION" AS "Brand",
            eb."BODEGA" AS "Warehouse",
            CAST(eb."CANT_DISPONIBLE" AS FLOAT) AS "Available",
            CAST(eb."CANT_RESERVADA" AS FLOAT) AS "Reserved",
            CAST(eb."CANT_TRANSITO" AS FLOAT) AS "In Transit",
            CAST(eb."COSTO_UNT_PROMEDIO_LOC" AS FLOAT) AS "Unit Cost",
            ac."DESCRIPCION" AS "Account Group",
            cc."CUENTA_CONTABLE" AS "GL Account",
            cc."DESCRIPCION" AS "GL Description",
            a."OBLIGA_INCLUIR_FASE_PY" AS "Project Mandatory"
        FROM "catalog_management_articulo" a
        LEFT JOIN "catalog_management_clasificacion" d ON d."CLASIFICACION" = a."CLASIFICACION_1"
        LEFT JOIN "catalog_management_clasificacion" c ON c."CLASIFICACION" = a."CLASIFICACION_2"
        LEFT JOIN "catalog_management_clasificacion" b ON b."CLASIFICACION" = a."CLASIFICACION_5"
        LEFT JOIN "catalog_management_existenciabodega" eb ON eb."ARTICULO" = a."ARTICULO"
        LEFT JOIN "catalog_management_articulocuenta" ac ON ac."ARTICULO_CUENTA" = a."ARTICULO_CUENTA"
        LEFT JOIN "catalog_management_cuentacontable" cc ON cc."CUENTA_CONTABLE" = ac."CTA_COMPRA_LOC"
        WHERE a."TIPO" IN ('F', 'V', 'O', 'L')
        ORDER BY eb."BODEGA", a."ARTICULO";
        """

        try:
            with connection.cursor() as cursor:
                cursor.execute(query)
                # Fetch column names to map to dictionary
                columns = [col[0] for col in cursor.description]
                results = [
                    dict(zip(columns, row))
                    for row in cursor.fetchall()
                ]

            return Response(results, status=status.HTTP_200_OK)

        except Exception as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'])
    def sales(self, request):
        start_date = request.query_params.get('start_date', str(date(date.today().year, 1, 1)))
        end_date = request.query_params.get('end_date', str(date.today()))

        query = """
                    SELECT
                        d."ARTICULO" AS "item_code",
                        MAX(a."DESCRIPCION") AS "item_name",
                        SUM(d."CANTIDAD") AS "total_quantity",
                        SUM(d."PRECIO_TOTAL") AS "total_amount",
                        CASE a."TIPO"
                            WHEN 'F' THEN 'Phantom (Assembly)'
                            WHEN 'V' THEN 'Service'
                            WHEN 'O' THEN 'Other / Miscellaneous'
                            WHEN 'L' THEN 'Labor'
                            ELSE 'Unknown Type'
                        END AS "item_type"
                    FROM catalog_management_facturalinea d
                    JOIN catalog_management_factura f ON f."FACTURA" = d."FACTURA" 
                         AND f."TIPO_DOCUMENTO" = d."TIPO_DOCUMENTO"
                    JOIN catalog_management_articulo a ON a."ARTICULO" = d."ARTICULO"
                    WHERE f."TIPO_DOCUMENTO" = 'F'
                      AND f."FECHA"::date BETWEEN %s AND %s
                      AND COALESCE(UPPER(f."ANULADA"), 'N') != 'S'
                      AND COALESCE(UPPER(d."ANULADA"), 'N') != 'S'
                      AND d."CANTIDAD" > 0
                      AND a."TIPO" IN ('V', 'F', 'O', 'L')
                    GROUP BY d."ARTICULO", a."TIPO"
                    ORDER BY "total_amount" DESC;
                """

        try:
            with connection.cursor() as cursor:
                cursor.execute(query, [start_date, end_date])

                # Fetching results as a list of dictionaries
                columns = [col[0] for col in cursor.description]
                results = [
                    dict(zip(columns, row))
                    for row in cursor.fetchall()
                ]
            total_revenue = sum(float(row['total_amount']) for row in results)
            total_units_sold = sum(float(row['total_quantity']) for row in results)
            unique_items_count = len(results)
            return Response({
                "summary": {
                    "total_revenue": round(total_revenue, 2),
                    "total_units_sold": round(total_units_sold, 2),
                    "unique_items_count": unique_items_count,
                    "average_revenue_per_item": round(total_revenue / unique_items_count,
                                                      2) if unique_items_count > 0 else 0
                },
                "period": {"start": start_date, "end": end_date},
                "data": results
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def classificacion_options(self, request):
        classifications = Clasificacion.objects.filter(
            AGRUPACION=request.query_params['group']
        ).values('CLASIFICACION', 'DESCRIPCION')
        return Response(classifications, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'])
    def account_options(self, request):
        accounts = ArticuloCuenta.objects.all().values(
            'ARTICULO_CUENTA', 'DESCRIPCION'
        ).order_by('ARTICULO_CUENTA')
        return Response(accounts, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'])
    def impuesto_options(self, request):
        taxes = Impuesto.objects.all().values(
            'IMPUESTO', 'DESCRIPCION'
        ).order_by('IMPUESTO')
        return Response(taxes, status=status.HTTP_200_OK)


class StandaloneArticuloViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Manual Management of Standalone Items (Types V, F, O, L).
    """
    serializer_class = StandaloneArticuloSerializer
    lookup_field = 'ARTICULO' # Allows access via /api/standalone/ITEM-CODE/

    def get_queryset(self):
        # Filter only standalone types to prevent accidental modification of ERP items
        return Articulo.objects.filter(TIPO__in=['V', 'F', 'O', 'L'])

    def perform_create(self, serializer):
        # Ensure the user who created it is logged in the model
        serializer.save(CreatedBy=self.request.user.username if self.request.user.username and
                                                                self.request.user.username is not None else 'SA')