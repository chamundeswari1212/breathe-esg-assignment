from django.urls import path
from .views import (
    list_tenants,
    list_import_batches,
    upload_csv,
    list_records,
    record_detail,
    approve_record,
    reject_record,
    lock_record,
    list_raw_records,
    list_audit_logs,
    summary,
)

urlpatterns = [
    path('tenants/', list_tenants, name='list-tenants'),
    path('import-batches/', list_import_batches, name='list-import-batches'),
    path('upload/', upload_csv, name='upload-csv'),
    path('records/', list_records, name='list-records'),
    path('records/<int:id>/', record_detail, name='record-detail'),
    path('records/<int:id>/approve/', approve_record, name='approve-record'),
    path('records/<int:id>/reject/', reject_record, name='reject-record'),
    path('records/<int:id>/lock/', lock_record, name='lock-record'),
    path('raw-records/', list_raw_records, name='list-raw-records'),
    path('audit/', list_audit_logs, name='list-audit-logs'),
    path('summary/', summary, name='summary'),
]