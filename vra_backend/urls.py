from rest_framework.routers import DefaultRouter
from django.urls import path, include
from . import views

router = DefaultRouter()
router.register("articulo", views.ArticuloViewSet, basename="articulo_readonly")
router.register("proveedor", views.VRAProveedorViewset, basename="proveedor_readonly")
router.register("solicitud_oc", views.VRASolicitudOcViewset, basename="solicitud_oc_readonly")
router.register("orden_compra", views.VRAOrdenCompraViewset, basename="orden_compra_readonly")
router.register("departmento", views.VRADepartmentoViewset, basename="departmento_readonly")
router.register("documento", views.VRADocumentoEmbarqueViewset, basename="documento_readonly")
router.register("embarque", views.VRAEmbarqueViewset, basename="embarque_readonly")
router.register("bodega", views.VRABodegaViewset, basename="bodega_readonly")
router.register("usuario", views.ERPADMINUsuarioViewset, basename="usuario_readonly")

urlpatterns = [
    path("", include(router.urls)),
    path("articulo-list/", views.ArticuloListView.as_view(), name="articulo-list"),
]