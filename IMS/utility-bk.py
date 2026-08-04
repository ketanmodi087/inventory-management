from catalog_management.models import ModelSyncManager
from user_management.models import Notification, NotificationType
import time, logging
from django.apps import apps
from datetime import datetime, timedelta
from vra_backend.models import DBOAuditSfDeletedRows
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

logger = logging.getLogger(__name__)


def to_pascal_case(s: str) -> str:
    """
    Convert a string from snake case with uppercase letters to PascalCase.
    """
    return ''.join(word.capitalize() for word in s.lower().split('_'))


def to_snake_case(s: str) -> str:
    """
    Convert a string from PascalCase to snake_case with uppercase letters.
    """
    return ''.join(['_' + c.lower() if c.isupper() else c for c in s]).lstrip('_').upper()

"""
def sync_database_models(source_model_name: str, target_model_name: str, filter_keys, task_id) -> tuple:
    total_new_records = 0
    total_updated_records = 0
    try:
        source_model = apps.get_model('vra_backend', source_model_name)
        target_model = apps.get_model('catalog_management', target_model_name)
        current_time = datetime.now()
        latest = target_model.objects.order_by('-CreateDate').first()
        page = 0
        last_synced = None
        if latest:
            new_items = source_model.objects.filter(
                CreateDate__gte=latest.CreateDate + timedelta(milliseconds=1)).order_by('CreateDate')
            if len(new_items):
                last_synced = new_items.first().RecordDate
            else:
                last_sync = ModelSyncManager.objects.filter(
                    table=target_model._meta.db_table
                ).order_by('-last_synced').first()
                if last_sync:
                    last_synced = last_sync.last_synced
            if last_synced:
                items = source_model.objects.filter(RecordDate__gte=(last_synced - timedelta(milliseconds=1))).order_by(
                    'RecordDate')
                if items.exists():
                    existing_records = []
                    new_records = []
                    for record in items.values():
                        try:
                            filters = {}
                            for k in filter_keys:
                                if k == 'RowPointer':
                                    filters[k] = str(record[k]).lower()
                                else:
                                    filters[k] = record[k]
                            obj_exists = target_model.objects.get(**filters)
                            for attr, value in record.items():
                                setattr(obj_exists, attr, value)
                            existing_records.append(obj_exists)
                        except target_model.DoesNotExist:
                            new_records.append(target_model(**record))
                    if existing_records:
                        target_model.objects.bulk_update(existing_records,
                                                         [field.name for field in target_model._meta.fields if
                                                          field.name not in (filter_keys + ['pk'])], batch_size=200)
                    if new_records:
                        target_model.objects.bulk_create(new_records, ignore_conflicts=True, batch_size=1000)
                    total_new_records += len(new_records)
                    total_updated_records += len(existing_records)
        else:
            while True:
                page += 1
                items = source_model.objects.all().order_by('CreateDate')[(page - 1) * 1000:page * 1000]
                if not items or not len(items):
                    break
                objects = [target_model(**record) for record in items.values()]
                target_model.objects.bulk_create(objects, ignore_conflicts=True)
                total_new_records += len(items)
                time.sleep(1)
        deleted_rows = DBOAuditSfDeletedRows.objects.filter(TableName=to_snake_case(target_model_name),
                                                            DeletedDate__gte=current_time - timedelta(days=7))
        deleted_records_count = deleted_rows.count()
        logging.info(
            f"Deleted {deleted_records_count} records from {target_model_name}: {to_snake_case(target_model_name)}")
        if deleted_rows.exists():
            for row in deleted_rows:
                try:
                    target_model.objects.filter(RowPointer=row.DeletedRP).delete()
                except Exception as e:
                    logging.error(
                        f"Error deleting record with RowPointer {row.DeletedRP} from {target_model_name}: {e}")

    except Exception as e:
        return None, None
    return total_new_records, total_updated_records
"""
def sync_database_models(source_model_name: str, target_model_name: str, filter_keys, task_id) -> tuple:
    total_new_records = 0
    total_updated_records = 0
    try:
        t0 = time.time()
        source_model = apps.get_model('vra_backend', source_model_name)
        target_model = apps.get_model('catalog_management', target_model_name)
        current_time = datetime.now()
        latest = target_model.objects.order_by('-CreateDate').first()
        last_synced = None
        if latest:
            new_item = source_model.objects.filter(
                CreateDate__gte=latest.CreateDate + timedelta(milliseconds=1)).order_by('CreateDate').first()
            if new_item:
                last_synced = new_item.RecordDate
            else:
                last_sync = ModelSyncManager.objects.filter(
                    table=target_model._meta.db_table
                ).order_by('-last_synced').first()
                if last_sync:
                    last_synced = last_sync.last_synced
            if last_synced:
                logger.info(f"Initial time: {time.time() - t0:.4f}s")
                t0 = time.time()
                source_queryset = source_model.objects.filter(RecordDate__gte=(last_synced - timedelta(milliseconds=1))) \
                    .values().iterator(chunk_size=5000)
                update_fields = [
                    f.name for f in target_model._meta.fields
                    if f.name not in (filter_keys + ['pk', 'id', 'RowPointer', 'CreateDate'])
                ]
                logger.info(f"Fetch source_queryset: {time.time() - t0:.4f}s")
                while True:
                    # 2. Extract a slice of records for processing (e.g., 2000 at a time)
                    # This keeps the 'lookup_keys' list manageable for the IN clause
                    source_batch = []
                    # Time the Data Retrieval
                    t0 = time.time()
                    try:
                        for _ in range(2000):
                            source_batch.append(next(source_queryset))
                    except StopIteration:
                        pass
                    logger.info(f"Fetch Batch: {time.time() - t0:.4f}s")
                    if not source_batch:
                        break
                    # Time the Mapping
                    t1 = time.time()
                    # 3. Bulk lookup for the current batch only
                    lookup_keys = [str(r['RowPointer']).lower() for r in source_batch]
                    existing_map = {
                        str(obj.RowPointer).lower(): obj
                        for obj in target_model.objects.filter(RowPointer__in=lookup_keys)
                    }
                    logger.info(f"PG Lookup: {time.time() - t1:.4f}s")
                    existing_records = []
                    new_records = []
                    t2 = time.time()
                    for record in source_batch:
                        rp = str(record['RowPointer']).lower()
                        if rp in existing_map:
                            obj = existing_map[rp]
                            # Filter record keys to match target model fields only
                            for attr, value in record.items():
                                if hasattr(obj, attr):
                                    setattr(obj, attr, value)
                            existing_records.append(obj)
                        else:
                            # Filter the dict to only keys that exist in target_model
                            new_records.append(target_model(**record))
                    logger.info(f"Logic Processing: {time.time() - t2:.4f}s")
                    t3 = time.time()
                    # 4. Perform DB writes for this batch
                    if existing_records:
                        target_model.objects.bulk_update(existing_records, update_fields, batch_size=500)
                        total_updated_records += len(existing_records)

                    if new_records:
                        target_model.objects.bulk_create(new_records, ignore_conflicts=True, batch_size=1000)
                        total_new_records += len(new_records)
                    logger.info(f"DB Write: {time.time() - t3:.4f}s")
                    # Clear batch to free memory
                    source_batch.clear()
        else:
            logger.info(f"Initial time: {time.time() - t0:.4f}s")
            t0 = time.time()
            total_new_records = 0
            queryset = source_model.objects.order_by('CreateDate').values().iterator(chunk_size=2000)
            batch = []
            logger.info(f"Fetch source_queryset: {time.time() - t0:.4f}s")
            t_fetch = time.time()
            for record in queryset:
                batch.append(target_model(**record))
                # When batch reaches size, save and clear memory
                if len(batch) >= 2000:
                    logger.info(f"Network Fetch Time: {time.time() - t_fetch:.4f}s")
                    t1 = time.time()
                    target_model.objects.bulk_create(batch, ignore_conflicts=True)
                    logger.info(f"Inserted 2000 records batch: {time.time() - t1:.4f}s")
                    total_new_records += len(batch)
                    batch = []
                    t_fetch = time.time()
            if batch:
                t1 = time.time()
                target_model.objects.bulk_create(batch, ignore_conflicts=True)
                logger.info(f"Inserted final {len(batch)} records batch: {time.time() - t1:.4f}s")
                total_new_records += len(batch)
        deleted_rows = DBOAuditSfDeletedRows.objects.filter(TableName=to_snake_case(target_model_name),
                                                            DeletedDate__gte=current_time - timedelta(days=7))
        deleted_records_count = deleted_rows.count()
        logging.info(
            f"Deleted {deleted_records_count} records from {target_model_name}: {to_snake_case(target_model_name)}")
        deleted_rp_list = list(deleted_rows.values_list('DeletedRP', flat=True))
        if deleted_rp_list:
            target_model.objects.filter(RowPointer__in=deleted_rp_list).delete()
        # if deleted_rows.exists():
        #     for row in deleted_rows:
        #         try:
        #             target_model.objects.filter(RowPointer=row.DeletedRP).delete()
        #         except Exception as e:
        #             logging.error(
        #                 f"Error deleting record with RowPointer {row.DeletedRP} from {target_model_name}: {e}")
        ModelSyncManager.objects.create(
            table=target_model._meta.db_table,
            last_synced=current_time,
            model=target_model.__name__,
            task_id=task_id,
            source_table=source_model._meta.db_table,
        )
    except Exception as e:
        logger.info(f"Error during sync: {e}")
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            'SOFTLAND_SYNC_ALERT',
            {
                "type": "task_notification",
                "message": f"Sync error: {str(e)}",
                "timestamp": datetime.now().isoformat(),
                "alert_type": "error",
            }
        )
        return None, None
    return total_new_records, total_updated_records


def send_low_stock_alert(items, users):
    try:
        notification_type = NotificationType.objects.get(name='Low stock')
        for user in users:
            for item in items:
                Notification.objects.update_or_create(
                    recipient=user, notification_type=notification_type,
                    title="Low stock: item %s" % item.ARTICULO,
                    message="Below ROP in {} (current: {:,.2f}, ROP: {:,.2f})".format(item.BODEGA, item.CANT_DISPONIBLE,
                                                                                      item.PUNTO_DE_REORDEN),
                    defaults={
                        "alert_type": "warning",
                        "timestamp": datetime.now(),
                    }
                )
    except NotificationType.DoesNotExist:
        pass


def send_new_requirement_alert(items, users):
    try:
        notification_type = NotificationType.objects.get(name='Requirement')
        for user in users:
            for requirement in items:
                Notification.objects.update_or_create(
                    recipient=user, notification_type=notification_type,
                    title="New Requirement: %s" % requirement.SOLICITUD_OC,
                    defaults={
                        "message": "Submitted, Approval pending!",
                        "alert_type": "success",
                        "timestamp": datetime.now(),
                    }
                )
    except NotificationType.DoesNotExist:
        pass


def send_approved_requirement_alert(items, users):
    try:
        notification_type = NotificationType.objects.get(name='Requirement')
        for user in users:
            for requirement in items:
                Notification.objects.update_or_create(
                    recipient=user, notification_type=notification_type,
                    title="Requirement Approved: %s" % requirement.SOLICITUD_OC,
                    defaults={
                        "message": "Approved, PO pending!",
                        "alert_type": "info",
                        "timestamp": datetime.now(),
                    }
                )
    except NotificationType.DoesNotExist:
        pass


def send_rejected_requirement_alert(items, users):
    try:
        notification_type = NotificationType.objects.get(name='Requirement')
        for user in users:
            for requirement in items:
                Notification.objects.update_or_create(
                    recipient=user, notification_type=notification_type,
                    title="Requirement Rejected: %s" % requirement.SOLICITUD_OC,
                    defaults={
                        "message": "Rejected, Please review!",
                        "alert_type": "error",
                        "timestamp": datetime.now(),
                    }
                )
    except NotificationType.DoesNotExist:
        pass


def send_cancelled_requirement_alert(items, users):
    try:
        notification_type = NotificationType.objects.get(name='Requirement')
        for user in users:
            for requirement in items:
                Notification.objects.update_or_create(
                    recipient=user, notification_type=notification_type,
                    title="Requirement Cancelled: %s" % requirement.SOLICITUD_OC,
                    defaults={
                        "message": "Cancelled, Please review!",
                        "alert_type": "warning",
                        "timestamp": datetime.now(),
                    }
                )
    except NotificationType.DoesNotExist:
        pass


def send_new_po_alert(items, users):
    try:
        notification_type = NotificationType.objects.get(name='Purchase Order')
        for user in users:
            for item in items:
                Notification.objects.update_or_create(
                    recipient=user, notification_type=notification_type,
                    title="New Purchase Order: %s" % item.ORDEN_COMPRA,
                    defaults={
                        "message": "Submitted, Approval pending!",
                        "alert_type": "success",
                        "timestamp": datetime.now(),
                    }
                )
    except NotificationType.DoesNotExist:
        pass


def send_overdue_po_alert(items, users):
    try:
        notification_type = NotificationType.objects.get(name='Purchase Order')
        for user in users:
            for item in items:
                Notification.objects.update_or_create(
                    recipient=user, notification_type=notification_type,
                    title="Purchase Order Overdue: %s" % item.ORDEN_COMPRA,
                    defaults={
                        "message": "Purchase Order Overdue since {} days!".format(item.overdue_days),
                        "alert_type": "warning",
                        "timestamp": datetime.now(),
                    }
                )
    except NotificationType.DoesNotExist:
        pass


def order_qty_alert(items, users):
    try:
        notification_type = NotificationType.objects.get(name='Purchase Order')
        for user in users:
            for item in items:
                Notification.objects.update_or_create(
                    recipient=user, notification_type=notification_type,
                    title="Order Quantity Alert: %s, %s" % (item['ARTICULO'], item['order_alert']),
                    defaults={
                        "message": "Ordered: {}, Required: {:.0f}".format(item['planned_qty'], item['reorder_qty']),
                        "alert_type": "warning",
                        "timestamp": datetime.now(),
                    }
                )
    except NotificationType.DoesNotExist:
        pass


def send_approved_po_alert(items, users):
    try:
        notification_type = NotificationType.objects.get(name='Purchase Order')
        for user in users:
            for item in items:
                Notification.objects.update_or_create(
                    recipient=user, notification_type=notification_type,
                    title="Purchase Order Approved: %s" % item.ORDEN_COMPRA,
                    defaults={
                        "message": "Approved, Shipment pending!",
                        "alert_type": "info",
                        "timestamp": datetime.now(),
                    }
                )
    except NotificationType.DoesNotExist:
        pass


def send_rejected_po_alert(items, users):
    try:
        notification_type = NotificationType.objects.get(name='Purchase Order')
        for user in users:
            for item in items:
                Notification.objects.update_or_create(
                    recipient=user, notification_type=notification_type,
                    title="Purchase Order Rejected: %s" % item.ORDEN_COMPRA,
                    defaults={
                        "message": "Rejected, Please review!",
                        "alert_type": "error",
                        "timestamp": datetime.now(),
                    }
                )
    except NotificationType.DoesNotExist:
        pass


def send_cancelled_po_alert(items, users):
    try:
        notification_type = NotificationType.objects.get(name='Purchase Order')
        for user in users:
            for item in items:
                Notification.objects.update_or_create(
                    recipient=user, notification_type=notification_type,
                    title="Purchase Order Cancelled: %s" % item.ORDEN_COMPRA,
                    defaults={
                        "message": "Cancelled, Please review!",
                        "alert_type": "warning",
                        "timestamp": datetime.now(),
                    }
                )
    except NotificationType.DoesNotExist:
        pass


def send_new_shipment_alert(items, users):
    try:
        notification_type = NotificationType.objects.get(name='Shipment')
        for user in users:
            for item in items:
                Notification.objects.update_or_create(
                    recipient=user, notification_type=notification_type,
                    title="New Shipment: %s" % item.EMBARQUE,
                    defaults={
                        "message": "Submitted, Approval pending!",
                        "alert_type": "success",
                        "timestamp": datetime.now(),
                    }
                )
    except NotificationType.DoesNotExist:
        pass


def send_approved_shipment_alert(items, users):
    try:
        notification_type = NotificationType.objects.get(name='Shipment')
        for user in users:
            for item in items:
                Notification.objects.update_or_create(
                    recipient=user, notification_type=notification_type,
                    title="Shipment Approved: %s" % item.EMBARQUE,
                    defaults={
                        "message": "Approved, In Transit!",
                        "alert_type": "info",
                        "timestamp": datetime.now(),
                    }
                )
    except NotificationType.DoesNotExist:
        pass


def send_cancelled_shipment_alert(items, users):
    try:
        notification_type = NotificationType.objects.get(name='Shipment')
        for user in users:
            for item in items:
                Notification.objects.update_or_create(
                    recipient=user, notification_type=notification_type,
                    title="Shipment Cancelled: %s" % item.EMBARQUE,
                    defaults={
                        "message": "Cancelled, Please review!",
                        "alert_type": "warning",
                        "timestamp": datetime.now(),
                    }
                )
    except NotificationType.DoesNotExist:
        pass


def send_rejected_shipment_alert(items, users):
    try:
        notification_type = NotificationType.objects.get(name='Shipment')
        for user in users:
            for item in items:
                Notification.objects.update_or_create(
                    recipient=user, notification_type=notification_type,
                    title="Shipment Rejected: %s" % item.EMBARQUE,
                    defaults={
                        "message": "Rejected, Please review!",
                        "alert_type": "error",
                        "timestamp": datetime.now(),
                    }
                )
    except NotificationType.DoesNotExist:
        pass


def send_softland_sync_alert(module: str):
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        'SOFTLAND_SYNC_ALERT',
        {
            "type": "task_notification",
            "message": "{}: sync completed".format(module),
            "timestamp": datetime.now().isoformat(),
            "alert_type": "info",
        }
    )

def send_audit_item_log_alert(items, users):
    try:
        notification_type = NotificationType.objects.get(name='Audit')
        for user in users:
            for item in items:
                Notification.objects.update_or_create(
                    recipient=user, notification_type=notification_type,
                    title="New Audit Logged: %s" % item.AUDIT_TRANS_INV,
                    defaults={
                        "message": "Consecutivo: %s, APLICACION: %s, Ref: %s" % (item.CONSECUTIVO, item.APLICACION,
                                                                                 item.REFERENCIA),
                        "alert_type": "success",
                        "timestamp": datetime.now(),
                    }
                )
    except NotificationType.DoesNotExist:
        pass

def send_new_stocktransfer_alert(items, users):
    try:
        notification_type = NotificationType.objects.get(name='Stock Transfer')
        for user in users:
            for item in items:
                Notification.objects.update_or_create(
                    recipient=user, notification_type=notification_type,
                    title="New Stock Transfer: %s" % item.DOCUMENTO_INV,
                    defaults={
                        "message": "Consecutivo: %s, Aprobado: %s" % (item.CONSECUTIVO,
                                                                      'Si' if item.APROBADO == 'S' else 'No'),
                        "alert_type": "success",
                        "timestamp": datetime.now(),
                    }
                )
    except NotificationType.DoesNotExist:
        pass


def send_approved_stocktransfer_alert(items, users):
    try:
        notification_type = NotificationType.objects.get(name='Stock Transfer')
        for user in users:
            for item in items:
                Notification.objects.update_or_create(
                    recipient=user, notification_type=notification_type,
                    title="Stock Transfer Approved: %s" % item.DOCUMENTO_INV,
                    defaults={
                        "message": "Approved, Waiting for Application!",
                        "alert_type": "info",
                        "timestamp": datetime.now(),
                    }
                )
    except NotificationType.DoesNotExist:
        pass


def send_cancelled_stocktransfer_alert(items, users):
    try:
        notification_type = NotificationType.objects.get(name='Stock Transfer')
        for user in users:
            for item in items:
                Notification.objects.update_or_create(
                    recipient=user, notification_type=notification_type,
                    title="Stock Transfer Cancelled: %s" % item.DOCUMENTO_INV,
                    defaults={
                        "message": "Cancelled, Please review!",
                        "alert_type": "warning",
                        "timestamp": datetime.now(),
                    }
                )
    except NotificationType.DoesNotExist:
        pass


def send_rejected_stocktransfer_alert(items, users):
    try:
        notification_type = NotificationType.objects.get(name='Stock Transfer')
        for user in users:
            for item in items:
                Notification.objects.update_or_create(
                    recipient=user, notification_type=notification_type,
                    title="Stock Transfer Rejected: %s" % item.DOCUMENTO_INV,
                    defaults={
                        "message": "Rejected, Please review!",
                        "alert_type": "error",
                        "timestamp": datetime.now(),
                    }
                )
    except NotificationType.DoesNotExist:
        pass


def send_applied_stocktransfer_alert(items, users):
    try:
        notification_type = NotificationType.objects.get(name='Stock Transfer')
        for user in users:
            for item in items:
                Notification.objects.update_or_create(
                    recipient=user, notification_type=notification_type,
                    title="Stock Transfer Applied: %s" % item,
                    defaults={
                        "message": "Stock transfer applied successfully!",
                        "alert_type": "info",
                        "timestamp": datetime.now(),
                    }
                )
    except NotificationType.DoesNotExist:
        pass


def get_forecast_reviews(existing_stock, forecast_total: float) -> dict:
    available_perc = existing_stock / forecast_total
    review = {"message": "Sufficient stocks available", "level": "good",
              "available_percentage": available_perc * 100, "forecast_total": forecast_total,
              "existing_stock": existing_stock}
    if available_perc > 1.5:
        review = {"message": "Item over stocked", "level": "over stock",
                  "available_percentage": available_perc * 100, "forecast_total": forecast_total,
                  "existing_stock": existing_stock}
    if available_perc < 0.8:
        review = {"message": "Item needs reordering", "level": "low stock",
                  "available_percentage": available_perc * 100, "forecast_total": forecast_total,
                  "existing_stock": existing_stock}
    if available_perc < 0.4:
        review = {"message": "Item needs urgent reordering", "level": "critical",
                  "available_percentage": available_perc * 100, "forecast_total": forecast_total,
                  "existing_stock": existing_stock}
    if available_perc < 0:
        review = {"message": "Sufficient stocks available", "level": "good",
                  "available_percentage": 100.00, "forecast_total": 0,
                  "existing_stock": existing_stock}
    return review


def send_new_cycle_count_alert(items, users):
    try:
        notification_type = NotificationType.objects.get(name='Cycle Count')
        for user in users:
            for item in items:
                Notification.objects.update_or_create(
                    recipient=user, notification_type=notification_type,
                    title=f"New Cycle Count batch: CYCB-{item.id:05d}",
                    defaults={
                        "message": "Scheduled on: {}".format(item.scheduled_date.strftime("%Y-%m-%d")),
                        "alert_type": "success",
                        "timestamp": datetime.now(),
                    }
                )
    except NotificationType.DoesNotExist:
        pass


def send_applied_cycle_count_alert(items, users):
    try:
        notification_type = NotificationType.objects.get(name='Cycle Count')
        for user in users:
            for item in items:
                Notification.objects.update_or_create(
                    recipient=user, notification_type=notification_type,
                    title=f"Cycle Count batch completed: CYCB-{item.id:05d}",
                    defaults={
                        "message": "Check Document INV({}) in ERP and apply!".format(item.document_number),
                        "alert_type": "info",
                        "timestamp": datetime.now(),
                    }
                )
    except NotificationType.DoesNotExist:
        pass
