from django.db import models
from django.utils import timezone


class Tenant(models.Model):
    """
    Multi-tenancy anchor. Every data record belongs to a tenant.
    In production this would integrate with an auth/org system.
    For the prototype, we seed one default tenant.
    """
    company_name = models.CharField(max_length=255)
    industry = models.CharField(max_length=100, blank=True, default='')
    country = models.CharField(max_length=100, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.company_name


class DataSource(models.Model):
    """
    Registered data source configuration for a tenant.
    Tracks what type of source (SAP, Utility, Travel) and how it's ingested.
    """
    SOURCE_TYPE_CHOICES = [
        ('SAP', 'SAP Fuel & Procurement'),
        ('UTILITY', 'Utility Electricity'),
        ('TRAVEL', 'Corporate Travel'),
    ]
    INGESTION_MODE_CHOICES = [
        ('CSV_UPLOAD', 'CSV File Upload'),
        ('API_STUB', 'API Integration (stub)'),
        ('MANUAL', 'Manual Entry'),
    ]

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='data_sources')
    source_type = models.CharField(max_length=20, choices=SOURCE_TYPE_CHOICES)
    ingestion_mode = models.CharField(max_length=20, choices=INGESTION_MODE_CHOICES, default='CSV_UPLOAD')
    description = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['tenant', 'source_type']

    def __str__(self):
        return f"{self.tenant.company_name} — {self.get_source_type_display()}"


class ImportBatch(models.Model):
    """
    Tracks each file upload / ingestion run.
    Source of truth for "what came in" — links to all raw and normalized rows.
    """
    STATUS_CHOICES = [
        ('PROCESSING', 'Processing'),
        ('COMPLETED', 'Completed'),
        ('COMPLETED_WITH_ERRORS', 'Completed with Errors'),
        ('FAILED', 'Failed'),
    ]

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='import_batches')
    data_source = models.ForeignKey(DataSource, on_delete=models.CASCADE, related_name='import_batches')
    original_filename = models.CharField(max_length=500)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='PROCESSING')
    total_rows = models.IntegerField(default=0)
    accepted_rows = models.IntegerField(default=0)
    failed_rows = models.IntegerField(default=0)

    class Meta:
        ordering = ['-uploaded_at']

    def __str__(self):
        return f"{self.original_filename} ({self.status})"


class RawRecord(models.Model):
    """
    Stores every row exactly as uploaded — immutable source of truth.
    raw_json preserves the original CSV row as a dict.
    parse_status tracks whether normalization succeeded or failed.
    """
    PARSE_STATUS_CHOICES = [
        ('RAW', 'Raw (not yet processed)'),
        ('NORMALIZED', 'Successfully Normalized'),
        ('FAILED', 'Failed to Normalize'),
    ]

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='raw_records')
    import_batch = models.ForeignKey(ImportBatch, on_delete=models.CASCADE, related_name='raw_records')
    row_number = models.IntegerField()
    raw_json = models.JSONField()
    parse_status = models.CharField(max_length=20, choices=PARSE_STATUS_CHOICES, default='RAW')
    error_message = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['row_number']

    def __str__(self):
        return f"Row {self.row_number} — {self.parse_status}"


class EmissionRecord(models.Model):
    """
    Normalized emission activity row — the core analyst-facing record.
    Created from a RawRecord after source-specific normalization.
    Tracks original and normalized quantities, scope, confidence, flags,
    review status, and audit locking.
    """
    SOURCE_TYPE_CHOICES = [
        ('SAP', 'SAP'),
        ('UTILITY', 'Utility'),
        ('TRAVEL', 'Travel'),
    ]
    SCOPE_CHOICES = [
        ('Scope 1', 'Scope 1 — Direct Emissions'),
        ('Scope 2', 'Scope 2 — Indirect (Electricity)'),
        ('Scope 3', 'Scope 3 — Value Chain'),
    ]
    CONFIDENCE_CHOICES = [
        ('HIGH', 'High'),
        ('MEDIUM', 'Medium'),
        ('LOW', 'Low'),
    ]
    REVIEW_STATUS_CHOICES = [
        ('NEEDS_REVIEW', 'Needs Review'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
        ('FLAGGED', 'Flagged'),
        ('LOCKED', 'Locked for Audit'),
    ]

    # Lineage
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='emission_records')
    import_batch = models.ForeignKey(ImportBatch, on_delete=models.CASCADE, related_name='emission_records')
    raw_record = models.OneToOneField(RawRecord, on_delete=models.CASCADE, related_name='emission_record', null=True, blank=True)

    # Source identification
    source_type = models.CharField(max_length=20, choices=SOURCE_TYPE_CHOICES)
    source_record_id = models.CharField(max_length=100, blank=True, default='',
                                         help_text='Original record ID from source system (e.g. SAP document number)')

    # Activity
    activity_type = models.CharField(max_length=200)
    category = models.CharField(max_length=100, blank=True, default='')
    period_start = models.DateField(null=True, blank=True)
    period_end = models.DateField(null=True, blank=True)

    # Quantities — preserve original and normalized
    quantity_original = models.FloatField()
    unit_original = models.CharField(max_length=50)
    quantity_normalized = models.FloatField()
    unit_normalized = models.CharField(max_length=50)

    # Classification
    scope = models.CharField(max_length=10, choices=SCOPE_CHOICES)

    # Location context — flexible JSON for source-specific fields
    # SAP: {"plant_code": "PL01"}, Utility: {"meter_id": "MTR001"}, Travel: {"origin": "DEL", "destination": "LHR"}
    location_details = models.JSONField(default=dict, blank=True)

    # Emissions estimate
    emission_factor_source = models.CharField(max_length=200, blank=True, default='')
    estimated_emissions_kgco2e = models.FloatField(null=True, blank=True)

    # Confidence and flags
    confidence = models.CharField(max_length=10, choices=CONFIDENCE_CHOICES, default='HIGH')
    flags = models.JSONField(default=list, blank=True,
                             help_text='List of flag strings, e.g. ["missing_plant", "zero_quantity"]')

    # Review workflow
    review_status = models.CharField(max_length=20, choices=REVIEW_STATUS_CHOICES, default='NEEDS_REVIEW')
    analyst_notes = models.TextField(blank=True, default='')

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    locked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.source_type} — {self.activity_type} ({self.review_status})"

    @property
    def is_locked(self):
        return self.review_status == 'LOCKED'


class AuditLog(models.Model):
    """
    Immutable audit trail. Every review action (approve, reject, edit, lock)
    creates a log entry with before/after snapshots.
    Actor is a simple string — no full auth in this prototype.
    """
    ACTION_CHOICES = [
        ('CREATED', 'Record Created'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
        ('FLAGGED', 'Flagged'),
        ('EDITED', 'Edited'),
        ('LOCKED', 'Locked for Audit'),
    ]

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='audit_logs')
    emission_record = models.ForeignKey(EmissionRecord, on_delete=models.CASCADE, related_name='audit_logs')
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    before_json = models.JSONField(null=True, blank=True)
    after_json = models.JSONField(null=True, blank=True)
    actor = models.CharField(max_length=100, default='analyst',
                              help_text='Simplified actor field — production would use auth user')
    timestamp = models.DateTimeField(auto_now_add=True)
    note = models.TextField(blank=True, default='')

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.action} — Record #{self.emission_record_id} — {self.timestamp}"