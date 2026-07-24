from rest_framework.routers import DefaultRouter
from django.urls import path, include
from . import views

router = DefaultRouter()
router.register("articulos", views.ArticuloViewSet, basename="articulo_readonly")
router.register("inventory", views.ItemMasterViewset, basename="inventory_readonly")
router.register("low_stocks", views.LowStockViewset, basename="low_stocks_readonly")
router.register("solicitud_oc", views.SolicitudeViewset, basename="solicitud_oc_readonly")
router.register("solicitud_oc_detail", views.SolicitudeDetailViewSet, basename="solicitud_oc_detail_readonly")
router.register("departments", views.DepartamentoViewSet, basename="departments_readonly")
router.register("orden_compra", views.OrdenCompraViewSet, basename="orden_compra_readonly")
router.register("orden_compra_detail", views.OrdenCompraDetailViewSet, basename="orden_compra_detail_readonly")
router.register("embarques", views.EmbarqueViewSet, basename="embarques_readonly")
router.register("embarque_detail", views.EmbarqueDetailViewSet, basename="embarque_detail_readonly")
router.register("documento_embarque", views.DocumentoEmbarqueViewSet, basename="documento_embarque_readonly")
router.register("proveedors", views.ProveedorViewSet, basename="proveedor_readonly")
router.register("stock_transfers", views.AuditTransInvViewSet, basename="stock_transfer_readonly")
router.register("stock_transfer_detail", views.AuditTransInvDetailViewSet, basename="stock_transfer_detail_readonly")
router.register("globales", views.GlobalesViewset, basename="globales_view")
router.register("orden_compra_form", views.PurchaseOrderViewset, basename="orden_compra_form")
router.register("shipment_form", views.ShipmentViewset, basename="shipment_form")
router.register("solicitud_form", views.SolicitudCompraViewset, basename="solicitud_form")
router.register("proveedor_details", views.ProveedorDetailViewSet, basename="proveedor_details_readonly")
router.register("paquete_inv", views.PaqueteInventarioViewSet, basename="paquete_inv_readonly")
router.register("documento_inv", views.DocumentoInvViewSet, basename="documento_inv_readonly")
router.register("documento_inv_detail", views.DocumentoInvDetailViewSet, basename="documento_inv_detail_readonly")
router.register("consecutivo_ci", views.ConsecutivoCiViewSet, basename="consecutivo_ci_readonly")
router.register("stock_transfer_form", views.StokTransferViewset, basename="stock_transfer_form")
router.register("email_form", views.EmailFormView, basename="email_form")
router.register("inventory_audits", views.InventoryAuditViewset, basename="inventory_audits")
router.register("top-selling-forecast", views.TopSellingForecastView, basename="top_selling_forecast")
router.register("stock-summary", views.StockSummaryViewset, basename="stock-summary")
router.register("aging-summary", views.AgingSummaryViewset, basename="aging-summary")
router.register("overstocks", views.OverstockViewset, basename="overstocks")
router.register("rop-low-stocks", views.ROPViewset, basename="rop-low-stocks")
router.register("rop-reports", views.RopReportViewset, basename="rop-reports")
router.register("consumption-summary", views.ConsumptionSummary, basename="consumption-summary")
router.register("warehouse-activity", views.WarehouseActivity, basename="warehouse-activity")
router.register(r'cycle-batches', views.CycleCountBatchViewSet, basename='cycle-batches')
router.register(r'inv-valuation', views.InvValuationReportViewset, basename='inv-valuation')
router.register(r'cycle-task', views.CycleCountTaskViewSet, basename='cycle-task')
router.register(r'abc-analysis', views.ABCAnalysisViewset, basename='abc-analysis')
router.register(r'department-usage', views.DepartmentUsageReportViewset, basename='department-usage')
router.register(r'purchase-summary', views.PurchaseSummaryViewset, basename='purchase-summary')
router.register(r'aging-report', views.AgingInvViewset, basename='aging-report')
router.register(r'spo-dispatches', views.SPDispatchViewSet, basename='dispatch')
router.register(r'spo-returns', views.SPReturnViewSet, basename='return')
router.register(r'spo-dispatch-items', views.SPDispatchItemViewSet, basename='dispatch-item')
router.register(r'spo-return-items', views.SPReturnItemViewSet, basename='return-item')
router.register(r'standalone-inv', views.StandaloneInventoryDashboardView, basename='stand-alone-inv-items')
router.register(r'standalone-items', views.StandaloneArticuloViewSet, basename='standalone-articulo')


urlpatterns = [
    path("", include(router.urls)),
    path("inventory_audit_details/<str:articulo>/<str:bodega>/", views.InventoryAuditDetailViewset.as_view(
        {'get': 'retrieve'}), name="articulo-list"),
]
