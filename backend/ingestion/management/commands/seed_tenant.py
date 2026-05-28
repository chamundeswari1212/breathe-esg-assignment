"""
Management command to seed demo tenants and data sources.
Run: python manage.py seed_tenant
"""
from django.core.management.base import BaseCommand
from ingestion.models import Tenant, DataSource


class Command(BaseCommand):
    help = 'Seeds multiple demo tenants and data sources for development/demo'

    def handle(self, *args, **options):
        demo_tenants = [
            {
                'company_name': 'Acme Corp',
                'industry': 'Manufacturing',
                'country': 'India',
            },
            {
                'company_name': 'BlueGrid Energy',
                'industry': 'Energy',
                'country': 'United Kingdom',
            },
            {
                'company_name': 'GreenMiles Logistics',
                'industry': 'Logistics',
                'country': 'United States',
            },
        ]

        sources = [
            ('SAP', 'CSV_UPLOAD', 'SAP MM fuel and procurement flat file export'),
            ('UTILITY', 'CSV_UPLOAD', 'Utility portal electricity billing CSV export'),
            ('TRAVEL', 'CSV_UPLOAD', 'Corporate travel platform (Concur/Navan) CSV export'),
        ]

        for tenant_payload in demo_tenants:
            tenant, created = Tenant.objects.get_or_create(
                company_name=tenant_payload['company_name'],
                defaults={
                    'industry': tenant_payload['industry'],
                    'country': tenant_payload['country'],
                }
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'Created tenant: {tenant.company_name}'))
            else:
                self.stdout.write(f'Tenant already exists: {tenant.company_name}')

            for source_type, mode, desc in sources:
                _, source_created = DataSource.objects.get_or_create(
                    tenant=tenant,
                    source_type=source_type,
                    defaults={'ingestion_mode': mode, 'description': desc}
                )
                if source_created:
                    self.stdout.write(self.style.SUCCESS(
                        f'  Created data source for {tenant.company_name}: {source_type}'
                    ))
                else:
                    self.stdout.write(
                        f'  Data source exists for {tenant.company_name}: {source_type}'
                    )

        self.stdout.write(self.style.SUCCESS('Tenant seeding complete.'))
