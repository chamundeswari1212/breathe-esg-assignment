"""
API views for the ESG ingestion platform.

Endpoints:
- GET  /api/tenants/                  — List tenants
- GET  /api/import-batches/           — List import batches
- POST /api/upload/                   — Upload a CSV file
- GET  /api/records/                  — List emission records (filterable)
- GET  /api/records/{id}/             — Single record detail
- PATCH /api/records/{id}/            — Edit record (notes, confidence)
- POST /api/records/{id}/approve/     — Approve a record
- POST /api/records/{id}/reject/      — Reject a record
- POST /api/records/{id}/lock/        — Lock an approved record
- GET  /api/raw-records/              — List raw records for a batch
- GET  /api/audit/                    — List audit logs
- GET  /api/summary/                  — Dashboard summary counts
"""
import csv
import io
import json

from django.db.models import Q, Count
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .models import (
    Tenant, DataSource, ImportBatch, RawRecord, EmissionRecord, AuditLog
)
from .serializers import (
    TenantSerializer, ImportBatchSerializer, RawRecordSerializer,
    EmissionRecordSerializer, EmissionRecordUpdateSerializer,
    AuditLogSerializer,
)
from .normalizers import get_normalizer


# ---------------------------------------------------------------------------
# API Root
# ---------------------------------------------------------------------------
@api_view(['GET'])
def api_root(request):
    return Response({
        'message': 'ESG ingestion API',
        'endpoints': {
            'tenants': 'tenants/',
            'import_batches': 'import-batches/',
            'upload': 'upload/',
            'records': 'records/',
            'raw_records': 'raw-records/',
            'audit': 'audit/',
            'summary': 'summary/',
        },
    })


# ---------------------------------------------------------------------------
# Tenants
# ---------------------------------------------------------------------------
@api_view(['GET'])
def list_tenants(request):
    # Hide the placeholder default tenant once real tenants are seeded.
    tenants = Tenant.objects.exclude(company_name='Default Tenant')
    if tenants.exists():
        serializer = TenantSerializer(tenants, many=True)
        return Response(serializer.data)

    # If only the placeholder/default tenant exists on the deployed DB,
    # return a stable demo list so the UI shows the expected companies.
    # This avoids forcing database seeding during demos.
    demo_list = [
        {'id': -1, 'company_name': 'Acme Corp', 'industry': '', 'country': '', 'created_at': None},
        {'id': -2, 'company_name': 'BlueGrid Energy', 'industry': '', 'country': '', 'created_at': None},
        {'id': -3, 'company_name': 'GreenMiles Logistics', 'industry': '', 'country': '', 'created_at': None},
    ]
    return Response(demo_list)


# ---------------------------------------------------------------------------
# Import Batches
# ---------------------------------------------------------------------------
@api_view(['GET'])
def list_import_batches(request):
    tenant_id = request.query_params.get('tenant')
    qs = ImportBatch.objects.select_related('data_source').all()
    
    # Handle demo tenant IDs by mapping to real tenant
    if tenant_id:
        demo_tenant_map = {
            '-1': 'Acme Corp',
            '-2': 'BlueGrid Energy',
            '-3': 'GreenMiles Logistics',
        }
        if str(tenant_id) in demo_tenant_map:
            tenant_name = demo_tenant_map[str(tenant_id)]
            try:
                real_tenant = Tenant.objects.get(company_name=tenant_name)
                qs = qs.filter(tenant_id=real_tenant.id)
            except Tenant.DoesNotExist:
                # Tenant doesn't exist yet, return empty
                pass
        else:
            qs = qs.filter(tenant_id=tenant_id)
    serializer = ImportBatchSerializer(qs, many=True)
    return Response(serializer.data)


# ---------------------------------------------------------------------------
# Upload CSV
# ---------------------------------------------------------------------------
@api_view(['POST'])
def upload_csv(request):
    """
    Upload a CSV file for ingestion.
    Expects: file, source_type (SAP|UTILITY|TRAVEL), tenant_id
    """
    file = request.FILES.get('file')
    source_type = request.data.get('source_type', '').upper()
    tenant_id = request.data.get('tenant_id')

    # Validate inputs
    if not file:
        return Response({'error': 'No file provided'}, status=status.HTTP_400_BAD_REQUEST)
    if source_type not in ('SAP', 'UTILITY', 'TRAVEL'):
        return Response({'error': f'Invalid source_type: {source_type}'}, status=status.HTTP_400_BAD_REQUEST)
    if not tenant_id:
        return Response({'error': 'tenant_id is required'}, status=status.HTTP_400_BAD_REQUEST)

    # Handle demo tenant IDs (negative) by creating/fetching real Tenant objects
    demo_tenant_map = {
        -1: 'Acme Corp',
        -2: 'BlueGrid Energy',
        -3: 'GreenMiles Logistics',
    }
    
    if int(tenant_id) in demo_tenant_map:
        # Create or get the real Tenant for this demo ID
        tenant, _ = Tenant.objects.get_or_create(
            company_name=demo_tenant_map[int(tenant_id)],
            defaults={'industry': '', 'country': ''}
        )
    else:
        try:
            tenant = Tenant.objects.get(id=tenant_id)
        except Tenant.DoesNotExist:
            return Response({'error': 'Tenant not found'}, status=status.HTTP_404_NOT_FOUND)

    # Get or create DataSource
    data_source, _ = DataSource.objects.get_or_create(
        tenant=tenant,
        source_type=source_type,
        defaults={'ingestion_mode': 'CSV_UPLOAD'}
    )

    # Create ImportBatch
    batch = ImportBatch.objects.create(
        tenant=tenant,
        data_source=data_source,
        original_filename=file.name,
        status='PROCESSING',
    )

    # Read CSV
    try:
        content = file.read().decode('utf-8-sig')  # Handle BOM
        reader = csv.DictReader(io.StringIO(content))
        rows = list(reader)
    except Exception as e:
        batch.status = 'FAILED'
        batch.save()
        return Response({'error': f'Failed to read CSV: {str(e)}'}, status=status.HTTP_400_BAD_REQUEST)

    if not rows:
        batch.status = 'FAILED'
        batch.save()
        return Response({'error': 'CSV file is empty'}, status=status.HTTP_400_BAD_REQUEST)

    # Get normalizer
    try:
        normalizer = get_normalizer(source_type)
    except ValueError as e:
        batch.status = 'FAILED'
        batch.save()
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    # Process rows
    seen_in_batch = set()
    accepted = 0
    failed = 0
    flagged = 0

    for row_num, row_data in enumerate(rows, start=1):
        # Clean row data — remove empty string keys
        clean_data = {k.strip(): v.strip() if isinstance(v, str) else v
                      for k, v in row_data.items() if k and k.strip()}

        # Create RawRecord
        raw_record = RawRecord.objects.create(
            tenant=tenant,
            import_batch=batch,
            row_number=row_num,
            raw_json=clean_data,
            parse_status='RAW',
        )

        # Normalize
        try:
            result = normalizer.normalize_row(clean_data)
        except Exception as e:
            raw_record.parse_status = 'FAILED'
            raw_record.error_message = f"Normalizer exception: {str(e)}"
            raw_record.save()
            failed += 1
            continue

        if result.get('error') or not result.get('fields'):
            raw_record.parse_status = 'FAILED'
            raw_record.error_message = result.get('error', 'Normalization returned no fields')
            raw_record.save()
            failed += 1
            continue

        # Utility duplicate billing detection
        if source_type == 'UTILITY' and result.get('fields'):
            fields = result['fields']
            m_id = fields.get('location_details', {}).get('meter_id')
            p_start = fields.get('period_start')
            p_end = fields.get('period_end')

            if m_id and p_start and p_end:
                in_batch = (m_id, p_start, p_end) in seen_in_batch
                in_db = EmissionRecord.objects.filter(
                    tenant=tenant,
                    source_type='UTILITY',
                    location_details__meter_id=m_id,
                    period_start=p_start,
                    period_end=p_end
                ).exists()

                if in_batch or in_db:
                    if 'duplicate_meter_period' not in result.setdefault('flags', []):
                        result['flags'].append('duplicate_meter_period')
                    result['confidence'] = 'LOW'

                seen_in_batch.add((m_id, p_start, p_end))

        # Create EmissionRecord
        fields = result['fields']
        record_flags = result.get('flags', [])
        confidence = result.get('confidence', 'HIGH')

        review_status = 'NEEDS_REVIEW'
        if record_flags:
            review_status = 'FLAGGED'
            flagged += 1

        emission_record = EmissionRecord.objects.create(
            tenant=tenant,
            import_batch=batch,
            raw_record=raw_record,
            source_type=fields.get('source_type', source_type),
            source_record_id=fields.get('source_record_id', ''),
            activity_type=fields.get('activity_type', ''),
            category=fields.get('category', ''),
            period_start=fields.get('period_start'),
            period_end=fields.get('period_end'),
            quantity_original=fields.get('quantity_original', 0),
            unit_original=fields.get('unit_original', ''),
            quantity_normalized=fields.get('quantity_normalized', 0),
            unit_normalized=fields.get('unit_normalized', ''),
            scope=fields.get('scope', ''),
            location_details=fields.get('location_details', {}),
            emission_factor_source=fields.get('emission_factor_source', ''),
            estimated_emissions_kgco2e=fields.get('estimated_emissions_kgco2e'),
            confidence=confidence,
            flags=record_flags,
            review_status=review_status,
        )

        # Mark raw as normalized
        raw_record.parse_status = 'NORMALIZED'
        raw_record.save()

        # Create audit log entry
        AuditLog.objects.create(
            tenant=tenant,
            emission_record=emission_record,
            action='CREATED',
            after_json=EmissionRecordSerializer(emission_record).data,
            actor='system',
            note=f'Imported from {file.name}, row {row_num}',
        )

        accepted += 1

    # Update batch
    batch.total_rows = len(rows)
    batch.accepted_rows = accepted
    batch.failed_rows = failed
    if failed == 0:
        batch.status = 'COMPLETED'
    elif accepted == 0:
        batch.status = 'FAILED'
    else:
        batch.status = 'COMPLETED_WITH_ERRORS'
    batch.save()

    return Response({
        'batch_id': batch.id,
        'filename': file.name,
        'source_type': source_type,
        'total_rows': len(rows),
        'accepted': accepted,
        'failed': failed,
        'flagged': flagged,
        'status': batch.status,
    })


# ---------------------------------------------------------------------------
# Emission Records
# ---------------------------------------------------------------------------
@api_view(['GET'])
def list_records(request):
    """List emission records with optional filters."""
    tenant_id = request.query_params.get('tenant')
    source_type = request.query_params.get('source_type')
    scope = request.query_params.get('scope')
    review_status = request.query_params.get('review_status')
    confidence = request.query_params.get('confidence')
    batch_id = request.query_params.get('batch')
    search = request.query_params.get('search')

    qs = EmissionRecord.objects.select_related('raw_record').all()

    # Handle demo tenant IDs by mapping to real tenant
    if tenant_id:
        demo_tenant_map = {
            '-1': 'Acme Corp',
            '-2': 'BlueGrid Energy',
            '-3': 'GreenMiles Logistics',
        }
        if str(tenant_id) in demo_tenant_map:
            tenant_name = demo_tenant_map[str(tenant_id)]
            try:
                real_tenant = Tenant.objects.get(company_name=tenant_name)
                qs = qs.filter(tenant_id=real_tenant.id)
            except Tenant.DoesNotExist:
                # Tenant doesn't exist yet, return empty
                pass
        else:
            qs = qs.filter(tenant_id=tenant_id)
    if source_type:
        qs = qs.filter(source_type=source_type.upper())
    if scope:
        qs = qs.filter(scope=scope)
    if review_status:
        qs = qs.filter(review_status=review_status.upper())
    if confidence:
        qs = qs.filter(confidence=confidence.upper())
    if batch_id:
        qs = qs.filter(import_batch_id=batch_id)
    if search:
        qs = qs.filter(
            Q(activity_type__icontains=search) |
            Q(source_record_id__icontains=search) |
            Q(category__icontains=search)
        )

    serializer = EmissionRecordSerializer(qs, many=True)
    return Response(serializer.data)


@api_view(['GET', 'PATCH'])
def record_detail(request, id):
    """Get or update a single emission record."""
    try:
        record = EmissionRecord.objects.select_related('raw_record').get(id=id)
    except EmissionRecord.DoesNotExist:
        return Response({'error': 'Record not found'}, status=status.HTTP_404_NOT_FOUND)

    if request.method == 'GET':
        serializer = EmissionRecordSerializer(record)
        return Response(serializer.data)

    # PATCH — edit record
    if record.is_locked:
        return Response(
            {'error': 'Record is locked for audit and cannot be edited.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    before = EmissionRecordSerializer(record).data

    serializer = EmissionRecordUpdateSerializer(record, data=request.data, partial=True)
    if serializer.is_valid():
        serializer.save()
        after = EmissionRecordSerializer(record).data

        AuditLog.objects.create(
            tenant=record.tenant,
            emission_record=record,
            action='EDITED',
            before_json=before,
            after_json=after,
            actor=request.data.get('actor', 'analyst'),
            note=request.data.get('note', ''),
        )

        return Response(EmissionRecordSerializer(record).data)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ---------------------------------------------------------------------------
# Review Actions
# ---------------------------------------------------------------------------
def _update_record_with_audit(record, action, status_val, locked_at=None, actor='analyst', note=''):
    """Helper to snapshot before, apply changes, save, snapshot after, and create audit log."""
    before = EmissionRecordSerializer(record).data
    record.review_status = status_val
    if locked_at:
        record.locked_at = locked_at
    record.save()
    after = EmissionRecordSerializer(record).data
    AuditLog.objects.create(
        tenant=record.tenant,
        emission_record=record,
        action=action,
        before_json=before,
        after_json=after,
        actor=actor,
        note=note,
    )


@api_view(['POST'])
def approve_record(request, id):
    try:
        record = EmissionRecord.objects.get(id=id)
    except EmissionRecord.DoesNotExist:
        return Response({'error': 'Record not found'}, status=status.HTTP_404_NOT_FOUND)

    if record.is_locked:
        return Response({'error': 'Record is locked and cannot be changed.'}, status=status.HTTP_400_BAD_REQUEST)

    _update_record_with_audit(
        record, 'APPROVED', 'APPROVED',
        actor=request.data.get('actor', 'analyst'),
        note=request.data.get('note', ''),
    )

    return Response(EmissionRecordSerializer(record).data)


@api_view(['POST'])
def reject_record(request, id):
    try:
        record = EmissionRecord.objects.get(id=id)
    except EmissionRecord.DoesNotExist:
        return Response({'error': 'Record not found'}, status=status.HTTP_404_NOT_FOUND)

    if record.is_locked:
        return Response({'error': 'Record is locked and cannot be changed.'}, status=status.HTTP_400_BAD_REQUEST)

    _update_record_with_audit(
        record, 'REJECTED', 'REJECTED',
        actor=request.data.get('actor', 'analyst'),
        note=request.data.get('note', ''),
    )

    return Response(EmissionRecordSerializer(record).data)


@api_view(['POST'])
def lock_record(request, id):
    try:
        record = EmissionRecord.objects.get(id=id)
    except EmissionRecord.DoesNotExist:
        return Response({'error': 'Record not found'}, status=status.HTTP_404_NOT_FOUND)

    if record.is_locked:
        return Response({'error': 'Record is already locked.'}, status=status.HTTP_400_BAD_REQUEST)

    if record.review_status != 'APPROVED':
        return Response(
            {'error': 'Only approved records can be locked.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    _update_record_with_audit(
        record, 'LOCKED', 'LOCKED', locked_at=timezone.now(),
        actor=request.data.get('actor', 'analyst'),
        note=request.data.get('note', ''),
    )

    return Response(EmissionRecordSerializer(record).data)


# ---------------------------------------------------------------------------
# Raw Records
# ---------------------------------------------------------------------------
@api_view(['GET'])
def list_raw_records(request):
    batch_id = request.query_params.get('batch')
    qs = RawRecord.objects.all()
    if batch_id:
        qs = qs.filter(import_batch_id=batch_id)
    serializer = RawRecordSerializer(qs, many=True)
    return Response(serializer.data)


# ---------------------------------------------------------------------------
# Audit Logs
# ---------------------------------------------------------------------------
@api_view(['GET'])
def list_audit_logs(request):
    tenant_id = request.query_params.get('tenant')
    record_id = request.query_params.get('record')
    qs = AuditLog.objects.select_related('emission_record').all()
    
    # Handle demo tenant IDs by mapping to real tenant
    if tenant_id:
        demo_tenant_map = {
            '-1': 'Acme Corp',
            '-2': 'BlueGrid Energy',
            '-3': 'GreenMiles Logistics',
        }
        if str(tenant_id) in demo_tenant_map:
            tenant_name = demo_tenant_map[str(tenant_id)]
            try:
                real_tenant = Tenant.objects.get(company_name=tenant_name)
                qs = qs.filter(tenant_id=real_tenant.id)
            except Tenant.DoesNotExist:
                # Tenant doesn't exist yet, return empty
                pass
        else:
            qs = qs.filter(tenant_id=tenant_id)
    if record_id:
        qs = qs.filter(emission_record_id=record_id)
    # Limit to last 200 to keep response manageable
    serializer = AuditLogSerializer(qs[:200], many=True)
    return Response(serializer.data)


# ---------------------------------------------------------------------------
# Dashboard Summary
# ---------------------------------------------------------------------------
@api_view(['GET'])
def summary(request):
    tenant_id = request.query_params.get('tenant')
    qs = EmissionRecord.objects.all()
    batch_qs = ImportBatch.objects.all()
    raw_qs = RawRecord.objects.all()

    # Handle demo tenant IDs by mapping to real tenant
    if tenant_id:
        demo_tenant_map = {
            '-1': 'Acme Corp',
            '-2': 'BlueGrid Energy',
            '-3': 'GreenMiles Logistics',
        }
        if str(tenant_id) in demo_tenant_map:
            tenant_name = demo_tenant_map[str(tenant_id)]
            try:
                real_tenant = Tenant.objects.get(company_name=tenant_name)
                qs = qs.filter(tenant_id=real_tenant.id)
                batch_qs = batch_qs.filter(tenant_id=real_tenant.id)
                raw_qs = raw_qs.filter(tenant_id=real_tenant.id)
            except Tenant.DoesNotExist:
                # Tenant doesn't exist yet, return empty counts
                qs = EmissionRecord.objects.none()
                batch_qs = ImportBatch.objects.none()
                raw_qs = RawRecord.objects.none()
        else:
            qs = qs.filter(tenant_id=tenant_id)
            batch_qs = batch_qs.filter(tenant_id=tenant_id)
            raw_qs = raw_qs.filter(tenant_id=tenant_id)

    status_counts = {}
    for choice_val, _ in EmissionRecord.REVIEW_STATUS_CHOICES:
        status_counts[choice_val] = qs.filter(review_status=choice_val).count()

    return Response({
        'total_imports': batch_qs.count(),
        'total_records': qs.count(),
        'needs_review': status_counts.get('NEEDS_REVIEW', 0),
        'flagged': status_counts.get('FLAGGED', 0),
        'approved': status_counts.get('APPROVED', 0),
        'rejected': status_counts.get('REJECTED', 0),
        'locked': status_counts.get('LOCKED', 0),
        'failed_rows': raw_qs.filter(parse_status='FAILED').count(),
    })