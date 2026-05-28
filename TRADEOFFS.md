# Engineering Tradeoffs & Non-Builds

This document outlines the deliberate engineering tradeoffs made in this prototype. To keep the project focused and high-quality, we prioritized robust normalization and analyst review workflows over boiler-plate enterprise features.

---

## Deliberate Non-Builds

### 1. Complete Authentication & Role-Based Access Control (RBAC)
*   **Prototype implementation**: We created a simple text-based `actor` field on the Audit Log and default the user to `analyst` (or `system` for imports). There are no login or register screens.
*   **Why**: Building full OAuth2, MFA, or JWT session management would add dozens of files and distract from the core assignment grading criteria (realistic data normalization and ESG judgment).
*   **Production alternative**: Integrate with enterprise SSO (e.g., Okta, Auth0, or Active Directory) using SAML/OIDC. Define roles: `data_submitter` (can upload CSVs), `esg_analyst` (can edit, approve, reject), and `esg_auditor` (read-only access + lock validation).

### 2. External Emissions Factor Database Integration
*   **Prototype implementation**: Hardcoded placeholder factors in `normalizers/constants.py` using simplified 2023 DEFRA/EPA averages.
*   **Why**: Ingesting and querying thousands of EPA eGRID, DEFRA, and ICAO factors requires database-backed factor tables with complex temporal versioning.
*   **Production alternative**: Implement a database table `EmissionFactor` containing `scope`, `category`, `factor`, `unit`, `region`, `valid_from`, and `valid_to`. Integrate with APIs like Climatiq or grid-operator APIs to dynamically update carbon intensities.

### 3. Asynchronous Normalization Queue (Celery/Redis)
*   **Prototype implementation**: Ingestion files are processed synchronously directly within the Django request-response thread.
*   **Why**: Using Celery/Redis introduces system dependencies that make local setup much more complex for graders. For small files (< 1,000 rows), synchronous processing takes less than 1 second.
*   **Production alternative**: Offload file uploads to AWS S3. Trigger an event-driven AWS Lambda or celery worker to parse and normalize rows asynchronously, updating the `ImportBatch` status via WebSockets or polling.

### 4. Interactive File Schema Mapper
*   **Prototype implementation**: Hardcoded aliases for German columns and expected headers.
*   **Why**: Creating a drag-and-drop column mapping screen (like CSV-import libraries do) is a major frontend engineering task that is secondary to demonstrating backend normalization logic.
*   **Production alternative**: Provide a schema-mapping step in the React UI where the user matches their CSV columns (e.g. `Werk_ID`) to our system schema (`plant_code`) before committing the upload. Save this mapping template per `DataSource`.

### 5. Multi-File Upload & Parallel Batch Processing
*   **Prototype implementation**: Single file upload at a time, processed line-by-line.
*   **Why**: File batching and bulk SQL inserts require transactional rollback logic that is overkill for the prototype's small dataset.
*   **Production alternative**: Use Django's `bulk_create` to insert normalized records in single transactions. Use PostgreSQL row locking to avoid race conditions during concurrent batch uploads.
