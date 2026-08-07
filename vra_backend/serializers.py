from .models import (
    VRACentroCosto, VRAArticulo, VRAProveedor, VRAClasificacion, VRAUnidadDeMedida, VRASolicitudOc, VRASolicitudOcLinea,
    VRAOrdenCompra, VRAOrdenCompraLinea, VRADepartamento, VRADocumentoEmbarque, VRAEmbarque, VRAEmbarqueLinea, VRABodega,
    VRAExistenciaLote, VRAExistenciaBodega, ERPADMINUsuario
)
from rest_framework import serializers
from django.utils.translation import gettext_lazy as _

class VRACentroCostoSerializer(serializers.ModelSerializer):
    class Meta:
        model = VRACentroCosto
        fields = [
            'CENTRO_COSTO',
            'DESCRIPCION',
            'ACEPTA_DATOS',
            'TIPO',
            'RowPointer',
            'NoteExistsFlag',
            'RecordDate',
            'CreatedBy',
            'UpdatedBy',
            'CreateDate'
        ]


class VRAProveedorSerializer(serializers.ModelSerializer):
    class Meta:
        model = VRAProveedor
        fields = '__all__'  # Include all fields from the VRAProveedor model

class VRAClasificacionSerializer(serializers.ModelSerializer):
    class Meta:
        model = VRAClasificacion
        fields = [
            'CLASIFICACION',
            'DESCRIPCION',
        ]

class VRAUnidadDeMedidaSerializer(serializers.ModelSerializer):
    class Meta:
        model = VRAUnidadDeMedida
        fields = [
            'UNIDAD_MEDIDA',
            'DESCRIPCION',
        ]


class VRAArticuloSerializer(serializers.ModelSerializer):

    class Meta:
        model = VRAArticulo
        exclude = ['CLASIFICACION_3', 'CLASIFICACION_4','CLASIFICACION_6', 'RowPointer', 'NoteExistsFlag', 'RecordDate', 'CreatedBy', 'UpdatedBy', 'CreateDate']


class VRASolicitudOcLineaSerializer(serializers.ModelSerializer):
    class Meta:
        model = VRASolicitudOcLinea
        fields = '__all__'  # Include all fields from the VRASolicitudOcLinea model


class VRASolicitudOcSerializer(serializers.ModelSerializer):
    solicitud_oc_lineas = serializers.SerializerMethodField()
    class Meta:
        model = VRASolicitudOc
        fields = '__all__'  # Include all fields from the VRASolicitudOc model

    def get_solicitud_oc_lineas(self, obj):
        """        Custom method to get the related VRASolicitudOcLinea objects.
        """
        linea = VRASolicitudOcLinea.objects.filter(SOLICITUD_OC=obj.SOLICITUD_OC)
        serializer = VRASolicitudOcLineaSerializer(linea, many=True)
        return serializer.data


class VRAOrdenCompraLineaSerializer(serializers.ModelSerializer):
    class Meta:
        model = VRAOrdenCompraLinea
        fields = '__all__'  # Include all fields from the VRAOrdenCompraLinea model

class VRAOrdenCompraSerializer(serializers.ModelSerializer):
    orden_compra_lineas = serializers.SerializerMethodField()

    class Meta:
        model = VRAOrdenCompra
        fields = '__all__'  # Include all fields from the VRAOrdenCompra model

    def get_orden_compra_lineas(self, obj):
        """Custom method to get the related VRAOrdenCompraLinea objects."""
        linea = VRAOrdenCompraLinea.objects.filter(ORDEN_COMPRA=obj.ORDEN_COMPRA)
        serializer = VRAOrdenCompraLineaSerializer(linea, many=True)
        return serializer.data


class VRADepartmentoSerializer(serializers.ModelSerializer):
    class Meta:
        model = VRADepartamento
        fields = '__all__'


class VRADocumentoEmbarqueSerializer(serializers.ModelSerializer):
    class Meta:
        model = VRADocumentoEmbarque
        fields = '__all__'


class VRAEmbarqueLineaSerializer(serializers.ModelSerializer):
    class Meta:
        model = VRAEmbarqueLinea
        fields = '__all__'  # Include all fields from the VRAOrdenCompraLinea model


class VRAEmbarqueSerializer(serializers.ModelSerializer):
    embarque_lineas = serializers.SerializerMethodField()

    class Meta:
        model = VRAEmbarque
        fields = '__all__'

    def get_embarque_lineas(self, obj):
        """Custom method to get the related VRAEmbarqueLinea objects."""
        linea = VRAEmbarqueLinea.objects.filter(EMBARQUE=obj.EMBARQUE)
        serializer = VRAEmbarqueLineaSerializer(linea, many=True)
        return serializer.data

class VRAExistenciaBodegaSerializer(serializers.ModelSerializer):
    # articulo = serializers.SerializerMethodField()
    class Meta:
        model = VRAExistenciaBodega
        fields = '__all__'

    # def get_articulo(self, obj):
    #     return VRAArticulo.objects.filter(ARTICULO=obj.ARTICULO).values('DESCRIPCION', 'UNIDAD_ALMACEN', 'UNIDAD_EMPAQUE', 'UNIDAD_VENTA')[0]

class VRABodegaSerializer(serializers.ModelSerializer):
    existencias = serializers.SerializerMethodField()
    class Meta:
        model = VRABodega
        fields = '__all__'

    def get_existencias(self, obj):
        objects =  VRAExistenciaBodega.objects.filter(BODEGA=obj.BODEGA).order_by('-RecordDate')
        serializer = VRAExistenciaBodegaSerializer(objects, many=True)
        return serializer.data


class ERPADMINUsuarioSerializer(serializers.ModelSerializer):
    class Meta:
        model = ERPADMINUsuario
        fields = '__all__'

