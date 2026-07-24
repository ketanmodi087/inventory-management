import logging
from celery import shared_task
from user_management.models import Role
from .models import (
    Articulo, Proveedor, ArticuloCompra, ArticuloProveedor, ArticuloCuenta, Impuesto, Clasificacion, ExistenciaLote,
    ArticuloPrecio, ArticuloEnsamble, ExistenciaBodega, SolicitudOcLinea, SolicitudOc, Departamento, OrdenCompra,
    OrdenCompraLinea, CentroCosto, CuentaContable, EmbarqueLinea, Embarque, DocumentoEmbarque, Devolucion,
    DevolLinEmbarque, AuditTransInv, TransaccionInv, DetLinEmbarque, DetDocumentoEmbarque, EmbarqueDocCp,
    SeguimientoOrden, UsuariosAprobOc, CondicionPago, Moneda, GlobalesCo, MonedaHist, ResponSeguimiento, Bodega,
    LowStockView, Localizacion, PaqueteInventario, DocumentoInv, LineaDocInv, ConsecutivoCi, AjusteConfig,
    AjusteSubsubtipo, AjusteSubtipo, ExistenciaReserva, ExistenciaCierre, ExistenciaLoteCierre, FacturaLinea, Factura,
    Diario, AsientoDeDiario, CgAux, Lote, Paquete, ItemsSalesHistory, ProphetForecast, SarimaForecast,
    HoltWintersForecast, ProphetForecastView, ItemLeadDaysView
)
from vra_backend.models import (
    VRAArticulo, VRAProveedor, VRAArticuloCompra, VRAArticuloProveedor, VRAArticuloCuenta, VRAImpuesto,
    VRAClasificacion, VRAExistenciaLote, VRAArticuloPrecio, VRAArticuloEnsamble, VRAExistenciaBodega, VRASolicitudOc,
    VRASolicitudOcLinea, VRADepartamento, VRAOrdenCompra, VRAOrdenCompraLinea, VRACentroCosto, VRACuentaContable,
    VRAEmbarque, VRAEmbarqueLinea, VRADocumentoEmbarque, VRADevolucion, VRADevolLinEmbarque, VRAAuditTransInv,
    VRATransaccionInv, VRADetDocumentoEmbarque, VRADetLinEmbarque, VRAEmbarqueDocCp, VRASeguimientoOrden,
    VRAUsuariosAprobOc, VRACondicionPago, VRAMoneda, VRAGlobalesCo, VRAMonedaHist, VRAResponSeguimiento, VRABodega,
    VRALocalizacion, VRAPaqueteInventario, VRADocumentoInv, VRALineaDocInv, VRAConsecutivoCi, VRAAjusteConfig,
    VRAAjusteSubsubtipo, VRAAjusteSubtipo, VRAExistenciaReserva, VRAFacturaLinea, VRAFactura, VRADiario,
    VRAAsientoDeDiario, VRACgAux, VRALote, VRAPaquete
)
from IMS.utility import (
    sync_database_models, send_softland_sync_alert, send_low_stock_alert, send_new_po_alert, send_new_shipment_alert,
    send_new_requirement_alert, send_new_stocktransfer_alert, send_overdue_po_alert, order_qty_alert,
    send_audit_item_log_alert
)
from .forecast_service import prophet_forecast, holt_winters_forecast, sarima_forecast
from django.db.models import (
    F, Sum, Min, IntegerField, Q, ExpressionWrapper, Max, Func, OuterRef, Subquery,
    Value, DecimalField
)
from decimal import Decimal
from django.db.models.functions import Coalesce, Now, ExtractDay
from django.db import connections
from datetime import datetime, timedelta
import uuid

logger = logging.getLogger(__name__)


@shared_task
def syncronize_articuloas():
    total_new_records, total_updated_records = sync_database_models(VRAArticulo.__name__, Articulo.__name__,
                                                                    ['ARTICULO'], syncronize_articuloas.request.id)
    result = ["Articulo -- new: %s, updated: %s" % (total_new_records, total_updated_records)]
    if total_new_records is not None:
        send_softland_sync_alert("Articulo")
    total_new_records, total_updated_records = sync_database_models(VRAProveedor.__name__, Proveedor.__name__,
                                                                    ['PROVEEDOR'], syncronize_articuloas.request.id)
    result.append("Proveedor -- new: %s, updated: %s" % (total_new_records, total_updated_records))
    if total_new_records is not None:
        send_softland_sync_alert("Proveedor")
    total_new_records, total_updated_records = sync_database_models(VRAArticuloCompra.__name__, ArticuloCompra.__name__,
                                                                    ['ARTICULO'], syncronize_articuloas.request.id)
    result.append("Articulo Compra -- new: %s, updated: %s" % (total_new_records, total_updated_records))

    total_new_records, total_updated_records = sync_database_models(VRAArticuloProveedor.__name__,
                                                                    ArticuloProveedor.__name__,
                                                                    ['ARTICULO', 'PROVEEDOR'],
                                                                    syncronize_articuloas.request.id)
    result.append("Articulo Proveedor -- new: %s, updated: %s" % (total_new_records, total_updated_records))
    total_new_records, total_updated_records = sync_database_models(VRAArticuloCuenta.__name__, ArticuloCuenta.__name__,
                                                                    ['ARTICULO_CUENTA'],
                                                                    syncronize_articuloas.request.id)
    result.append("Articulo Cuenta -- new: %s, updated: %s" % (total_new_records, total_updated_records))
    total_new_records, total_updated_records = sync_database_models(VRAImpuesto.__name__, Impuesto.__name__,
                                                                    ['IMPUESTO'],
                                                                    syncronize_articuloas.request.id)
    result.append("Impuesto -- new: %s, updated: %s" % (total_new_records, total_updated_records))
    total_new_records, total_updated_records = sync_database_models(VRAClasificacion.__name__, Clasificacion.__name__,
                                                                    ['CLASIFICACION'],
                                                                    syncronize_articuloas.request.id)
    result.append("Clasificacion -- new: %s, updated: %s" % (total_new_records, total_updated_records))

    total_new_records, total_updated_records = sync_database_models(VRAArticuloPrecio.__name__, ArticuloPrecio.__name__,
                                                                    ['NIVEL_PRECIO', 'ARTICULO', 'MONEDA', 'VERSION'],
                                                                    syncronize_articuloas.request.id)
    result.append("Articulo Precio -- new: %s, updated: %s" % (total_new_records, total_updated_records))
    total_new_records, total_updated_records = sync_database_models(VRAArticuloEnsamble.__name__,
                                                                    ArticuloEnsamble.__name__,
                                                                    ['ARTICULO_PADRE', 'ARTICULO_HIJO'],
                                                                    syncronize_articuloas.request.id)
    result.append("Articulo Ensamble -- new: %s, updated: %s" % (total_new_records, total_updated_records))
    return " ,\n ".join(result)


@shared_task
def syncronize_solicitudes():
    total_new_records, total_updated_records = sync_database_models(VRADepartamento.__name__, Departamento.__name__,
                                                                    ['DEPARTAMENTO'], syncronize_solicitudes.request.id)
    result = ["Department -- new: %s, updated: %s" % (total_new_records, total_updated_records)]
    new_records, total_updated_records = sync_database_models(VRASolicitudOc.__name__, SolicitudOc.__name__,
                                                              ['SOLICITUD_OC'], syncronize_solicitudes.request.id)
    result.append("Solicitude -- new: %s, updated: %s" % (new_records, total_updated_records))
    if new_records is not None:
        send_softland_sync_alert("Solicitude")
    total_new_records, total_updated_records = sync_database_models(VRASolicitudOcLinea.__name__,
                                                                    SolicitudOcLinea.__name__,
                                                                    ['SOLICITUD_OC', 'SOLICITUD_OC_LINEA'],
                                                                    syncronize_solicitudes.request.id)
    result.append("Solicitude lineas -- new: %s, updated: %s" % (total_new_records, total_updated_records))
    admin_role = Role.objects.filter(code='admin').first()
    if new_records:
        pm_role = Role.objects.filter(code='purchase-manager').first()
        wm_role = Role.objects.filter(code='warehouse-manager').first()
        requirements = SolicitudOc.objects.order_by(F('CreateDate').desc(nulls_last=True))[:new_records]
        if admin_role:
            send_new_requirement_alert(requirements, admin_role.users.all())
        if pm_role:
            send_new_requirement_alert(requirements, pm_role.users.all())
        if wm_role:
            send_new_requirement_alert(requirements, wm_role.users.all())

    return " ,\n ".join(result)


@shared_task
def syncronize_orden_compras():
    total_new_records, total_updated_records = sync_database_models(VRACentroCosto.__name__, CentroCosto.__name__,
                                                                    ['CENTRO_COSTO'],
                                                                    syncronize_orden_compras.request.id)
    result = ["Centro Costo -- new: %s, updated: %s" % (total_new_records, total_updated_records)]
    total_new_records, total_updated_records = sync_database_models(VRACuentaContable.__name__, CuentaContable.__name__,
                                                                    ['CUENTA_CONTABLE'],
                                                                    syncronize_orden_compras.request.id)
    result.append("Cuenta Contable -- new: %s, updated: %s" % (total_new_records, total_updated_records))

    new_records, total_updated_records = sync_database_models(VRAOrdenCompra.__name__, OrdenCompra.__name__,
                                                              ['ORDEN_COMPRA'], syncronize_orden_compras.request.id)
    result.append("Orden Compra -- new: %s, updated: %s" % (new_records, total_updated_records))
    if new_records is not None:
        send_softland_sync_alert("Orden Compra")
    total_new_records, total_updated_records = sync_database_models(VRAOrdenCompraLinea.__name__,
                                                                    OrdenCompraLinea.__name__,
                                                                    ['ORDEN_COMPRA', 'ORDEN_COMPRA_LINEA'],
                                                                    syncronize_orden_compras.request.id)
    result.append("Orden Compra Linea -- new: %s, updated: %s" % (total_new_records, total_updated_records))
    total_new_records, total_updated_records = sync_database_models(VRASeguimientoOrden.__name__,
                                                                    SeguimientoOrden.__name__,
                                                                    ['RowPointer'],
                                                                    syncronize_orden_compras.request.id)
    result.append("Seguimiento Orden -- new: %s, updated: %s" % (total_new_records, total_updated_records))
    total_new_records, total_updated_records = sync_database_models(VRAUsuariosAprobOc.__name__,
                                                                    UsuariosAprobOc.__name__,
                                                                    ['RowPointer'],
                                                                    syncronize_orden_compras.request.id)
    result.append("Usuarios Aprob Oc -- new: %s, updated: %s" % (total_new_records, total_updated_records))
    admin_role = Role.objects.filter(code='admin').first()
    if new_records:
        pm_role = Role.objects.filter(code='purchase-manager').first()
        wm_role = Role.objects.filter(code='warehouse-manager').first()
        orders = OrdenCompra.objects.order_by(F('CreateDate').desc(nulls_last=True))[:new_records]
        if admin_role:
            send_new_po_alert(orders, admin_role.users.all())
        if pm_role:
            send_new_po_alert(orders, pm_role.users.all())
        if wm_role:
            send_new_po_alert(orders, wm_role.users.all())
    return " ,\n ".join(result)


@shared_task
def sync_embarques():
    total_new_records, total_updated_records = sync_database_models(VRADocumentoEmbarque.__name__,
                                                                    DocumentoEmbarque.__name__,
                                                                    ['RowPointer'], sync_embarques.request.id)
    result = ["Documento Embarque -- new: %s, updated: %s" % (total_new_records, total_updated_records)]
    new_records, total_updated_records = sync_database_models(VRAEmbarque.__name__, Embarque.__name__,
                                                              ['EMBARQUE'], sync_embarques.request.id)
    result.append("Embarque -- new: %s, updated: %s" % (new_records, total_updated_records))
    if new_records is not None:
        send_softland_sync_alert("Embarque")
    total_new_records, total_updated_records = sync_database_models(VRAEmbarqueLinea.__name__, EmbarqueLinea.__name__,
                                                                    ['RowPointer'],
                                                                    sync_embarques.request.id)
    result.append("Embarque Linea -- new: %s, updated: %s" % (total_new_records, total_updated_records))
    total_new_records, total_updated_records = sync_database_models(VRADevolucion.__name__, Devolucion.__name__,
                                                                    ['DEVOLUCION'], sync_embarques.request.id)
    result.append("Devolucion -- new: %s, updated: %s" % (total_new_records, total_updated_records))
    total_new_records, total_updated_records = sync_database_models(VRADevolLinEmbarque.__name__,
                                                                    DevolLinEmbarque.__name__,
                                                                    ['DEVOLUCION', 'DEVOLUCION_LINEA'],
                                                                    sync_embarques.request.id)
    result.append("Devolucion Linea -- new: %s, updated: %s" % (total_new_records, total_updated_records))
    total_new_records, total_updated_records = sync_database_models(VRADetDocumentoEmbarque.__name__,
                                                                    DetDocumentoEmbarque.__name__,
                                                                    ['RowPointer'], sync_embarques.request.id)
    result.append("Detalle Documento Embarque -- new: %s, updated: %s" % (total_new_records, total_updated_records))
    total_new_records, total_updated_records = sync_database_models(VRADetLinEmbarque.__name__, DetLinEmbarque.__name__,
                                                                    ['RowPointer'], sync_embarques.request.id)
    result.append("Detalle Linea Embarque -- new: %s, updated: %s" % (total_new_records, total_updated_records))
    total_new_records, total_updated_records = sync_database_models(VRAEmbarqueDocCp.__name__, EmbarqueDocCp.__name__,
                                                                    ['RowPointer'], sync_embarques.request.id)
    result.append("Embarque Documento Cp -- new: %s, updated: %s" % (total_new_records, total_updated_records))
    total_new_records, total_updated_records = sync_database_models(VRACondicionPago.__name__, CondicionPago.__name__,
                                                                    ['RowPointer'], sync_embarques.request.id)
    result.append("Condicion Pago -- new: %s, updated: %s" % (total_new_records, total_updated_records))
    total_new_records, total_updated_records = sync_database_models(VRAMoneda.__name__, Moneda.__name__,
                                                                    ['MONEDA'], sync_embarques.request.id)
    result.append("Moneda -- new: %s, updated: %s" % (total_new_records, total_updated_records))
    total_new_records, total_updated_records = sync_database_models(VRAMonedaHist.__name__, MonedaHist.__name__,
                                                                    ['RowPointer'], sync_embarques.request.id)
    result.append("Moneda Hist -- new: %s, updated: %s" % (total_new_records, total_updated_records))
    total_new_records, total_updated_records = sync_database_models(VRAGlobalesCo.__name__, GlobalesCo.__name__,
                                                                    ['RowPointer'], sync_embarques.request.id)
    result.append("Globales Co -- new: %s, updated: %s" % (total_new_records, total_updated_records))
    total_new_records, total_updated_records = sync_database_models(VRAResponSeguimiento.__name__,
                                                                    ResponSeguimiento.__name__,
                                                                    ['RowPointer'], sync_embarques.request.id)
    result.append("Respon Seguimiento -- new: %s, updated: %s" % (total_new_records, total_updated_records))
    total_new_records, total_updated_records = sync_database_models(VRABodega.__name__, Bodega.__name__,
                                                                    ['RowPointer'], sync_embarques.request.id)
    result.append("Bodega -- new: %s, updated: %s" % (total_new_records, total_updated_records))
    admin_role = Role.objects.filter(code='admin').first()
    if new_records:
        pm_role = Role.objects.filter(code='purchase-manager').first()
        wm_role = Role.objects.filter(code='warehouse-manager').first()
        shipments = Embarque.objects.order_by(F('CreateDate').desc(nulls_last=True))[:new_records]
        if admin_role:
            send_new_shipment_alert(shipments, admin_role.users.all())
        if pm_role:
            send_new_shipment_alert(shipments, pm_role.users.all())
        if wm_role:
            send_new_shipment_alert(shipments, wm_role.users.all())
    return " ,\n ".join(result)


@shared_task
def sync_stock_transfer():
    admin_role = Role.objects.filter(code='admin').first()
    wm_role = Role.objects.filter(code='warehouse-manager').first()
    pm_role = Role.objects.filter(code='purchase-manager').first()
    new_records, total_updated_records = sync_database_models(VRAAuditTransInv.__name__, AuditTransInv.__name__,
                                                              ['AUDIT_TRANS_INV'], sync_stock_transfer.request.id)
    result = ["Audit Trans Inv -- new: %s, updated: %s" % (new_records, total_updated_records)]
    if new_records:
        audits = AuditTransInv.objects.order_by(F('CreateDate').desc(nulls_last=True))[:new_records]
        items = LowStockView.objects.filter(LAST_TRANSACTION__gt=(datetime.now() - timedelta(days=90))).all()[
            :new_records]
        if admin_role:
            send_low_stock_alert(items, admin_role.users.all())
            send_audit_item_log_alert(audits, admin_role.users.all())
        if wm_role:
            send_low_stock_alert(items, wm_role.users.all())
            send_audit_item_log_alert(audits, wm_role.users.all())
        if pm_role:
            send_low_stock_alert(items, pm_role.users.all())
            send_audit_item_log_alert(audits, pm_role.users.all())
    total_new_records, total_updated_records = sync_database_models(VRATransaccionInv.__name__, TransaccionInv.__name__,
                                                                    ['AUDIT_TRANS_INV', 'CONSECUTIVO'],
                                                                    sync_stock_transfer.request.id)
    result.append("Transaccion Inv -- new: %s, updated: %s" % (total_new_records, total_updated_records))
    total_new_records, total_updated_records = sync_database_models(VRAPaqueteInventario.__name__,
                                                                    PaqueteInventario.__name__,
                                                                    ['RowPointer'], sync_stock_transfer.request.id)
    result.append("Paquete Inventario -- new: %s, updated: %s" % (total_new_records, total_updated_records))
    new_records, total_updated_records = sync_database_models(VRADocumentoInv.__name__, DocumentoInv.__name__,
                                                              ['RowPointer'], sync_stock_transfer.request.id)
    if new_records is not None:
        send_softland_sync_alert("Stock Transfer")
        items = DocumentoInv.objects.order_by(F('CreateDate').desc(nulls_last=True))[:new_records]
        if admin_role:
            send_new_stocktransfer_alert(items, admin_role.users.all())
        if wm_role:
            send_new_stocktransfer_alert(items, wm_role.users.all())
        if pm_role:
            send_new_stocktransfer_alert(items, pm_role.users.all())
    result.append("Documento Inv -- new: %s, updated: %s" % (total_new_records, total_updated_records))
    total_new_records, total_updated_records = sync_database_models(VRALineaDocInv.__name__, LineaDocInv.__name__,
                                                                    ['RowPointer'], sync_stock_transfer.request.id)
    result.append("Linea Doc Inv -- new: %s, updated: %s" % (total_new_records, total_updated_records))
    total_new_records, total_updated_records = sync_database_models(VRAConsecutivoCi.__name__, ConsecutivoCi.__name__,
                                                                    ['RowPointer'], sync_stock_transfer.request.id)
    result.append("Consecutivo Ci -- new: %s, updated: %s" % (total_new_records, total_updated_records))
    total_new_records, total_updated_records = sync_database_models(VRAAjusteConfig.__name__, AjusteConfig.__name__,
                                                                    ['RowPointer'], sync_stock_transfer.request.id)
    result.append("Ajuste Config -- new: %s, updated: %s" % (total_new_records, total_updated_records))
    total_new_records, total_updated_records = sync_database_models(VRAAjusteSubtipo.__name__, AjusteSubtipo.__name__,
                                                                    ['RowPointer'], sync_stock_transfer.request.id)
    result.append("Ajuste Subtipo -- new: %s, updated: %s" % (total_new_records, total_updated_records))
    total_new_records, total_updated_records = sync_database_models(VRAAjusteSubsubtipo.__name__,
                                                                    AjusteSubsubtipo.__name__,
                                                                    ['RowPointer'], sync_stock_transfer.request.id)
    result.append("Ajuste Subsubtipo -- new: %s, updated: %s" % (total_new_records, total_updated_records))
    total_new_records, total_updated_records = sync_database_models(VRAExistenciaReserva.__name__,
                                                                    ExistenciaReserva.__name__,
                                                                    ['RowPointer'], sync_stock_transfer.request.id)
    result.append("Existencia Reserva -- new: %s, updated: %s" % (total_new_records, total_updated_records))
    total_new_records, total_updated_records = sync_database_models(VRAExistenciaLote.__name__, ExistenciaLote.__name__,
                                                                    ['BODEGA', 'ARTICULO', 'LOCALIZACION'],
                                                                    sync_stock_transfer.request.id)
    result.append("Existencias Lote -- new: %s, updated: %s" % (total_new_records, total_updated_records))
    total_new_records, total_updated_records = sync_database_models(VRAExistenciaBodega.__name__,
                                                                    ExistenciaBodega.__name__,
                                                                    ['ARTICULO', 'BODEGA'],
                                                                    sync_stock_transfer.request.id)
    result.append("Existencia Bodega -- new: %s, updated: %s" % (total_new_records, total_updated_records))
    total_new_records, total_updated_records = sync_database_models(VRALocalizacion.__name__, Localizacion.__name__,
                                                                    ['RowPointer'],
                                                                    sync_stock_transfer.request.id)
    result.append("Localizacion -- new: %s, updated: %s" % (total_new_records, total_updated_records))

    total_new_records, total_updated_records = sync_database_models(VRALote.__name__, Lote.__name__,
                                                                    ['RowPointer'],
                                                                    sync_stock_transfer.request.id)
    result.append("Lote -- new: %s, updated: %s" % (total_new_records, total_updated_records))
    total_new_records, total_updated_records = sync_database_models(VRADiario.__name__, Diario.__name__,
                                                                    ['RowPointer'], sync_stock_transfer.request.id)
    result.append("Diario -- new: %s, updated: %s" % (total_new_records, total_updated_records))
    total_new_records, total_updated_records = sync_database_models(VRAAsientoDeDiario.__name__, AsientoDeDiario.__name__,
                                                                    ['RowPointer'],
                                                                    sync_stock_transfer.request.id)
    result.append("Asiento De Diario -- new: %s, updated: %s" % (total_new_records, total_updated_records))
    total_new_records, total_updated_records = sync_database_models(VRACgAux.__name__, CgAux.__name__,
                                                                    ['RowPointer'], sync_stock_transfer.request.id)
    result.append("Cg Aux -- new: %s, updated: %s" % (total_new_records, total_updated_records))
    total_new_records, total_updated_records = sync_database_models(VRAPaquete.__name__, Paquete.__name__,
                                                                    ['RowPointer'], sync_stock_transfer.request.id)
    result.append("Paquete -- new: %s, updated: %s" % (total_new_records, total_updated_records))

    return " ,\n ".join(result)


@shared_task
def sync_facturas():
    total_new_records, total_updated_records = sync_database_models(VRAFactura.__name__, Factura.__name__,
                                                                    ['RowPointer'], sync_facturas.request.id)
    result = ["Factura -- new: %s, updated: %s" % (total_new_records, total_updated_records)]
    if total_new_records is not None:
        send_softland_sync_alert("Factura")
    total_new_records, total_updated_records = sync_database_models(VRAFacturaLinea.__name__, FacturaLinea.__name__,
                                                                    ['RowPointer'],
                                                                    sync_facturas.request.id)
    result.append("Factura Linea -- new: %s, updated: %s" % (total_new_records, total_updated_records))
    return " ,\n ".join(result)


@shared_task
def refresh_materialized_views():
    with connections['default'].cursor() as cursor:
        cursor.execute("REFRESH MATERIALIZED VIEW ims_item_low_stock_view")
        cursor.execute("REFRESH MATERIALIZED VIEW ims_items_sales_history")
        cursor.execute("REFRESH MATERIALIZED VIEW ims_inventory_audit")
        cursor.execute("REFRESH MATERIALIZED VIEW ims_inventory_lote_audit")
        cursor.execute("REFRESH MATERIALIZED VIEW ims_inventory_aging_summary")
        cursor.execute("REFRESH MATERIALIZED VIEW ims_item_lead_days_view")


# @shared_task
# def truncate_tables():
#     with connections['default'].cursor() as cursor:
#         cursor.execute(f'TRUNCATE TABLE "{ExistenciaLote._meta.db_table}" RESTART IDENTITY CASCADE;')
#         cursor.execute(f'TRUNCATE TABLE "{ExistenciaBodega._meta.db_table}" RESTART IDENTITY CASCADE;')
#         cursor.execute(f'TRUNCATE TABLE "{ExistenciaReserva._meta.db_table}" RESTART IDENTITY CASCADE;')
#         cursor.execute(f'TRUNCATE TABLE "{AuditTransInv._meta.db_table}" RESTART IDENTITY CASCADE;')
#         cursor.execute(f'TRUNCATE TABLE "{TransaccionInv._meta.db_table}" RESTART IDENTITY CASCADE;')
#         cursor.execute(f'TRUNCATE TABLE "{DocumentoInv._meta.db_table}" RESTART IDENTITY CASCADE;')
#         cursor.execute(f'TRUNCATE TABLE "{LineaDocInv._meta.db_table}" RESTART IDENTITY CASCADE;')
#         cursor.execute(f'TRUNCATE TABLE "{OrdenCompraLinea._meta.db_table}" RESTART IDENTITY CASCADE;')
#         cursor.execute(f'TRUNCATE TABLE "{OrdenCompra._meta.db_table}" RESTART IDENTITY CASCADE;')
#         cursor.execute(f'TRUNCATE TABLE "{Embarque._meta.db_table}" RESTART IDENTITY CASCADE;')
#         cursor.execute(f'TRUNCATE TABLE "{EmbarqueLinea._meta.db_table}" RESTART IDENTITY CASCADE;')
#         cursor.execute(f'TRUNCATE TABLE "{DetLinEmbarque._meta.db_table}" RESTART IDENTITY CASCADE;')
#         cursor.execute(f'TRUNCATE TABLE "{GlobalesCo._meta.db_table}" RESTART IDENTITY CASCADE;')
#         cursor.execute(f'TRUNCATE TABLE "{SolicitudOc._meta.db_table}" RESTART IDENTITY CASCADE;')
#         cursor.execute(f'TRUNCATE TABLE "{SolicitudOcLinea._meta.db_table}" RESTART IDENTITY CASCADE;')
#         cursor.execute(f'TRUNCATE TABLE "{Localizacion._meta.db_table}" RESTART IDENTITY CASCADE;')
#         cursor.execute(f'TRUNCATE TABLE "{UsuariosAprobOc._meta.db_table}" RESTART IDENTITY CASCADE;')
#         cursor.execute(f'TRUNCATE TABLE "{SeguimientoOrden._meta.db_table}" RESTART IDENTITY CASCADE;')
#         cursor.execute(f'TRUNCATE TABLE "{ArticuloCompra._meta.db_table}" RESTART IDENTITY CASCADE;')
#         cursor.execute(f'TRUNCATE TABLE "{ConsecutivoCi._meta.db_table}" RESTART IDENTITY CASCADE;')


@shared_task
def generate_daily_notification():
    overdue_pos = (
        OrdenCompra.objects
        .filter(
            FECHA_REQUERIDA__lt=datetime.now(),
            ESTADO='A'  # Open POs only
        )
        .exclude(
            Q(FECHA_HORA_CIERRE__isnull=False) |
            Q(FECHA_HORA_CANCELA__isnull=False) |
            Q(RECIBIDO_DE_MAS='S')
        )
        .annotate(
            overdue_days=ExpressionWrapper(
                ExtractDay(Now() - F("FECHA_REQUERIDA")),
                output_field=IntegerField()
            )
        )
    )
    forecast_subquery = Subquery(
        ProphetForecastView.objects.filter(
            ARTICULO=OuterRef("ARTICULO")
        )
        .values("total_forecast")[:1]
    )
    rop_data = (
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
        .values(
            "ARTICULO",
            "reorder_qty",
        ))
    planned_pos = OrdenCompraLinea.objects.filter(ESTADO='A').values('ARTICULO').annotate(
        planned_qty=Sum('CANTIDAD_ORDENADA'))
    rop_map = {
        row["ARTICULO"]: row.get("reorder_qty", 0)
        for row in rop_data
    }
    planned_map = {
        row["ARTICULO"]: row.get("planned_qty", 0)
        for row in planned_pos
    }
    order_alerts = []
    for articulo, planned_qty in planned_map.items():
        reorder_qty = Decimal(rop_map.get(articulo, 0))

        # 🔔 Alert Logic
        if reorder_qty == 0 and planned_qty > 0:
            alert = "UNNECESSARY ORDER"
        elif planned_qty * Decimal("1.25") < reorder_qty:
            alert = "ORDER TOO LOW"
        elif planned_qty > reorder_qty * Decimal("1.25"):
            alert = "ORDER TOO HIGH"
        else:
            continue

        order_alerts.append({
            "ARTICULO": articulo,
            "reorder_qty": float(reorder_qty),
            "planned_qty": float(planned_qty),
            "order_alert": alert,
        })
    admin_role = Role.objects.filter(code='admin').first()
    pm_role = Role.objects.filter(code='purchase-manager').first()
    wm_role = Role.objects.filter(code='warehouse-manager').first()
    users_to_notify = set()
    if pm_role:
        users_to_notify.update(pm_role.users.all())
    if admin_role:
        users_to_notify.update(admin_role.users.all())
    if wm_role:
        users_to_notify.update(wm_role.users.all())
    send_overdue_po_alert(overdue_pos, users_to_notify)
    order_qty_alert(order_alerts, users_to_notify)

    return f"Generated {overdue_pos.count()} overdue PO alerts and {len(order_alerts)} order quantity alerts."


@shared_task
def log_existencia_bodega():
    bodega_sql = """
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
    existing_entries = []
    with connections['default'].cursor() as cursor:
        cursor.execute(f'TRUNCATE TABLE "{ExistenciaCierre._meta.db_table}" RESTART IDENTITY CASCADE;')
        cursor.execute(f'TRUNCATE TABLE "{ExistenciaLoteCierre._meta.db_table}" RESTART IDENTITY CASCADE;')
    with connections['mssql_db'].cursor() as cursor:
        cursor.execute(bodega_sql)
        existing_entries = cursor.fetchall()
    logs = []
    for entry in existing_entries:
        logs.append(ExistenciaCierre(
            ARTICULO=entry[1],
            BODEGA=entry[0],
            TIPO_COSTO=entry[2],
            CANT_DISPONIBLE=entry[3],
            CANT_RESERVADA=entry[4],
            CANT_NO_APROBADA=entry[5],
            CANT_VENCIDA=entry[6],
            CANT_REMITIDA=entry[7],
            COSTO_FISC_UNT_LOC=entry[8],
            COSTO_FISC_UNT_DOL=entry[9],
            COSTO_COMP_UNT_LOC=entry[10],
            COSTO_COMP_UNT_DOL=entry[11],
            FECHA_CIERRE=datetime.now(),
            TIPO_FECHA="S",
            RowPointer=str(uuid.uuid4()).upper(),
            CreatedBy="SA",
            UpdatedBy="SA",
            CreateDate=datetime.now(),
            RecordDate=datetime.now(),
            NoteExistsFlag=False
        ))
    ExistenciaCierre.objects.bulk_create(logs)
    existencia_lote = VRAExistenciaLote.objects.all()
    lote_logs = []
    for lote in existencia_lote:
        lote_logs.append(ExistenciaLoteCierre(
            ARTICULO=lote.ARTICULO,
            BODEGA=lote.BODEGA,
            LOCALIZACION=lote.LOCALIZACION,
            LOTE=lote.LOTE,
            CANT_DISPONIBLE=lote.CANT_DISPONIBLE,
            CANT_RESERVADA=lote.CANT_RESERVADA,
            CANT_NO_APROBADA=lote.CANT_NO_APROBADA,
            CANT_VENCIDA=lote.CANT_VENCIDA,
            CANT_REMITIDA=lote.CANT_REMITIDA,
            FECHA_CIERRE=datetime.now(),
            TIPO_FECHA="S",
            COSTO_FISC_UNT_LOC=lote.COSTO_UNT_ESTANDAR_LOC,
            COSTO_FISC_UNT_DOL=lote.COSTO_UNT_ESTANDAR_DOL,
            COSTO_COMP_UNT_LOC=lote.COSTO_UNT_PROMEDIO_LOC,
            COSTO_COMP_UNT_DOL=lote.COSTO_UNT_PROMEDIO_DOL,
            CreateDate=datetime.now(),
            RecordDate=datetime.now()
        ))
    ExistenciaLoteCierre.objects.bulk_create(lote_logs)
    return f"Logged {len(logs)} existencia bodega records. Logged {len(lote_logs)} existencia lote records."


@shared_task
def generate_sales_forecast(start, end):
    articulos = (
        ItemsSalesHistory.objects
        .values('ARTICULO')
        .annotate(
            min_ds=Min('DS'),
            max_ds=Max('DS'),
        )
        .filter(max_ds__gte=F('min_ds') + timedelta(days=365 * 2))
        .order_by('ARTICULO')
    )
    articulos = list(articulos)[start:end]

    for articulo in articulos:
        try:
            prophet_results = prophet_forecast(articulo['ARTICULO'])
            for prophet in prophet_results:
                ProphetForecast.objects.update_or_create(
                    article=articulo['ARTICULO'],
                    forecast_month=prophet['ds'],
                    defaults={
                        'forecast_quantity': round(prophet['yhat'], 4),
                        'forecast_lower': round(prophet['yhat_lower'], 4),
                        'forecast_upper': round(prophet['yhat_upper'], 4),
                    }
                )
        except Exception as e:
            logger.info(f"Error processing PROPHET forecast for articulo {articulo['ARTICULO']}: {e}")
        try:
            sarima_results = sarima_forecast(articulo['ARTICULO'])
            for date_str, quantity in sarima_results.items():
                SarimaForecast.objects.update_or_create(
                    article=articulo['ARTICULO'],
                    forecast_month=datetime.strptime(date_str, '%Y-%m-%d').date(),
                    defaults={
                        'forecast_quantity': round(quantity, 4)
                    }
                )
        except Exception as e:
            logger.info(f"Error processing SARIMA forecast for articulo {articulo['ARTICULO']}: {e}")
        try:
            hw_results = holt_winters_forecast(articulo['ARTICULO'])
            for date_str, quantity in hw_results.items():
                HoltWintersForecast.objects.update_or_create(
                    article=articulo['ARTICULO'],
                    forecast_month=datetime.strptime(date_str, '%Y-%m-%d').date(),
                    defaults={
                        'forecast_quantity': round(quantity, 4)
                    }
                )
        except Exception as e:
            logger.info(f"Error processing Holt-Winters forecast for articulo {articulo['ARTICULO']}: {e}")
    return f"Processed sales forecast for articulos {start} to {end}."


@shared_task
def process_sales_forecast_batch(batch_size=100):
    articulos = (
        ItemsSalesHistory.objects
        .values('ARTICULO')
        .annotate(
            min_ds=Min('DS'),
            max_ds=Max('DS'),
        )
        .filter(max_ds__gte=F('min_ds') + timedelta(days=365 * 2))
        .order_by('ARTICULO')
    )
    ProphetForecast.objects.filter(forecast_month__lte=datetime.now().date()).delete()
    SarimaForecast.objects.filter(forecast_month__lte=datetime.now().date()).delete()
    HoltWintersForecast.objects.filter(forecast_month__lte=datetime.now().date()).delete()
    articulos = list(articulos)
    total_articulos = len(articulos)
    for index, start in enumerate(range(0, total_articulos, batch_size)):
        end = min(start + batch_size, total_articulos)
        generate_sales_forecast.apply_async((start, end), countdown=15 * index)
    return f"Scheduled forecast generation for {total_articulos} articulos in batches of {batch_size}."



