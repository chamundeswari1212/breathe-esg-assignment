from rest_framework import serializers
from .models import (
    Tenant, DataSource, ImportBatch, RawRecord, EmissionRecord, AuditLog
)


class TenantSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tenant
        fields = ['id', 'company_name', 'industry', 'country', 'created_at']


class DataSourceSerializer(serializers.ModelSerializer):
    source_type_display = serializers.CharField(source='get_source_type_display', read_only=True)

    class Meta:
        model = DataSource
        fields = ['id', 'tenant', 'source_type', 'source_type_display',
                  'ingestion_mode', 'description', 'created_at']


class ImportBatchSerializer(serializers.ModelSerializer):
    source_type = serializers.CharField(source='data_source.source_type', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = ImportBatch
        fields = ['id', 'tenant', 'data_source', 'source_type', 'original_filename',
                  'uploaded_at', 'status', 'status_display', 'total_rows',
                  'accepted_rows', 'failed_rows']


class RawRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = RawRecord
        fields = ['id', 'tenant', 'import_batch', 'row_number', 'raw_json',
                  'parse_status', 'error_message', 'created_at']


class EmissionRecordSerializer(serializers.ModelSerializer):
    """Full serializer for emission records in the review queue."""
    scope_display = serializers.CharField(source='get_scope_display', read_only=True)
    confidence_display = serializers.CharField(source='get_confidence_display', read_only=True)
    review_status_display = serializers.CharField(source='get_review_status_display', read_only=True)
    raw_json = serializers.SerializerMethodField()

    class Meta:
        model = EmissionRecord
        fields = [
            'id', 'tenant', 'import_batch', 'raw_record',
            'source_type', 'source_record_id',
            'activity_type', 'category',
            'period_start', 'period_end',
            'quantity_original', 'unit_original',
            'quantity_normalized', 'unit_normalized',
            'scope', 'scope_display',
            'location_details',
            'emission_factor_source', 'estimated_emissions_kgco2e',
            'confidence', 'confidence_display',
            'flags',
            'review_status', 'review_status_display',
            'analyst_notes',
            'created_at', 'updated_at', 'locked_at',
            'raw_json',
        ]
        read_only_fields = [
            'id', 'tenant', 'import_batch', 'raw_record',
            'source_type', 'source_record_id',
            'activity_type', 'category',
            'period_start', 'period_end',
            'quantity_original', 'unit_original',
            'quantity_normalized', 'unit_normalized',
            'scope', 'location_details',
            'emission_factor_source', 'estimated_emissions_kgco2e',
            'created_at', 'updated_at', 'locked_at',
            'raw_json',
        ]

    def get_raw_json(self, obj):
        if obj.raw_record:
            return obj.raw_record.raw_json
        return None


class EmissionRecordUpdateSerializer(serializers.ModelSerializer):
    """Restricted serializer for analyst edits — only notes and confidence."""
    class Meta:
        model = EmissionRecord
        fields = ['analyst_notes', 'confidence']


class AuditLogSerializer(serializers.ModelSerializer):
    action_display = serializers.CharField(source='get_action_display', read_only=True)
    record_summary = serializers.SerializerMethodField()

    class Meta:
        model = AuditLog
        fields = ['id', 'tenant', 'emission_record', 'action', 'action_display',
                  'before_json', 'after_json', 'actor', 'timestamp', 'note',
                  'record_summary']

    def get_record_summary(self, obj):
        rec = obj.emission_record
        return f"{rec.source_type}: {rec.activity_type}"