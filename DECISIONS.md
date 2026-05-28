# Ingestion & Mapping Decisions

This document details the product design decisions, source mappings, data assumptions, and product management considerations for the Breathe ESG Ingestion Platform.

---

## 1. Source Mappings & Data Normalization

We developed custom mapping parsers for the three realistic datasets, handling inconsistent column headers, mixed locales, and missing fields.

### Source Type A: SAP Fuel & Procurement
SAP datasets are notoriously messy, frequently using localized German names or abbreviations.
- **Header Mapping**:
  - `BELNR` / `Belegnummer` → `source_record_id` (Document Number)
  - `BUDAT` / `Buchungsdatum` → `period_start` and `period_end` (Posting date represents point-in-time)
  - `Werk` / `Plant` → `location_details.plant_code`
  - `MATNR` / `Materialnummer` → `location_details.material_number`
  - `MAKTX` / `Materialkurztext` → `activity_type` (e.g., Diesel Combustion, Petrol Combustion)
  - `Menge` / `Quantity` → `quantity_original`
  - `MEINS` / `Mengeneinheit` → `unit_original`
- **Fuel Material Recognition Rules**:
  - Checks if the lowercase description (`MAKTX`) contains keywords: `diesel`, `kraftstoff`, `petrol`, `benzin`, `gasoline`, `natural gas`, `erdgas`, `lpg`, `flüssiggas`, `heating oil`, `heizöl`, `coal`, `kohle`.
  - Non-fuel rows (e.g., purchasing paper, office supplies) are mapped to **Scope 3** (purchased goods/services) and flagged as `procurement_not_fuel` with `LOW` confidence. They do not trigger fatal validation errors since they represent actual business activity.
- **Date Formats**:
  - Supports standard ISO (`YYYY-MM-DD`), German (`DD.MM.YYYY`), and SAP internal format (`YYYYMMDD`).
  - Failing to parse the date flags the record as `date_parse_failure` with `LOW` confidence.

### Source Type B: Utility Electricity Portal
Utility portal exports are typical billing statements for grid power.
- **Header Mapping**:
  - `meter_id` → `source_record_id` (Meter ID)
  - `facility` → `location_details.facility`
  - `billing_start` → `period_start`
  - `billing_end` → `period_end`
  - `usage_kwh` → `quantity_original` (Standardized to KWH)
  - `demand_kw` → `location_details.demand_kw`
  - `tariff` → `location_details.tariff`
- **Scope Mapping**: All grid-supplied electricity is classified as **Scope 2 (Indirect)**.
- **Reasonability Checks & Flags**:
  - Billing end date preceding start date triggers `billing_end_before_start`.
  - Invoices representing billing periods over 45 days trigger `billing_period_too_long` (utility bills should be monthly).
  - Single-meter usage exceeding 100,000 kWh triggers `unusually_high_usage` to flag potential data entry errors.
  - Usage below 10 kWh triggers `unusually_low_usage` to flag inactive sites.

### Source Type C: Corporate Travel (Concur Export)
Concur travel exports capture business trips (flights, trains, hotels, taxis).
- **Header Mapping**:
  - `trip_id` → `source_record_id`
  - `traveler` → `location_details.traveler`
  - `category` → `activity_type` (mapped to flight, hotel, rail, taxi, rideshare)
  - `travel_date` → `period_start` and `period_end`
  - `distance_km` / `hotel_nights` → `quantity_original`
  - `origin` / `destination` → `location_details.origin` / `location_details.destination`
- **Flight Distance Estimation**:
  - If a flight record is missing the `distance_km` column but has valid 3-letter IATA airport codes for `origin` and `destination`, the system computes the Great-Circle distance using the **Haversine formula** and a built-in coordinate database for 20 major airports.
  - This marks the record with the `distance_estimated` flag.
  - If airport codes are unrecognized and distance is missing, normalization fails.

---

## 2. Product Questions for the PM

To move this from prototype to enterprise-ready, we would align with the Product Manager on:

1. **How should we handle unmapped SAP materials?**
   - *Current Decision*: We flag them as `unknown_material` and categorize them as Scope 3 with low confidence.
   - *PM Question*: Do we want a self-service UI for analysts to map material codes (e.g. `MAT-9021` → `Diesel`) directly in the app?
2. **What boundary definitions apply to travel emissions?**
   - *Current Decision*: Hotel nights are Scope 3, taxis are Scope 3.
   - *PM Question*: Are company-owned vehicles included in Concur exports? If yes, should taxi/rental car records be Scope 1 (if company-owned fuel card used) or Scope 3?
3. **How granular should grid-specific factors be for Scope 2?**
   - *Current Decision*: We use a single US national average factor (0.417 kgCO2e/kWh).
   - *PM Question*: Should we integrate regional eGRID subregion factors (e.g., ERCT for Texas vs NYCW for New York) based on the zip code/facility state?
