# Emissions Calculations & Sources Reference

This document compiles the scientific and regulatory basis for the emission factors and conversion formulas implemented in this platform.

---

## 1. Scope 1: Stationary & Mobile Fuel Combustion (SAP)

Scope 1 emissions represent direct greenhouse gas emissions from sources owned or controlled by the tenant.

### Emission Factors (Stationary & Mobile Fuel)
Derived from the **UK Department for Environment, Food & Rural Affairs (DEFRA) 2023 Greenhouse Gas Conversion Factors**:

| Fuel Category | Activity Type | Unit | factor (kgCO2e/unit) | Source / Standard |
| :--- | :--- | :--- | :--- | :--- |
| **Diesel / Dieselkraftstoff** | Diesel Combustion | Liters (L) | `2.68` | DEFRA 2023 - Fuel (Commercial) |
| **Petrol / Benzin** | Petrol Combustion | Liters (L) | `2.31` | DEFRA 2023 - Petrol |
| **Natural Gas / Erdgas** | Natural Gas Combustion | Cubic Meters (M3) | `2.02` | DEFRA 2023 - Natural Gas |
| **LPG / Flüssiggas** | LPG Combustion | Liters (L) | `1.51` | DEFRA 2023 - LPG (Liquid) |
| **Heating Oil / Heizöl** | Heating Oil Combustion | Liters (L) | `2.54` | DEFRA 2023 - Burning Oil |
| **Coal / Kohle** | Coal Combustion | Kilograms (KG) | `2.42` | DEFRA 2023 - Industrial Coal |

### Calculation Formula
$$\text{Emissions } (\text{kgCO}_2\text{e}) = \text{Quantity (Normalized)} \times \text{Emission Factor}$$

*Note: For coal purchased in tonnes (T), quantity is multiplied by $1000$ before applying the factor.*

---

## 2. Scope 2: Purchased Electricity (Utility)

Scope 2 emissions represent indirect emissions from the generation of purchased electricity consumed by the tenant.

### Emission Factors
*   **Grid Average**: `0.417 kgCO2e/kWh`
*   **Source**: **US EPA eGRID 2022 National Average** (released January 2024).
*   *Note*: In an enterprise implementation, the location-based method requires matching the billing region (e.g. state/zip/grid node) with local grid subregion factors.

### Reasonability Thresholds
*   **Usage Boundary**: $10\text{ kWh} < \text{Usage} < 100,000\text{ kWh}$.
*   **Period Boundary**: Billing duration $\le 45\text{ days}$. Periods exceeding this are flagged to verify if multiple months are combined.

---

## 3. Scope 3: Value Chain (Corporate Travel)

Scope 3 emissions are all indirect emissions (not included in scope 2) that occur in the value chain of the reporting company.

### 1. Flights
*   **Factor**: `0.255 kgCO2e/passenger-km`
*   **Source**: DEFRA 2023 Passenger transport (Air - Short/Long haul average economy class, including radiative forcing).
*   **Estimation (Haversine Formula)**:
    If distance is omitted but airport IATA codes are provided, we estimate distance via:
    $$d = 2R \arcsin\left(\sqrt{\sin^2\left(\frac{\Delta \phi}{2}\right) + \cos(\phi_1)\cos(\phi_2)\sin^2\left(\frac{\Delta \lambda}{2}\right)}\right)$$
    *Where $R = 6371\text{ km}$, $\phi$ is latitude, and $\lambda$ is longitude.*

### 2. Hotel Stays
*   **Factor**: `20.6 kgCO2e/night`
*   **Source**: Cornell Hotel Sustainability Benchmarking Index (CHSB) 2023 global average placeholder per room-night.

### 3. Rail Travel
*   **Factor**: `0.041 kgCO2e/passenger-km`
*   **Source**: DEFRA 2023 Passenger transport (National Rail average).

### 4. Taxis & Rideshares (Uber/Lyft)
*   **Factor**: `0.21 kgCO2e/km`
*   **Source**: DEFRA 2023 Passenger transport (Average petrol/diesel passenger car).
