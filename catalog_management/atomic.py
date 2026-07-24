"""Módulo para operaciones atómicas entre bases de datos MSSQL y PostgreSQL."""
import uuid, logging
from datetime import datetime
from django.db import transaction, connections, IntegrityError
from django.db.models import Sum
from django.forms.models import model_to_dict
from catalog_management.models import (
    OrdenCompra, OrdenCompraLinea, Embarque, EmbarqueLinea, DetLinEmbarque, GlobalesCo, SolicitudOc, SolicitudOcLinea,
    Localizacion, UsuariosAprobOc, SeguimientoOrden, ArticuloCompra, ExistenciaBodega, DocumentoInv, AuditTransInv,
    ExistenciaReserva, TransaccionInv, LineaDocInv, ConsecutivoCi, ExistenciaLote, Articulo, ArticuloCuenta,
    CuentaContable
)
from vra_backend.models import (
    VRAOrdenCompra, VRAOrdenCompraLinea, VRAGlobalesCo, VRAEmbarque, VRAEmbarqueLinea, VRADetLinEmbarque,
    VRASolicitudOc, VRASolicitudOcLinea, VRALocalizacion, VRAUsuariosAprobOc, VRASeguimientoOrden, VRAArticuloCompra,
    VRAExistenciaBodega, VRADocumentoInv, VRAAuditTransInv, VRAExistenciaReserva, VRATransaccionInv, VRALineaDocInv,
    VRAConsecutivoCi, VRAExistenciaLote, VRAArticulo, VRALote, VRAAsientoDeDiario, VRADiario, VRACgAux, VRAPaquete
)
from user_management.models import Role
from IMS.utility import (
    send_new_po_alert, send_new_shipment_alert, send_new_requirement_alert, send_approved_requirement_alert,
    send_approved_po_alert, send_approved_shipment_alert, send_rejected_po_alert, send_rejected_requirement_alert,
    send_rejected_shipment_alert, send_cancelled_shipment_alert, send_cancelled_po_alert,
    send_cancelled_requirement_alert, send_cancelled_stocktransfer_alert, send_new_stocktransfer_alert,
    send_approved_stocktransfer_alert, send_rejected_stocktransfer_alert, send_applied_stocktransfer_alert
)
from django.db.models import F

logger = logging.getLogger(__name__)



def create_purchase_order(data_dict):
    """
    Crea una orden de compra tanto en la base de datos MSSQL como en PostgreSQL de manera atómica.
    Si alguna de las operaciones falla, se revierte toda la transacción para mantener la integridad de los datos.
    :param data_dict:
    :return:
    """
    try:
        with transaction.atomic(using='mssql_db'):
            lineas = data_dict.pop('orden_compra_lineas')
            data_dict['RecordDate'] = datetime.now()
            data_dict['CreateDate'] = datetime.now()
            data_dict['RowPointer'] = str(uuid.uuid4()).upper()
            VRAOrdenCompra.objects.create(**data_dict)
            for linea in lineas:
                linea['ORDEN_COMPRA'] = data_dict['ORDEN_COMPRA']
                linea['RecordDate'] = datetime.now()
                linea['CreateDate'] = datetime.now()
                linea['RowPointer'] = str(uuid.uuid4()).upper()
                VRAOrdenCompraLinea.objects.create(**linea)
            vra_globales = VRAGlobalesCo.objects.first()
            vra_globales.ULT_ORDEN_COMPRA = data_dict['ORDEN_COMPRA']
            vra_globales.save(update_fields=['ULT_ORDEN_COMPRA'])

        with transaction.atomic(using='default'):
            oc_new = VRAOrdenCompra.objects.get(ORDEN_COMPRA=data_dict['ORDEN_COMPRA'])
            oc_new_dict = model_to_dict(oc_new)
            OrdenCompra.objects.create(**oc_new_dict)
            lineas = VRAOrdenCompraLinea.objects.filter(ORDEN_COMPRA=data_dict['ORDEN_COMPRA'])
            for linea in lineas:
                line_item = model_to_dict(linea)
                OrdenCompraLinea.objects.create(**line_item)
            globales = GlobalesCo.objects.first()
            globales.ULT_ORDEN_COMPRA = data_dict['ORDEN_COMPRA']
            globales.save(update_fields=['ULT_ORDEN_COMPRA'])
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
            send_new_po_alert([oc_new], users_to_notify)
    except Exception as e:
        raise e
    finally:
        for query in connections['mssql_db'].queries:
            logger.info(query['sql'])

def update_purchase_order(orden_compra, data_dict):
    """
    Actualiza una orden de compra tanto en la base de datos MSSQL como en PostgreSQL de manera atómica.
    Si alguna de las operaciones falla, se revierte toda la transacción para mantener la integridad de los datos.
    :param orden_compra:
    :param data_dict:
    :return:
    """
    try:
        with ((transaction.atomic(using='mssql_db'))):
            lineas = data_dict.pop('orden_compra_lineas', [])
            data_dict['RecordDate'] = datetime.now()
            VRAOrdenCompra.objects.filter(ORDEN_COMPRA=orden_compra).update(**data_dict)
            remove_linea = list(VRAOrdenCompraLinea.objects.filter(ORDEN_COMPRA=orden_compra)
                                .values_list('ORDEN_COMPRA_LINEA', flat=True))
            for linea in lineas:
                linea['RecordDate'] = datetime.now()
                oc_linea = linea.get('ORDEN_COMPRA_LINEA')
                if oc_linea in remove_linea:
                    remove_linea.remove(oc_linea)
                VRAOrdenCompraLinea.objects.filter(ORDEN_COMPRA=orden_compra, ORDEN_COMPRA_LINEA=oc_linea
                                                   ).update(**linea)
            if remove_linea:
                VRAOrdenCompraLinea.objects.filter(ORDEN_COMPRA=orden_compra, ORDEN_COMPRA_LINEA__in=remove_linea
                                                   ).delete()

        with transaction.atomic(using='default'):
            OrdenCompra.objects.filter(ORDEN_COMPRA=orden_compra).update(**data_dict)
            remove_linea = list(OrdenCompraLinea.objects.filter(ORDEN_COMPRA=orden_compra)
                                .values_list('ORDEN_COMPRA_LINEA', flat=True))
            for linea in lineas:
                linea['RecordDate'] = datetime.now()
                oc_linea = linea.get('ORDEN_COMPRA_LINEA')
                if oc_linea in remove_linea:
                    remove_linea.remove(oc_linea)
                OrdenCompraLinea.objects.filter(ORDEN_COMPRA=orden_compra, ORDEN_COMPRA_LINEA=oc_linea).update(**linea)
            if remove_linea:
                OrdenCompraLinea.objects.filter(ORDEN_COMPRA=orden_compra, ORDEN_COMPRA_LINEA__in=remove_linea).delete()
    except Exception as e:
        raise e
    finally:
        for query in connections['mssql_db'].queries:
            logger.info(query['sql'])

def approve_purchase_order(orden_compra, approver):
    """
    Aprueba una orden de compra tanto en la base de datos MSSQL como en PostgreSQL de manera atómica.
    Si alguna de las operaciones falla, se revierte toda la transacción para mantener la integridad de los datos.
    :param orden_compra:
    :param approver:
    :return:
    """
    try:
        current_time = datetime.now()
        with transaction.atomic(using='mssql_db'):
            lineas_counts = VRAOrdenCompraLinea.objects.filter(ORDEN_COMPRA=orden_compra).count()
            if lineas_counts == 0:
                raise IntegrityError(f"La orden de compra {orden_compra} no tiene líneas asociadas.")
            orden = VRAOrdenCompra.objects.get(ORDEN_COMPRA=orden_compra)
            if not orden.FECHA_COTIZACION:
                raise IntegrityError(f"La orden de compra {orden_compra} no tiene fecha de cotización.")
            VRAOrdenCompra.objects.filter(ORDEN_COMPRA=orden_compra).update(
                ESTADO='E',
                CONFIRMADA='S',
                USUARIO_CONFIRMA=approver,
                FECHA_HORA_CONFIR=current_time,
                RecordDate=current_time
            )
            VRAOrdenCompraLinea.objects.filter(ORDEN_COMPRA=orden_compra).update(
                ESTADO='E',
                RecordDate=current_time
            )
            seguimiento_count = VRASeguimientoOrden.objects.filter(ORDEN_COMPRA=orden_compra).count()
            VRAUsuariosAprobOc.objects.create(
                ORDEN_COMPRA=orden_compra,
                USUARIO=approver,
                FECHA_APROB=current_time,
                RecordDate=current_time,
                CreateDate=current_time,
                RowPointer=str(uuid.uuid4()).upper(),
                NoteExistsFlag=False,
            )
            VRASeguimientoOrden.objects.create(
                ORDEN_COMPRA=orden_compra,
                CONSECUTIVO=seguimiento_count+1,
                ESTADO='C',
                DESCRIPCION="Se genera orden de compra",
                MEDIO="M",
                FUENTE=approver,
                RecordDate=current_time,
                CreateDate=current_time,
                RowPointer=str(uuid.uuid4()).upper(),
                NoteExistsFlag=False,
            )
            lineas = VRAOrdenCompraLinea.objects.filter(ORDEN_COMPRA=orden_compra)
            for linea in lineas:
                articulo = linea.ARTICULO
                cantidad = linea.CANTIDAD_ORDENADA
                existencia, created = VRAExistenciaBodega.objects.get_or_create(
                    ARTICULO=articulo,
                    BODEGA=linea.BODEGA,
                    defaults={
                        'EXISTENCIA_MINIMA': 0,
                        'EXISTENCIA_MAXIMA': 0,
                        'PUNTO_DE_REORDEN': 0,
                        'CANT_DISPONIBLE': 0,
                        'CANT_RESERVADA': 0,
                        'CANT_NO_APROBADA': 0,
                        'CANT_VENCIDA': 0,
                        'CANT_TRANSITO': cantidad,
                        'CANT_PRODUCCION': 0,
                        'CANT_PEDIDA': 0,
                        'CANT_REMITIDA': 0,
                        'COSTO_UNT_PROMEDIO_LOC': 0,
                        'COSTO_UNT_PROMEDIO_DOL': 0,
                        'COSTO_UNT_ESTANDAR_LOC': 0,
                        'COSTO_UNT_ESTANDAR_DOL': 0,
                        'COSTO_PROM_COMPARATIVO_LOC': 0,
                        'COSTO_PROM_COMPARATIVO_DOLAR': 0,
                        'RecordDate': current_time,
                        'CreateDate': current_time,
                        'RowPointer': str(uuid.uuid4()).upper(),
                        'NoteExistsFlag': False,
                    }
                )
                if not created:
                    VRAExistenciaBodega.objects.filter(ARTICULO=articulo,BODEGA=linea.BODEGA).update(
                        CANT_TRANSITO=existencia.CANT_TRANSITO+cantidad,
                        RecordDate=current_time
                    )
                articulo_compra, art_created = VRAArticuloCompra.objects.get_or_create(
                    ARTICULO=articulo,
                    defaults={
                        'ULT_PREC_UNITARIO': linea.PRECIO_UNITARIO,
                        'ULT_PROVEEDOR': orden.PROVEEDOR,
                        'ULT_MONEDA': orden.MONEDA,
                        'ULT_FECHA_COTIZA': orden.FECHA_COTIZACION,
                        'IMPUESTO': linea.CODIGO_IMPUESTO,
                        'IMP1_AFECTA_COSTO': 'S' if linea.CODIGO_IMPUESTO == '1' else 'N',
                        'RECIBIR_MAS': orden.RECIBIDO_DE_MAS,
                        'RecordDate': current_time,
                        'CreateDate': current_time,
                        'RowPointer': str(uuid.uuid4()).upper(),
                        'NoteExistsFlag': False,
                    }
                )
                if not art_created:
                    articulo_compra.ULT_PREC_UNITARIO = linea.PRECIO_UNITARIO
                    articulo_compra.ULT_PROVEEDOR = orden.PROVEEDOR
                    articulo_compra.ULT_MONEDA = orden.MONEDA
                    articulo_compra.ULT_FECHA_COTIZA = orden.FECHA_COTIZACION
                    articulo_compra.RecordDate = current_time
                    articulo_compra.save(update_fields=['ULT_PREC_UNITARIO', 'ULT_PROVEEDOR', 'ULT_MONEDA',
                                                        'ULT_FECHA_COTIZA', 'RecordDate'])

        with transaction.atomic(using='default'):
            lineas_counts = OrdenCompraLinea.objects.filter(ORDEN_COMPRA=orden_compra).count()
            if lineas_counts == 0:
                raise IntegrityError(f"La orden de compra {orden_compra} no tiene líneas asociadas.")
            orden = OrdenCompra.objects.get(ORDEN_COMPRA=orden_compra)
            if not orden.FECHA_COTIZACION:
                raise IntegrityError(f"La orden de compra {orden_compra} no tiene fecha de cotización.")
            OrdenCompra.objects.filter(ORDEN_COMPRA=orden_compra).update(
                ESTADO='E',
                CONFIRMADA='S',
                USUARIO_CONFIRMA=approver,
                FECHA_HORA_CONFIR=current_time,
                RecordDate=current_time
            )
            OrdenCompraLinea.objects.filter(ORDEN_COMPRA=orden_compra).update(
                ESTADO='E',
                RecordDate=current_time
            )
            seguimiento_count = SeguimientoOrden.objects.filter(ORDEN_COMPRA=orden_compra).count()
            UsuariosAprobOc.objects.create(
                ORDEN_COMPRA=orden_compra,
                USUARIO=approver,
                FECHA_APROB=current_time,
                RecordDate=current_time,
                CreateDate=current_time,
                RowPointer=str(uuid.uuid4()).upper(),
                NoteExistsFlag=False,
            )
            SeguimientoOrden.objects.create(
                ORDEN_COMPRA=orden_compra,
                CONSECUTIVO=seguimiento_count+1,
                ESTADO='C',
                DESCRIPCION="Se genera orden de compra",
                MEDIO="M",
                FUENTE=approver,
                RecordDate=current_time,
                CreateDate=current_time,
                RowPointer=str(uuid.uuid4()).upper(),
                NoteExistsFlag=False,
            )
            lineas = OrdenCompraLinea.objects.filter(ORDEN_COMPRA=orden_compra)
            for linea in lineas:
                articulo = linea.ARTICULO
                cantidad = linea.CANTIDAD_ORDENADA
                existencia, created = ExistenciaBodega.objects.get_or_create(
                    ARTICULO=articulo,
                    BODEGA=linea.BODEGA,
                    defaults={
                        'EXISTENCIA_MINIMA': 0,
                        'EXISTENCIA_MAXIMA': 0,
                        'PUNTO_DE_REORDEN': 0,
                        'CANT_DISPONIBLE': 0,
                        'CANT_RESERVADA': 0,
                        'CANT_NO_APROBADA': 0,
                        'CANT_VENCIDA': 0,
                        'CANT_TRANSITO': cantidad,
                        'CANT_PRODUCCION': 0,
                        'CANT_PEDIDA': 0,
                        'CANT_REMITIDA': 0,
                        'COSTO_UNT_PROMEDIO_LOC': 0,
                        'COSTO_UNT_PROMEDIO_DOL': 0,
                        'COSTO_UNT_ESTANDAR_LOC': 0,
                        'COSTO_UNT_ESTANDAR_DOL': 0,
                        'COSTO_PROM_COMPARATIVO_LOC': 0,
                        'COSTO_PROM_COMPARATIVO_DOLAR': 0,
                        'RecordDate': current_time,
                        'CreateDate': current_time,
                        'RowPointer': str(uuid.uuid4()).upper(),
                        'NoteExistsFlag': False,
                    }
                )
                if not created:
                    existencia.CANT_TRANSITO += cantidad
                    existencia.RecordDate = current_time
                    existencia.save(update_fields=['CANT_TRANSITO', 'RecordDate'])
                articulo_compra, art_created = ArticuloCompra.objects.get_or_create(
                    ARTICULO=articulo,
                    defaults={
                        'ULT_PREC_UNITARIO': linea.PRECIO_UNITARIO,
                        'ULT_PROVEEDOR': orden.PROVEEDOR,
                        'ULT_MONEDA': orden.MONEDA,
                        'ULT_FECHA_COTIZA': orden.FECHA_COTIZACION,
                        'IMPUESTO': linea.CODIGO_IMPUESTO,
                        'IMP1_AFECTA_COSTO': 'S' if linea.CODIGO_IMPUESTO == '1' else 'N',
                        'RECIBIR_MAS': orden.RECIBIDO_DE_MAS,
                        'RecordDate': current_time,
                        'CreateDate': current_time,
                        'RowPointer': str(uuid.uuid4()).upper(),
                        'NoteExistsFlag': False,
                    }
                )
                if not art_created:
                    articulo_compra.ULT_PREC_UNITARIO = linea.PRECIO_UNITARIO
                    articulo_compra.ULT_PROVEEDOR = orden.PROVEEDOR
                    articulo_compra.ULT_MONEDA = orden.MONEDA
                    articulo_compra.ULT_FECHA_COTIZA = orden.FECHA_COTIZACION
                    articulo_compra.RecordDate = current_time
                    articulo_compra.save(update_fields=['ULT_PREC_UNITARIO', 'ULT_PROVEEDOR', 'ULT_MONEDA',
                                                        'ULT_FECHA_COTIZA', 'RecordDate'])
        users_to_notify = set()
        pm_role = Role.objects.filter(code='purchase-manager').first()
        admin_role = Role.objects.filter(code='admin').first()
        if pm_role:
            users_to_notify.update(pm_role.users.all())
        if admin_role:
            users_to_notify.update(admin_role.users.all())
        orden_compra = OrdenCompra.objects.get(ORDEN_COMPRA=orden_compra)
        send_approved_po_alert([orden_compra], users_to_notify)

    except Exception as e:
        raise e
    finally:
        for query in connections['mssql_db'].queries:
            logger.info(query['sql'])

def disapprove_purchase_order(orden_compra, disapprover):
    """
    Desaprueba una orden de compra tanto en la base de datos MSSQL como en PostgreSQL de manera atómica.
    Si alguna de las operaciones falla, se revierte toda la transacción para mantener la integridad de los datos.
    :param orden_compra:
    :param disapprover:
    :return:
    """
    try:
        current_time = datetime.now()
        with transaction.atomic(using='mssql_db'):
            VRAOrdenCompra.objects.filter(ORDEN_COMPRA=orden_compra).update(
                ESTADO='A',
                FECHA_ULT_NOTIF=None,
                CONFIRMADA='N',
                USUARIO_CONFIRMA=None,
                FECHA_HORA_CONFIR=None,
                RecordDate=current_time
            )
            VRAOrdenCompraLinea.objects.filter(ORDEN_COMPRA=orden_compra).exclude(ESTADO__in=('O','U')).update(
                ESTADO='A',
                CANTIDAD_ACEPTADA=0,
                RecordDate=current_time
            )
            VRAUsuariosAprobOc.objects.filter(ORDEN_COMPRA=orden_compra).delete()
            seguimiento_count = VRASeguimientoOrden.objects.filter(ORDEN_COMPRA=orden_compra).count()
            VRASeguimientoOrden.objects.create(
                ORDEN_COMPRA=orden_compra,
                CONSECUTIVO=seguimiento_count+1,
                ESTADO='D',
                DESCRIPCION="Se genera orden de compra",
                MEDIO="M",
                FUENTE=disapprover,
                RecordDate=current_time,
                CreateDate=current_time,
                RowPointer=str(uuid.uuid4()).upper(),
                NoteExistsFlag=False,
            )
            lineas = VRAOrdenCompraLinea.objects.filter(ORDEN_COMPRA=orden_compra)
            for linea in lineas:
                articulo = linea.ARTICULO
                cantidad = linea.CANTIDAD_ORDENADA
                existencia = VRAExistenciaBodega.objects.filter(ARTICULO=articulo, BODEGA=linea.BODEGA).first()
                if existencia:
                    VRAExistenciaBodega.objects.filter(ARTICULO=articulo, BODEGA=linea.BODEGA).update(
                        CANT_TRANSITO=max(0, existencia.CANT_TRANSITO - cantidad),
                        RecordDate=current_time
                    )

        with transaction.atomic(using='default'):
            OrdenCompra.objects.filter(ORDEN_COMPRA=orden_compra).update(
                ESTADO='A',
                FECHA_ULT_NOTIF=None,
                CONFIRMADA='N',
                USUARIO_CONFIRMA=None,
                FECHA_HORA_CONFIR=None,
                RecordDate=current_time
            )
            OrdenCompraLinea.objects.filter(ORDEN_COMPRA=orden_compra).exclude(ESTADO__in=('O','U')).update(
                ESTADO='A',
                CANTIDAD_ACEPTADA=0,
                RecordDate=current_time
            )
            UsuariosAprobOc.objects.filter(ORDEN_COMPRA=orden_compra).delete()
            seguimiento_count = SeguimientoOrden.objects.filter(ORDEN_COMPRA=orden_compra).count()
            SeguimientoOrden.objects.create(
                ORDEN_COMPRA=orden_compra,
                CONSECUTIVO=seguimiento_count+1,
                ESTADO='D',
                DESCRIPCION="Se genera orden de compra",
                MEDIO="M",
                FUENTE=disapprover,
                RecordDate=current_time,
                CreateDate=current_time,
                RowPointer=str(uuid.uuid4()).upper(),
                NoteExistsFlag=False,
            )
            lineas = OrdenCompraLinea.objects.filter(ORDEN_COMPRA=orden_compra)
            for linea in lineas:
                articulo = linea.ARTICULO
                cantidad = linea.CANTIDAD_ORDENADA
                existencia = ExistenciaBodega.objects.filter(ARTICULO=articulo, BODEGA=linea.BODEGA).first()
                if existencia:
                    existencia.CANT_TRANSITO = max(0, existencia.CANT_TRANSITO - cantidad)
                    existencia.RecordDate = current_time
                    existencia.save(update_fields=['CANT_TRANSITO', 'RecordDate'])

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
        orden_compra_obj = OrdenCompra.objects.get(ORDEN_COMPRA=orden_compra)
        send_rejected_po_alert([orden_compra_obj], users_to_notify)
    except Exception as e:
        raise e

def cancel_purchase_order(orden_compra, canceller):
    """
    Cancela una orden de compra tanto en la base de datos MSSQL como en PostgreSQL de manera atómica.
    Si alguna de las operaciones falla, se revierte toda la transacción para mantener la integridad de los datos.
    :param orden_compra:
    :param canceller:
    :return:
    """
    try:
        current_time = datetime.now()
        with transaction.atomic(using='mssql_db'):
            VRAOrdenCompra.objects.filter(ORDEN_COMPRA=orden_compra).update(
                ESTADO='O',
                PORC_DESCUENTO=0,
                MONTO_DESCUENTO=0,
                USUARIO_CANCELA=canceller,
                FECHA_HORA_CANCELA=current_time,
                RecordDate=current_time
            )
            seguimiento_count = VRASeguimientoOrden.objects.filter(ORDEN_COMPRA=orden_compra).count()
            VRASeguimientoOrden.objects.create(
                ORDEN_COMPRA=orden_compra,
                CONSECUTIVO=seguimiento_count+1,
                ESTADO='N',
                DESCRIPCION="se genera orden de compra",
                MEDIO="M",
                FUENTE=canceller,
                RecordDate=current_time,
                CreateDate=current_time,
                RowPointer=str(uuid.uuid4()).upper(),
                NoteExistsFlag=False,
            )
            lineas = VRAOrdenCompraLinea.objects.filter(ORDEN_COMPRA=orden_compra, ESTADO__in=('A','E', 'I'))
            for linea in lineas:
                VRAOrdenCompraLinea.objects.filter(
                    ORDEN_COMPRA=orden_compra, ORDEN_COMPRA_LINEA=linea.ORDEN_COMPRA_LINEA
                ).update(
                    ESTADO='O',
                    USUARIO_CANCELA=canceller,
                    FECHA_HORA_CANCELA=current_time,
                    COMENTARIO=f"{linea.COMENTARIO} cancelacion ({linea.CANTIDAD_ORDENADA})",
                    RecordDate=current_time,
                )

        with transaction.atomic(using='default'):
            OrdenCompra.objects.filter(ORDEN_COMPRA=orden_compra).update(
                ESTADO='O',
                PORC_DESCUENTO=0,
                MONTO_DESCUENTO=0,
                USUARIO_CANCELA=canceller,
                FECHA_HORA_CANCELA=current_time,
                RecordDate=current_time
            )
            seguimiento_count = SeguimientoOrden.objects.filter(ORDEN_COMPRA=orden_compra).count()
            SeguimientoOrden.objects.create(
                ORDEN_COMPRA=orden_compra,
                CONSECUTIVO=seguimiento_count+1,
                ESTADO='N',
                DESCRIPCION="se genera orden de compra",
                MEDIO="M",
                FUENTE=canceller,
                RecordDate=current_time,
                CreateDate=current_time,
                RowPointer=str(uuid.uuid4()).upper(),
                NoteExistsFlag=False,
            )
            lineas = OrdenCompraLinea.objects.filter(ORDEN_COMPRA=orden_compra, ESTADO__in=('A','E', 'I'))
            for linea in lineas:
                linea.ESTADO = 'O'
                linea.USUARIO_CANCELA = canceller
                linea.FECHA_HORA_CANCELA = current_time
                linea.COMENTARIO = f"{linea.COMENTARIO} cancelacion ({linea.CANTIDAD_ORDENADA})"
                linea.RecordDate = current_time
                linea.save(update_fields=['ESTADO', 'USUARIO_CANCELA', 'FECHA_HORA_CANCELA',
                                          'COMENTARIO', 'RecordDate'])
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
        orden_compra_obj = OrdenCompra.objects.get(ORDEN_COMPRA=orden_compra)
        send_cancelled_po_alert([orden_compra_obj], users_to_notify)
    except Exception as e:
        raise e

def create_shipment(data_dict):
    """
    Crea un embarque tanto en la base de datos MSSQL como en PostgreSQL de manera atómica.
    Si alguna de las operaciones falla, se revierte toda la transacción para mantener la integridad de los datos.
    :param data_dict:
    :return:
    """
    try:
        with transaction.atomic(using='mssql_db'):
            lineas = data_dict.pop('embarque_lineas', [])
            desglose_lineas = data_dict.pop('desglose_lineas', [])
            data_dict['RecordDate'] = datetime.now()
            data_dict['CreateDate'] = datetime.now()
            data_dict['RowPointer'] = str(uuid.uuid4()).upper()
            VRAEmbarque.objects.create(**data_dict)
            for linea in lineas:
                linea['EMBARQUE'] = data_dict['EMBARQUE']
                linea['RecordDate'] = datetime.now()
                linea['CreateDate'] = datetime.now()
                linea['RowPointer'] = str(uuid.uuid4()).upper()
                VRAEmbarqueLinea.objects.create(**linea)
            for desglose in desglose_lineas:
                desglose['EMBARQUE'] = data_dict['EMBARQUE']
                desglose['RecordDate'] = datetime.now()
                desglose['CreateDate'] = datetime.now()
                desglose['RowPointer'] = str(uuid.uuid4()).upper()
                VRADetLinEmbarque.objects.create(**desglose)
            vra_globales = VRAGlobalesCo.objects.first()
            vra_globales.ULT_EMBARQUE = data_dict['EMBARQUE']
            vra_globales.ULT_CRM = data_dict['CRM']
            vra_globales.save(update_fields=['ULT_EMBARQUE', 'ULT_CRM'])

        with transaction.atomic(using='default'):
            emb_new = VRAEmbarque.objects.get(EMBARQUE=data_dict['EMBARQUE'])
            emb_new_dict = model_to_dict(emb_new)
            Embarque.objects.create(**emb_new_dict)
            lineas = VRAEmbarqueLinea.objects.filter(EMBARQUE=data_dict['EMBARQUE'])
            for linea in lineas:
                line_item = model_to_dict(linea)
                EmbarqueLinea.objects.create(**line_item)
            desglose_lineas = VRADetLinEmbarque.objects.filter(EMBARQUE=data_dict['EMBARQUE'])
            for desglose in desglose_lineas:
                desglose_item = model_to_dict(desglose)
                DetLinEmbarque.objects.create(**desglose_item)
            globales = GlobalesCo.objects.first()
            globales.ULT_EMBARQUE = data_dict['EMBARQUE']
            globales.ULT_CRM = data_dict['CRM']
            globales.save(update_fields=['ULT_EMBARQUE', 'ULT_CRM'])
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
            send_new_shipment_alert([emb_new], users_to_notify)

    except Exception as e:
        raise e
    finally:
        for query in connections['mssql_db'].queries:
            logger.info(query['sql'])

def update_em_shipment(embarque, data_dict):
    """
    Actualiza un embarque tanto en la base de datos MSSQL como en PostgreSQL de manera atómica.
    Si alguna de las operaciones falla, se revierte toda la transacción para mantener la integridad de los datos.
    :param embarque:
    :param data_dict:
    :return:
    """
    try:
        with transaction.atomic(using='mssql_db'):
            lineas = data_dict.pop('embarque_lineas', [])
            desglose_lineas = data_dict.pop('desglose_lineas', [])
            data_dict['RecordDate'] = datetime.now()
            VRAEmbarque.objects.filter(EMBARQUE=embarque).update(**data_dict)
            remove_linea = list(VRAEmbarqueLinea.objects.filter(EMBARQUE=embarque)
                                .values_list('EMBARQUE_LINEA', flat=True))
            remove_desglose = list(VRADetLinEmbarque.objects.filter(EMBARQUE=embarque)
                                   .values_list('EMBARQUE_LINEA', flat=True))
            for linea in lineas:
                linea['RecordDate'] = datetime.now()
                emb_linea = linea.get('EMBARQUE_LINEA')
                if emb_linea in remove_linea:
                    remove_linea.remove(emb_linea)
                VRAEmbarqueLinea.objects.filter(EMBARQUE=embarque, EMBARQUE_LINEA=emb_linea).update(**linea)
            for desglose in desglose_lineas:
                desglose['RecordDate'] = datetime.now()
                det_linea = desglose.get('EMBARQUE_LINEA')
                if det_linea in remove_desglose:
                    remove_desglose.remove(det_linea)
                VRADetLinEmbarque.objects.filter(EMBARQUE=embarque, EMBARQUE_LINEA=det_linea).update(**desglose)
            if remove_linea:
                VRAEmbarqueLinea.objects.filter(EMBARQUE=embarque, EMBARQUE_LINEA__in=remove_linea).delete()
            if remove_desglose:
                VRADetLinEmbarque.objects.filter(EMBARQUE=embarque, EMBARQUE_LINEA__in=remove_desglose).delete()

        with transaction.atomic(using='default'):
            Embarque.objects.filter(EMBARQUE=embarque).update(**data_dict)
            remove_linea = list(
                EmbarqueLinea.objects.filter(EMBARQUE=embarque).values_list('EMBARQUE_LINEA', flat=True))
            remove_desglose = list(
                DetLinEmbarque.objects.filter(EMBARQUE=embarque).values_list('EMBARQUE_LINEA', flat=True))
            for linea in lineas:
                linea['RecordDate'] = datetime.now()
                emb_linea = linea.get('EMBARQUE_LINEA')
                if emb_linea in remove_linea:
                    remove_linea.remove(emb_linea)
                EmbarqueLinea.objects.filter(EMBARQUE=embarque, EMBARQUE_LINEA=emb_linea).update(**linea)
            for desglose in desglose_lineas:
                desglose['RecordDate'] = datetime.now()
                det_linea = desglose.get('EMBARQUE_LINEA')
                if det_linea in remove_desglose:
                    remove_desglose.remove(det_linea)
                DetLinEmbarque.objects.filter(EMBARQUE=embarque, EMBARQUE_LINEA=det_linea).update(**desglose)
            if remove_linea:
                EmbarqueLinea.objects.filter(EMBARQUE=embarque, EMBARQUE_LINEA__in=remove_linea).delete()
            if remove_desglose:
                DetLinEmbarque.objects.filter(EMBARQUE=embarque, EMBARQUE_LINEA__in=remove_desglose).delete()

    except Exception as e:
        raise e
    finally:
        for query in connections['mssql_db'].queries:
            logger.info(query['sql'])

def approve_shipment(embarque):
    """
    Aprueba un embarque tanto en la base de datos MSSQL como en PostgreSQL de manera atómica.
    Si alguna de las operaciones falla, se revierte toda la transacción para mantener la integridad de los datos.
    :param embarque:
    :return:
    """
    try:
        current_time = datetime.now()
        with transaction.atomic(using='mssql_db'):
            VRAEmbarque.objects.filter(EMBARQUE=embarque).update(
                ESTADO='T',
                RecordDate=current_time
            )
        with transaction.atomic(using='default'):
            Embarque.objects.filter(EMBARQUE=embarque).update(
                ESTADO='T',
                RecordDate=current_time
            )
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
        embarque_obj = Embarque.objects.get(EMBARQUE=embarque)
        send_approved_shipment_alert([embarque_obj], users_to_notify)
    except Exception as e:
        raise e

def disapprove_shipment(embarque):
    """
    Desaprueba un embarque tanto en la base de datos MSSQL como en PostgreSQL de manera atómica.
    Si alguna de las operaciones falla, se revierte toda la transacción para mantener la integridad de los datos.
    :param embarque:
    :return:
    """
    try:
        current_time = datetime.now()
        with transaction.atomic(using='mssql_db'):
            VRAEmbarque.objects.filter(EMBARQUE=embarque).update(
                ESTADO='P',
                RecordDate=current_time
            )
        with transaction.atomic(using='default'):
            Embarque.objects.filter(EMBARQUE=embarque).update(
                ESTADO='P',
                RecordDate=current_time
            )
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
        embarque_obj = Embarque.objects.get(EMBARQUE=embarque)
        send_rejected_shipment_alert([embarque_obj], users_to_notify)
    except Exception as e:
        raise e

def cancel_shipment(embarque):
    """
    Cancela un embarque tanto en la base de datos MSSQL como en PostgreSQL de manera atómica.
    Si alguna de las operaciones falla, se revierte toda la transacción para mantener la integridad de los datos.
    :param embarque:
    :return:
    """
    try:
        current_time = datetime.now()
        with transaction.atomic(using='mssql_db'):
            VRAEmbarque.objects.filter(EMBARQUE=embarque).update(
                ESTADO='C',
                RecordDate=current_time
            )
            VRADetLinEmbarque.objects.filter(EMBARQUE=embarque).delete()
            lineas = VRAEmbarqueLinea.objects.filter(EMBARQUE=embarque)
            for linea in lineas:
                oc_linea = VRAOrdenCompraLinea.objects.filter(ORDEN_COMPRA=linea.ORDEN_COMPRA,
                                                              ORDEN_COMPRA_LINEA=linea.ORDEN_COMPRA_LINEA).first()
                if oc_linea:
                    VRAOrdenCompraLinea.objects.filter(ORDEN_COMPRA=linea.ORDEN_COMPRA,
                                                       ORDEN_COMPRA_LINEA=linea.ORDEN_COMPRA_LINEA).update(
                        CANTIDAD_EMBARCADA=oc_linea.CANTIDAD_EMBARCADA - linea.CANTIDAD_EMBARCADA,
                        MONTO_APLICADO=max(0, (
                            oc_linea.MONTO_APLICADO if oc_linea.MONTO_APLICADO else 0) - linea.MONTO_APLICADO_OC),
                        RecordDate=current_time
                    )
        with transaction.atomic(using='default'):
            Embarque.objects.filter(EMBARQUE=embarque).update(
                ESTADO='C',
                NOTAS='',
                RecordDate=current_time
            )
            DetLinEmbarque.objects.filter(EMBARQUE=embarque).delete()
            lineas = EmbarqueLinea.objects.filter(EMBARQUE=embarque)
            for linea in lineas:
                oc_linea = OrdenCompraLinea.objects.filter(ORDEN_COMPRA=linea.ORDEN_COMPRA,
                                                           ORDEN_COMPRA_LINEA=linea.ORDEN_COMPRA_LINEA).first()
                if oc_linea:
                    oc_linea.CANTIDAD_EMBARCADA = oc_linea.CANTIDAD_EMBARCADA - linea.CANTIDAD_EMBARCADA
                    oc_linea.MONTO_APLICADO = max(0, (
                        oc_linea.MONTO_APLICADO if oc_linea.MONTO_APLICADO else 0) - linea.MONTO_APLICADO_OC)
                    oc_linea.RecordDate = current_time
                    oc_linea.save(update_fields=['CANTIDAD_EMBARCADA', 'MONTO_APLICADO', 'RecordDate'])
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
        embarque_obj = Embarque.objects.get(EMBARQUE=embarque)
        send_cancelled_shipment_alert([embarque_obj], users_to_notify)
    except Exception as e:
        raise e

def create_purchase_request(data_dict):
    """
    Crea una solicitud de compra tanto en la base de datos MSSQL como en PostgreSQL de manera atómica.
    Si alguna de las operaciones falla, se revierte toda la transacción para mantener la integridad de los datos.
    :param data_dict:
    :return:
    """
    try:
        with transaction.atomic(using='mssql_db'):
            lineas = data_dict.pop('solicitud_lineas')
            data_dict['RecordDate'] = datetime.now()
            data_dict['CreateDate'] = datetime.now()
            data_dict['RowPointer'] = str(uuid.uuid4()).upper()
            VRASolicitudOc.objects.create(**data_dict)
            for linea in lineas:
                linea['SOLICITUD_OC'] = data_dict['SOLICITUD_OC']
                linea['RecordDate'] = datetime.now()
                linea['CreateDate'] = datetime.now()
                linea['RowPointer'] = str(uuid.uuid4()).upper()
                VRASolicitudOcLinea.objects.create(**linea)
            vra_globales = VRAGlobalesCo.objects.first()
            vra_globales.ULT_SOLICITUD = data_dict['SOLICITUD_OC']
            vra_globales.save(update_fields=['ULT_SOLICITUD'])

        with transaction.atomic(using='default'):
            oc_new = VRASolicitudOc.objects.get(SOLICITUD_OC=data_dict['SOLICITUD_OC'])
            oc_new_dict = model_to_dict(oc_new)
            SolicitudOc.objects.create(**oc_new_dict)
            lineas = VRASolicitudOcLinea.objects.filter(SOLICITUD_OC=data_dict['SOLICITUD_OC'])
            for linea in lineas:
                line_item = model_to_dict(linea)
                SolicitudOcLinea.objects.create(**line_item)
            globales = GlobalesCo.objects.first()
            globales.ULT_SOLICITUD = data_dict['SOLICITUD_OC']
            globales.save(update_fields=['ULT_SOLICITUD'])
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
            send_new_requirement_alert([oc_new], users_to_notify)
    except Exception as e:
        raise e
    finally:
        for query in connections['mssql_db'].queries:
            logger.info(query['sql'])

def update_purchase_request(solicitud_oc, data_dict):
    """
    Actualiza una solicitud de compra tanto en la base de datos MSSQL como en PostgreSQL de manera atómica.
    Si alguna de las operaciones falla, se revierte toda la transacción para mantener la integridad de los datos.
    :param solicitud_oc:
    :param data_dict:
    :return:
    """
    try:
        current_time = datetime.now()
        with transaction.atomic(using='mssql_db'):
            lineas = data_dict.pop('solicitud_lineas', [])
            data_dict['RecordDate'] = current_time
            VRASolicitudOc.objects.filter(SOLICITUD_OC=solicitud_oc).update(**data_dict)
            remove_linea = list(VRASolicitudOcLinea.objects.filter(SOLICITUD_OC=solicitud_oc)
                                .values_list('SOLICITUD_OC_LINEA', flat=True))
            for linea in lineas:
                linea['RecordDate'] = current_time
                oc_linea = linea.get('SOLICITUD_OC_LINEA')
                if oc_linea in remove_linea:
                    remove_linea.remove(oc_linea)
                VRASolicitudOcLinea.objects.filter(SOLICITUD_OC=solicitud_oc, SOLICITUD_OC_LINEA=oc_linea).update(
                    **linea)
            if remove_linea:
                VRASolicitudOcLinea.objects.filter(SOLICITUD_OC=solicitud_oc,
                                                   SOLICITUD_OC_LINEA__in=remove_linea).delete()

        with transaction.atomic(using='default'):
            SolicitudOc.objects.filter(SOLICITUD_OC=solicitud_oc).update(**data_dict)
            remove_linea = list(
                SolicitudOcLinea.objects.filter(SOLICITUD_OC=solicitud_oc)
                .values_list('SOLICITUD_OC_LINEA', flat=True))
            for linea in lineas:
                linea['RecordDate'] = current_time
                oc_linea = linea.get('SOLICITUD_OC_LINEA')
                if oc_linea in remove_linea:
                    remove_linea.remove(oc_linea)
                SolicitudOcLinea.objects.filter(SOLICITUD_OC=solicitud_oc, SOLICITUD_OC_LINEA=oc_linea).update(**linea)
            if remove_linea:
                SolicitudOcLinea.objects.filter(SOLICITUD_OC=solicitud_oc, SOLICITUD_OC_LINEA__in=remove_linea).delete()
    except Exception as e:
        raise e
    finally:
        for query in connections['mssql_db'].queries:
            logger.info(query['sql'])

def approve_purchase_request(solicitud_oc, approver):
    """
    Aprueba una solicitud de compra tanto en la base de datos MSSQL como en PostgreSQL de manera atómica.
    Si alguna de las operaciones falla, se revierte toda la transacción para mantener la integridad de los datos.
    :param solicitud_oc:
    :param approver:
    :return:
    """
    try:
        current_time = datetime.now()
        with transaction.atomic(using='mssql_db'):
            lineas_counts = VRASolicitudOcLinea.objects.filter(SOLICITUD_OC=solicitud_oc).count()
            if lineas_counts == 0:
                raise IntegrityError(f"La solicitud de compra {solicitud_oc} no tiene líneas asociadas.")
            VRASolicitudOc.objects.filter(SOLICITUD_OC=solicitud_oc).update(
                ESTADO='E',
                AUTORIZADA_POR=approver,
                FECHA_AUTORIZADA=current_time,
                RecordDate=current_time
            )
            VRASolicitudOcLinea.objects.filter(SOLICITUD_OC=solicitud_oc).update(
                ESTADO='E',
                RecordDate=current_time
            )

        with transaction.atomic(using='default'):
            SolicitudOc.objects.filter(SOLICITUD_OC=solicitud_oc).update(
                ESTADO='E',
                AUTORIZADA_POR=approver,
                FECHA_AUTORIZADA=current_time,
                RecordDate=current_time
            )
            SolicitudOcLinea.objects.filter(SOLICITUD_OC=solicitud_oc).update(
                ESTADO='E',
                RecordDate=current_time
            )

        users_to_notify = set()
        admin_role = Role.objects.filter(code='admin').first()
        pm_role = Role.objects.filter(code='purchase-manager').first()
        if pm_role:
            users_to_notify.update(pm_role.users.all())
        if admin_role:
            users_to_notify.update(admin_role.users.all())
        solicitud_oc = SolicitudOc.objects.get(SOLICITUD_OC=solicitud_oc)
        send_approved_requirement_alert([solicitud_oc], users_to_notify)
    except Exception as e:
        raise e
    finally:
        for query in connections['mssql_db'].queries:
            logger.info(query['sql'])

def disapprove_purchase_request(solicitud_oc):
    """
    Desaprueba una solicitud de compra tanto en la base de datos MSSQL como en PostgreSQL de manera atómica.
    Si alguna de las operaciones falla, se revierte toda la transacción para mantener la integridad de los datos.
    :param solicitud_oc:
    :return:
    """
    try:
        current_time = datetime.now()
        with transaction.atomic(using='mssql_db'):
            VRASolicitudOc.objects.filter(SOLICITUD_OC=solicitud_oc).update(
                ESTADO='A',
                AUTORIZADA_POR=None,
                FECHA_AUTORIZADA=None,
                RecordDate=current_time
            )
            VRASolicitudOcLinea.objects.filter(SOLICITUD_OC=solicitud_oc).update(
                ESTADO='A',
                RecordDate=current_time
            )

        with transaction.atomic(using='default'):
            SolicitudOc.objects.filter(SOLICITUD_OC=solicitud_oc).update(
                ESTADO='A',
                AUTORIZADA_POR=None,
                FECHA_AUTORIZADA=None,
                RecordDate=current_time
            )
            SolicitudOcLinea.objects.filter(SOLICITUD_OC=solicitud_oc).update(
                ESTADO='A',
                RecordDate=current_time
            )

        users_to_notify = set()
        admin_role = Role.objects.filter(code='admin').first()
        pm_role = Role.objects.filter(code='purchase-manager').first()
        if pm_role:
            users_to_notify.update(pm_role.users.all())
        if admin_role:
            users_to_notify.update(admin_role.users.all())
        solicitud_oc = SolicitudOc.objects.get(SOLICITUD_OC=solicitud_oc)
        send_rejected_requirement_alert([solicitud_oc], users_to_notify)
    except Exception as e:
        raise e

def cancel_purchase_request(solicitud_oc, canceller, comment=""):
    """
    Cancela una solicitud de compra tanto en la base de datos MSSQL como en PostgreSQL de manera atómica.
    Si alguna de las operaciones falla, se revierte toda la transacción para mantener la integridad de los datos.
    :param solicitud_oc:
    :param canceller:
    :param comment:
    :return:
    """
    try:
        current_time = datetime.now()
        with transaction.atomic(using='mssql_db'):
            solicitud = VRASolicitudOc.objects.filter(SOLICITUD_OC=solicitud_oc).first()
            if not solicitud:
                raise IntegrityError(f"La solicitud de compra {solicitud_oc} no existe.")
            solicitud.COMENTARIO = f"{solicitud.COMENTARIO} Motivo de cancelación: {comment}"
            solicitud.ESTADO = 'O'
            solicitud.USUARIO_CANCELA = canceller
            solicitud.FECHA_HORA_CANCELA = current_time
            solicitud.RecordDate = current_time
            solicitud.save(update_fields=['COMENTARIO', 'ESTADO', 'USUARIO_CANCELA',
                                            'FECHA_HORA_CANCELA', 'RecordDate'])
            lineas = VRASolicitudOcLinea.objects.filter(SOLICITUD_OC=solicitud_oc)
            for linea in lineas:
                VRASolicitudOcLinea.objects.filter(
                    SOLICITUD_OC=solicitud_oc, SOLICITUD_OC_LINEA=linea.SOLICITUD_OC_LINEA
                ).update(
                    COMENTARIO = f"{linea.COMENTARIO} Motivo deCANCELACIóN: {comment}",
                    ESTADO='O',
                    USUARIO_CANCELA=canceller,
                    FECHA_HORA_CANCELA=current_time,
                    RecordDate=current_time
                )

        with transaction.atomic(using='default'):
            solicitud = SolicitudOc.objects.filter(SOLICITUD_OC=solicitud_oc).first()
            if not solicitud:
                raise IntegrityError(f"La solicitud de compra {solicitud_oc} no existe.")
            solicitud.COMENTARIO = f"{solicitud.COMENTARIO} Motivo de cancelación: {comment}"
            solicitud.ESTADO = 'O'
            solicitud.USUARIO_CANCELA = canceller
            solicitud.FECHA_HORA_CANCELA = current_time
            solicitud.RecordDate = current_time
            solicitud.save(update_fields=['COMENTARIO', 'ESTADO', 'USUARIO_CANCELA',
                                            'FECHA_HORA_CANCELA', 'RecordDate'])
            lineas = SolicitudOcLinea.objects.filter(SOLICITUD_OC=solicitud_oc)
            for linea in lineas:
                linea.COMENTARIO = f"{linea.COMENTARIO} Motivo deCANCELACIóN: {comment}"
                linea.ESTADO = 'O'
                linea.USUARIO_CANCELA = canceller
                linea.FECHA_HORA_CANCELA = current_time
                linea.RecordDate = current_time
                linea.save(update_fields=['COMENTARIO', 'ESTADO', 'USUARIO_CANCELA', 'FECHA_HORA_CANCELA',
                                          'RecordDate'])
        pm_role = Role.objects.filter(code='purchase-manager').first()
        admin_role = Role.objects.filter(code='admin').first()
        users_to_notify = set()
        if pm_role:
            users_to_notify.update(pm_role.users.all())
        if admin_role:
            users_to_notify.update(admin_role.users.all())
        solicitud = SolicitudOc.objects.get(SOLICITUD_OC=solicitud_oc)
        send_cancelled_requirement_alert([solicitud], users_to_notify)
    except Exception as e:
        raise e
    finally:
        for query in connections['mssql_db'].queries:
            logger.info(query['sql'])

def create_location(data_dict):
    """
    Crea una localización tanto en la base de datos MSSQL como en PostgreSQL de manera atómica.
    Si alguna de las operaciones falla, se revierte toda la transacción para mantener la integridad de los datos.
    :param data_dict:
    :return:
    """
    try:
        with transaction.atomic(using='mssql_db'):
            data_dict['RecordDate'] = datetime.now()
            data_dict['CreateDate'] = datetime.now()
            data_dict['RowPointer'] = str(uuid.uuid4()).upper()
            VRALocalizacion.objects.create(**data_dict)

        with transaction.atomic(using='default'):
            loc_new = VRALocalizacion.objects.get(LOCALIZACION=data_dict['LOCALIZACION'])
            loc_new_dict = model_to_dict(loc_new)
            Localizacion.objects.create(**loc_new_dict)

    except Exception as e:
        raise e
    finally:
        for query in connections['mssql_db'].queries:
            logger.info(query['sql'])

def create_inter_inv_stock_transfer(data_dict, user='SA'):
    """
    Crea una transferencia de inventario entre bodegas tanto en la base de datos MSSQL como en PostgreSQL de manera
    atómica.
    Si alguna de las operaciones falla, se revierte toda la transacción para mantener la integridad de los datos.
    :param data_dict:
    :param user:
    :return:
    """
    try:
        doc_exists = VRADocumentoInv.objects.filter(DOCUMENTO_INV=data_dict['DOCUMENTO_INV']).exists()
        if doc_exists:
            raise IntegrityError(f"El documento de inventario {data_dict['DOCUMENTO_INV']} ya existe.")
        current_time = datetime.now()
        doc_inv = None
        audit_inv = None
        lineas = data_dict.pop('lineas', [])
        index = int(data_dict['DOCUMENTO_INV'][3:])
        siguiente = index + 1
        data_dict['SIGUIENTE_CONSEC'] = f"TR-{siguiente:05d}"
        with transaction.atomic(using='mssql_db'):
            VRAConsecutivoCi.objects.filter(CONSECUTIVO='TRASPASO').update(
                SIGUIENTE_CONSEC=data_dict['SIGUIENTE_CONSEC'],
                ULTIMO_USUARIO=user,
                ULT_FECHA_HORA=current_time,
            )
            doc_inv = VRADocumentoInv.objects.create(
                REFERENCIA=data_dict['REFERENCIA'],
                USUARIO=user,
                FECHA_DOCUMENTO=data_dict['FECHA_DOCUMENTO'],
                SELECCIONADO=data_dict['SELECCIONADO'],
                CONSECUTIVO=data_dict['CONSECUTIVO'],
                PAQUETE_INVENTARIO=data_dict['PAQUETE_INVENTARIO'],
                DOCUMENTO_INV=data_dict['DOCUMENTO_INV'],
                FECHA_HOR_CREACION=current_time,  # erpadmin.Sf_getdate()
                MENSAJE_SISTEMA='',
                APROBADO=None,
                RecordDate=current_time,
                CreateDate=current_time,
                RowPointer=str(uuid.uuid4()).upper(),
                NoteExistsFlag=False,
            )
            audit_inv = VRAAuditTransInv.objects.create(
                REFERENCIA='Reservación automática de Documentos por Paquete',
                CONSECUTIVO=data_dict['CONSECUTIVO'],
                APLICACION=data_dict['DOCUMENTO_INV'],
                ASIENTO=None,
                PAQUETE_INVENTARIO=None,
                MODULO_ORIGEN='CI',
                USUARIO=user,
                FECHA_HORA=current_time,
                RecordDate=current_time,
                CreateDate=current_time,
                RowPointer=str(uuid.uuid4()).upper(),
                NoteExistsFlag=False,
            )
            for linea in lineas:
                VRAExistenciaBodega.objects.filter(
                    BODEGA=linea['BODEGA'],
                    ARTICULO=linea['ARTICULO'],
                ).update(
                    CANT_DISPONIBLE=F('CANT_DISPONIBLE') - linea['CANTIDAD'],
                    CANT_RESERVADA=F('CANT_RESERVADA') + linea['CANTIDAD'],
                )
                VRAExistenciaLote.objects.filter(
                    BODEGA=linea['BODEGA'],
                    ARTICULO=linea['ARTICULO'],
                    LOTE='ND',
                    LOCALIZACION=linea['LOCALIZACION'],
                ).update(
                    CANT_DISPONIBLE=F('CANT_DISPONIBLE') - linea['CANTIDAD'],
                    CANT_RESERVADA=F('CANT_RESERVADA') + linea['CANTIDAD'],
                )
                VRAExistenciaReserva.objects.create(
                    ARTICULO=linea['ARTICULO'],
                    BODEGA=linea['BODEGA'],
                    LOTE='ND',
                    LOCALIZACION=linea['LOCALIZACION'],
                    APLICACION=data_dict['DOCUMENTO_INV'],
                    CANTIDAD=linea['CANTIDAD'],
                    MODULO_ORIGEN='CI',
                    FECHA_HORA=current_time,
                    USUARIO=user,
                    SERIE_CADENA=None,
                    RecordDate=current_time,
                    CreateDate=current_time,
                    RowPointer=str(uuid.uuid4()).upper(),
                    NoteExistsFlag=False,
                )
                articulo = VRAArticulo.objects.filter(ARTICULO=linea['ARTICULO']).first()
                if articulo.ULTIMO_MOVIMIENTO < current_time:
                    articulo.ULTIMO_MOVIMIENTO = current_time
                    articulo.save(update_fields=['ULTIMO_MOVIMIENTO'])
                VRATransaccionInv.objects.create(
                    AUDIT_TRANS_INV=audit_inv.AUDIT_TRANS_INV,
                    CONSECUTIVO=linea['LINEA'],
                    ARTICULO=linea['ARTICULO'],
                    BODEGA=linea['BODEGA'],
                    LOCALIZACION=linea['LOCALIZACION'],
                    LOTE=None,
                    TIPO='R',
                    SUBTIPO=' ',
                    SUBSUBTIPO=' ',
                    NATURALEZA='S',
                    CANTIDAD=linea['CANTIDAD'],
                    COSTO_TOT_FISC_LOC=float(articulo.COSTO_ULT_LOC) * float(linea['CANTIDAD']),
                    #COSTO_ULT_LOC from VRA.ARTICULO
                    COSTO_TOT_FISC_DOL=float(articulo.COSTO_ULT_DOL) * float(linea['CANTIDAD']),
                    #COSTO_ULT_DOL from VRA.ARTICULO
                    COSTO_TOT_COMP_LOC=float(articulo.COSTO_PROM_LOC) * float(linea['CANTIDAD']),
                    #COSTO_PROM_LOC from VRA.ARTICULO
                    COSTO_TOT_COMP_DOL=float(articulo.COSTO_PROM_DOL) * float(linea['CANTIDAD']),
                    #COSTO_PROM_DOL from VRA.ARTICULO
                    PRECIO_TOTAL_LOCAL=float(articulo.PRECIO_BASE_LOCAL) * float(linea['CANTIDAD']),
                    PRECIO_TOTAL_DOLAR=float(articulo.PRECIO_BASE_DOLAR) * float(linea['CANTIDAD']),
                    CONTABILIZADA='N',
                    FECHA=data_dict['FECHA_DOCUMENTO'],
                    CENTRO_COSTO=None,
                    AJUSTE_CONFIG='~RR~',
                    SERIE_CADENA=None,
                    NIT=None,
                    UNIDAD_DISTRIBUCIO=None,
                    CUENTA_CONTABLE=None,
                    TIPO_OPERACION=None,
                    TIPO_PAGO=None,
                    GEN_DOC_ELE=None,
                    FECHA_HORA_TRANSAC=current_time,  # erpadmin.Sf_getdate()
                    RecordDate=current_time,
                    CreateDate=current_time,
                    RowPointer=str(uuid.uuid4()).upper(),
                    NoteExistsFlag=False,
                )
                VRALineaDocInv.objects.create(
                    ARTICULO=linea['ARTICULO'],
                    BODEGA=linea['BODEGA'],
                    LOCALIZACION=linea['LOCALIZACION'],
                    LOCALIZACION_DEST=linea['LOCALIZACION_DEST'],
                    LOTE=None,
                    TIPO='T',
                    SUBTIPO='R',
                    SUBSUBTIPO=' ',  # empty string means not NULL
                    CANTIDAD=linea['CANTIDAD'],
                    COSTO_TOTAL_LOCAL=0,
                    COSTO_TOTAL_DOLAR=0,
                    COSTO_TOTAL_LOCAL_COMP=0,
                    COSTO_TOTAL_DOLAR_COMP=0,
                    PRECIO_TOTAL_LOCAL=0,
                    PRECIO_TOTAL_DOLAR=0,
                    BODEGA_DESTINO=linea['BODEGA_DESTINO'],
                    CENTRO_COSTO=None,
                    AJUSTE_CONFIG='~TT~',
                    SECUENCIA=None,
                    CUENTA_CONTABLE=None,
                    TIPO_OPERACION=None,
                    TIPO_PAGO=None,
                    GEN_DOC_ELE=None,
                    SERIE_CADENA=None,
                    UNIDAD_DISTRIBUCIO=None,
                    PAQUETE_INVENTARIO=data_dict['PAQUETE_INVENTARIO'],
                    DOCUMENTO_INV=data_dict['DOCUMENTO_INV'],
                    LINEA_DOC_INV=linea['LINEA'],
                    RecordDate=current_time,
                    CreateDate=current_time,
                    RowPointer=str(uuid.uuid4()).upper(),
                    NoteExistsFlag=False,
                )
        with transaction.atomic(using='default'):
            ConsecutivoCi.objects.filter(CONSECUTIVO='TRASPASO').update(
                SIGUIENTE_CONSEC=data_dict['SIGUIENTE_CONSEC'],
                ULTIMO_USUARIO=user,
                ULT_FECHA_HORA=current_time,
            )
            doc_inv_new_dict = model_to_dict(doc_inv)
            DocumentoInv.objects.create(**doc_inv_new_dict)
            audit_dict = model_to_dict(audit_inv)
            AuditTransInv.objects.create(**audit_dict)
            trans_lineas = VRATransaccionInv.objects.filter(AUDIT_TRANS_INV=audit_inv.AUDIT_TRANS_INV)
            docs_lineas = VRALineaDocInv.objects.filter(DOCUMENTO_INV=data_dict['DOCUMENTO_INV'])
            ext_lineas = VRAExistenciaReserva.objects.filter(APLICACION=data_dict['DOCUMENTO_INV'])
            for linea in ext_lineas:
                line_item = model_to_dict(linea)
                ExistenciaBodega.objects.filter(
                    BODEGA=line_item['BODEGA'],
                    ARTICULO=line_item['ARTICULO'],
                ).update(
                    CANT_DISPONIBLE=F('CANT_DISPONIBLE') - line_item['CANTIDAD'],
                    CANT_RESERVADA=F('CANT_RESERVADA') + line_item['CANTIDAD'],
                )
                ExistenciaLote.objects.filter(
                    BODEGA=line_item['BODEGA'],
                    ARTICULO=line_item['ARTICULO'],
                    LOTE='ND',
                    LOCALIZACION=line_item['LOCALIZACION'],
                ).update(
                    CANT_DISPONIBLE=F('CANT_DISPONIBLE') - line_item['CANTIDAD'],
                    CANT_RESERVADA=F('CANT_RESERVADA') + line_item['CANTIDAD'],
                )
                ExistenciaReserva.objects.create(**line_item)
                articulo = Articulo.objects.filter(ARTICULO=linea.ARTICULO).first()
                if articulo:
                    articulo.ULTIMO_MOVIMIENTO = current_time
                    articulo.save(update_fields=['ULTIMO_MOVIMIENTO'])
            for linea in docs_lineas:
                line_item = model_to_dict(linea)
                LineaDocInv.objects.create(**line_item)
            for linea in trans_lineas:
                line_item = model_to_dict(linea)
                TransaccionInv.objects.create(**line_item)
        wm_role = Role.objects.filter(code='warehouse-manager').first()
        admin_role = Role.objects.filter(code='admin').first()
        users_to_notify = set()
        if wm_role:
            users_to_notify.update(wm_role.users.all())
        if admin_role:
            users_to_notify.update(admin_role.users.all())
        send_new_stocktransfer_alert([doc_inv], users_to_notify)
    except Exception as e:
        raise e
    finally:
        for query in connections['mssql_db'].queries:
            logger.info(query['sql'])

def update_inter_inv_stock_transfer(documento_inv, data_dict, user='SA'):
    """
    Actualiza una transferencia de inventario entre bodegas tanto en la base de datos MSSQL como en PostgreSQL de
    manera atómica.
    Si alguna de las operaciones falla, se revierte toda la transacción para mantener la integridad de los datos.
    :param documento_inv:
    :param data_dict:
    :param user:
    :return:
    """
    try:
        current_time = datetime.now()
        lineas = data_dict.pop('lineas', [])
        with (transaction.atomic(using='mssql_db')):
            VRADocumentoInv.objects.filter(DOCUMENTO_INV=documento_inv).update(
                REFERENCIA=data_dict['REFERENCIA'],
                RecordDate=current_time,
            )
            audit = VRAAuditTransInv.objects.filter(APLICACION=documento_inv).first()
            lineas_doc_inv = VRALineaDocInv.objects.filter(DOCUMENTO_INV=documento_inv)
            for linea in lineas:
                linea_existente = lineas_doc_inv.filter(
                    LINEA_DOC_INV=linea['LINEA'],
                    ARTICULO=linea['ARTICULO'],
                    BODEGA=linea['BODEGA'],
                    LOCALIZACION=linea['LOCALIZACION']
                ).first()
                if linea_existente:
                    cantidad_anterior = linea_existente.CANTIDAD
                    VRALineaDocInv.objects.filter(
                        DOCUMENTO_INV=documento_inv,
                        LINEA_DOC_INV=linea['LINEA'],
                        ARTICULO=linea['ARTICULO'],
                        BODEGA=linea['BODEGA'],
                        LOCALIZACION=linea['LOCALIZACION'],
                    ).update(
                        LOCALIZACION_DEST=linea['LOCALIZACION_DEST'],
                        CANTIDAD=linea['CANTIDAD'],
                        BODEGA_DESTINO=linea['BODEGA_DESTINO'],
                        RecordDate=current_time,
                    )
                    VRATransaccionInv.objects.filter(
                        AUDIT_TRANS_INV=audit.AUDIT_TRANS_INV,
                        CONSECUTIVO=linea['LINEA'],
                        ARTICULO=linea['ARTICULO'],
                        BODEGA=linea['BODEGA'],
                        LOCALIZACION=linea['LOCALIZACION'],
                    ).update(
                        CANTIDAD=linea['CANTIDAD'],
                        RecordDate=current_time,
                    )
                    diferencia_cantidad = linea['CANTIDAD'] - cantidad_anterior
                    VRAExistenciaBodega.objects.filter(
                        BODEGA=linea['BODEGA'],
                        ARTICULO=linea['ARTICULO'],
                    ).update(
                        CANT_DISPONIBLE=F('CANT_DISPONIBLE') - diferencia_cantidad,
                        CANT_RESERVADA=F('CANT_RESERVADA') + diferencia_cantidad,
                    )
                    VRAExistenciaLote.objects.filter(
                        BODEGA=linea['BODEGA'],
                        ARTICULO=linea['ARTICULO'],
                        LOTE='ND',
                        LOCALIZACION=linea['LOCALIZACION'],
                    ).update(
                        CANT_DISPONIBLE=F('CANT_DISPONIBLE') - diferencia_cantidad,
                        CANT_RESERVADA=F('CANT_RESERVADA') + diferencia_cantidad,
                    )
                    VRAExistenciaReserva.objects.filter(
                        ARTICULO=linea['ARTICULO'],
                        BODEGA=linea['BODEGA'],
                        LOTE='ND',
                        LOCALIZACION=linea['LOCALIZACION'],
                        APLICACION=documento_inv,
                    ).update(
                        CANTIDAD=linea['CANTIDAD'],
                        FECHA_HORA=current_time,
                        USUARIO=user,
                        RecordDate=current_time,
                    )
                else:
                    linea_existente = lineas_doc_inv.filter(
                        LINEA_DOC_INV=linea['LINEA']
                    ).first()
                    VRAExistenciaBodega.objects.filter(
                        BODEGA=linea_existente.BODEGA,
                        ARTICULO=linea_existente.ARTICULO,
                    ).update(
                        CANT_DISPONIBLE=F('CANT_DISPONIBLE') + linea_existente.CANTIDAD,
                        CANT_RESERVADA=F('CANT_RESERVADA') - linea_existente.CANTIDAD,
                    )
                    VRAExistenciaLote.objects.filter(
                        BODEGA=linea_existente.BODEGA,
                        ARTICULO=linea_existente.ARTICULO,
                        LOTE='ND',
                        LOCALIZACION=linea_existente.LOCALIZACION,
                    ).update(
                        CANT_DISPONIBLE=F('CANT_DISPONIBLE') + linea_existente.CANTIDAD,
                        CANT_RESERVADA=F('CANT_RESERVADA') - linea_existente.CANTIDAD,
                    )
                    VRAExistenciaReserva.objects.filter(
                        BODEGA=linea_existente.BODEGA,
                        ARTICULO=linea_existente.ARTICULO,
                        LOTE='ND',
                        LOCALIZACION=linea_existente.LOCALIZACION,
                        APLICACION=documento_inv,
                    ).delete()
                    VRATransaccionInv.objects.filter(
                        AuditTransInv=audit.AUDIT_TRANS_INV,
                        CONSECUTIVO=linea_existente.LINEA_DOC_INV,
                        ARTICULO=linea_existente.ARTICULO,
                        BODEGA=linea_existente.BODEGA,
                        LOCALIZACION=linea_existente.LOCALIZACION,
                    ).delete()
                    linea_existente.delete()
                    articulo = VRAArticulo.objects.filter(ARTICULO=linea['ARTICULO']).first()
                    if articulo and articulo.ULTIMO_MOVIMIENTO < current_time:
                        articulo.ULTIMO_MOVIMIENTO = current_time
                        articulo.save(update_fields=['ULTIMO_MOVIMIENTO'])
                    VRATransaccionInv.objects.create(
                        AUDIT_TRANS_INV=audit.AUDIT_TRANS_INV,
                        CONSECUTIVO=linea['LINEA'],
                        ARTICULO=linea['ARTICULO'],
                        BODEGA=linea['BODEGA'],
                        LOCALIZACION=linea['LOCALIZACION'],
                        LOTE=None,
                        TIPO='R',
                        SUBTIPO=' ',
                        SUBSUBTIPO=' ',
                        NATURALEZA='S',
                        CANTIDAD=linea['CANTIDAD'],
                        COSTO_TOT_FISC_LOC=articulo.COSTO_ULT_LOC * linea['CANTIDAD'],
                        # COSTO_ULT_LOC from VRA.ARTICULO
                        COSTO_TOT_FISC_DOL=articulo.COSTO_ULT_DOL * linea['CANTIDAD'],
                        # COSTO_ULT_DOL from VRA.ARTICULO
                        COSTO_TOT_COMP_LOC=articulo.COSTO_PROM_LOC * linea['CANTIDAD'],
                        # COSTO_PROM_LOC from VRA.ARTICULO
                        COSTO_TOT_COMP_DOL=articulo.COSTO_PROM_DOL * linea['CANTIDAD'],
                        # COSTO_PROM_DOL from VRA.ARTICULO
                        PRECIO_TOTAL_LOCAL=articulo.PRECIO_BASE_LOCAL * linea['CANTIDAD'],
                        PRECIO_TOTAL_DOLAR=articulo.PRECIO_BASE_DOLAR * linea['CANTIDAD'],
                        CONTABILIZADA='N',
                        FECHA=data_dict['FECHA_DOCUMENTO'],
                        CENTRO_COSTO=None,
                        AJUSTE_CONFIG='~RR~',
                        SERIE_CADENA=None,
                        NIT=None,
                        UNIDAD_DISTRIBUCIO=None,
                        CUENTA_CONTABLE=None,
                        TIPO_OPERACION=None,
                        TIPO_PAGO=None,
                        GEN_DOC_ELE=None,
                        FECHA_HORA_TRANSAC=current_time,  # erpadmin.Sf_getdate()
                        RecordDate=current_time,
                        CreateDate=current_time,
                        RowPointer=str(uuid.uuid4()).upper(),
                        NoteExistsFlag=False,
                    )
                    VRALineaDocInv.objects.create(
                        ARTICULO=linea['ARTICULO'],
                        BODEGA=linea['BODEGA'],
                        LOCALIZACION=linea['LOCALIZACION'],
                        LOCALIZACION_DEST=linea['LOCALIZACION_DEST'],
                        LOTE=None,
                        TIPO='T',
                        SUBTIPO='R',
                        SUBSUBTIPO=' ',  # empty string means not NULL
                        CANTIDAD=linea['CANTIDAD'],
                        COSTO_TOTAL_LOCAL=0,
                        COSTO_TOTAL_DOLAR=0,
                        COSTO_TOTAL_LOCAL_COMP=0,
                        COSTO_TOTAL_DOLAR_COMP=0,
                        PRECIO_TOTAL_LOCAL=0,
                        PRECIO_TOTAL_DOLAR=0,
                        BODEGA_DESTINO=linea['BODEGA_DESTINO'],
                        CENTRO_COSTO=None,
                        AJUSTE_CONFIG='~TT~',
                        SECUENCIA=None,
                        CUENTA_CONTABLE=None,
                        TIPO_OPERACION=None,
                        TIPO_PAGO=None,
                        GEN_DOC_ELE=None,
                        SERIE_CADENA=None,
                        UNIDAD_DISTRIBUCIO=None,
                        PAQUETE_INVENTARIO=data_dict['PAQUETE_INVENTARIO'],
                        DOCUMENTO_INV=documento_inv,
                        LINEA_DOC_INV=linea['LINEA'],
                        RecordDate=current_time,
                        CreateDate=current_time,
                        RowPointer=str(uuid.uuid4()).upper(),
                        NoteExistsFlag=False,
                    )
                    VRAExistenciaBodega.objects.filter(
                        BODEGA=linea['BODEGA'],
                        ARTICULO=linea['ARTICULO'],
                    ).update(
                        CANT_DISPONIBLE=F('CANT_DISPONIBLE') - linea['CANTIDAD'],
                        CANT_RESERVADA=F('CANT_RESERVADA') + linea['CANTIDAD'],
                    )
                    VRAExistenciaLote.objects.filter(
                        BODEGA=linea['BODEGA'],
                        ARTICULO=linea['ARTICULO'],
                        LOTE='ND',
                        LOCALIZACION=linea['LOCALIZACION'],
                    ).update(
                        CANT_DISPONIBLE=F('CANT_DISPONIBLE') - linea['CANTIDAD'],
                        CANT_RESERVADA=F('CANT_RESERVADA') + linea['CANTIDAD'],
                    )
                    VRAExistenciaReserva.objects.create(
                        ARTICULO=linea['ARTICULO'],
                        BODEGA=linea['BODEGA'],
                        LOTE='ND',
                        LOCALIZACION=linea['LOCALIZACION'],
                        APLICACION=data_dict['DOCUMENTO_INV'],
                        CANTIDAD=linea['CANTIDAD'],
                        MODULO_ORIGEN='CI',
                        FECHA_HORA=current_time,
                        USUARIO=user,
                        SERIE_CADENA=None,
                        RecordDate=current_time,
                        CreateDate=current_time,
                        RowPointer=str(uuid.uuid4()).upper(),
                        NoteExistsFlag=False,
                    )
        with (transaction.atomic(using='default')):
            DocumentoInv.objects.filter(DOCUMENTO_INV=documento_inv).update(
                REFERENCIA=data_dict['REFERENCIA'],
                RecordDate=current_time,
            )
            audit = AuditTransInv.objects.filter(APLICACION=documento_inv).first()
            lineas_doc_inv = LineaDocInv.objects.filter(DOCUMENTO_INV=documento_inv)
            for linea in lineas:
                linea_existente = lineas_doc_inv.filter(
                    LINEA_DOC_INV=linea['LINEA'],
                    ARTICULO=linea['ARTICULO'],
                    BODEGA=linea['BODEGA'],
                    LOCALIZACION=linea['LOCALIZACION']
                ).first()
                if linea_existente:
                    cantidad_anterior = linea_existente.CANTIDAD
                    LineaDocInv.objects.filter(
                        DOCUMENTO_INV=documento_inv,
                        LINEA_DOC_INV=linea['LINEA'],
                        ARTICULO=linea['ARTICULO'],
                        BODEGA=linea['BODEGA'],
                        LOCALIZACION=linea['LOCALIZACION'],
                    ).update(
                        LOCALIZACION_DEST=linea['LOCALIZACION_DEST'],
                        CANTIDAD=linea['CANTIDAD'],
                        BODEGA_DESTINO=linea['BODEGA_DESTINO'],
                        RecordDate=current_time,
                    )
                    TransaccionInv.objects.filter(
                        AUDIT_TRANS_INV=audit.AUDIT_TRANS_INV,
                        CONSECUTIVO=linea['LINEA'],
                        ARTICULO=linea['ARTICULO'],
                        BODEGA=linea['BODEGA'],
                        LOCALIZACION=linea['LOCALIZACION'],
                    ).update(
                        CANTIDAD=linea['CANTIDAD'],
                        RecordDate=current_time,
                    )
                    diferencia_cantidad = linea['CANTIDAD'] - cantidad_anterior
                    ExistenciaBodega.objects.filter(
                        BODEGA=linea['BODEGA'],
                        ARTICULO=linea['ARTICULO'],
                    ).update(
                        CANT_DISPONIBLE=F('CANT_DISPONIBLE') - diferencia_cantidad,
                        CANT_RESERVADA=F('CANT_RESERVADA') + diferencia_cantidad,
                    )
                    ExistenciaLote.objects.filter(
                        BODEGA=linea['BODEGA'],
                        ARTICULO=linea['ARTICULO'],
                        LOTE='ND',
                        LOCALIZACION=linea['LOCALIZACION'],
                    ).update(
                        CANT_DISPONIBLE=F('CANT_DISPONIBLE') - diferencia_cantidad,
                        CANT_RESERVADA=F('CANT_RESERVADA') + diferencia_cantidad,
                    )
                    ExistenciaReserva.objects.filter(
                        ARTICULO=linea['ARTICULO'],
                        BODEGA=linea['BODEGA'],
                        LOTE='ND',
                        LOCALIZACION=linea['LOCALIZACION'],
                        APLICACION=documento_inv,
                    ).update(
                        CANTIDAD=linea['CANTIDAD'],
                        FECHA_HORA=current_time,
                        USUARIO=user,
                        RecordDate=current_time,
                    )
                else:
                    linea_existente = lineas_doc_inv.filter(
                        LINEA_DOC_INV=linea['LINEA']
                    ).first()
                    ExistenciaBodega.objects.filter(
                        BODEGA=linea_existente.BODEGA,
                        ARTICULO=linea_existente.ARTICULO,
                    ).update(
                        CANT_DISPONIBLE=F('CANT_DISPONIBLE') + linea_existente.CANTIDAD,
                        CANT_RESERVADA=F('CANT_RESERVADA') - linea_existente.CANTIDAD,
                    )
                    ExistenciaLote.objects.filter(
                        BODEGA=linea_existente.BODEGA,
                        ARTICULO=linea_existente.ARTICULO,
                        LOTE='ND',
                        LOCALIZACION=linea_existente.LOCALIZACION,
                    ).update(
                        CANT_DISPONIBLE=F('CANT_DISPONIBLE') + linea_existente.CANTIDAD,
                        CANT_RESERVADA=F('CANT_RESERVADA') - linea_existente.CANTIDAD,
                    )
                    ExistenciaReserva.objects.filter(
                        BODEGA=linea_existente.BODEGA,
                        ARTICULO=linea_existente.ARTICULO,
                        LOTE='ND',
                        LOCALIZACION=linea_existente.LOCALIZACION,
                        APLICACION=documento_inv,
                    ).delete()
                    TransaccionInv.objects.filter(
                        AuditTransInv=audit.AUDIT_TRANS_INV,
                        CONSECUTIVO=linea_existente.LINEA_DOC_INV,
                        ARTICULO=linea_existente.ARTICULO,
                        BODEGA=linea_existente.BODEGA,
                        LOCALIZACION=linea_existente.LOCALIZACION,
                    ).delete()
                    linea_existente.delete()
                    articulo = VRAArticulo.objects.filter(ARTICULO=linea['ARTICULO']).first()
                    if articulo and articulo.ULTIMO_MOVIMIENTO < current_time:
                        articulo.ULTIMO_MOVIMIENTO = current_time
                        articulo.save(update_fields=['ULTIMO_MOVIMIENTO'])
                    TransaccionInv.objects.create(
                        AUDIT_TRANS_INV=audit.AUDIT_TRANS_INV,
                        CONSECUTIVO=linea['LINEA'],
                        ARTICULO=linea['ARTICULO'],
                        BODEGA=linea['BODEGA'],
                        LOCALIZACION=linea['LOCALIZACION'],
                        LOTE=None,
                        TIPO='R',
                        SUBTIPO=' ',
                        SUBSUBTIPO=' ',
                        NATURALEZA='S',
                        CANTIDAD=linea['CANTIDAD'],
                        COSTO_TOT_FISC_LOC=articulo.COSTO_ULT_LOC * linea['CANTIDAD'],
                        # COSTO_ULT_LOC from ARTICULO
                        COSTO_TOT_FISC_DOL=articulo.COSTO_ULT_DOL * linea['CANTIDAD'],
                        # COSTO_ULT_DOL from ARTICULO
                        COSTO_TOT_COMP_LOC=articulo.COSTO_PROM_LOC * linea['CANTIDAD'],
                        # COSTO_PROM_LOC from ARTICULO
                        COSTO_TOT_COMP_DOL=articulo.COSTO_PROM_DOL * linea['CANTIDAD'],
                        # COSTO_PROM_DOL from ARTICULO
                        PRECIO_TOTAL_LOCAL=articulo.PRECIO_BASE_LOCAL * linea['CANTIDAD'],
                        PRECIO_TOTAL_DOLAR=articulo.PRECIO_BASE_DOLAR * linea['CANTIDAD'],
                        CONTABILIZADA='N',
                        FECHA=data_dict['FECHA_DOCUMENTO'],
                        CENTRO_COSTO=None,
                        AJUSTE_CONFIG='~RR~',
                        SERIE_CADENA=None,
                        NIT=None,
                        UNIDAD_DISTRIBUCIO=None,
                        CUENTA_CONTABLE=None,
                        TIPO_OPERACION=None,
                        TIPO_PAGO=None,
                        GEN_DOC_ELE=None,
                        FECHA_HORA_TRANSAC=current_time,  # erpadmin.Sf_getdate()
                        RecordDate=current_time,
                        CreateDate=current_time,
                        RowPointer=str(uuid.uuid4()).upper(),
                        NoteExistsFlag=False,
                    )
                    LineaDocInv.objects.create(
                        ARTICULO=linea['ARTICULO'],
                        BODEGA=linea['BODEGA'],
                        LOCALIZACION=linea['LOCALIZACION'],
                        LOCALIZACION_DEST=linea['LOCALIZACION_DEST'],
                        LOTE=None,
                        TIPO='T',
                        SUBTIPO='R',
                        SUBSUBTIPO=' ',  # empty string means not NULL
                        CANTIDAD=linea['CANTIDAD'],
                        COSTO_TOTAL_LOCAL=0,
                        COSTO_TOTAL_DOLAR=0,
                        COSTO_TOTAL_LOCAL_COMP=0,
                        COSTO_TOTAL_DOLAR_COMP=0,
                        PRECIO_TOTAL_LOCAL=0,
                        PRECIO_TOTAL_DOLAR=0,
                        BODEGA_DESTINO=linea['BODEGA_DESTINO'],
                        CENTRO_COSTO=None,
                        AJUSTE_CONFIG='~TT~',
                        SECUENCIA=None,
                        CUENTA_CONTABLE=None,
                        TIPO_OPERACION=None,
                        TIPO_PAGO=None,
                        GEN_DOC_ELE=None,
                        SERIE_CADENA=None,
                        UNIDAD_DISTRIBUCIO=None,
                        PAQUETE_INVENTARIO=data_dict['PAQUETE_INVENTARIO'],
                        DOCUMENTO_INV=documento_inv,
                        LINEA_DOC_INV=linea['LINEA'],
                        RecordDate=current_time,
                        CreateDate=current_time,
                        RowPointer=str(uuid.uuid4()).upper(),
                        NoteExistsFlag=False,
                    )
                    ExistenciaBodega.objects.filter(
                        BODEGA=linea['BODEGA'],
                        ARTICULO=linea['ARTICULO'],
                    ).update(
                        CANT_DISPONIBLE=F('CANT_DISPONIBLE') - linea['CANTIDAD'],
                        CANT_RESERVADA=F('CANT_RESERVADA') + linea['CANTIDAD'],
                    )
                    ExistenciaLote.objects.filter(
                        BODEGA=linea['BODEGA'],
                        ARTICULO=linea['ARTICULO'],
                        LOTE='ND',
                        LOCALIZACION=linea['LOCALIZACION'],
                    ).update(
                        CANT_DISPONIBLE=F('CANT_DISPONIBLE') - linea['CANTIDAD'],
                        CANT_RESERVADA=F('CANT_RESERVADA') + linea['CANTIDAD'],
                    )
                    ExistenciaReserva.objects.create(
                        ARTICULO=linea['ARTICULO'],
                        BODEGA=linea['BODEGA'],
                        LOTE='ND',
                        LOCALIZACION=linea['LOCALIZACION'],
                        APLICACION=data_dict['DOCUMENTO_INV'],
                        CANTIDAD=linea['CANTIDAD'],
                        MODULO_ORIGEN='CI',
                        FECHA_HORA=current_time,
                        USUARIO=user,
                        SERIE_CADENA=None,
                        RecordDate=current_time,
                        CreateDate=current_time,
                        RowPointer=str(uuid.uuid4()).upper(),
                        NoteExistsFlag=False,
                    )
    except Exception as e:
        raise e

def cancel_inter_inv_stock_transfer(documento_inv, user='SA'):
    """
    Cancela una transferencia de inventario entre bodegas tanto en la base de datos MSSQL como en PostgreSQL de
    manera atómica.
    Si alguna de las operaciones falla, se revierte toda la transacción para mantener la integridad de los datos.
    :param documento_inv:
    :param user:
    :return:
    """
    try:
        current_time = datetime.now()
        doc_inv = VRADocumentoInv.objects.filter(DOCUMENTO_INV=documento_inv).first()
        paquete_inv = doc_inv.PAQUETE_INVENTARIO
        doc_inv_lineas = VRALineaDocInv.objects.filter(DOCUMENTO_INV=documento_inv, PAQUETE_INVENTARIO=paquete_inv)
        audit_inv = None
        if not doc_inv or not doc_inv_lineas.exists():
            raise ValueError(f"El documento de inventario {documento_inv} no existe o no tiene líneas asociadas.")
        with transaction.atomic(using='mssql_db'):
            audit_inv = VRAAuditTransInv.objects.create(
                REFERENCIA='DesReservación automática de Documentos por Paquete',
                CONSECUTIVO='TRASPASO',
                APLICACION=documento_inv,
                ASIENTO=None,
                PAQUETE_INVENTARIO=None,
                MODULO_ORIGEN='CI',
                USUARIO=user,
                FECHA_HORA=current_time,
                RecordDate=current_time,
                CreateDate=current_time,
                RowPointer=str(uuid.uuid4()).upper(),
                NoteExistsFlag=False,
            )
            for linea in doc_inv_lineas:
                articulo = VRAArticulo.objects.filter(ARTICULO=linea.ARTICULO).first()
                if articulo and articulo.ULTIMO_MOVIMIENTO < current_time:
                    articulo.ULTIMO_MOVIMIENTO = current_time
                    articulo.save(update_fields=['ULTIMO_MOVIMIENTO'])
                VRATransaccionInv.objects.create(
                    AUDIT_TRANS_INV=audit_inv.AUDIT_TRANS_INV,
                    CONSECUTIVO=linea.LINEA_DOC_INV,
                    ARTICULO=linea.ARTICULO,
                    BODEGA=linea.BODEGA,
                    LOCALIZACION=linea.LOCALIZACION,
                    LOTE=None,
                    TIPO='R',
                    SUBTIPO=' ',
                    SUBSUBTIPO=' ',  # empty string means not NULL
                    NATURALEZA='E',
                    CANTIDAD=0 - linea.CANTIDAD,
                    COSTO_TOT_FISC_LOC=articulo.COSTO_ULT_LOC * linea.CANTIDAD,  #COSTO_ULT_LOC from VRA.ARTICULO
                    COSTO_TOT_FISC_DOL=articulo.COSTO_ULT_DOL * linea.CANTIDAD,  #COSTO_ULT_DOL from VRA.ARTICULO
                    COSTO_TOT_COMP_LOC=articulo.COSTO_PROM_LOC * linea.CANTIDAD,  #COSTO_PROM_LOC from VRA.ARTICULO
                    COSTO_TOT_COMP_DOL=articulo.COSTO_PROM_DOL * linea.CANTIDAD,  #COSTO_PROM_DOL from VRA.ARTICULO
                    PRECIO_TOTAL_LOCAL=articulo.PRECIO_BASE_LOCAL * linea.CANTIDAD,
                    PRECIO_TOTAL_DOLAR=articulo.PRECIO_BASE_DOLAR * linea.CANTIDAD,
                    CONTABILIZADA='N',
                    FECHA=current_time,
                    CENTRO_COSTO=None,
                    AJUSTE_CONFIG='~RR~',
                    SERIE_CADENA=None,
                    NIT=None,
                    UNIDAD_DISTRIBUCIO=None,
                    CUENTA_CONTABLE=None,
                    TIPO_OPERACION=None,
                    TIPO_PAGO=None,
                    GEN_DOC_ELE=None,
                    FECHA_HORA_TRANSAC=current_time,
                    RecordDate=current_time,
                    CreateDate=current_time,
                    RowPointer=str(uuid.uuid4()).upper(),
                    NoteExistsFlag=False,
                )
                VRAExistenciaBodega.objects.filter(
                    BODEGA=linea.BODEGA,
                    ARTICULO=linea.ARTICULO,
                ).update(
                    CANT_DISPONIBLE=F('CANT_DISPONIBLE') + linea.CANTIDAD,
                    CANT_RESERVADA=F('CANT_RESERVADA') - linea.CANTIDAD,
                )
                VRAExistenciaLote.objects.filter(
                    BODEGA=linea.BODEGA,
                    ARTICULO=linea.ARTICULO,
                    LOTE='ND',
                    LOCALIZACION=linea.LOCALIZACION,
                ).update(
                    CANT_DISPONIBLE=F('CANT_DISPONIBLE') + linea.CANTIDAD,
                    CANT_RESERVADA=F('CANT_RESERVADA') - linea.CANTIDAD,
                )
                VRAExistenciaReserva.objects.filter(
                    ARTICULO=linea.ARTICULO,
                    BODEGA=linea.BODEGA,
                    LOTE='ND',
                    LOCALIZACION=linea.LOCALIZACION,
                    APLICACION=documento_inv,
                ).delete()
            VRALineaDocInv.objects.filter(
                DOCUMENTO_INV=documento_inv,
                PAQUETE_INVENTARIO=paquete_inv
            ).delete()
            VRADocumentoInv.objects.filter(
                DOCUMENTO_INV=documento_inv,
                PAQUETE_INVENTARIO=paquete_inv
            ).delete()
        with transaction.atomic(using='default'):
            audit_dict = model_to_dict(audit_inv)
            audit_inv = AuditTransInv.objects.create(**audit_dict)
            desres_lineas = VRATransaccionInv.objects.filter(AUDIT_TRANS_INV=audit_inv.AUDIT_TRANS_INV)
            doc_inv_lineas = LineaDocInv.objects.filter(DOCUMENTO_INV=documento_inv, PAQUETE_INVENTARIO=paquete_inv)
            for linea in desres_lineas:
                line_item = model_to_dict(linea)
                TransaccionInv.objects.create(**line_item)
            for linea in doc_inv_lineas:
                articulo = Articulo.objects.filter(ARTICULO=linea.ARTICULO).first()
                if articulo and articulo.ULTIMO_MOVIMIENTO < current_time:
                    articulo.ULTIMO_MOVIMIENTO = current_time
                    articulo.save(update_fields=['ULTIMO_MOVIMIENTO'])
                ExistenciaBodega.objects.filter(
                    BODEGA=linea.BODEGA,
                    ARTICULO=linea.ARTICULO,
                ).update(
                    CANT_DISPONIBLE=F('CANT_DISPONIBLE') + linea.CANTIDAD,
                    CANT_RESERVADA=F('CANT_RESERVADA') - linea.CANTIDAD,
                )
                ExistenciaLote.objects.filter(
                    BODEGA=linea.BODEGA,
                    ARTICULO=linea.ARTICULO,
                    LOTE='ND',
                    LOCALIZACION=linea.LOCALIZACION,
                ).update(
                    CANT_DISPONIBLE=F('CANT_DISPONIBLE') + linea.CANTIDAD,
                    CANT_RESERVADA=F('CANT_RESERVADA') - linea.CANTIDAD,
                )
                ExistenciaReserva.objects.filter(
                    ARTICULO=linea.ARTICULO,
                    BODEGA=linea.BODEGA,
                    LOTE='ND',
                    LOCALIZACION=linea.LOCALIZACION,
                    APLICACION=documento_inv,
                ).delete()
            LineaDocInv.objects.filter(
                DOCUMENTO_INV=documento_inv,
                PAQUETE_INVENTARIO=paquete_inv
            ).delete()
            DocumentoInv.objects.filter(
                DOCUMENTO_INV=documento_inv,
                PAQUETE_INVENTARIO=paquete_inv
            ).delete()
        wm_role = Role.objects.filter(code='warehouse-manager').first()
        admin_role = Role.objects.filter(code='admin').first()
        users_to_notify = set()
        if wm_role:
            users_to_notify.update(wm_role.users.all())
        if admin_role:
            users_to_notify.update(admin_role.users.all())
        send_cancelled_stocktransfer_alert([doc_inv], users_to_notify)
    except Exception as e:
        raise e
    finally:
        for query in connections['mssql_db'].queries:
            logger.info(query['sql'])

def approve_inter_inv_stock_transfer(documento_inv, user='SA'):
    """
    Aprueba una transferencia de inventario entre bodegas tanto en la base de datos MSSQL como en PostgreSQL de
    manera atómica.
    Si alguna de las operaciones falla, se revierte toda la transacción para mantener la integridad de los datos.
    :param documento_inv:
    :param user:
    :return:
    """
    try:
        current_time = datetime.now()
        data_dict = VRADocumentoInv.objects.filter(DOCUMENTO_INV=documento_inv).values(
            'DOCUMENTO_INV',
            'PAQUETE_INVENTARIO'
        ).first()
        with transaction.atomic(using='mssql_db'):
            VRADocumentoInv.objects.filter(
                DOCUMENTO_INV=data_dict['DOCUMENTO_INV'],
                PAQUETE_INVENTARIO=data_dict['PAQUETE_INVENTARIO']
            ).update(
                APROBADO='S',
                USUARIO_APRO=user,
                FECHA_HORA_APROB=current_time,
                # SELECCIONADO='S',
                RecordDate=current_time
            )
        with transaction.atomic(using='default'):
            DocumentoInv.objects.filter(
                DOCUMENTO_INV=data_dict['DOCUMENTO_INV'],
                PAQUETE_INVENTARIO=data_dict['PAQUETE_INVENTARIO']
            ).update(
                APROBADO='S',
                USUARIO_APRO=user,
                FECHA_HORA_APROB=current_time,
                # SELECCIONADO='S',
                RecordDate=current_time
            )
        wm_role = Role.objects.filter(code='warehouse-manager').first()
        admin_role = Role.objects.filter(code='admin').first()
        users_to_notify = set()
        if wm_role:
            users_to_notify.update(wm_role.users.all())
        if admin_role:
            users_to_notify.update(admin_role.users.all())
        doc_inv = VRADocumentoInv.objects.filter(DOCUMENTO_INV=documento_inv).first()
        send_approved_stocktransfer_alert([doc_inv], users_to_notify)
    except Exception as e:
        raise e
    finally:
        for query in connections['mssql_db'].queries:
            logger.info(query['sql'])

def disapprove_inter_inv_stock_transfer(documento_inv):
    """
    Desaprueba una transferencia de inventario entre bodegas tanto en la base de datos MSSQL como en PostgreSQL de
    manera atómica.
    Si alguna de las operaciones falla, se revierte toda la transacción para mantener la integridad de los datos.
    :param documento_inv:
    :return:
    """
    try:
        current_time = datetime.now()
        data_dict = VRADocumentoInv.objects.filter(DOCUMENTO_INV=documento_inv).values(
            'DOCUMENTO_INV',
            'PAQUETE_INVENTARIO'
        ).first()
        with transaction.atomic(using='mssql_db'):
            VRADocumentoInv.objects.filter(
                DOCUMENTO_INV=data_dict['DOCUMENTO_INV'],
                PAQUETE_INVENTARIO=data_dict['PAQUETE_INVENTARIO']
            ).update(

                APROBADO='N',
                USUARIO_APRO=None,
                FECHA_HORA_APROB=None,
                # SELECCIONADO='N',
                RecordDate=current_time
            )
        with transaction.atomic(using='default'):
            DocumentoInv.objects.filter(
                DOCUMENTO_INV=data_dict['DOCUMENTO_INV'],
                PAQUETE_INVENTARIO=data_dict['PAQUETE_INVENTARIO']
            ).update(
                APROBADO='N',
                USUARIO_APRO=None,
                FECHA_HORA_APROB=None,
                # SELECCIONADO='N',
                RecordDate=current_time
            )
        wm_role = Role.objects.filter(code='warehouse-manager').first()
        admin_role = Role.objects.filter(code='admin').first()
        users_to_notify = set()
        if wm_role:
            users_to_notify.update(wm_role.users.all())
        if admin_role:
            users_to_notify.update(admin_role.users.all())
        doc_inv = VRADocumentoInv.objects.filter(DOCUMENTO_INV=documento_inv).first()
        send_rejected_stocktransfer_alert([doc_inv], users_to_notify)
    except Exception as e:
        raise e
    finally:
        for query in connections['mssql_db'].queries:
            logger.info(query['sql'])

def apply_inter_inv_stock_transfer(documento_inv, user='SA'):
    """
    Aplica una transferencia de inventario entre bodegas tanto en la base de datos MSSQL como en PostgreSQL de
    manera atómica.
    Si alguna de las operaciones falla, se revierte toda la transacción para mantener la integridad de los datos.
    :param documento_inv:
    :param user:
    :return:
    """
    try:
        doc_inv = VRADocumentoInv.objects.filter(DOCUMENTO_INV=documento_inv).first()
        audit_inv = None
        tr_audit = None
        if not doc_inv:
            raise ValueError(f"El documento de inventario {documento_inv} no existe.")
        with transaction.atomic(using='mssql_db'):
            if not doc_inv:
                raise IntegrityError(f"El documento de inventario {documento_inv} no existe.")
            lineas_inv = VRALineaDocInv.objects.filter(DOCUMENTO_INV=documento_inv)
            audit_inv = VRAAuditTransInv.objects.create(
                USUARIO=user,
                FECHA_HORA=datetime.now(),
                MODULO_ORIGEN='CI',
                CONSECUTIVO='TRASPASO',
                APLICACION=doc_inv.DOCUMENTO_INV,
                REFERENCIA='Desreservación automática de Documentos por Paquete',
                ASIENTO=None,
                PAQUETE_INVENTARIO=None,
                RecordDate=datetime.now(),
                CreateDate=datetime.now(),
                RowPointer=str(uuid.uuid4()).upper(),
                NoteExistsFlag=False,
            )
            tr_audit = VRAAuditTransInv.objects.create(
                USUARIO=user,
                FECHA_HORA=datetime.now(),
                MODULO_ORIGEN='CI',
                CONSECUTIVO='TRASPASO',
                APLICACION=doc_inv.DOCUMENTO_INV,
                REFERENCIA=doc_inv.REFERENCIA,
                ASIENTO=None,
                PAQUETE_INVENTARIO=doc_inv.PAQUETE_INVENTARIO,
                USUARIO_APRO=user,
                FECHA_HORA_APROB=datetime.now(),
                RecordDate=datetime.now(),
                CreateDate=datetime.now(),
                RowPointer=str(uuid.uuid4()).upper(),
                NoteExistsFlag=False,
            )
            for linea in lineas_inv:
                articulo = VRAArticulo.objects.filter(ARTICULO=linea.ARTICULO).first()
                if articulo:
                    VRATransaccionInv.objects.create(
                        AUDIT_TRANS_INV=audit_inv.AUDIT_TRANS_INV,
                        CONSECUTIVO=linea.LINEA_DOC_INV,
                        ARTICULO=linea.ARTICULO,
                        BODEGA=linea.BODEGA,
                        LOCALIZACION=linea.LOCALIZACION,
                        LOTE=None,
                        TIPO='R',
                        SUBTIPO=' ',
                        SUBSUBTIPO=' ',
                        NATURALEZA='E',
                        CANTIDAD=0 - linea.CANTIDAD,
                        COSTO_TOT_FISC_LOC=articulo.COSTO_ULT_LOC*linea.CANTIDAD,  # COSTO_ULT_LOC from VRA.ARTICULO
                        COSTO_TOT_FISC_DOL=articulo.COSTO_ULT_DOL*linea.CANTIDAD,  # COSTO_ULT_DOL from VRA.ARTICULO
                        COSTO_TOT_COMP_LOC=articulo.COSTO_PROM_LOC*linea.CANTIDAD,  # COSTO_PROM_LOC from VRA.ARTICULO
                        COSTO_TOT_COMP_DOL=articulo.COSTO_PROM_DOL*linea.CANTIDAD,  # COSTO_PROM_DOL from VRA.ARTICULO
                        PRECIO_TOTAL_LOCAL=articulo.PRECIO_BASE_LOCAL*linea.CANTIDAD,
                        PRECIO_TOTAL_DOLAR=articulo.PRECIO_BASE_DOLAR*linea.CANTIDAD,
                        CONTABILIZADA='N',
                        FECHA=doc_inv.FECHA_DOCUMENTO,
                        CENTRO_COSTO=None,
                        AJUSTE_CONFIG='~RR~',
                        SERIE_CADENA=None,
                        NIT=None,
                        UNIDAD_DISTRIBUCIO=None,
                        CUENTA_CONTABLE=None,
                        TIPO_OPERACION=None,
                        TIPO_PAGO=None,
                        GEN_DOC_ELE=None,
                        FECHA_HORA_TRANSAC=datetime.now(),
                        RecordDate=datetime.now(),
                        CreateDate=datetime.now(),
                        RowPointer=str(uuid.uuid4()).upper(),
                        NoteExistsFlag=False,
                    )
                    VRATransaccionInv.objects.create(
                        AUDIT_TRANS_INV=tr_audit.AUDIT_TRANS_INV,
                        CONSECUTIVO=linea.LINEA_DOC_INV * 2 - 1,
                        ARTICULO=linea.ARTICULO,
                        BODEGA=linea.BODEGA,
                        LOCALIZACION=linea.LOCALIZACION,
                        LOTE=None,
                        TIPO='T',
                        SUBTIPO='D',
                        SUBSUBTIPO=' ',
                        NATURALEZA='S',
                        CANTIDAD=0 - linea.CANTIDAD,
                        COSTO_TOT_FISC_LOC=articulo.COSTO_ULT_LOC * linea.CANTIDAD,  # COSTO_ULT_LOC from VRA.ARTICULO
                        COSTO_TOT_FISC_DOL=articulo.COSTO_ULT_DOL * linea.CANTIDAD,  # COSTO_ULT_DOL from VRA.ARTICULO
                        COSTO_TOT_COMP_LOC=articulo.COSTO_PROM_LOC * linea.CANTIDAD,  # COSTO_PROM_LOC from VRA.ARTICULO
                        COSTO_TOT_COMP_DOL=articulo.COSTO_PROM_DOL * linea.CANTIDAD,  # COSTO_PROM_DOL from VRA.ARTICULO
                        PRECIO_TOTAL_LOCAL=articulo.PRECIO_BASE_LOCAL * linea.CANTIDAD,
                        PRECIO_TOTAL_DOLAR=articulo.PRECIO_BASE_DOLAR * linea.CANTIDAD,
                        CONTABILIZADA='N',
                        FECHA=doc_inv.FECHA_DOCUMENTO,
                        CENTRO_COSTO=None,
                        AJUSTE_CONFIG='~TT~',
                        SERIE_CADENA=None,
                        NIT=None,
                        UNIDAD_DISTRIBUCIO=None,
                        CUENTA_CONTABLE=None,
                        TIPO_OPERACION=None,
                        TIPO_PAGO=None,
                        GEN_DOC_ELE=None,
                        FECHA_HORA_TRANSAC=datetime.now(),
                        RecordDate=datetime.now(),
                        CreateDate=datetime.now(),
                        RowPointer=str(uuid.uuid4()).upper(),
                        NoteExistsFlag=False,
                    )
                    VRATransaccionInv.objects.create(
                        AUDIT_TRANS_INV=tr_audit.AUDIT_TRANS_INV,
                        CONSECUTIVO=linea.LINEA_DOC_INV * 2,
                        ARTICULO=linea.ARTICULO,
                        BODEGA=linea.BODEGA_DESTINO,
                        LOCALIZACION=linea.LOCALIZACION_DEST,
                        LOTE=None,
                        TIPO='T',
                        SUBTIPO='D',
                        SUBSUBTIPO=' ',
                        NATURALEZA='E',
                        CANTIDAD=linea.CANTIDAD,
                        COSTO_TOT_FISC_LOC=articulo.COSTO_ULT_LOC * linea.CANTIDAD,  # COSTO_ULT_LOC from VRA.ARTICULO
                        COSTO_TOT_FISC_DOL=articulo.COSTO_ULT_DOL * linea.CANTIDAD,  # COSTO_ULT_DOL from VRA.ARTICULO
                        COSTO_TOT_COMP_LOC=articulo.COSTO_PROM_LOC * linea.CANTIDAD,  # COSTO_PROM_LOC from VRA.ARTICULO
                        COSTO_TOT_COMP_DOL=articulo.COSTO_PROM_DOL * linea.CANTIDAD,  # COSTO_PROM_DOL from VRA.ARTICULO
                        PRECIO_TOTAL_LOCAL=articulo.PRECIO_BASE_LOCAL * linea.CANTIDAD,
                        PRECIO_TOTAL_DOLAR=articulo.PRECIO_BASE_DOLAR * linea.CANTIDAD,
                        CONTABILIZADA='N',
                        FECHA=doc_inv.FECHA_DOCUMENTO,
                        CENTRO_COSTO=None,
                        AJUSTE_CONFIG='~TT~',
                        SERIE_CADENA=None,
                        NIT=None,
                        UNIDAD_DISTRIBUCIO=None,
                        CUENTA_CONTABLE=None,
                        TIPO_OPERACION=None,
                        TIPO_PAGO=None,
                        GEN_DOC_ELE=None,
                        FECHA_HORA_TRANSAC=datetime.now(),
                        RecordDate=datetime.now(),
                        CreateDate=datetime.now(),
                        RowPointer=str(uuid.uuid4()).upper(),
                        NoteExistsFlag=False,
                    )
                    VRAExistenciaBodega.objects.filter(
                        BODEGA=linea.BODEGA,
                        ARTICULO=linea.ARTICULO,
                    ).update(
                        CANT_RESERVADA=F('CANT_RESERVADA') - linea.CANTIDAD,
                    )
                    VRAExistenciaLote.objects.filter(
                        BODEGA=linea.BODEGA,
                        ARTICULO=linea.ARTICULO,
                        LOTE='ND',
                        LOCALIZACION=linea.LOCALIZACION,
                    ).update(
                        CANT_RESERVADA=F('CANT_RESERVADA') - linea.CANTIDAD,
                    )
                    VRAExistenciaBodega.objects.filter(
                        BODEGA=linea.BODEGA_DESTINO,
                        ARTICULO=linea.ARTICULO,
                    ).update(
                        COSTO_UNT_PROMEDIO_LOC=((F('COSTO_UNT_PROMEDIO_LOC') * F('CANT_DISPONIBLE')) + (
                                articulo.COSTO_PROM_LOC * linea.CANTIDAD)) / (F('CANT_DISPONIBLE') + linea.CANTIDAD),
                        COSTO_UNT_PROMEDIO_DOL=((F('COSTO_UNT_PROMEDIO_DOL') * F('CANT_DISPONIBLE')) + (
                                articulo.COSTO_PROM_DOL * linea.CANTIDAD)) / (F('CANT_DISPONIBLE') + linea.CANTIDAD),
                        CANT_DISPONIBLE=F('CANT_DISPONIBLE') + linea.CANTIDAD
                    )
                    VRAExistenciaLote.objects.filter(
                        BODEGA=linea.BODEGA_DESTINO,
                        ARTICULO=linea.ARTICULO,
                        LOTE='ND',
                        LOCALIZACION=linea.LOCALIZACION_DEST,
                    ).update(
                        CANT_DISPONIBLE=F('CANT_DISPONIBLE') + linea.CANTIDAD
                    )
                VRAExistenciaReserva.objects.filter(
                    ARTICULO=linea.ARTICULO,
                    BODEGA=linea.BODEGA,
                    LOTE='ND',
                    LOCALIZACION=linea.LOCALIZACION,
                    APLICACION=doc_inv.DOCUMENTO_INV,
                ).delete()
                if articulo and articulo.ULTIMO_MOVIMIENTO < datetime.now():
                    articulo.ULTIMO_MOVIMIENTO = datetime.now()
                    articulo.save(update_fields=['ULTIMO_MOVIMIENTO'])
            VRALineaDocInv.objects.filter(DOCUMENTO_INV=documento_inv).delete()
            VRADocumentoInv.objects.filter(DOCUMENTO_INV=documento_inv).delete()

        with transaction.atomic(using='default'):
            lineas_inv = LineaDocInv.objects.filter(DOCUMENTO_INV=documento_inv)
            res_lineas = VRATransaccionInv.objects.filter(AUDIT_TRANS_INV=audit_inv.AUDIT_TRANS_INV)
            tr_lineas = VRATransaccionInv.objects.filter(AUDIT_TRANS_INV=tr_audit.AUDIT_TRANS_INV)
            AuditTransInv.objects.create(**model_to_dict(audit_inv))
            AuditTransInv.objects.create(**model_to_dict(tr_audit))
            for linea in res_lineas:
                line_item = model_to_dict(linea)
                TransaccionInv.objects.create(**line_item)
            for linea in tr_lineas:
                line_item = model_to_dict(linea)
                TransaccionInv.objects.create(**line_item)
            for linea in lineas_inv:
                articulo = VRAArticulo.objects.filter(ARTICULO=linea.ARTICULO).first()
                ExistenciaBodega.objects.filter(
                    BODEGA=linea.BODEGA,
                    ARTICULO=linea.ARTICULO,
                ).update(
                    CANT_RESERVADA=F('CANT_RESERVADA') - linea.CANTIDAD,
                )
                ExistenciaLote.objects.filter(
                    BODEGA=linea.BODEGA,
                    ARTICULO=linea.ARTICULO,
                    LOTE='ND',
                    LOCALIZACION=linea.LOCALIZACION,
                ).update(
                    CANT_RESERVADA=F('CANT_RESERVADA') - linea.CANTIDAD,
                )
                ExistenciaBodega.objects.filter(
                    BODEGA=linea.BODEGA_DESTINO,
                    ARTICULO=linea.ARTICULO,
                ).update(
                    COSTO_UNT_PROMEDIO_LOC=((F('COSTO_UNT_PROMEDIO_LOC') * F('CANT_DISPONIBLE')) + (
                            articulo.COSTO_PROM_LOC * linea.CANTIDAD)) / (F('CANT_DISPONIBLE') + linea.CANTIDAD),
                    COSTO_UNT_PROMEDIO_DOL=((F('COSTO_UNT_PROMEDIO_DOL') * F('CANT_DISPONIBLE')) + (
                            articulo.COSTO_PROM_DOL * linea.CANTIDAD)) / (F('CANT_DISPONIBLE') + linea.CANTIDAD),
                    CANT_DISPONIBLE=F('CANT_DISPONIBLE') + linea.CANTIDAD
                )
                ExistenciaLote.objects.filter(
                    BODEGA=linea.BODEGA_DESTINO,
                    ARTICULO=linea.ARTICULO,
                    LOTE='ND',
                    LOCALIZACION=linea.LOCALIZACION_DEST,
                ).update(
                    CANT_DISPONIBLE=F('CANT_DISPONIBLE') + linea.CANTIDAD
                )
                ExistenciaReserva.objects.filter(
                    ARTICULO=linea.ARTICULO,
                    BODEGA=linea.BODEGA,
                    LOTE='ND',
                    LOCALIZACION=linea.LOCALIZACION,
                    APLICACION=doc_inv.DOCUMENTO_INV,
                ).delete()
                articulo_pg = Articulo.objects.get(ARTICULO=linea.ARTICULO)
                articulo_pg.ULTIMO_MOVIMIENTO = articulo.ULTIMO_MOVIMIENTO
                articulo_pg.save(update_fields=['ULTIMO_MOVIMIENTO'])
            LineaDocInv.objects.filter(DOCUMENTO_INV=documento_inv).delete()
            DocumentoInv.objects.filter(DOCUMENTO_INV=documento_inv).delete()
        wm_role = Role.objects.filter(code='warehouse-manager').first()
        admin_role = Role.objects.filter(code='admin').first()
        users_to_notify = set()
        if wm_role:
            users_to_notify.update(wm_role.users.all())
        if admin_role:
            users_to_notify.update(admin_role.users.all())
        send_applied_stocktransfer_alert([documento_inv], users_to_notify)
    except Exception as e:
        raise e
    finally:
        for query in connections['mssql_db'].queries:
            logger.info(query['sql'])

def create_stock_transfer_adjustment(batch: dict, tasks: list, user='SA'):
    """
    Crea un ajuste de transferencia de inventario entre bodegas tanto en la base de datos MSSQL como en PostgreSQL de
    manera atómica.
    Si alguna de las operaciones falla, se revierte toda la transacción para mantener la integridad de los datos.
    :param batch:
    :param tasks:
    :param user:
    :return:
    """
    try:
        documento_inv = batch['document_number']
        doc_exist = VRADocumentoInv.objects.filter(DOCUMENTO_INV=documento_inv).first()
        if doc_exist:
            raise IntegrityError(f"El documento de inventario {documento_inv} ya existe.")
        current_time = datetime.now()
        index = int(batch['document_number'][3:])
        siguiente = index + 1
        batch['SIGUIENTE_CONSEC'] = f"FI-{siguiente:05d}"
        doc_inv = None
        with transaction.atomic(using='mssql_db'):
            VRAConsecutivoCi.objects.filter(CONSECUTIVO='FISICO').update(
                SIGUIENTE_CONSEC=batch['SIGUIENTE_CONSEC'],
                ULTIMO_USUARIO=user,
                ULT_FECHA_HORA=current_time,
            )
            doc_inv = VRADocumentoInv.objects.create(
                DOCUMENTO_INV=documento_inv,
                CONSECUTIVO='FISICO',
                FECHA_DOCUMENTO=datetime.today(),
                REFERENCIA=batch['referencia'] if batch['referencia'] else ' ',
                USUARIO=user,
                SELECCIONADO='N',
                PAQUETE_INVENTARIO=batch['paquete_inventario'],
                FECHA_HOR_CREACION=current_time,
                MENSAJE_SISTEMA='',
                APROBADO='S',
                USUARIO_APRO=user,
                FECHA_HORA_APROB=current_time,
                RecordDate=current_time,
                CreateDate=current_time,
                RowPointer=str(uuid.uuid4()).upper(),
                NoteExistsFlag=False,
            )
            for index, task in enumerate(tasks):
                articulo = VRAArticulo.objects.filter(ARTICULO=task['articulo']).first()
                VRALineaDocInv.objects.create(
                    ARTICULO=task['articulo'],
                    BODEGA=task['bodega'],
                    LOCALIZACION=task['location'],
                    LOCALIZACION_DEST=None,
                    LOTE=None,
                    TIPO='F',
                    SUBTIPO='D',
                    SUBSUBTIPO=' ',  # empty string means not NULL
                    CANTIDAD=task['physical_qty'],
                    COSTO_TOTAL_LOCAL=articulo.COSTO_ULT_LOC,
                    COSTO_TOTAL_DOLAR=articulo.COSTO_ULT_DOL,
                    COSTO_TOTAL_LOCAL_COMP=articulo.COSTO_ULT_LOC,
                    COSTO_TOTAL_DOLAR_COMP=articulo.COSTO_ULT_DOL,
                    PRECIO_TOTAL_LOCAL=0,
                    PRECIO_TOTAL_DOLAR=0,
                    BODEGA_DESTINO=None,
                    CENTRO_COSTO=None,
                    AJUSTE_CONFIG='~FF~',
                    SECUENCIA=None,
                    CUENTA_CONTABLE=None,
                    TIPO_OPERACION=None,
                    TIPO_PAGO=None,
                    GEN_DOC_ELE=None,
                    SERIE_CADENA=None,
                    UNIDAD_DISTRIBUCIO=None,
                    PAQUETE_INVENTARIO=batch['paquete_inventario'],
                    DOCUMENTO_INV=batch['document_number'],
                    LINEA_DOC_INV=index + 1,
                    RecordDate=current_time,
                    CreateDate=current_time,
                    RowPointer=str(uuid.uuid4()).upper(),
                    NoteExistsFlag=False,
                )
        with transaction.atomic(using='default'):
            ConsecutivoCi.objects.filter(CONSECUTIVO='FISICO').update(
                SIGUIENTE_CONSEC=batch['SIGUIENTE_CONSEC'],
                ULTIMO_USUARIO=user,
                ULT_FECHA_HORA=current_time,
            )
            doc_inv_new_dict = model_to_dict(doc_inv)
            DocumentoInv.objects.create(**doc_inv_new_dict)
            lineas = VRALineaDocInv.objects.filter(DOCUMENTO_INV=batch['document_number'])
            for linea in lineas:
                linea_dict = model_to_dict(linea)
                LineaDocInv.objects.create(**linea_dict)
    except Exception as e:
        raise e
    finally:
        for query in connections['mssql_db'].queries:
            logger.info(query['sql'])

def apply_stock_transfer_adjustment(documento_inv, user='SA'):
    """
    Aplica un ajuste de transferencia de inventario entre bodegas tanto en la base de datos MSSQL como en PostgreSQL de
    manera atómica.
    Si alguna de las operaciones falla, se revierte toda la transacción para mantener la integridad de los datos.
    :param documento_inv:
    :param user:
    :return:
    """
    try:
        doc_inv = VRADocumentoInv.objects.filter(DOCUMENTO_INV=documento_inv).first()
        if not doc_inv:
            raise IntegrityError(f"El documento de inventario {documento_inv} no existe.")
        audit_inv = None
        with transaction.atomic(using='mssql_db'):
            lineas_inv = VRALineaDocInv.objects.filter(DOCUMENTO_INV=documento_inv)
            audit_inv = VRAAuditTransInv.objects.create(
                USUARIO=user,
                FECHA_HORA=datetime.now(),
                MODULO_ORIGEN='CI',
                CONSECUTIVO=doc_inv.CONSECUTIVO,
                APLICACION=doc_inv.DOCUMENTO_INV,
                REFERENCIA=doc_inv.REFERENCIA,
                ASIENTO=None,
                PAQUETE_INVENTARIO=doc_inv.PAQUETE_INVENTARIO,
                USUARIO_APRO=user,
                FECHA_HORA_APROB=datetime.now(),
                RecordDate=datetime.now(),
                CreateDate=datetime.now(),
                RowPointer=str(uuid.uuid4()).upper(),
                NoteExistsFlag=False,
            )
            for linea in lineas_inv:
                articulo = VRAArticulo.objects.filter(ARTICULO=linea.ARTICULO).first()
                physical_qty = linea.CANTIDAD
                system_qty = VRAExistenciaLote.objects.filter(
                    ARTICULO=linea.ARTICULO, BODEGA=linea.BODEGA, LOCALIZACION=linea.LOCALIZACION
                ).aggregate(total_available=Sum('CANT_DISPONIBLE'))[
                                 'total_available'] or 0
                variance_qty = physical_qty - system_qty
                total_qty = VRAExistenciaBodega.objects \
                                .filter(ARTICULO=linea.ARTICULO, BODEGA=linea.BODEGA) \
                                .aggregate(total_available=Sum('CANT_DISPONIBLE') + Sum('CANT_RESERVADA'))[
                                'total_available'] or 0
                costo_prom_loc = (articulo.COSTO_PROM_LOC * total_qty +
                                  linea.COSTO_TOTAL_LOCAL_COMP * variance_qty) / \
                                 (total_qty + variance_qty) if (total_qty + variance_qty) > 0 else 0
                costo_prom_dol = (articulo.COSTO_PROM_DOL * total_qty +
                                  linea.COSTO_TOTAL_DOLAR_COMP * variance_qty) / \
                                 (total_qty + variance_qty) if (total_qty + variance_qty) > 0 else 0
                articulo.COSTO_ULT_LOC = articulo.COSTO_PROM_LOC
                articulo.COSTO_ULT_DOL = articulo.COSTO_PROM_DOL
                articulo.COSTO_PROM_LOC = round(costo_prom_loc, 3)
                articulo.COSTO_PROM_DOL = round(costo_prom_dol, 3)
                articulo.ULTIMO_MOVIMIENTO = datetime.now()
                articulo.ULTIMO_INVENTARIO = datetime.now()
                articulo.save(update_fields=['COSTO_PROM_LOC', 'COSTO_PROM_DOL', 'ULTIMO_MOVIMIENTO',
                                             'COSTO_ULT_LOC', 'COSTO_ULT_DOL', 'ULTIMO_INVENTARIO'])

                VRAExistenciaBodega.objects.filter(ARTICULO=linea.ARTICULO, BODEGA=linea.BODEGA).update(
                    CANT_DISPONIBLE=F('CANT_DISPONIBLE') + variance_qty
                )
                VRAExistenciaLote.objects.filter(
                    ARTICULO=linea.ARTICULO, BODEGA=linea.BODEGA, LOCALIZACION=linea.LOCALIZACION, LOTE='ND'
                ).update(
                    CANT_DISPONIBLE=F('CANT_DISPONIBLE') + variance_qty
                )
                VRALote.objects.filter(LOTE='ND', ARTICULO=linea.ARTICULO).update(
                    CANTIDAD_INGRESADA=F('CANTIDAD_INGRESADA') + variance_qty
                )
                paquete = VRAPaquete.objects.filter(PAQUETE='CI').first()
                index = int(paquete.ULTIMO_ASIENTO[2:])
                siguiente = index + 1
                ultimo_asiento = f"CI{siguiente:06d}"
                paquete.ULTIMO_ASIENTO = ultimo_asiento
                paquete.save(update_fields=['ULTIMO_ASIENTO'])
                VRATransaccionInv.objects.create(
                    AUDIT_TRANS_INV=audit_inv.AUDIT_TRANS_INV,
                    CONSECUTIVO=linea.LINEA_DOC_INV,
                    ARTICULO=linea.ARTICULO,
                    BODEGA=linea.BODEGA,
                    LOCALIZACION=linea.LOCALIZACION,
                    LOTE=None,
                    TIPO='F',
                    SUBTIPO='D',
                    SUBSUBTIPO=' ',
                    NATURALEZA='E',
                    CANTIDAD=variance_qty,
                    COSTO_TOT_FISC_LOC=articulo.COSTO_ULT_LOC * variance_qty,  # COSTO_ULT_LOC from VRA.ARTICULO
                    COSTO_TOT_FISC_DOL=articulo.COSTO_ULT_DOL * variance_qty,  # COSTO_ULT_DOL from VRA.ARTICULO
                    COSTO_TOT_COMP_LOC=articulo.COSTO_PROM_LOC * variance_qty,  # COSTO_PROM_LOC from VRA.ARTICULO
                    COSTO_TOT_COMP_DOL=articulo.COSTO_PROM_DOL * variance_qty,  # COSTO_PROM_DOL from VRA.ARTICULO
                    PRECIO_TOTAL_LOCAL=articulo.PRECIO_BASE_LOCAL * variance_qty,
                    PRECIO_TOTAL_DOLAR=articulo.PRECIO_BASE_DOLAR * variance_qty,
                    CONTABILIZADA='S',
                    FECHA=doc_inv.FECHA_DOCUMENTO,
                    CENTRO_COSTO=None,
                    AJUSTE_CONFIG='~FF~',
                    SERIE_CADENA=None,
                    NIT=None,
                    UNIDAD_DISTRIBUCIO=None,
                    CUENTA_CONTABLE=None,
                    TIPO_OPERACION=None,
                    TIPO_PAGO=None,
                    GEN_DOC_ELE=None,
                    FECHA_HORA_TRANSAC=datetime.now(),
                    RecordDate=datetime.now(),
                    CreateDate=datetime.now(),
                    RowPointer=str(uuid.uuid4()).upper(),
                    NoteExistsFlag=False,
                )
                audit_inv.ASIENTO = ultimo_asiento
                audit_inv.save(update_fields=['ASIENTO'])
                debito_loc = round(articulo.COSTO_PROM_LOC * variance_qty, 2) if variance_qty > 0 else 0
                debito_dol = round(articulo.COSTO_PROM_DOL * variance_qty, 2) if variance_qty > 0 else 0
                VRAAsientoDeDiario.objects.create(
                    PAQUETE='CI',
                    TIPO_ASIENTO='CI',
                    FECHA=datetime.today(),
                    CONTABILIDAD='F',
                    ORIGEN='CI',
                    NOTAS=' ',
                    MARCADO='N',
                    TOTAL_DEBITO_LOC=debito_loc,
                    TOTAL_CREDITO_LOC=debito_loc,
                    TOTAL_DEBITO_DOL=debito_dol,
                    TOTAL_CREDITO_DOL=debito_dol,
                    TOTAL_CONTROL_LOC=debito_loc,
                    TOTAL_CONTROL_DOL=debito_dol,
                    ULTIMO_USUARIO=user,
                    FECHA_ULT_MODIF=datetime.today(),
                    USUARIO_CREACION=user,
                    FECHA_CREACION=datetime.today(),
                    RowPointer=str(uuid.uuid4()).upper(),
                    NoteExistsFlag=False,
                    RecordDate=datetime.now(),
                    CreateDate=datetime.now(),
                    DEPENDENCIA=None,
                    DOCUMENTO_GLOBAL=None,
                    ASIENTO=ultimo_asiento,
                    CLASE_ASIENTO='N'
                )
                articulo_cuenta = ArticuloCuenta.objects.filter(ARTICULO_CUENTA=articulo.ARTICULO_CUENTA).first()
                cg_aux_index = linea.LINEA_DOC_INV * 2 - 1
                VRACgAux.objects.create(
                    GUID_ORIGEN=str(audit_inv.RowPointer),
                    TABLA_ORIGEN='AUDIT_TRANS_INV',
                    ASIENTO=ultimo_asiento,
                    LINEA=cg_aux_index,
                    COMENTARIO='GUID - Origen',
                    RowPointer=str(uuid.uuid4()).upper(),
                    NoteExistsFlag=False,
                    RecordDate=datetime.now(),
                    CreateDate=datetime.now(),
                )
                cuenta = CuentaContable.objects.filter(DESCRIPCION__iexact=articulo_cuenta.DESCRIPCION).first()
                VRADiario.objects.create(
                    ASIENTO=ultimo_asiento,
                    CONSECUTIVO=cg_aux_index,
                    CUENTA_CONTABLE=cuenta.CUENTA_CONTABLE,
                    CENTRO_COSTO='00-00000-00-00',
                    REFERENCIA='ajuste físico de %s' % articulo.ARTICULO,
                    FUENTE='CI-%s' % documento_inv,
                    DEBITO_LOCAL=debito_loc,
                    DEBITO_DOLAR=debito_dol,
                    CREDITO_LOCAL=None,
                    CREDITO_DOLAR=None,
                    DEBITO_UNIDADES=None,
                    CREDITO_UNIDADES=None,
                    NIT='ND',
                    TIPO_CAMBIO=None,
                    RowPointer=str(uuid.uuid4()).upper(),
                    NoteExistsFlag=False,
                    RecordDate=datetime.now(),
                    CreateDate=datetime.now(),
                    BASE_LOCAL=None,
                    BASE_DOLAR=None,
                    FASE=None,
                    PROYECTO=None,
                    DOCUMENTO_GLOBAL=None,
                )
                cg_aux_index = linea.LINEA_DOC_INV * 2
                VRACgAux.objects.create(
                    GUID_ORIGEN=str(audit_inv.RowPointer),
                    TABLA_ORIGEN='AUDIT_TRANS_INV',
                    ASIENTO=ultimo_asiento,
                    LINEA=cg_aux_index,
                    COMENTARIO='GUID - Origen',
                    RowPointer=str(uuid.uuid4()).upper(),
                    NoteExistsFlag=False,
                    RecordDate=datetime.now(),
                    CreateDate=datetime.now(),
                )
                cuenta = CuentaContable.objects.filter(DESCRIPCION__iexact='Faltante De Inventario').first()
                VRADiario.objects.create(
                    ASIENTO=ultimo_asiento,
                    CONSECUTIVO=cg_aux_index,
                    CUENTA_CONTABLE=cuenta.CUENTA_CONTABLE,
                    CENTRO_COSTO='00-00000-00-00',
                    REFERENCIA='ajuste físico de %s' % articulo.ARTICULO,
                    FUENTE='CI-%s' % documento_inv,
                    DEBITO_LOCAL=None,
                    DEBITO_DOLAR=None,
                    CREDITO_LOCAL=debito_loc,
                    CREDITO_DOLAR=debito_dol,
                    DEBITO_UNIDADES=None,
                    CREDITO_UNIDADES=None,
                    NIT='ND',
                    TIPO_CAMBIO=None,
                    RowPointer=str(uuid.uuid4()).upper(),
                    RecordDate=datetime.now(),
                    CreateDate=datetime.now(),
                    NoteExistsFlag=False,
                    BASE_LOCAL=None,
                    BASE_DOLAR=None,
                    FASE=None,
                    PROYECTO=None,
                    DOCUMENTO_GLOBAL=None,
                )
            VRALineaDocInv.objects.filter(DOCUMENTO_INV=documento_inv).delete()
            VRADocumentoInv.objects.filter(DOCUMENTO_INV=documento_inv).delete()
        with transaction.atomic(using='default'):
            lineas_inv = LineaDocInv.objects.filter(DOCUMENTO_INV=documento_inv)
            audit_dict = model_to_dict(audit_inv)
            AuditTransInv.objects.create(**audit_dict)
            lineas = VRATransaccionInv.objects.filter(AUDIT_TRANS_INV=audit_inv.AUDIT_TRANS_INV)
            for linea in lineas:
                linea_dict = model_to_dict(linea)
                TransaccionInv.objects.create(**linea_dict)
            for linea in lineas_inv:
                articulo_local = VRAArticulo.objects.filter(ARTICULO=linea.ARTICULO).first()
                Articulo.objects.filter(ARTICULO=linea.ARTICULO).update(
                    ULTIMO_MOVIMIENTO=articulo_local.ULTIMO_MOVIMIENTO,
                    ULTIMO_INVENTARIO=articulo_local.ULTIMO_INVENTARIO,
                    COSTO_PROM_LOC=articulo_local.COSTO_PROM_LOC,
                    COSTO_PROM_DOL=articulo_local.COSTO_PROM_DOL,
                    COSTO_ULT_LOC=articulo_local.COSTO_ULT_LOC,
                    COSTO_ULT_DOL=articulo_local.COSTO_ULT_DOL,
                )
                existencia_bodega_local = VRAExistenciaBodega.objects.filter(
                    ARTICULO=linea.ARTICULO, BODEGA=linea.BODEGA
                ).first()
                ExistenciaBodega.objects.filter(ARTICULO=linea.ARTICULO, BODEGA=linea.BODEGA).update(
                    CANT_DISPONIBLE=existencia_bodega_local.CANT_DISPONIBLE
                )
                existencia_lote_local = VRAExistenciaLote.objects.filter(
                    ARTICULO=linea.ARTICULO, BODEGA=linea.BODEGA, LOCALIZACION=linea.LOCALIZACION, LOTE='ND'
                ).first()
                ExistenciaLote.objects.filter(
                    ARTICULO=linea.ARTICULO, BODEGA=linea.BODEGA, LOCALIZACION=linea.LOCALIZACION, LOTE='ND'
                ).update(
                    CANT_DISPONIBLE=existencia_lote_local.CANT_DISPONIBLE
                )
            LineaDocInv.objects.filter(DOCUMENTO_INV=documento_inv).delete()
            DocumentoInv.objects.filter(DOCUMENTO_INV=documento_inv).delete()
    except Exception as e:
        raise e
    finally:
        for query in connections['mssql_db'].queries:
            logger.info(query['sql'])