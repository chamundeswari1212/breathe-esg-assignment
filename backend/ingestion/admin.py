from django.contrib import admin
from .models import Tenant, DataSource, ImportBatch, RawRecord, EmissionRecord, AuditLog


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = ['company_name', 'industry', 'country', 'created_at']


@admin.register(DataSource)
class DataSourceAdmin(admin.ModelAdmin):
    list_display = ['tenant', 'source_type', 'ingestion_mode', 'created_at']
    list_filter = ['source_type']


@admin.register(ImportBatch)
class ImportBatchAdmin(admin.ModelAdmin):
    list_display = ['original_filename', 'tenant', 'data_source', 'status',
                    'total_rows', 'accepted_rows', 'failed_rows', 'uploaded_at']
    list_filter = ['status', 'data_source__source_type']


@admin.register(RawRecord)
class RawRecordAdmin(admin.ModelAdmin):
    list_display = ['id', 'import_batch', 'row_number', 'parse_status']
    list_filter = ['parse_status']


@admin.register(EmissionRecord)
class EmissionRecordAdmin(admin.ModelAdmin):
    list_display = ['id', 'source_type', 'activity_type', 'quantity_normalized',
                    'unit_normalized', 'scope', 'confidence', 'review_status', 'created_at']
    list_filter = ['source_type', 'scope', 'confidence', 'review_status']
    search_fields = ['activity_type', 'source_record_id']


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ['emission_record', 'action', 'actor', 'timestamp']
    list_filter = ['action']