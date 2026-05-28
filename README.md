# Breathe ESG Ingestion Platform — Analyst Dashboard

Welcome to the **Breathe ESG Ingestion Platform**. This platform is a fully realized prototype designed for ingesting, normalizing, auditing, and reviewing activity data from three realistic corporate source types: SAP fuel & procurement, utility electricity portals, and Concur travel logs.

---

## Key Features

1.  **Multi-Tenancy Anchor**: All data points FK to a `Tenant` model, ensuring data isolation.
2.  **Raw Ingest Immutability**: Every uploaded CSV row is captured exactly as sent in a `RawRecord` JSON table before normalization, ensuring full lineage.
3.  **Source-Specific Normalizers**:
    *   **SAP**: Automatically maps localized German columns (e.g. `Menge`, `Werk`), identifies fuel materials (e.g. diesel, benzin), converts units (e.g. to/t to KG), and flags non-fuel procurement (Scope 3).
    *   **Utility**: Classifies electricity as Scope 2, parses billing periods, and flags suspicious usage thresholds (>100MWh or <10kWh) or billing periods (>45 days).
    *   **Travel**: Classifies travel categories (flight, rail, hotel, taxi), estimates missing flight distances using the **Haversine formula** from IATA codes, and estimates emissions per night or passenger-km.
4.  **Operational Review Queue**: Analysts can search, filter, edit notes, approve, reject, or lock records.
5.  **Locked Audit Ledger**: Once a record is marked `LOCKED`, its state is frozen and cannot be modified. Every transition is backed by a snapshot-based `AuditLog`.
6.  **Full-Feature Analyst UI**: Designed in a dark, operational theme using React and vanilla CSS, featuring summary widgets, interactive modals, audit history timelines, and CSV file upload triggers.

---

## Tech Stack

*   **Backend**: Django 6.0 + Django REST Framework, Python 3.10+
*   **Frontend**: React 19.x, Axios, Vanilla CSS
*   **Database**: SQLite (default for development/testing)
*   **Styling**: High-quality dark UI (Inter font, glassmorphic layout)

---

## Repository Structure

```text
breathe-esg-assignment/
├── backend/                  # Django project root
│   ├── backend/              # Django settings & WSGI config
│   ├── ingestion/            # Core ESG app
│   │   ├── normalizers/      # Custom SAP, Utility, and Travel parsers
│   │   ├── admin.py          # Django admin configuration
│   │   ├── models.py         # Relational database models
│   │   ├── serializers.py    # REST Framework serializers
│   │   ├── views.py          # Ingestion view & Review actions
│   │   ├── urls.py           # API routes
│   │   └── tests.py          # Normalization & review workflow test suite
│   ├── requirements.txt      # Python dependencies
│   └── manage.py             # Django entrypoint
├── frontend/                 # React project root
│   ├── src/                  # React source files
│   │   ├── App.js            # Main dashboard component
│   │   ├── App.css           # Custom dark theme styles
│   │   ├── api.js            # Axios client settings
│   │   └── index.js          # React startup script
│   └── package.json          # Node dependencies
└── sample_data/              # Realistic messy CSV files
```

---

## Installation & Running

### 1. Prerequisites
Ensure you have the following installed on your machine:
*   [Python 3.10+](https://www.python.org/downloads/)
*   [Node.js (v18+)](https://nodejs.org/)

---

### 2. Backend Setup
Open a terminal in the `backend` directory:

1.  **Create a virtual environment**:
    ```bash
    python -m venv venv
    ```
2.  **Activate the virtual environment**:
    *   **Windows (PowerShell)**:
        ```powershell
        .\venv\Scripts\Activate.ps1
        ```
    *   **Mac/Linux**:
        ```bash
        source venv/bin/activate
        ```
3.  **Install dependencies**:
    ```bash
    pip install -r requirements.txt
    ```
4.  **Create & Run database migrations**:
    ```bash
    python manage.py makemigrations ingestion
    python manage.py migrate
    ```
5.  **Seed default tenant & data sources**:
    ```bash
    python manage.py seed_tenant
    ```
6.  **Start the development server**:
    ```bash
    python manage.py runserver
    ```
    *The API will run at `http://127.0.0.1:8000`.*

---

### 3. Frontend Setup
Open a new terminal in the `frontend` directory:

1.  **Install npm packages**:
    ```bash
    npm install
    ```
2.  **Start the development server**:
    ```bash
    npm start
    ```
    *The application will open in your browser at `http://localhost:3000`.*

---

## Running Verification & Tests

### Backend Tests
To run the Django test suite covering normalizers, API endpoints, review transitions, and audit trails:
```bash
cd backend
python manage.py test ingestion -v 2
```

---

## Supporting Architecture Docs

*   [MODEL.md](MODEL.md): Database models, multi-tenancy, and audit timeline specifications.
*   [DECISIONS.md](DECISIONS.md): Mapping decisions, airport coordinates database, and key product questions.
*   [TRADEOFFS.md](TRADEOFFS.md): List of deliberate prototype non-builds and production alternatives.
*   [SOURCES.md](SOURCES.md): Formula definitions, emissions factors, and EPA/DEFRA references.
updated by chamundeswari1212
contributor update