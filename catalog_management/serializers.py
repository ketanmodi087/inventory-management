from rest_framework import serializers
from django.db.models import Sum, Subquery, OuterRef
from IMS.utility import send_new_cycle_count_alert
from user_management.models import Role
from .models import (
    Articulo, ArticuloCompra, Proveedor, ArticuloProveedor, ArticuloCuenta, Impuesto, Clasificacion, ExistenciaLote,
    ArticuloPrecio, ArticuloEnsamble, Departamento, ItemMasterView, SolicitudOc, SolicitudOcLinea, OrdenCompra,
    OrdenCompraLinea, CentroCosto, CuentaContable, Embarque, EmbarqueLinea, DocumentoEmbarque, Devolucion,
    DevolLinEmbarque, AuditTransInv, TransaccionInv, LowStockView, EmbarqueDocCp, DetDocumentoEmbarque, DetLinEmbarque,
    SeguimientoOrden, Moneda, CondicionPago, Localizacion, PaqueteInventario, DocumentoInv, LineaDocInv, ConsecutivoCi,
    InventoryAuditView, InventoryAuditLoteView, AjusteConfig, ItemsSalesHistory, AgingInventorySummary, CycleCountTask,
    CycleCountBatch, SarimaForecast, ProphetForecast, HoltWintersForecast, SPDispatchHeader, SPDispatchItem,
    SPReturnHeader, SPReturnItem
)
from datetime import datetime
from django.db import transaction
from decimal import Decimal


class PaqueteInventarioSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaqueteInventario
        exclude = ['CreateDate', 'NoteExistsFlag', 'RecordDate', 'RowPointer', 'UpdatedBy', 'CreatedBy']


class DocumentoInvSerializer(serializers.ModelSerializer):
    class Meta:
        model = DocumentoInv
        exclude = ['CreateDate', 'NoteExistsFlag', 'RecordDate', 'RowPointer', 'UpdatedBy', 'CreatedBy']


class LineaDocInvSerializer(serializers.ModelSerializer):
    class Meta:
        model = LineaDocInv
        exclude = ['CreateDate', 'NoteExistsFlag', 'RecordDate', 'RowPointer', 'UpdatedBy', 'CreatedBy']


class DocumentoInvDetailSerializer(serializers.ModelSerializer):
    lineas = serializers.SerializerMethodField()

    class Meta:
        model = DocumentoInv
        exclude = ['CreateDate', 'NoteExistsFlag', 'RecordDate', 'RowPointer', 'UpdatedBy', 'CreatedBy']

    def get_lineas(self, obj):
        lineas = LineaDocInv.objects.filter(DOCUMENTO_INV=obj.DOCUMENTO_INV)
        serializer = LineaDocInvSerializer(lineas, many=True)
        return serializer.data


class ConsecutivoCiSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConsecutivoCi
        exclude = ['CreateDate', 'NoteExistsFlag', 'RecordDate', 'RowPointer', 'UpdatedBy', 'CreatedBy']


class ProveedorSerializer(serializers.ModelSerializer):
    """
    Serializer for Proveedor model.
    This serializer includes fields from the Proveedor model.
    """

    class Meta:
        model = Proveedor
        fields = ['PROVEEDOR', 'NOMBRE', 'PAIS', 'MONEDA', 'MULTIMONEDA', 'DIRECCION', 'TELEFONO1', 'TELEFONO2', 'E_MAIL', 'CONTACTO', 'FAX', 'CARGO', 'RecordDate', 'CONGELADO']
        # exclude = ['CreateDate', 'NoteExistsFlag', 'RowPointer', 'UpdatedBy', 'CreatedBy']

class ProveedorDetailSerializer(serializers.ModelSerializer):
    """
    Serializer for Proveedor model.
    This serializer includes fields from the Proveedor model.
    """
    monedas = serializers.SerializerMethodField()
    condition_pago = serializers.SerializerMethodField()

    class Meta:
        model = Proveedor
        fields = ['PROVEEDOR', 'NOMBRE', 'PAIS', 'MONEDA', 'MULTIMONEDA', 'DIRECCION', 'TELEFONO1', 'TELEFONO2',
                  'E_MAIL', 'CONTACTO', 'FAX', 'CARGO', 'condition_pago', 'monedas', 'CONDICION_PAGO']

    def get_monedas(self, obj):
        if obj.MULTIMONEDA == "S":
            return Moneda.objects.exclude(CODIGO_ISO=None).values('MONEDA', 'NOMBRE', 'CODIGO_ISO')
        else:
            return Moneda.objects.filter(MONEDA=obj.MONEDA).values('MONEDA', 'NOMBRE', 'CODIGO_ISO')

    def get_condition_pago(self, obj):
        return CondicionPago.objects.filter(CONDICION_PAGO=obj.CONDICION_PAGO).values('CONDICION_PAGO', 'DESCRIPCION',
                                                                                      'DIAS_NETO', 'TIPO_CONDPAGO',
                                                                                      'PLAZO_CONDPAGO',
                                                                                      'CONDICION_VENTA')


class ArticuloProveedorSerializer(serializers.ModelSerializer):
    """
    Serializer for ArticuloProveedor model.
    This serializer includes fields from the ArticuloProveedor model.
    """

    class Meta:
        model = ArticuloProveedor
        exclude = ['CreateDate', 'NoteExistsFlag', 'RecordDate', 'RowPointer']

class ArticuloProveedorDetailSerializer(serializers.ModelSerializer):
    """
    Serializer for ArticuloProveedor model.
    This serializer includes fields from the ArticuloProveedor model.
    """
    articulo = serializers.SerializerMethodField()
    default_impuesto = serializers.SerializerMethodField()

    class Meta:
        model = ArticuloProveedor
        exclude = ['CreateDate', 'NoteExistsFlag', 'RecordDate', 'RowPointer']

    def get_articulo(self, obj):
        try:
            articulo = ArticuloCompra.objects.get(ARTICULO=obj.ARTICULO, ULT_PROVEEDOR=obj.PROVEEDOR)
            serializer = ArticuloCompraSerializer(articulo)
            return serializer.data
        except ArticuloCompra.DoesNotExist:
            return None

    def get_default_impuesto(self, obj):
        try:
            impuesto = '1' if obj.PAIS == "RDO" else '2'
            impuesto = Impuesto.objects.get(IMPUESTO=impuesto)
            serializer = ImpuestoSerializer(impuesto)
            return serializer.data
        except Impuesto.DoesNotExist:
            return None

class ArticuloCompraSerializer(serializers.ModelSerializer):
    """
    Serializer for ArticuloCompra model.
    This serializer includes fields from the ArticuloCompra model.
    """
    impuesto = serializers.SerializerMethodField()

    class Meta:
        model = ArticuloCompra
        # fields = '__all__'
        exclude = ['CreateDate', 'NoteExistsFlag', 'RecordDate', 'RowPointer', 'UpdatedBy', 'CreatedBy']

    def get_impuesto(self, obj):
        queryset = Impuesto.objects.filter(IMPUESTO=obj.IMPUESTO).first()
        serializer = ImpuestoSerializer(queryset)
        return serializer.data


class ArticuloSerializer(serializers.ModelSerializer):
    class Meta:
        model = Articulo
        fields = ['ARTICULO', 'DESCRIPCION', 'UNIDAD_ALMACEN', 'UNIDAD_VENTA', 'CLASIFICACION_1', 'CLASIFICACION_2',
                  'CLASIFICACION_5', 'CODIGO_HACIENDA', 'PROVEEDOR', 'PRECIO_BASE_LOCAL', 'PRECIO_BASE_DOLAR',
                  'COSTO_ULT_LOC', 'COSTO_ULT_DOL', 'COSTO_PROM_LOC', 'COSTO_PROM_DOL', 'UNIDAD_EMPAQUE',
                  'CODIGO_BARRAS_VENT', 'CODIGO_BARRAS_INVT']

        #exclude = ['CreateDate', 'NoteExistsFlag', 'RecordDate', 'RowPointer']


class ArticuloSearchSerializer(serializers.ModelSerializer):
    class Meta:
        model = Articulo
        fields = ['ARTICULO', 'DESCRIPCION', 'UNIDAD_ALMACEN', 'UNIDAD_VENTA']


class ProveedorSearchSerializer(serializers.ModelSerializer):
    class Meta:
        model = Proveedor
        fields = ['PROVEEDOR', 'NOMBRE', 'PAIS', 'MULTIMONEDA']


class ArticuloCuentaSerializer(serializers.ModelSerializer):
    """
    Serializer for ArticuloCuenta model.
    This serializer includes fields from the ArticuloCuenta model.
    """

    class Meta:
        model = ArticuloCuenta
        fields = ['ARTICULO_CUENTA','DESCRIPCION']


class ClasificacionSerializer(serializers.ModelSerializer):
    """
    Serializer for ArticuloCuenta model.
    This serializer includes fields from the ArticuloCuenta model.
    """

    class Meta:
        model = Clasificacion
        fields = ['CLASIFICACION','DESCRIPCION']


class ImpuestoSerializer(serializers.ModelSerializer):
    """
    Serializer for Impuesto model.
    This serializer includes fields from the Impuesto model.
    """

    class Meta:
        model = Impuesto
        fields = ['IMPUESTO', 'DESCRIPCION', 'IMPUESTO2_CANTIDAD', 'USA_IMPUESTO2_CANTIDAD', 'IMPUESTO1', 'IMPUESTO2']


class ExistenciaLoteSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExistenciaLote
        fields =['BODEGA', 'LOCALIZACION', 'CANT_RESERVADA', 'CANT_DISPONIBLE', 'CANT_REMITIDA']


class LocalizacionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Localizacion
        fields =['BODEGA', 'LOCALIZACION']


class ArticuloPrecioSerializer(serializers.ModelSerializer):
    class Meta:
        model = ArticuloPrecio
        exclude = ['CreateDate', 'NoteExistsFlag', 'RecordDate', 'RowPointer', 'UpdatedBy', 'CreatedBy']


class ArticuloEnsambleSerializer(serializers.ModelSerializer):
    class Meta:
        model = ArticuloEnsamble
        exclude = ['CreateDate', 'NoteExistsFlag', 'RecordDate', 'RowPointer', 'UpdatedBy', 'CreatedBy']


class ArticuloDetailSerializer(serializers.ModelSerializer):
    """
    Serializer for detailed view of Articulo.
    This serializer includes all fields from the Articulo model.
    """
    articulo_compra = serializers.SerializerMethodField()
    proveedor = serializers.SerializerMethodField()
    articulo_proveedor = serializers.SerializerMethodField()
    articulo_cuenta = serializers.SerializerMethodField()
    impuesto = serializers.SerializerMethodField()
    clasificacion_1 = serializers.SerializerMethodField()
    clasificacion_2 = serializers.SerializerMethodField()
    clasificacion_3 = serializers.SerializerMethodField()
    clasificacion_4 = serializers.SerializerMethodField()
    clasificacion_5 = serializers.SerializerMethodField()
    clasificacion_6 = serializers.SerializerMethodField()
    existencia_lote = serializers.SerializerMethodField()
    precios = serializers.SerializerMethodField()
    child_items = serializers.SerializerMethodField()

    class Meta:
        model = Articulo
        exclude = ['CreateDate', 'NoteExistsFlag', 'RowPointer', 'UpdatedBy', 'CreatedBy']

    def get_articulo_compra(self, obj):
        """
        Returns the related ArticuloCompra objects for the given Articulo.
        """
        queryset = ArticuloCompra.objects.filter(ARTICULO=obj.ARTICULO).first()
        serializer = ArticuloCompraSerializer(queryset)
        return serializer.data

    def get_proveedor(self, obj):
        """
        Returns the related Proveedor object for the given Articulo.
        """
        if obj.PROVEEDOR:
            try:
                proveedor = Proveedor.objects.get(PROVEEDOR=obj.PROVEEDOR)
                return ProveedorSerializer(proveedor).data
            except Proveedor.DoesNotExist:
                return None
        return None

    def get_articulo_proveedor(self, obj):
        """
        Returns the related ArticuloProveedor objects for the given Articulo.
        """
        queryset = ArticuloProveedor.objects.filter(ARTICULO=obj.ARTICULO)
        serializer = ArticuloProveedorSerializer(queryset, many=True)
        return serializer.data

    def get_articulo_cuenta(self, obj):
        """
        Returns the related ArticuloCuenta objects for the given Articulo.
        """
        queryset = ArticuloCuenta.objects.filter(ARTICULO_CUENTA=obj.ARTICULO_CUENTA).first()
        serializer = ArticuloCuentaSerializer(queryset)
        return serializer.data

    def get_impuesto(self, obj):
        """
        Returns the related Impuesto objects for the given Articulo.
        """
        queryset = Impuesto.objects.filter(IMPUESTO=obj.IMPUESTO).first()
        serializer = ImpuestoSerializer(queryset)
        return serializer.data

    def get_clasificacion_1(self, obj):
        """
        Returns the related Impuesto objects for the given Articulo.
        """
        queryset = Clasificacion.objects.filter(CLASIFICACION=obj.CLASIFICACION_1).first()
        serializer = ClasificacionSerializer(queryset)
        return serializer.data

    def get_clasificacion_2(self, obj):
        """
        Returns the related Impuesto objects for the given Articulo.
        """
        queryset = Clasificacion.objects.filter(CLASIFICACION=obj.CLASIFICACION_2).first()
        serializer = ClasificacionSerializer(queryset)
        return serializer.data

    def get_clasificacion_5(self, obj):
        """
        Returns the related Impuesto objects for the given Articulo.
        """
        queryset = Clasificacion.objects.filter(CLASIFICACION=obj.CLASIFICACION_5).first()
        serializer = ClasificacionSerializer(queryset)
        return serializer.data

    def get_clasificacion_4(self, obj):
        """
        Returns the related Impuesto objects for the given Articulo.
        """
        queryset = Clasificacion.objects.filter(CLASIFICACION=obj.CLASIFICACION_4).first()
        serializer = ClasificacionSerializer(queryset)
        return serializer.data

    def get_clasificacion_3(self, obj):
        """
        Returns the related Impuesto objects for the given Articulo.
        """
        queryset = Clasificacion.objects.filter(CLASIFICACION=obj.CLASIFICACION_3).first()
        serializer = ClasificacionSerializer(queryset)
        return serializer.data

    def get_clasificacion_6(self, obj):
        """
        Returns the related Impuesto objects for the given Articulo.
        """
        queryset = Clasificacion.objects.filter(CLASIFICACION=obj.CLASIFICACION_6).first()
        serializer = ClasificacionSerializer(queryset)
        return serializer.data

    def get_existencia_lote(self, obj):
        queryset = ExistenciaLote.objects.filter(ARTICULO=obj.ARTICULO)
        serializer = ExistenciaLoteSerializer(queryset, many=True)
        return serializer.data

    def get_precios(self, obj):
        queryset = ArticuloPrecio.objects.filter(ARTICULO=obj.ARTICULO)
        serializer = ArticuloPrecioSerializer(queryset, many=True)
        return serializer.data

    def get_child_items(self, obj):
        queryset = ArticuloEnsamble.objects.filter(ARTICULO_PADRE=obj.ARTICULO)
        serializer = ArticuloEnsambleSerializer(queryset, many=True)
        return serializer.data


class ItemMasterSerializer(serializers.ModelSerializer):
    class Meta:
        model = ItemMasterView
        fields = '__all__'


class LowStockViewSerializer(serializers.ModelSerializer):
    lead_time_days = serializers.SerializerMethodField()

    class Meta:
        model = LowStockView
        fields = '__all__'

    def get_lead_time_days(self, obj):
        """calculate the lead time days"""
        star_date = obj.SHIP_EMISION if obj.SHIP_EMISION and obj.SHIP_CONFIR and obj.SHIP_EMISION < obj.SHIP_CONFIR else obj.SHIP_CONFIR
        end_date = obj.SHIP_PLANTA if obj.SHIP_PLANTA else obj.SHIP_CRM
        if star_date and end_date:
            delta = end_date - star_date
            return delta.days if delta.days >=0 else 0
        return None


class AgingInventorySummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = AgingInventorySummary
        fields = '__all__'


class InventoryAuditViewSerializer(serializers.ModelSerializer):
    class Meta:
        model = InventoryAuditView
        fields = '__all__'


class InventoryAuditDetailViewSerializer(serializers.ModelSerializer):
    localizacions = serializers.SerializerMethodField()

    class Meta:
        model = InventoryAuditView
        fields = '__all__'

    def get_localizacions(self, obj):
        queryset = InventoryAuditLoteView.objects.filter(ARTICULO=obj.ARTICULO, BODEGA=obj.BODEGA)
        serializer = InventoryAuditLoteViewSerializer(queryset, many=True)
        return serializer.data


class InventoryAuditLoteViewSerializer(serializers.ModelSerializer):
    # transactions = serializers.SerializerMethodField()
    summary = serializers.SerializerMethodField()

    class Meta:
        model = InventoryAuditLoteView
        fields = '__all__'

    def get_transactions(self, obj):
        # FECHA_HORA_TRANSAC__gte=obj.FECHA_CIERRE
        # for testing purposes only FECHA_HORA_TRANSAC__gte = '2025-04-01'
        queryset = TransaccionInv.objects.filter(ARTICULO=obj.ARTICULO, BODEGA=obj.BODEGA,
                                                 LOCALIZACION=obj.LOCALIZACION,
                                                 # AJUSTE_CONFIG='~TT~',
                                                 FECHA_HORA_TRANSAC__gte=obj.FECHA_CIERRE).order_by('FECHA_HORA_TRANSAC')
        serializer = TransaccionInvSerializer(queryset, many=True)
        return serializer.data

    def get_summary(self, obj):
        queryset = (TransaccionInv.objects.filter(ARTICULO=obj.ARTICULO, BODEGA=obj.BODEGA,
                                                  LOCALIZACION=obj.LOCALIZACION,
                                                  FECHA_HORA_TRANSAC__gte=obj.FECHA_CIERRE)
        .values('AJUSTE_CONFIG').annotate(
            total_cant=Sum('CANTIDAD'),
            ajuste_desc=Subquery(
                AjusteConfig.objects.filter(AJUSTE_CONFIG=OuterRef('AJUSTE_CONFIG'))
                .values('DESCRIPCION')[:1]
            )
        ))
        return queryset.values('AJUSTE_CONFIG', 'total_cant', 'ajuste_desc')


class ItemsSalesHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ItemsSalesHistory
        fields = '__all__'


class SolicitudOcLineaSerializer(serializers.ModelSerializer):
    articulo = serializers.SerializerMethodField()
    compras = serializers.SerializerMethodField()

    class Meta:
        model = SolicitudOcLinea
        exclude = ['CreateDate', 'NoteExistsFlag', 'RowPointer', 'UpdatedBy', 'CreatedBy']

    def get_articulo(self, obj):
        try:
            articulo = Articulo.objects.get(ARTICULO=obj.ARTICULO)
            serializer = ArticuloSerializer(articulo)
            return serializer.data
        except Articulo.DoesNotExist:
            return None

    def get_compras(self, obj):
        try:
            articulo = ArticuloCompra.objects.get(ARTICULO=obj.ARTICULO)
            serializer = ArticuloCompraSerializer(articulo)
            return serializer.data
        except ArticuloCompra.DoesNotExist:
            return None


class DepartamentoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Departamento
        exclude = ['NoteExistsFlag', 'RowPointer', 'UpdatedBy', 'CreatedBy', 'CreateDate']


class SolicitudOcSerializer(serializers.ModelSerializer):
    class Meta:
        model = SolicitudOc
        exclude = ['CreateDate', 'NoteExistsFlag', 'RowPointer', 'UpdatedBy', 'CreatedBy']


class SolicitudOcDetailSerializer(serializers.ModelSerializer):
    solicitud_oc_lineas = serializers.SerializerMethodField()

    class Meta:
        model = SolicitudOc
        exclude = ['CreateDate', 'NoteExistsFlag', 'RowPointer', 'UpdatedBy', 'CreatedBy']

    def get_solicitud_oc_lineas(self, obj):
        linea = SolicitudOcLinea.objects.filter(SOLICITUD_OC=obj.SOLICITUD_OC)
        serializer = SolicitudOcLineaSerializer(linea, many=True)
        return serializer.data


class CentroCostoSerializer(serializers.ModelSerializer):
    class Meta:
        model = CentroCosto
        fields = ['CENTRO_COSTO', 'DESCRIPCION']


class CuentaContableSerializer(serializers.ModelSerializer):
    class Meta:
        model = CuentaContable
        fields = ['CUENTA_CONTABLE', 'DESCRIPCION', 'USO_RESTRINGIDO']


class OrdenCompraLineaSerializer(serializers.ModelSerializer):
    articulo = serializers.SerializerMethodField()

    class Meta:
        model = OrdenCompraLinea
        exclude = ['CreateDate', 'NoteExistsFlag', 'RowPointer', 'UpdatedBy', 'CreatedBy']

    def get_articulo(self, obj):
        try:
            articulo = Articulo.objects.get(ARTICULO=obj.ARTICULO)
            serializer = ArticuloSearchSerializer(articulo)
            return serializer.data
        except Articulo.DoesNotExist:
            return None


class OrdenCompraSerializer(serializers.ModelSerializer):
    proveedor = serializers.SerializerMethodField()

    class Meta:
        model = OrdenCompra
        exclude = ['CreateDate', 'NoteExistsFlag', 'RowPointer', 'UpdatedBy', 'CreatedBy']

    def get_proveedor(self, obj):
        try:
            proveedor = Proveedor.objects.get(PROVEEDOR=obj.PROVEEDOR)
            serializer = ProveedorSearchSerializer(proveedor)
            return serializer.data
        except Proveedor.DoesNotExist:
            return None

class SeguimientoOrdenSerializer(serializers.ModelSerializer):
    class Meta:
        model = SeguimientoOrden
        exclude = ['CreateDate', 'NoteExistsFlag', 'RowPointer', 'UpdatedBy', 'CreatedBy','FUENTE']

class OrdenCompraDetailSerializer(serializers.ModelSerializer):
    orden_compra_lineas = serializers.SerializerMethodField()
    seguimiento = serializers.SerializerMethodField()

    class Meta:
        model = OrdenCompra
        exclude = ['NoteExistsFlag', 'RowPointer']

    def get_orden_compra_lineas(self, obj):
        linea = OrdenCompraLinea.objects.filter(ORDEN_COMPRA=obj.ORDEN_COMPRA)
        serializer = OrdenCompraLineaSerializer(linea, many=True)
        return serializer.data

    def get_seguimiento(self, obj):
        seguimeineto = [{'FECHA': obj.FECHA_REQUERIDA, 'ESTADO': 'Solicitud', 'USUARIO': None}]
        if obj.FECHA_COTIZACION:
            seguimeineto.append({'FECHA': obj.FECHA_COTIZACION, 'ESTADO': 'Cotizacion', 'USUARIO': None})

        if obj.FECHA_HORA_CONFIR:
            if obj.FECHA_HORA_CONFIR and obj.FECHA_EMISION:
                if obj.FECHA_HORA_CONFIR < obj.FECHA_EMISION:
                    seguimeineto.append({'FECHA': obj.FECHA_HORA_CONFIR, 'ESTADO': 'Colocar orden/Transito', 'USUARIO': None})
                else:
                    seguimeineto.append({'FECHA': obj.FECHA_EMISION, 'ESTADO': 'Colocar orden/Transito', 'USUARIO': None})
            embarque_linea = EmbarqueLinea.objects.filter(ORDEN_COMPRA=obj.ORDEN_COMPRA).order_by('-CreateDate').first()
            if embarque_linea:
                embarque = Embarque.objects.filter(EMBARQUE=embarque_linea.EMBARQUE).first()
                if embarque:
                    if embarque.FECHA_PLANTA and embarque.FECHA_PLANTA > embarque.FECHA_CRM:
                        seguimeineto.append({'FECHA': embarque.FECHA_PLANTA, 'ESTADO': 'Recepcion de mercancia', 'USUARIO': None})
                    else:
                        seguimeineto.append(
                            {'FECHA': embarque.FECHA_CRM, 'ESTADO': 'Recepcion de mercancia', 'USUARIO': None})
                    seguimeineto.append({'FECHA': embarque.FECHA_HORA_APLICAC, 'ESTADO': 'Creacion de embarque/ingreso de mercancia', 'USUARIO': None})
                    if embarque.FECHA_HORA_LIQUIDA:
                        seguimeineto.append({'FECHA': embarque.FECHA_HORA_LIQUIDA, 'ESTADO': 'Liquidacion de mercancia', 'USUARIO': embarque.USUARIO_LIQUIDACIO})
        if obj.FECHA_NO_APRUEBA:
            seguimeineto.append({'FECHA': obj.FECHA_NO_APRUEBA, 'ESTADO': 'No aprobada', 'USUARIO': obj.USUARIO_NO_APRUEBA})
        if obj.FECHA_HORA_CANCELA:
            seguimeineto.append({'FECHA': obj.FECHA_HORA_CANCELA, 'ESTADO': 'Cancelada', 'USUARIO': obj.USUARIO_CANCELA})
        if obj.FECHA_HORA_CIERRE:
            seguimeineto.append({'FECHA': obj.FECHA_HORA_CIERRE, 'ESTADO': 'Cerrada', 'USUARIO': obj.USUARIO_CIERRE})
        return seguimeineto



class EmbarqueLineaSerializer(serializers.ModelSerializer):
    articulo = serializers.SerializerMethodField()

    class Meta:
        model = EmbarqueLinea
        exclude = ['CreateDate', 'NoteExistsFlag', 'RowPointer', 'UpdatedBy', 'CreatedBy']

    def get_articulo(self, obj):
        try:
            articulo = Articulo.objects.get(ARTICULO=obj.ARTICULO)
            serializer = ArticuloSearchSerializer(articulo)
            return serializer.data
        except Articulo.DoesNotExist:
            return None


class EmbarqueSerializer(serializers.ModelSerializer):
    proveedor = serializers.SerializerMethodField()

    class Meta:
        model = Embarque
        exclude = ['CreateDate', 'NoteExistsFlag', 'RowPointer', 'UpdatedBy', 'CreatedBy']

    def get_proveedor(self, obj):
        try:
            proveedor = Proveedor.objects.get(PROVEEDOR=obj.PROVEEDOR)
            serializer = ProveedorSearchSerializer(proveedor)
            return serializer.data
        except Proveedor.DoesNotExist:
            return None


class DevolLinEmbarqueSerializer(serializers.ModelSerializer):
    class Meta:
        model = DevolLinEmbarque
        exclude = ['CreateDate', 'NoteExistsFlag', 'RowPointer', 'UpdatedBy', 'CreatedBy']


class DevolucionSerializer(serializers.ModelSerializer):
    linea = serializers.SerializerMethodField()

    class Meta:
        model = Devolucion
        exclude = ['CreateDate', 'NoteExistsFlag', 'RowPointer', 'UpdatedBy', 'CreatedBy']

    def get_linea(self, obj):
        linea = DevolLinEmbarque.objects.filter(DEVOLUCION=obj.DEVOLUCION)
        serializer = DevolLinEmbarqueSerializer(linea, many=True)
        return serializer.data


class DetLinEmbarqueSerializer(serializers.ModelSerializer):
    class Meta:
        model = DetLinEmbarque
        exclude = ['CreateDate', 'NoteExistsFlag', 'RowPointer', 'UpdatedBy', 'CreatedBy']


class EmbarqueDetailSerializer(serializers.ModelSerializer):
    linea = serializers.SerializerMethodField()
    devoluciones = serializers.SerializerMethodField()
    desglose = serializers.SerializerMethodField()
    class Meta:
        model = Embarque
        exclude = ['NoteExistsFlag', 'RowPointer', 'UpdatedBy', 'CreatedBy']

    def get_linea(self, obj):
        linea = EmbarqueLinea.objects.filter(EMBARQUE=obj.EMBARQUE)
        serializer = EmbarqueLineaSerializer(linea, many=True)
        return serializer.data

    def get_devoluciones(self, obj):
        devoluciones = Devolucion.objects.filter(EMBARQUE=obj.EMBARQUE)
        serializer = DevolucionSerializer(devoluciones, many=True)
        return serializer.data

    def get_desglose(self, obj):
        desglose = DetLinEmbarque.objects.filter(EMBARQUE=obj.EMBARQUE)
        serializer = DetLinEmbarqueSerializer(desglose, many=True)
        return serializer.data

class EmbarqueDocCpSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmbarqueDocCp
        exclude = ['CreateDate', 'NoteExistsFlag', 'RowPointer', 'UpdatedBy', 'CreatedBy']


class DetDocumentoEmbarqueSerializer(serializers.ModelSerializer):
    class Meta:
        model = DetDocumentoEmbarque
        exclude = ['CreateDate', 'NoteExistsFlag', 'RowPointer', 'UpdatedBy', 'CreatedBy']


class DocumentoEmbarqueSerializer(serializers.ModelSerializer):
    doc_cp = serializers.SerializerMethodField()
    detalle = serializers.SerializerMethodField()

    class Meta:
        model = DocumentoEmbarque
        exclude = ['CreateDate', 'NoteExistsFlag', 'RowPointer', 'UpdatedBy', 'CreatedBy']

    def get_doc_cp(self, obj):
        doc_cp = EmbarqueDocCp.objects.filter(DOCUMENTO=obj.DOCUMENTO).first()
        serializer = EmbarqueDocCpSerializer(doc_cp)
        return serializer.data

    def get_detalle(self, obj):
        detalle = DetDocumentoEmbarque.objects.filter(DOCUMENTO=obj.DOCUMENTO).first()
        serializer = DetDocumentoEmbarqueSerializer(detalle)
        return serializer.data


class TransaccionInvSerializer(serializers.ModelSerializer):
    articulo = serializers.SerializerMethodField()

    class Meta:
        model = TransaccionInv
        exclude = ['CreateDate', 'NoteExistsFlag', 'RowPointer', 'UpdatedBy', 'CreatedBy']

    def get_articulo(self, obj):
        try:
            articulo = Articulo.objects.get(ARTICULO=obj.ARTICULO)
            serializer = ArticuloSearchSerializer(articulo)
            return serializer.data
        except Articulo.DoesNotExist:
            return None


class TransaccionInventorySerializer(serializers.ModelSerializer):
    class Meta:
        model = TransaccionInv
        exclude = ['CreateDate', 'NoteExistsFlag', 'RowPointer', 'UpdatedBy', 'CreatedBy']


class AuditTransInvSerializer(serializers.ModelSerializer):
    class Meta:
        model = AuditTransInv
        exclude = ['CreateDate', 'NoteExistsFlag', 'RowPointer', 'UpdatedBy', 'CreatedBy']


class AuditTransInvDetailSerializer(serializers.ModelSerializer):
    transaccion = serializers.SerializerMethodField()

    class Meta:
        model = AuditTransInv
        exclude = ['CreateDate', 'NoteExistsFlag', 'RowPointer', 'UpdatedBy', 'CreatedBy']

    def get_transaccion(self, obj):
        transaccion = TransaccionInv.objects.filter(AUDIT_TRANS_INV=obj.AUDIT_TRANS_INV)
        serializer = TransaccionInvSerializer(transaccion, many=True)
        return serializer.data


class OrdernCompraLineaRequestSerializer(serializers.Serializer):
    """
    orden_compra = 'OC012192'
    orden_compra_linea = 4.0
    linea_usuario = 4.0
    articulo = '208-327-2'
    descripcion = 'Active backplane 6ES7193-6BP00-0BA0'
    bodega = 'A001'
    factor_conversion = 1.0
    cantidad_ordenada = 6.0
    cantidad_embarcada = 0.0
    cantidad_recibida = 0.0
    cantidad_rechazada = 0.0
    precio_unitario = 100.0
    impuesto1 = 0.0
    imp1_asumido_desc = 0.0
    imp1_asumido_nodesc = 0.0
    imp2_por_cantidad = 'N'
    impuesto2 = 0.0
    tipo_descuento = 'P'
    porc_descuento = 0.0
    monto_descuento = 0.0
    fecha = '20250905 03:34:08.000'
    estado = 'A'
    comentario = NULL
    fecha_requerida = '20250901 00:00:00.000'
    fec_embarque_prov = NULL
    dias_para_entrega = 0.0
    lote = NULL
    localizacion = NULL
    factura = NULL
    unidad_distribucio = NULL
    centro_costo = NULL
    cuenta_contable = NULL
    e_mail = NULL
    cantidad_aceptada = 0.0
    proyecto = NULL
    fase = NULL
    serie_cadena = NULL
    orden_cambio = NULL
    imp1_afecta_costo = 'S'
    imp1_retenido_desc = 0.0
    imp1_retenido_nodesc = 0.0
    precio_art_prov = 100.0
    concepto_me = NULL
    tipo_impuesto1 = NULL
    tipo_tarifa1 = NULL
    tipo_impuesto2 = NULL
    tipo_tarifa2 = NULL
    es_canasta_basica = 'N'
    porc_exoneracion = 0.0
    monto_exoneracion = 0.0
    montototalimpuestoacreditar = NULL
    montototaldegastoaplicable = NULL
    montoproporcionalidad = NULL
    subtotal_bienes = 600.0
    subtotal_servicios = 0.0
    imp1_por_cantidad = 'N'
    codigo_impuesto = '2'
    tipo_descuento_linea = NULL
    tipo_descuento_otro = NULL
    rowpointer 'F84D374A-5B57-4F46-AED2-F154EAB5E7CD'
    """
    ORDERN_COMPRA = serializers.CharField(max_length=20, required=False)
    ORDEN_COMPRA_LINEA = serializers.IntegerField()
    LINEA_USUARIO = serializers.IntegerField()
    ARTICULO = serializers.CharField(max_length=30, allow_blank=False)
    DESCRIPCION = serializers.CharField(max_length=200)
    BODEGA = serializers.CharField(max_length=10)
    FACTOR_CONVERSION = serializers.DecimalField(max_digits=18, decimal_places=8)
    CANTIDAD_ORDENADA = serializers.DecimalField(max_digits=18, decimal_places=8)
    CANTIDAD_EMBARCADA = serializers.DecimalField(max_digits=18, decimal_places=8, default=0.0)
    CANTIDAD_RECIBIDA = serializers.DecimalField(max_digits=18, decimal_places=8, default=0.0)
    CANTIDAD_RECHAZADA = serializers.DecimalField(max_digits=18, decimal_places=8, default=0.0)
    PRECIO_UNITARIO = serializers.DecimalField(max_digits=18, decimal_places=8)
    IMPUESTO1 = serializers.DecimalField(max_digits=18, decimal_places=8)
    IMP1_ASUMIDO_DESC = serializers.DecimalField(max_digits=18, decimal_places=8, default=0.0)
    IMP1_ASUMIDO_NODESC = serializers.DecimalField(max_digits=18, decimal_places=8, default=0.0)
    IMP2_POR_CANTIDAD = serializers.CharField(max_length=1, default='N')
    IMPUESTO2 = serializers.DecimalField(max_digits=18, decimal_places=8, default=0.0)
    TIPO_DESCUENTO = serializers.CharField(max_length=1, default="P")
    PORC_DESCUENTO = serializers.DecimalField(max_digits=18, decimal_places=8, default=0.0)
    MONTO_DESCUENTO = serializers.DecimalField(max_digits=18, decimal_places=8, default=0.0)
    FECHA = serializers.DateTimeField()
    ESTADO = serializers.CharField(max_length=1)
    COMENTARIO = serializers.CharField(allow_null=True, default=None)
    FECHA_REQUERIDA = serializers.DateTimeField()
    FEC_EMBARQUE_PROV = serializers.DateTimeField(allow_null=True, default=None)
    DIAS_PARA_ENTREGA = serializers.DecimalField(max_digits=18, decimal_places=8, default=0.0)
    LOTE = serializers.CharField(max_length=20, allow_null=True, default=None)
    LOCALIZACION = serializers.CharField(max_length=20, allow_null=True, default=None)
    FACTURA = serializers.CharField(max_length=20, allow_null=True, default=None)
    UNIDAD_DISTRIBUCIO = serializers.CharField(max_length=10, allow_null=True, default=None)
    CENTRO_COSTO = serializers.CharField(max_length=20, allow_null=True, default=None)
    CUENTA_CONTABLE = serializers.CharField(max_length=20, allow_null=True, default=None)
    E_MAIL = serializers.EmailField(allow_null=True, default=None)
    CANTIDAD_ACEPTADA = serializers.DecimalField(max_digits=18, decimal_places=8, default=0.0)
    PROYECTO = serializers.CharField(max_length=20, allow_null=True, default=None)
    FASE = serializers.CharField(max_length=20, allow_null=True, default=None)
    SERIE_CADENA = serializers.CharField(max_length=50, allow_null=True, default=None)
    ORDEN_CAMBIO = serializers.CharField(max_length=20, allow_null=True, default=None)
    IMP1_AFECTA_COSTO = serializers.CharField(max_length=1)
    IMP1_RETENIDO_DESC = serializers.DecimalField(max_digits=18, decimal_places=8, default=0.0)
    IMP1_RETENIDO_NODESC = serializers.DecimalField(max_digits=18, decimal_places=8, default=0.0)
    PRECIO_ART_PROV = serializers.DecimalField(max_digits=18, decimal_places=8)
    CONCEPTO_ME = serializers.CharField(max_length=30, allow_null=True, default=None)
    TIPO_IMPUESTO1 = serializers.CharField(max_length=10, allow_null=True, default=None)
    TIPO_TARIFA1 = serializers.CharField(max_length=10, allow_null=True, default=None)
    TIPO_IMPUESTO2 = serializers.CharField(max_length=10, allow_null=True, default=None)
    TIPO_TARIFA2 = serializers.CharField(max_length=10, allow_null=True, default=None)
    ES_CANASTA_BASICA = serializers.CharField(max_length=1, default='N')
    PORC_EXONERACION = serializers.DecimalField(max_digits=10, decimal_places=8, default=0.0)
    MONTO_EXONERACION = serializers.DecimalField(max_digits=18, decimal_places=8, default=0.0)
    MontoTotalImpuestoAcreditar = serializers.DecimalField(max_digits=18, decimal_places=8, allow_null=True, default=None)
    MontoTotalDeGastoAplicable = serializers.DecimalField(max_digits=18, decimal_places=8, allow_null=True, default=None)
    MontoProporcionalidad = serializers.DecimalField(max_digits=18, decimal_places=8, allow_null=True, default=None)
    SUBTOTAL_BIENES = serializers.DecimalField(max_digits=18, decimal_places=8)
    SUBTOTAL_SERVICIOS = serializers.DecimalField(max_digits=18, decimal_places=8, default=0.0)
    IMP1_POR_CANTIDAD = serializers.CharField(max_length=1, default="N")
    CODIGO_IMPUESTO = serializers.CharField(max_length=10)
    TIPO_DESCUENTO_LINEA = serializers.CharField(max_length=1, allow_null=True, default=None)
    TIPO_DESCUENTO_OTRO = serializers.CharField(max_length=1, allow_null=True, default=None)
    NoteExistsFlag = serializers.BooleanField(default=False)
    # CreatedBy = serializers.CharField(max_length=50, default="CO/DEVELOPER")
    # UpdatedBy = serializers.CharField(max_length=50, default="CO/DEVELOPER")


class OrdenCompraRequestSerializer(serializers.Serializer):
    """
       orden_compra = 'OC012192'
       proveedor = 'P0120',
       pais = 'USA',
       moneda = 'RD$',
       condicion_pago = '0',
       bodega = 'A001',
       modulo_origen = 'CO', /// set by backend
       respon_seguimiento = 'JHENRIQUEZ',
       fecha = '20250901 00:00:00.000',
       fecha_cotizacion = NULL,
       fecha_ofrecida = NULL,
       fecha_emision = NULL,
       fecha_req_embarque = '20250901 00:00:00.000',
       fecha_requerida = '20250901 00:00:00.000',
       direccion_embarque = NULL,
       direccion_cobro = NULL,
       tipo_descuento = ' ',
       porc_descuento = 0.0,
       monto_descuento = 0.0,
       total_mercaderia = 1989.0,
       total_impuesto1 = 0.0,
       total_impuesto2 = 0.0,
       monto_flete = 0.0,
       monto_seguro = 0.0,
       monto_documentacio = 0.0,
       monto_anticipo = 0.0,
       total_a_comprar = 1989.0,
       rubro1 = NULL,
       rubro2 = NULL,
       rubro3 = NULL,
       rubro4 = NULL,
       rubro5 = NULL,
       prioridad = 'M',
       estado = 'A',
       impresa = 'N',
       instrucciones = NULL,
       comentario_cxp = NULL,
       observaciones = 'This is an test purchase order from Kanhasoft',
       fecha_hora = '20250901 02:57:38.020',
       usuario = NULL,
       requiere_confirma = 'S',
       confirmada = 'N',
       orden_programada = 'P',
       usuario_cancela = NULL,
       fecha_hora_cancela = NULL,
       cod_direc_emb = NULL,
       tipo_prorrateo_oc = 'NI',
       presupuesto_cr = NULL,
       notas_noaprobar = NULL,
       departamento = NULL,
       usuario_no_aprueba = NULL,
       fecha_no_aprueba = NULL,
       base_impuesto1 = 0.0,
       base_impuesto2 = 0.0,
       tot_imp1_asum_desc = 0.0,
       tot_imp1_asum_nodesc = 0.0,
       tot_imp1_rete_desc = 0.0,
       tot_imp1_rete_nodesc = 0.0,
       clase_doc_es = NULL,
       resolucion = NULL,
       serie = NULL,
       control_interno = NULL,
       serie_numero = NULL,
       codigo_generador = NULL,
       sello_recepcion = NULL,
       dte = NULL,
       mascara_dte = NULL,
       estado_doc_dte = 'NO PROCESADO',
       clave_referencia_de = NULL
       fecha_hora_confir = NULL
       usuario_confirma = NULL
       fecha_hora_cierre = NULL
       usuario_cierre = NULL
       asiento_cierre = NULL
       recibido_de_mas = 'N'
    """
    ORDEN_COMPRA = serializers.CharField(max_length=20)
    PROVEEDOR = serializers.CharField(max_length=20)
    PAIS = serializers.CharField(max_length=3)
    MONEDA = serializers.CharField(max_length=5)
    CONDICION_PAGO = serializers.CharField(max_length=10)
    BODEGA = serializers.CharField(max_length=10)
    MODULO_ORIGEN = serializers.CharField(max_length=2, default='CO')
    RESPON_SEGUIMIENTO = serializers.CharField(max_length=50)
    FECHA = serializers.DateTimeField()
    FECHA_COTIZACION = serializers.DateTimeField(allow_null=True, default=None)
    FECHA_OFRECIDA = serializers.DateTimeField(allow_null=True, default=None)
    FECHA_EMISION = serializers.DateTimeField(allow_null=True, default=None)
    FECHA_REQ_EMBARQUE = serializers.DateTimeField()
    FECHA_REQUERIDA = serializers.DateTimeField()
    DIRECCION_EMBARQUE = serializers.CharField(max_length=200, allow_null=True, default=None)
    DIRECCION_COBRO = serializers.CharField(max_length=200, allow_null=True, default=None)
    TIPO_DESCUENTO = serializers.CharField(default=" ",  allow_blank=True)
    PORC_DESCUENTO = serializers.DecimalField(max_digits=18, decimal_places=8, default=0.0)
    MONTO_DESCUENTO = serializers.DecimalField(max_digits=18, decimal_places=8, default=0.0)
    TOTAL_MERCADERIA = serializers.DecimalField(max_digits=18, decimal_places=8)
    TOTAL_IMPUESTO1 = serializers.DecimalField(max_digits=18, decimal_places=8)
    TOTAL_IMPUESTO2 = serializers.DecimalField(max_digits=18, decimal_places=8, default=0.0)
    MONTO_FLETE = serializers.DecimalField(max_digits=18, decimal_places=8, default=0.0)
    MONTO_SEGURO = serializers.DecimalField(max_digits=18, decimal_places=8, default=0.0)
    MONTO_DOCUMENTACIO = serializers.DecimalField(max_digits=18, decimal_places=8, default=0.0)
    MONTO_ANTICIPO = serializers.DecimalField(max_digits=18, decimal_places=8, default=0.0)
    TOTAL_A_COMPRAR = serializers.DecimalField(max_digits=18, decimal_places=8)
    RUBRO1 = serializers.CharField(max_length=20, allow_null=True, default=None)
    RUBRO2 = serializers.CharField(max_length=20, allow_null=True, default=None)
    RUBRO3 = serializers.CharField(max_length=20, allow_null=True, default=None)
    RUBRO4 = serializers.CharField(max_length=20, allow_null=True, default=None)
    RUBRO5 = serializers.CharField(max_length=20, allow_null=True, default=None)
    PRIORIDAD = serializers.CharField(max_length=1)
    ESTADO = serializers.CharField(max_length=1)
    IMPRESA = serializers.CharField(max_length=1)
    INSTRUCCIONES = serializers.CharField(allow_null=True, default=None)
    COMENTARIO_CXP = serializers.CharField(allow_null=True, default=None)
    OBSERVACIONES = serializers.CharField(allow_null=True, default=None)
    FECHA_HORA = serializers.DateTimeField()
    USUARIO = serializers.CharField(max_length=50, allow_null=True, default=None)
    REQUIERE_CONFIRMA = serializers.CharField(max_length=1)
    CONFIRMADA = serializers.CharField(max_length=1)
    ORDEN_PROGRAMADA = serializers.CharField(max_length=1)
    USUARIO_CANCELA = serializers.CharField(max_length=50, allow_null=True, default=None)
    FECHA_HORA_CANCELA = serializers.DateTimeField(allow_null=True, default=None)
    COD_DIREC_EMB = serializers.CharField(max_length=20, allow_null=True, default=None)
    TIPO_PRORRATEO_OC = serializers.CharField(max_length=10, default="NI")
    PRESUPUESTO_CR = serializers.CharField(max_length=20, allow_null=True, default=None)
    NOTAS_NOAPROBAR = serializers.CharField(allow_null=True, default=None)
    DEPARTAMENTO = serializers.CharField(max_length=10, allow_null=True, default=None)
    USUARIO_NO_APRUEBA = serializers.CharField(max_length=50, allow_null=True, default=None)
    FECHA_NO_APRUEBA = serializers.DateTimeField(allow_null=True, default=None)
    BASE_IMPUESTO1 = serializers.DecimalField(max_digits=18, decimal_places=8)
    BASE_IMPUESTO2 = serializers.DecimalField(max_digits=18, decimal_places=8)
    TOT_IMP1_ASUM_DESC = serializers.DecimalField(max_digits=18, decimal_places=8, default=0.0)
    TOT_IMP1_ASUM_NODESC = serializers.DecimalField(max_digits=18, decimal_places=8, default=0.0)
    TOT_IMP1_RETE_DESC = serializers.DecimalField(max_digits=18, decimal_places=8, default=0.0)
    TOT_IMP1_RETE_NODESC = serializers.DecimalField(max_digits=18, decimal_places=8, default=0.0)
    CLASE_DOC_ES = serializers.CharField(max_length=10, allow_null=True, default=None)
    RESOLUCION = serializers.CharField(max_length=20, allow_null=True, default=None)
    SERIE = serializers.CharField(max_length=10, allow_null=True, default=None)
    CONTROL_INTERNO = serializers.CharField(max_length=50, allow_null=True, default=None)
    SERIE_NUMERO = serializers.CharField(max_length=50, allow_null=True, default=None)
    CODIGO_GENERADOR = serializers.CharField(max_length=50, allow_null=True, default=None)
    SELLO_RECEPCION = serializers.CharField(max_length=100, allow_null=True, default=None)
    DTE = serializers.CharField(max_length=500, allow_null=True, default=None)
    MASCARA_DTE = serializers.CharField(max_length=100, allow_null=True, default=None)
    ESTADO_DOC_DTE = serializers.CharField(max_length=50, default="NO PROCESADO")
    CLAVE_REFERENCIA_DE = serializers.CharField(max_length=100, allow_null=True, default=None)
    FECHA_HORA_CONFIR = serializers.DateTimeField(allow_null=True, default=None)
    USUARIO_CONFIRMA = serializers.CharField(max_length=50, allow_null=True, default=None)
    FECHA_HORA_CIERRE = serializers.DateTimeField(allow_null=True, default=None)
    USUARIO_CIERRE = serializers.CharField(max_length=50, allow_null=True, default=None)
    ASIENTO_CIERRE = serializers.CharField(max_length=20, allow_null=True, default=None)
    RECIBIDO_DE_MAS = serializers.CharField(max_length=1, default="N")
    NoteExistsFlag = serializers.BooleanField(default=False)
    # CreatedBy = serializers.CharField(max_length=50, default="CO/DEVELOPER")
    # UpdatedBy = serializers.CharField(max_length=50, default="CO/DEVELOPER")
    orden_compra_lineas = OrdernCompraLineaRequestSerializer(many=True)

class EmbarqueLineaRequestSerializer(serializers.Serializer):
    """
    | **Column**                  | **Value**                      |
    | --------------------------- | ------------------------------ |
    | embarque                    | EM006701                       |
    | embarque_linea              | 3                              |
    | proveedor                   | P0730                          |
    | orden_compra                | OC012189                       |
    | orden_compra_linea          | 3                              |
    | articulo                    | 101-999-21                     |
    | bodega                      | A001                           |
    | cantidad_embarcada          | 10                             |
    | cantidad_recibida           | 0                              |
    | cantidad_rechazada          | 0                              |
    | precio_unitario             | 14.831 (approx, long decimal)  |
    | monto_desc_unitario         | 0                              |
    | porc_desc_unitario          | 0                              |
    | moneda_oc                   | RD$                            |
    | cost_un_fisc_local          | 0                              |
    | cost_un_fisc_dolar          | 0                              |
    | cost_un_esti_local          | 0                              |
    | cost_un_esti_dolar          | 0                              |
    | cost_un_real_local          | 0                              |
    | cost_un_real_dolar          | 0                              |
    | plazo_reabast               | 0                              |
    | porc_ajuste_costo           | 0                              |
    | existencia_tot_ing          | 0                              |
    | cant_recibida_ua            | 0                              |
    | cant_rechazada_ua           | 0                              |
    | recibido_de_mas             | N                              |
    | unidad_distribucio          | NULL                           |
    | cantidad_devuelta           | 0                              |
    | cant_devueltaua             | 0                              |
    | centro_costo                | NULL                           |
    | cuenta_contable             | NULL                           |
    | numero                      | NULL                           |
    | linea_apartado              | NULL                           |
    | unidad_operativa            | NULL                           |
    | documento                   | NULL                           |
    | tipo_documento              | NULL                           |
    | proyecto                    | NULL                           |
    | fase                        | NULL                           |
    | orden_cambio                | NULL                           |
    | imp1_afectacosto            | S                              |
    | concepto_me                 | NULL                           |
    | cost_un_comp_local          | 0                              |
    | cost_un_comp_dolar          | 0                              |
    | cost_un_esti_comp_local     | 0                              |
    | cost_un_esti_comp_dolar     | 0                              |
    | cost_un_real_comp_local     | 0                              |
    | cost_un_real_comp_dolar     | 0                              |
    | monto_aplicado_oc           | 0                              |
    | backorder_monto             | N                           |
    | tipo_impuesto1              | NULL                           |
    | tipo_tarifa1                | NULL                           |
    | tipo_impuesto2              | NULL                           |
    | tipo_tarifa2                | NULL                           |
    | es_canasta_basica           | N                              |
    | porc_exoneracion            | 0                              |
    | monto_exoneracion           | 0                              |
    | subtotal_bienes_oc          | 148.310 (approx, long decimal) |
    | subtotal_servicios_oc       | 0                              |
    | codigo_impuesto             | 1                              |
    | tipo_descuento              | P                              |
    """
    EMBARQUE = serializers.CharField(max_length=20)
    EMBARQUE_LINEA = serializers.IntegerField()
    PROVEEDOR = serializers.CharField(max_length=20)
    ORDEN_COMPRA = serializers.CharField(max_length=20)
    ORDEN_COMPRA_LINEA = serializers.IntegerField()
    ARTICULO = serializers.CharField(max_length=30, allow_blank=False)
    BODEGA = serializers.CharField(max_length=10)
    CANTIDAD_EMBARCADA = serializers.DecimalField(max_digits=18, decimal_places=8)
    CANTIDAD_RECIBIDA = serializers.DecimalField(max_digits=18, decimal_places=8, default=0.0)
    CANTIDAD_RECHAZADA = serializers.DecimalField(max_digits=18, decimal_places=8, default=0.0)
    PRECIO_UNITARIO = serializers.DecimalField(max_digits=18, decimal_places=8)
    MONTO_DESC_UNITARIO = serializers.DecimalField(max_digits=18, decimal_places=8, default=0.0)
    PORC_DESC_UNITARIO = serializers.DecimalField(max_digits=18, decimal_places=8, default=0.0)
    MONEDA_OC = serializers.CharField(max_length=10)
    COST_UN_FISC_LOCAL = serializers.DecimalField(max_digits=18, decimal_places=8, default=0.0)
    COST_UN_FISC_DOLAR = serializers.DecimalField(max_digits=18, decimal_places=8, default=0.0)
    COST_UN_ESTI_LOCAL = serializers.DecimalField(max_digits=18, decimal_places=8, default=0.0)
    COST_UN_ESTI_DOLAR = serializers.DecimalField(max_digits=18, decimal_places=8, default=0.0)
    COST_UN_REAL_LOCAL = serializers.DecimalField(max_digits=18, decimal_places=8, default=0.0)
    COST_UN_REAL_DOLAR = serializers.DecimalField(max_digits=18, decimal_places=8, default=0.0)
    PLAZO_REABAST = serializers.DecimalField(max_digits=18, decimal_places=8, default=0.0)
    PORC_AJUSTE_COSTO = serializers.DecimalField(max_digits=18, decimal_places=8, default=0.0)
    EXISTENCIA_TOT_ING = serializers.DecimalField(max_digits=18, decimal_places=8, default=0.0)
    CANT_RECIBIDA_UA = serializers.DecimalField(max_digits=18, decimal_places=8, default=0.0)
    CANT_RECHAZADA_UA = serializers.DecimalField(max_digits=18, decimal_places=8, default=0.0)
    RECIBIDO_DE_MAS = serializers.CharField(max_length=1, default='N')
    UNIDAD_DISTRIBUCIO = serializers.CharField(max_length=10, allow_null=True, default=None)
    CANTIDAD_DEVUELTA = serializers.DecimalField(max_digits=18, decimal_places=8, default=0.0)
    CANT_DEVUELTAUA = serializers.DecimalField(max_digits=18, decimal_places=8, default=0.0)
    CENTRO_COSTO = serializers.CharField(max_length=20, allow_null=True, default=None)
    CUENTA_CONTABLE = serializers.CharField(max_length=20, allow_null=True, default=None)
    NUMERO = serializers.CharField(max_length=20, allow_null=True, default=None)
    LINEA_APARTADO = serializers.CharField(max_length=20, allow_null=True, default=None)
    UNIDAD_OPERATIVA = serializers.CharField(max_length=20, allow_null=True, default=None)
    DOCUMENTO = serializers.CharField(max_length=20, allow_null=True, default=None)
    TIPO_DOCUMENTO = serializers.CharField(max_length=10, allow_null=True, default=None)
    PROYECTO = serializers.CharField(max_length=20, allow_null=True, default=None)
    FASE = serializers.CharField(max_length=20, allow_null=True, default=None)
    ORDEN_CAMBIO = serializers.CharField(max_length=20, allow_null=True, default=None)
    IMP1_AFECTACOSTO = serializers.CharField(max_length=1, default='S')
    CONCEPTO_ME = serializers.CharField(max_length=30, allow_null=True, default=None)
    COST_UN_COMP_LOCAL = serializers.DecimalField(max_digits=18, decimal_places=8, default=0.0)
    COST_UN_COMP_DOLAR = serializers.DecimalField(max_digits=18, decimal_places=8, default=0.0)
    COST_UN_ESTI_COMP_LOCAL = serializers.DecimalField(max_digits=18, decimal_places=8, default=0.0)
    COST_UN_ESTI_COMP_DOLAR = serializers.DecimalField(max_digits=18, decimal_places=8, default=0.0)
    COST_UN_REAL_COMP_LOCAL = serializers.DecimalField(max_digits=18, decimal_places=8, default=0.0)
    COST_UN_REAL_COMP_DOLAR = serializers.DecimalField(max_digits=18, decimal_places=8, default=0.0)
    MONTO_APLICADO_OC = serializers.DecimalField(max_digits=18, decimal_places=8, default=0.0)
    BACKORDER_MONTO = serializers.CharField(max_length=1, default='N')
    IMPUESTO1 = serializers.DecimalField(max_digits=28, decimal_places=8)
    TIPO_IMPUESTO1 = serializers.CharField(max_length=10, allow_null=True, default=None)
    TIPO_TARIFA1 = serializers.CharField(max_length=10, allow_null=True, default=None)
    TIPO_IMPUESTO2 = serializers.CharField(max_length=10, allow_null=True, default=None)
    TIPO_TARIFA2 = serializers.CharField(max_length=10, allow_null=True, default=None)
    ES_CANASTA_BASICA = serializers.CharField(max_length=1, default='N')
    PORC_EXONERACION = serializers.DecimalField(max_digits=10, decimal_places=8, default=0.0)
    MONTO_EXONERACION = serializers.DecimalField(max_digits=18, decimal_places=8, default=0.0)
    SUBTOTAL_BIENES_OC = serializers.DecimalField(max_digits=18, decimal_places=8)
    SUBTOTAL_SERVICIOS_OC = serializers.DecimalField(max_digits=18, decimal_places=8, default=0.0)
    CODIGO_IMPUESTO = serializers.CharField(max_length=10, allow_null=True, allow_blank=True)
    TIPO_DESCUENTO = serializers.CharField(max_length=1, default='P')
    NoteExistsFlag = serializers.BooleanField(default=False)
    # CreatedBy = serializers.CharField(max_length=50, default="CO/DEVELOPER")
    # UpdatedBy = serializers.CharField(max_length=50, default="CO/DEVELOPER")

class DetLinEmabarqueRequestSerializer(serializers.Serializer):
    """
    | **Column**          | **Value**                            |
    | ------------------- | ------------------------------------ |
    | embarque            | em006701                             |
    | embarque_linea      | 1                                    |
    | secuencia           | 1                                    |
    | cant_recibida       | 3                                    |
    | cant_rechazada      | 0                                    |
    | cant_recibida_ua    | 3                                    |
    | cant_rechazada_ua   | 0                                    |
    | bodega              | a001                                 |
    | serie_cadena        | NULL                                 |
    | localizacion        | 1-05-24                              |
    | lote                | NULL                                 |
    | rowpointer          | 6dc606f1-7f78-4296-a2a9-e0233ef12986 |
    """
    EMBARQUE = serializers.CharField(max_length=20)
    EMBARQUE_LINEA = serializers.IntegerField()
    SECUENCIA = serializers.IntegerField()
    CANT_RECIBIDA = serializers.DecimalField(max_digits=18, decimal_places=8)
    CANT_RECHAZADA = serializers.DecimalField(max_digits=18, decimal_places=8, default=0.0)
    CANT_RECIBIDA_UA = serializers.DecimalField(max_digits=18, decimal_places=8)
    CANT_RECHAZADA_UA = serializers.DecimalField(max_digits=18, decimal_places=8, default=0.0)
    BODEGA = serializers.CharField(max_length=10)
    SERIE_CADENA = serializers.CharField(max_length=50, allow_null=True, default=None)
    LOCALIZACION = serializers.CharField(max_length=20)
    LOTE = serializers.CharField(max_length=20, allow_null=True, default=None)
    NoteExistsFlag = serializers.BooleanField(default=False)
    # CreatedBy = serializers.CharField(max_length=50, default="CO/DEVELOPER")
    # UpdatedBy = serializers.CharField(max_length=50, default="CO/DEVELOPER")

class EmbarqueRequestSerializer(serializers.Serializer):
    """
    | **Column**           | **Value**                            |
    | -------------------- | ------------------------------------ |
    | embarque             | EM006701                             |
    | proveedor            | P0730                                |
    | crm                  | NULL                                 |
    | fecha_requerida      | NULL                                 |
    | fecha_ofrecida       | NULL                                 |
    | fecha_embarque       | 2025-09-11 00:00:00.000              |
    | fecha_a_consol       | NULL                                 |
    | fecha_desde_cons     | NULL                                 |
    | fecha_aduana         | NULL                                 |
    | fecha_agencia        | NULL                                 |
    | fecha_tramite        | NULL                                 |
    | fecha_planta         | NULL                                 |
    | fecha_crm            | 2025-09-11 00:00:00.000              |
    | asiento_recibo       | N                                    |
    | asiento_liquidacio   | N                                    |
    | notas                | (empty string)                       |
    | estado               | P                                    |
    | liquidado            | N                                    |
    | referencia           | NULL                                 |
    | recmas_afectaback    | N                                    |
    | demas_sepaga         | N                                    |
    | tiene_factura        | S                                    |
    | pedimento            | NULL                                 |
    | rubro1               | NULL                                 |
    | rubro2               | NULL                                 |
    | rubro3               | NULL                                 |
    | rubro4               | NULL                                 |
    | rubro5               | NULL                                 |
    | usuario_creado       | DEVELOPER                            |
    | fecha_hora_creado    | 2025-09-11 03:51:19.277              |
    | usuario_aplicado     | NULL                                 |
    | fecha_hora_aplicac   | NULL                                 |
    | audit_trans_inv      | NULL                                 |
    | usuario_liquidacio   | NULL                                 |
    | fecha_hora_liquida   | NULL                                 |
    | asiento              | NULL                                 |
    | liquidac_compra      | NULL                                 |
    | recibido_de_mas      | N                                    |
    | multimoneda          | S                                    |
    | RowPointer           | 31163A59-F72B-4348-8E1B-5FBA31FCB0E3 |
    """
    EMBARQUE = serializers.CharField(max_length=20)
    PROVEEDOR = serializers.CharField(max_length=20)
    CRM = serializers.CharField(max_length=10)
    FECHA_REQUERIDA = serializers.DateTimeField(allow_null=True, default=None)
    FECHA_OFRECIDA = serializers.DateTimeField(allow_null=True, default=None)
    FECHA_EMBARQUE = serializers.DateTimeField()
    FECHA_A_CONSOL = serializers.DateTimeField(allow_null=True, default=None)
    FECHA_DESDE_CONS = serializers.DateTimeField(allow_null=True, default=None)
    FECHA_ADUANA = serializers.DateTimeField(allow_null=True, default=None)
    FECHA_AGENCIA = serializers.DateTimeField(allow_null=True, default=None)
    FECHA_TRAMITE = serializers.DateTimeField(allow_null=True, default=None)
    FECHA_PLANTA = serializers.DateTimeField(allow_null=True, default=None)
    FECHA_CRM = serializers.DateTimeField()
    ASIENTO_RECIBO = serializers.CharField(max_length=1, default='N')
    ASIENTO_LIQUIDACIO = serializers.CharField(max_length=1, default='N')
    NOTAS = serializers.CharField(allow_blank=True, default="")
    ESTADO = serializers.CharField(max_length=1, default='P')
    LIQUIDADO = serializers.CharField(max_length=1, default='N')
    REFERENCIA = serializers.CharField(max_length=20, allow_null=True, default=None)
    RECMAS_AFECTABACK = serializers.CharField(max_length=1, default='N')
    DEMAS_SEPAGA = serializers.CharField(max_length=1, default='N')
    TIENE_FACTURA = serializers.CharField(max_length=1, default='S')
    PEDIMENTO = serializers.CharField(max_length=20, allow_null=True, default=None)
    RUBRO1 = serializers.CharField(max_length=20, allow_null=True, default=None)
    RUBRO2 = serializers.CharField(max_length=20, allow_null=True, default=None)
    RUBRO3 = serializers.CharField(max_length=20, allow_null=True, default=None)
    RUBRO4 = serializers.CharField(max_length=20, allow_null=True, default=None)
    RUBRO5 = serializers.CharField(max_length=20, allow_null=True, default=None)
    USUARIO_CREADO = serializers.CharField(max_length=50, default="DEVELOPER")
    FECHA_HORA_CREADO = serializers.DateTimeField()
    USUARIO_APLICADO = serializers.CharField(max_length=50, allow_null=True, default=None)
    FECHA_HORA_APLICAC = serializers.DateTimeField(allow_null=True, default=None)
    AUDIT_TRANS_INV = serializers.CharField(max_length=50, allow_null=True, default=None)
    USUARIO_LIQUIDACIO = serializers.CharField(max_length=50, allow_null=True, default=None)
    FECHA_HORA_LIQUIDA = serializers.DateTimeField(allow_null=True, default=None)
    ASIENTO = serializers.CharField(max_length=20, allow_null=True, default=None)
    LIQUIDAC_COMPRA = serializers.CharField(max_length=15, allow_null=True, default=None)
    RECIBIDO_DE_MAS = serializers.CharField(max_length=1, default='N')
    MULTIMONEDA = serializers.CharField(max_length=1, default='S')
    NoteExistsFlag = serializers.BooleanField(default=False)
    # CreatedBy = serializers.CharField(max_length=50, default="CO/DEVELOPER")
    # UpdatedBy = serializers.CharField(max_length=50, default="CO/DEVELOPER")
    embarque_lineas = EmbarqueLineaRequestSerializer(many=True)
    desglose_lineas = DetLinEmabarqueRequestSerializer(many=True)


class ConversionRateRequestSerializer(serializers.Serializer):
    moneda = serializers.CharField(max_length=5)
    fecha = serializers.DateField()


class ArticuloProveedorRequestSerializer(serializers.Serializer):
    articulo = serializers.CharField(max_length=30)
    proveedor = serializers.CharField(max_length=20)

class SolicitudLineaRequestSerializer(serializers.Serializer):
    """
    | Column             | Value                                  |
    | ------------------ | -------------------------------------- |
    | solicitud_oc       | `SC000999`                             |
    | solicitud_oc_linea | `1.0`                                  |
    | articulo           | `194-359-2`                            |
    | descripcion        | `' '` (empty space)                    |
    | cantidad           | `24.0`                                 |
    | saldo              | `24.0`                                 |
    | estado             | `A`                                    |
    | comentario         | `NULL`                                 |
    | fecha_requerida    | `2025-09-29 00:00:00.000`              |
    | unidad_distribucio | `NULL`                                 |
    | fecha_hora_cancela | `NULL`                                 |
    | usuario_cancela    | `NULL`                                 |
    | centro_costo       | `NULL`                                 |
    | cuenta_contable    | `NULL`                                 |
    | e_mail             | `NULL`                                 |
    | proyecto           | `NULL`                                 |
    | fase               | `NULL`                                 |
    | orden_cambio       | `NULL`                                 |
    | rowpointer         | `6E6AFB47-D5C5-47E0-9894-890567E88848` |

    """
    SOLICITUD_OC = serializers.CharField(max_length=20)
    SOLICITUD_OC_LINEA = serializers.IntegerField()
    ARTICULO = serializers.CharField(max_length=30, allow_blank=False)
    DESCRIPCION = serializers.CharField(max_length=200, default=' ', allow_null=True)
    CANTIDAD = serializers.DecimalField(max_digits=18, decimal_places=8)
    SALDO = serializers.DecimalField(max_digits=18, decimal_places=8)
    ESTADO = serializers.CharField(max_length=1, default='A')
    COMENTARIO = serializers.CharField(allow_null=True, default=None)
    FECHA_REQUERIDA = serializers.DateTimeField()
    UNIDAD_DISTRIBUCIO = serializers.CharField(max_length=10, allow_null=True, default=None)
    FECHA_HORA_CANCELA = serializers.DateTimeField(allow_null=True, default=None)
    USUARIO_CANCELA = serializers.CharField(max_length=50, allow_null=True, default=None)
    CENTRO_COSTO = serializers.CharField(max_length=20, allow_null=True, default=None)
    CUENTA_CONTABLE = serializers.CharField(max_length=20, allow_null=True, default=None)
    E_MAIL = serializers.CharField(max_length=100, allow_null=True, default=None)
    PROYECTO = serializers.CharField(max_length=20, allow_null=True, default=None)
    FASE = serializers.CharField(max_length=20, allow_null=True, default=None)
    ORDEN_CAMBIO = serializers.CharField(max_length=20, allow_null=True, default=None)
    NoteExistsFlag = serializers.BooleanField(default=False)
    # CreatedBy = serializers.CharField(max_length=50, default="CO/DEVELOPER")
    # UpdatedBy = serializers.CharField(max_length=50, default="CO/DEVELOPER")


class SolicitudCompraRequestSerializer(serializers.Serializer):
    """
    | Column             | Value                                  |
    | ------------------ | -------------------------------------- |
    | solicitud_oc       | `SC000999`                             |
    | departamento       | `D011`                                 |
    | fecha_solicitud    | `2025-09-29 00:00:00.000`              |
    | fecha_requerida    | `2025-09-29 00:00:00.000`              |
    | autorizada_por     | `NULL`                                 |
    | prioridad          | `M`                                    |
    | lineas_no_asig     | `2.0`                                  |
    | estado             | `A`                                    |
    | comentario         | `''` (empty string)                    |
    | rubro1             | `NULL`                                 |
    | rubro2             | `NULL`                                 |
    | rubro3             | `NULL`                                 |
    | rubro4             | `NULL`                                 |
    | rubro5             | `NULL`                                 |
    | fecha_hora         | `2025-09-29 06:29:44.123`              |
    | usuario            | `SA`                                   |
    | fecha_autorizada   | `NULL`                                 |
    | usuario_cancela    | `NULL`                                 |
    | fecha_hora_cancela | `NULL`                                 |
    | rowpointer         | `AA4A905D-366D-4686-B9E1-4366BEFCFFE6` |
    """
    SOLICITUD_OC = serializers.CharField(max_length=20)
    DEPARTAMENTO = serializers.CharField(max_length=10)
    FECHA_SOLICITUD = serializers.DateTimeField()
    FECHA_REQUERIDA = serializers.DateTimeField()
    AUTORIZADA_POR = serializers.CharField(max_length=50, allow_null=True, default=None)
    PRIORIDAD = serializers.CharField(max_length=1, default='M')
    LINEAS_NO_ASIG = serializers.IntegerField()
    ESTADO = serializers.CharField(max_length=1, default='A')
    COMENTARIO = serializers.CharField(allow_blank=True, default="")
    RUBRO1 = serializers.CharField(max_length=20, allow_null=True, default=None)
    RUBRO2 = serializers.CharField(max_length=20, allow_null=True, default=None)
    RUBRO3 = serializers.CharField(max_length=20, allow_null=True, default=None)
    RUBRO4 = serializers.CharField(max_length=20, allow_null=True, default=None)
    RUBRO5 = serializers.CharField(max_length=20, allow_null=True, default=None)
    FECHA_HORA = serializers.DateTimeField()
    USUARIO = serializers.CharField(max_length=50, default="DEVELOPER")
    FECHA_AUTORIZADA = serializers.DateTimeField(allow_null=True, default=None)
    USUARIO_CANCELA = serializers.CharField(max_length=50, allow_null=True, default=None)
    FECHA_HORA_CANCELA = serializers.DateTimeField(allow_null=True, default=None)
    NoteExistsFlag = serializers.BooleanField(default=False)
    # CreatedBy = serializers.CharField(max_length=50, default="CO/DEVELOPER")
    # UpdatedBy = serializers.CharField(max_length=50, default="CO/DEVELOPER")
    solicitud_lineas = SolicitudLineaRequestSerializer(many=True)

class StockTransferLineasSerializer(serializers.Serializer):
    ARTICULO = serializers.CharField(max_length=30)
    LINEA = serializers.IntegerField()
    BODEGA = serializers.CharField(max_length=5)
    BODEGA_DESTINO = serializers.CharField(max_length=5)
    LOCALIZACION = serializers.CharField(max_length=10)
    LOCALIZACION_DEST = serializers.CharField(max_length=10)
    CANTIDAD = serializers.DecimalField(max_digits=18, decimal_places=8)

class StockTransferRequestSerializer(serializers.Serializer):
    REFERENCIA = serializers.CharField(max_length=250)
    CONSECUTIVO = serializers.CharField(max_length=20)
    DOCUMENTO_INV = serializers.CharField(max_length=10)
    PAQUETE_INVENTARIO = serializers.CharField(max_length=4)
    SELECCIONADO = serializers.CharField(max_length=1, default="N")
    FECHA_DOCUMENTO = serializers.DateTimeField()
    lineas = StockTransferLineasSerializer(many=True)


class EmailFormSerializer(serializers.Serializer):
    email = serializers.EmailField()
    subject = serializers.CharField(max_length=255)
    html_content = serializers.CharField()
    attachment1 = serializers.FileField(required=False)
    attachment2 = serializers.FileField(required=False)


class EmailFormAttachmentsSerializer(serializers.Serializer):
    email = serializers.EmailField()
    subject = serializers.CharField(max_length=255)
    html_content = serializers.CharField()
    attachment1 = serializers.FileField()
    attachment2 = serializers.FileField()


class CycleCountTaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = CycleCountTask
        fields = [
            "id",
            "linea",
            "articulo",
            "bodega",
            "location",
            "system_qty",
            "physical_qty",
            "counted_by",
            "counted_at",
            "variance_qty",
            "variance_value",
            "status",
            "reviewed_by",
            "reviewed_at",
            "batch",
        ]
        read_only_fields = ["counted_by", "counted_at", "variance_qty", "variance_value"]
        extra_kwargs = {
            'linea': {'required': True},
            "batch": {'required': False},
        }

    def create(self, validated_data):
        physical_qty = validated_data.get('physical_qty', None)
        if physical_qty is not None:
            validated_data['status'] = 'COUNTED'
            validated_data['counted_by'] = self.context['request'].user
            validated_data['counted_at'] = datetime.now()
            validated_data['variance_qty'] = physical_qty - validated_data['system_qty']
            articulo = Articulo.objects.filter(ARTICULO=validated_data['articulo']).first()
            validated_data['variance_value'] = validated_data['variance_qty'] * articulo.COSTO_ULT_LOC
        return super().create(validated_data)

    def update(self, instance, validated_data):
        physical_qty = validated_data.get('physical_qty', instance.physical_qty)
        instance.physical_qty = physical_qty
        instance.artticulo = validated_data.get('articulo', instance.articulo)
        instance.bodega = validated_data.get('bodega', instance.bodega)
        instance.location = validated_data.get('location', instance.location)
        instance.system_qty = validated_data.get('system_qty', instance.system_qty)
        if physical_qty is not None:
            instance.status = 'COUNTED'
            instance.counted_by = self.context['request'].user
            instance.counted_at = datetime.now()
            instance.variance_qty = physical_qty - instance.system_qty
            articulo = Articulo.objects.filter(ARTICULO=instance.articulo).first()
            instance.variance_value = instance.variance_qty * articulo.COSTO_ULT_LOC
        instance.save()
        return instance


class CycleCountBatchSerializer(serializers.ModelSerializer):
    tasks = CycleCountTaskSerializer(many=True, write_only=True)
    created_by = serializers.HiddenField(default=serializers.CurrentUserDefault())
    batch_number = serializers.SerializerMethodField()

    class Meta:
        model = CycleCountBatch
        fields = [
            "id",
            "document_number",
            "paquete_inventario",
            "scheduled_date",
            "created_by",
            "referencia",
            "status",
            "tasks",
            "batch_number",
        ]
        extra_kwargs = {
            'document_number': {'required': False},  # Make 'description' optional
            'status': {'required': False},  # Make 'description' optional
            'paquete_inventario': {'required': True},
            'scheduled_date': {'required': True},
            # Explicitly make 'name' required and not allow empty strings
        }

    def get_batch_number(self, obj):
        return f"CYCB-{obj.id:05d}"

    def create(self, validated_data):
        tasks_data = validated_data.pop("tasks")

        status_flag = any(['physical_qty' in task_data and task_data['physical_qty'] is not None
                           for task_data in tasks_data])
        validated_data['status'] = 'IN_PROGRESS' if status_flag else 'OPEN'
        # if status_flag and ("document_number" not in validated_data or validated_data["document_number"] is None):
        #     item = ConsecutivoCi.objects.filter(CONSECUTIVO="FISICO").first()
        #     validated_data["document_number"] = item.SIGUIENTE_CONSEC
        batch = CycleCountBatch.objects.create(**validated_data)
        # Create all tasks (bulk or loop)
        for task_data in tasks_data:
            if 'physical_qty' in task_data and task_data['physical_qty'] is not None:
                task_data['status'] = 'COUNTED'
                task_data['variance_qty'] = task_data['physical_qty'] - task_data['system_qty']
                articulo = Articulo.objects.filter(ARTICULO=task_data['articulo']).first()
                task_data['variance_value'] = task_data['variance_qty'] * articulo.COSTO_ULT_LOC
                task_data['counted_by'] = self.context['request'].user
                task_data['counted_at'] = datetime.now()
        tasks = [
            CycleCountTask(batch=batch, **task_data)
            for task_data in tasks_data
        ]
        CycleCountTask.objects.bulk_create(tasks)
        wm_role = Role.objects.filter(code='warehouse-manager').first()
        admin_role = Role.objects.filter(code='admin').first()
        users_to_notify = set()
        if wm_role:
            users_to_notify.update(wm_role.users.all())
        if admin_role:
            users_to_notify.update(admin_role.users.all())
        send_new_cycle_count_alert([batch], users_to_notify)
        return batch

    def update(self, instance, validated_data):
        tasks_data = validated_data.pop("tasks", [])
        instance.document_number = validated_data.get("document_number", instance.document_number)
        instance.paquete_inventario = validated_data.get("paquete_inventario", instance.paquete_inventario)
        instance.scheduled_date = validated_data.get("scheduled_date", instance.scheduled_date)
        instance.referencia = validated_data.get("referencia", instance.referencia)
        instance.save()

        for task_data in tasks_data:
            task_id = task_data.get("id")
            if task_id:
                try:
                    task_instance = CycleCountTask.objects.get(id=task_id, batch=instance)
                    physical_qty = task_data.get('physical_qty', task_instance.physical_qty)
                    task_instance.articulo = task_data.get('articulo', task_instance.articulo)
                    task_instance.bodega = task_data.get('bodega', task_instance.bodega)
                    task_instance.location = task_data.get('location', task_instance.location)
                    task_instance.system_qty = task_data.get('system_qty', task_instance.system_qty)
                    task_instance.physical_qty = physical_qty
                    if physical_qty is not None:
                        task_instance.status = 'COUNTED'
                        task_instance.counted_by = self.context['request'].user
                        task_instance.counted_at = datetime.now()
                        task_instance.variance_qty = physical_qty - task_instance.system_qty
                        articulo = Articulo.objects.filter(ARTICULO=task_instance.articulo).first()
                        task_instance.variance_value = task_instance.variance_qty * articulo.COSTO_ULT_LOC
                    task_instance.save()
                except CycleCountTask.DoesNotExist:
                    continue

        status_flag = any([task.physical_qty is not None for task in instance.tasks.all()])
        instance.status = 'IN_PROGRESS' if status_flag else 'OPEN'
        instance.save()
        return instance


class CycleCountTaskStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = CycleCountTask
        fields = ["status"]
        extra_kwargs = {
            "status": {"required": True}
        }


class HoltWintersForecastSerializer(serializers.ModelSerializer):
    class Meta:
        model = HoltWintersForecast
        fields = [
            "article",
            "forecast_month",
            "forecast_quantity",
        ]


class SarimaForecastSerializer(serializers.ModelSerializer):
    class Meta:
        model = SarimaForecast
        fields = [
            "article",
            "forecast_month",
            "forecast_quantity",
        ]


class ProphetForecastSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProphetForecast
        fields = [
            "article",
            "forecast_month",
            "forecast_quantity",
            "forecast_lower",
            "forecast_upper",
        ]


class SPDispatchItemSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False)

    class Meta:
        model = SPDispatchItem
        fields = ['id', 'article', 'quantity', 'unit_of_measure', 'specifications', 'serial_code']

class SPDispatchHeaderSerializer(serializers.ModelSerializer):
    items = SPDispatchItemSerializer(many=True)
    requested_by_user = serializers.SerializerMethodField()
    returns = serializers.SerializerMethodField()

    class Meta:
        model = SPDispatchHeader
        fields = ['id', 'form_number', 'dispatch_date', 'exit_type', 'exit_type_others',
                  'recipient_name', 'centro_costo', 'observations', 'requested_by', 'items', 'requested_by_user',
                  'returns']

    def get_returns(self, obj):
        returns = SPReturnHeader.objects.filter(original_dispatch=obj).values()
        return returns

    def get_requested_by_user(self, obj):
        if obj.requested_by:
            return {
                "username": obj.requested_by.username,
                "first_name": obj.requested_by.first_name,
                "last_name": obj.requested_by.last_name,
                "email": obj.requested_by.email,
            }
        return None

    def create(self, validated_data):
        # Transaction ensures that if one item fails, the header isn't created
        items_data = validated_data.pop('items')
        with transaction.atomic():
            header = SPDispatchHeader.objects.create(**validated_data)
            for item_data in items_data:
                SPDispatchItem.objects.create(header=header, **item_data)
        return header

    def update(self, instance, validated_data):
        items_data = validated_data.pop('items', None)
        with transaction.atomic():
            # 1. Update the Header fields (Recipient, Project/Centro Costo, etc.)
            for attr, value in validated_data.items():
                setattr(instance, attr, value)
            instance.save()
            # 2. Update Nested Items (if provided in the request)
            if items_data is not None:
                # Get IDs of items currently in the database for this header
                existing_items = {item.id: item for item in instance.items.all()}
                new_items_list = []
                for item_data in items_data:
                    item_id = item_data.get('id', None)
                    if item_id and item_id in existing_items:
                        # Update existing specialized item
                        item_instance = existing_items.pop(item_id)
                        for item_attr, item_value in item_data.items():
                            setattr(item_instance, item_attr, item_value)
                        item_instance.save()
                    else:
                        # Insert new item into the dispatch
                        SPDispatchItem.objects.create(header=instance, **item_data)

                # 3. Delete items that were removed from the form
                # (Ensures items not present in the PUT/PATCH request are removed)
                for remaining_item in existing_items.values():
                    # Rule: Don't delete if it's already been returned
                    if not SPReturnItem.objects.filter(dispatch_item=remaining_item).exists():
                        remaining_item.delete()

        return instance

class SPReturnItemSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False)

    class Meta:
        model = SPReturnItem
        fields = ['id', 'dispatch_item', 'quantity_returned']

    def validate(self, data):
        # Business Logic: Cannot return more than what was dispatched
        dispatch_item = data['dispatch_item']
        if data['quantity_returned'] > dispatch_item.quantity:
            raise serializers.ValidationError(
                f"Cannot return {data['quantity_returned']}. Maximum allowed is {dispatch_item.quantity}."
            )
        return data

class SPReturnHeaderSerializer(serializers.ModelSerializer):
    returned_items = SPReturnItemSerializer(many=True)
    dispatch_id = serializers.SerializerMethodField()
    original_dispatch_details = serializers.SerializerMethodField()
    received_by_user = serializers.SerializerMethodField()

    class Meta:
        model = SPReturnHeader
        fields = ['id', 'original_dispatch', 'return_date', 'received_by', 'reason_for_return', 'returned_items',
                  'dispatch_id', 'original_dispatch_details', 'received_by_user']

    def get_received_by_user(self, obj):
        if obj.received_by:
            return {
                "username": obj.received_by.username,
                "first_name": obj.received_by.first_name,
                "last_name": obj.received_by.last_name,
                "email": obj.received_by.email,
            }
        return None

    def get_dispatch_id(self, obj):
        if obj.original_dispatch:
            # Format as 6 digits with leading zeros
            return f"#{obj.original_dispatch.id:06d}"
        return None

    def get_original_dispatch_details(self, obj):
        # Access the joined original_dispatch object
        if obj.original_dispatch:
            # We pass the object to the detailed serializer
            return SPDispatchHeaderSerializer(obj.original_dispatch).data
        return None

    def create(self, validated_data):
        items_data = validated_data.pop('returned_items')
        with transaction.atomic():
            header = SPReturnHeader.objects.create(**validated_data)
            for item_data in items_data:
                SPReturnItem.objects.create(header=header, **item_data)
        return header

    def update(self, instance, validated_data):
        items_data = validated_data.pop('returned_items', None)

        with transaction.atomic():
            # 1. Update Header fields (date, receiver, reason)
            for attr, value in validated_data.items():
                setattr(instance, attr, value)
            instance.save()

            # 2. Update Nested Items
            if items_data is not None:
                # Map existing items by their ID for easy lookup
                existing_items = {item.id: item for item in instance.returned_items.all()}

                for item_data in items_data:
                    item_id = item_data.get('id')

                    if item_id and item_id in existing_items:
                        # Update existing return line
                        item_instance = existing_items.pop(item_id)
                        for item_attr, item_value in item_data.items():
                            setattr(item_instance, item_attr, item_value)
                        item_instance.save()
                    else:
                        # Create new return line
                        # Note: The SPReturnItemSerializer.validate() still runs here
                        SPReturnItem.objects.create(header=instance, **item_data)

                # 3. Delete return lines that were removed from the request
                for remaining_item in existing_items.values():
                    remaining_item.delete()

        return instance


class SPDispatchItemActionSerializer(serializers.ModelSerializer):
    class Meta:
        model = SPDispatchItem
        fields = '__all__'

    # def validate(self, data):
    #     # Business Rule: If the item is special order, ensure the header has a cost center
    #     if data['article'].OBLIGA_INCLUIR_FASE_PY == 'S' and not data['header'].centro_costo:
    #         raise serializers.ValidationError(
    #             "This article is a Special Order item and must be linked to a Project/Cost Center."
    #         )
    #     return data


class SPReturnItemActionSerializer(serializers.ModelSerializer):
    class Meta:
        model = SPReturnItem
        fields = '__all__'


class StandaloneArticuloSerializer(serializers.ModelSerializer):
    class Meta:
        model = Articulo
        fields = '__all__'

        # We list all the fields that the frontend WON'T send here
        extra_kwargs = {
            field: {'required': False} for field in [
                'PUNTO_DE_REORDEN', 'COSTO_FISCAL', 'COSTO_COMPARATIVO',
                'COSTO_PROM_LOC', 'COSTO_PROM_DOL', 'COSTO_STD_LOC', 'COSTO_STD_DOL',
                'COSTO_ULT_LOC', 'COSTO_ULT_DOL', 'PRECIO_BASE_LOCAL', 'PRECIO_BASE_DOLAR',
                'ULTIMA_SALIDA', 'ULTIMO_MOVIMIENTO', 'ULTIMO_INGRESO', 'ULTIMO_INVENTARIO',
                'CLASE_ABC', 'FRECUENCIA_CONTEO', 'USA_LOTES', 'OBLIGA_CUARENTENA',
                'MIN_VIDA_COMPRA', 'MIN_VIDA_CONSUMO', 'MIN_VIDA_VENTA', 'VIDA_UTIL_PROM',
                'DIAS_CUARENTENA', 'ORDEN_MINIMA', 'PLAZO_REABAST', 'LOTE_MULTIPLO',
                'UTILIZADO_MANUFACT', 'USA_NUMEROS_SERIE', 'UNIDAD_EMPAQUE', 'UNIDAD_VENTA',
                'PERECEDERO', 'TIPO_COSTO', 'ES_ENVASE', 'USA_CONTROL_ENVASE',
                'COSTO_PROM_COMPARATIVO_LOC', 'COSTO_PROM_COMPARATIVO_DOLAR',
                'COSTO_PROM_ULTIMO_LOC', 'COSTO_PROM_ULTIMO_DOL', 'UTILIZADO_EN_CONTRATOS',
                'VALIDA_CANT_FASE_PY', 'ES_IMPUESTO', 'CANASTA_BASICA', 'ES_OTRO_CARGO',
                'SERVICIO_MEDICO', 'SUGIERE_MIN', 'CALC_PERCEP', 'ES_INAFECTO',
                'IMP1_INCLUIDO_ES', 'NoteExistsFlag', 'RecordDate', 'CreatedBy',
                'UpdatedBy', 'CreateDate', 'BULTOS', 'ORIGEN_CORP', 'ACTIVO', 'PESO_NETO', 'PESO_BRUTO', 'VOLUMEN',
                'FACTOR_EMPAQUE', 'FACTOR_VENTA'
            ]
        }

    def to_representation(self, instance):
        result = super().to_representation(instance)
        return {key: value for key, value in result.items() if value is not None}

    def create(self, validated_data):
        # Inject all those missing required fields with valid ERP defaults
        defaults = self._get_standalone_defaults()
        validated_data.update(defaults)

        # Specific fix for DateFields that can't be null
        now = datetime.now()
        date_fields = {
            'ULTIMA_SALIDA': now, 'ULTIMO_MOVIMIENTO': now,
            'ULTIMO_INGRESO': now, 'ULTIMO_INVENTARIO': now,
            'CreateDate': now, 'RecordDate': now
        }
        validated_data.update(date_fields)

        return super().create(validated_data)

    def update(self, instance, validated_data):
        static_defaults = self._get_standalone_defaults()
        validated_data.update(static_defaults)
        return super().update(instance, validated_data)

    def _get_standalone_defaults(self):
        """Centralized definition of static ERP constants for standalone items"""
        return {
            'FACTOR_CONVER_1': Decimal('1.00000000'),
            'FACTOR_CONVER_2': Decimal('1.00000000'),
            'FACTOR_CONVER_3': Decimal('1.00000000'),
            'FACTOR_CONVER_4': Decimal('1.00000000'),
            'FACTOR_CONVER_5': Decimal('1.00000000'),
            'FACTOR_CONVER_6': Decimal('1.00000000'),
            'FACTOR_EMPAQUE': Decimal('1.00000000'),
            'FACTOR_VENTA': Decimal('1.00000000'),
            'PESO_NETO': Decimal('0.00000000'),
            'PESO_BRUTO': Decimal('0.00000000'),
            'VOLUMEN': Decimal('0.00000000'),
            'BULTOS': 0, 'CLASE_ABC': 'A', 'FRECUENCIA_CONTEO': 0,
            'USA_LOTES': 'N', 'OBLIGA_CUARENTENA': 'N',
            'MIN_VIDA_COMPRA': 0, 'MIN_VIDA_CONSUMO': 0, 'MIN_VIDA_VENTA': 0,
            'VIDA_UTIL_PROM': 0, 'DIAS_CUARENTENA': 0, 'PLAZO_REABAST': 0,
            'UTILIZADO_MANUFACT': 'N', 'USA_NUMEROS_SERIE': 'N',
            'PERECEDERO': 'N', 'TIPO_COSTO': 'A', 'ES_ENVASE': 'N',
            'USA_CONTROL_ENVASE': 'N', 'UTILIZADO_EN_CONTRATOS': 'N',
            'VALIDA_CANT_FASE_PY': 'N', 'ES_IMPUESTO': 'N', 'CANASTA_BASICA': 'N',
            'ES_OTRO_CARGO': 'N', 'SERVICIO_MEDICO': 'N', 'SUGIERE_MIN': 'N',
            'CALC_PERCEP': 'N', 'ES_INAFECTO': 'N', 'IMP1_INCLUIDO_ES': 'N',
            'NoteExistsFlag': False, 'COSTO_FISCAL': 'L', 'COSTO_COMPARATIVO': 'P',
            'PUNTO_DE_REORDEN': 0, 'ORDEN_MINIMA': 0, 'LOTE_MULTIPLO': 0,
            'ORIGEN_CORP': 'T', 'ACTIVO': 'S', 'TIENDA': 'No Definido', 'COSTO_PROM_LOC': Decimal('0.00000000'),
            'COSTO_PROM_DOL': Decimal('0.00000000'),
            'COSTO_STD_LOC': Decimal('0.00000000'),
            'COSTO_STD_DOL': Decimal('0.00000000'),
            'COSTO_ULT_LOC': Decimal('0.00000000'),
            'COSTO_ULT_DOL': Decimal('0.00000000'),
            'PRECIO_BASE_LOCAL': Decimal('0.00000000'),
            'PRECIO_BASE_DOLAR': Decimal('0.00000000'),
            'COSTO_PROM_COMPARATIVO_LOC': Decimal('0.00000000'),
            'COSTO_PROM_COMPARATIVO_DOLAR': Decimal('0.00000000'),
            'COSTO_PROM_ULTIMO_LOC': Decimal('0.00000000'),
            'COSTO_PROM_ULTIMO_DOL': Decimal('0.00000000'),
            'CreatedBy': self.context['request'].user.username if 'request' in self.context else 'SA',
            'UpdatedBy': self.context['request'].user.username if 'request' in self.context else 'SA',
        }