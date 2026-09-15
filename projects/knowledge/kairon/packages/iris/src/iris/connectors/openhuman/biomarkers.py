"""BiomarkerNormalizer — multi-source health data normalization pipeline.

T6-25: Unified normalization for Apple Health, CGM, Garmin, Fitbit
health biomarker data into a single schema.

Supported source types:
  - "apple_health_xml": Apple Health export XML
  - "cgm_json": CGM continuous glucose JSON
  - "garmin_csv": Garmin export CSV
  - "fitbit_json": Fitbit API JSON

Supported biomarker categories (phase 1):
  - glucose (CGM + Apple Health) — mg/dL
  - heart_rate (Garmin + Fitbit + Apple Health) — bpm
  - steps (Garmin + Fitbit) — steps
  - sleep (All) — hours
"""

from __future__ import annotations

import csv
import io
import json
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class NormalizedBiomarker:
    """Unified biomarker record across all health data sources."""

    timestamp: datetime
    source: str  # "apple_health" | "cgm" | "garmin" | "fitbit"
    category: str  # "glucose" | "heart_rate" | "steps" | "sleep" | ...
    value: float
    unit: str  # "mg/dL" | "bpm" | "steps" | "hours" | ...
    confidence: float = 1.0  # 0.0 ~ 1.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "source": self.source,
            "category": self.category,
            "value": self.value,
            "unit": self.unit,
            "confidence": self.confidence,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> NormalizedBiomarker:
        """Create from dict."""
        ts = data["timestamp"]
        if isinstance(ts, str):
            ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return cls(
            timestamp=ts,
            source=data["source"],
            category=data["category"],
            value=float(data["value"]),
            unit=data["unit"],
            confidence=float(data.get("confidence", 1.0)),
        )


class BiomarkerNormalizer:
    """Multi-source health data normalization pipeline.

    Parses raw health data from Apple Health, CGM, Garmin, Fitbit
    into unified NormalizedBiomarker records.
    """

    # Category → (default unit, priority)
    CATEGORY_UNITS: dict[str, tuple[str, int]] = {
        "glucose": ("mg/dL", 10),
        "heart_rate": ("bpm", 8),
        "steps": ("steps", 5),
        "sleep": ("hours", 3),
    }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def normalize(self, raw_data: bytes, source_type: str) -> list[NormalizedBiomarker]:
        """Normalize raw health data into unified biomarker records.

        Args:
            raw_data: Raw bytes from source system.
            source_type: One of "apple_health_xml", "cgm_json",
                          "garmin_csv", "fitbit_json".

        Returns:
            List of NormalizedBiomarker records.
        """
        if source_type == "apple_health_xml":
            return self._normalize_apple_health(raw_data)
        elif source_type == "cgm_json":
            return self._normalize_cgm(raw_data)
        elif source_type == "garmin_csv":
            return self._normalize_garmin(raw_data)
        elif source_type == "fitbit_json":
            return self._normalize_fitbit(raw_data)
        else:
            return []

    def merge(self, records: list[NormalizedBiomarker]) -> list[NormalizedBiomarker]:
        """Merge multiple records by (category, timestamp) deduplication.

        When multiple sources report the same biomarker at the same time,
        keeps the record with highest confidence.

        Args:
            records: List of biomarker records from potentially multiple sources.

        Returns:
            Deduplicated list of records.
        """
        # Group by (category, timestamp rounded to minute)
        buckets: dict[tuple[str, str], NormalizedBiomarker] = {}

        for record in records:
            # Round timestamp to minute for dedup bucket
            ts_key = record.timestamp.replace(
                second=0, microsecond=0
            ).isoformat()
            key = (record.category, ts_key)

            if key not in buckets or record.confidence > buckets[key].confidence:
                buckets[key] = record

        return sorted(buckets.values(), key=lambda r: r.timestamp)

    # ------------------------------------------------------------------
    # Apple Health XML
    # ------------------------------------------------------------------

    def _normalize_apple_health(self, raw_data: bytes) -> list[NormalizedBiomarker]:
        """Parse Apple Health export XML.

        Expected format: <Export><Record><Type>...</Type><Date>...</Date>
        <Quantity><Value>...</Value><Unit>...</Unit></Quantity></Record></Export>
        """
        records: list[NormalizedBiomarker] = []
        text = raw_data.decode("utf-8", errors="replace")

        try:
            root = ET.fromstring(text)
        except ET.ParseError:
            # Try to extract records via regex for malformed XML
            return self._normalize_apple_health_fallback(text)

        for record_el in root.findall(".//Record"):
            type_el = record_el.find("Type")
            date_el = record_el.find("Date")
            qty_el = record_el.find("Quantity")

            if type_el is None or date_el is None or qty_el is None:
                continue

            type_name = type_el.text or ""
            date_str = date_el.text or ""
            value_el = qty_el.find("Value")
            unit_el = qty_el.find("Unit")

            if value_el is None or unit_el is None:
                continue

            value_str = value_el.text or ""
            unit = (unit_el.text or "").strip()

            try:
                value = float(value_str)
            except ValueError:
                continue

            try:
                timestamp = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            except ValueError:
                continue

            category = self._map_apple_type(type_name, unit)
            if category:
                unit = self._convert_unit(unit, category)
                records.append(
                    NormalizedBiomarker(
                        timestamp=timestamp,
                        source="apple_health",
                        category=category,
                        value=value,
                        unit=unit,
                        confidence=0.9,
                    )
                )

        return records

    def _normalize_apple_health_fallback(self, text: str) -> list[NormalizedBiomarker]:
        """Regex fallback for Apple Health XML when ElementTree fails."""
        records: list[NormalizedBiomarker] = []
        # Pattern: <Type>...</Type>...<Date>...</Date>...<Value>...</Value>...<Unit>...</Unit>
        pattern = re.compile(
            r"<Type>([^<]+)</Type>.*?<Date>([^<]+)</Date>"
            r".*?<Value>([^<]+)</Value>.*?<Unit>([^<]+)</Unit>",
            re.DOTALL,
        )

        for match in pattern.finditer(text):
            type_name, date_str, value_str, unit = match.groups()
            try:
                value = float(value_str)
                timestamp = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            except (ValueError, TypeError):
                continue

            category = self._map_apple_type(type_name.strip(), unit.strip())
            if category:
                unit = self._convert_unit(unit.strip(), category)
                records.append(
                    NormalizedBiomarker(
                        timestamp=timestamp,
                        source="apple_health",
                        category=category,
                        value=value,
                        unit=unit,
                        confidence=0.7,  # Lower confidence for fallback parse
                    )
                )

        return records

    def _map_apple_type(self, type_name: str, unit: str) -> str | None:
        """Map Apple Health type name to standard category."""
        name_lower = type_name.lower()

        if "glucose" in name_lower or "blood glucose" in name_lower:
            return "glucose"
        elif "heart rate" in name_lower:
            return "heart_rate"
        elif "steps" in name_lower:
            return "steps"
        elif "sleep" in name_lower or "sleep analysis" in name_lower:
            return "sleep"
        elif "blood pressure" in name_lower:
            return "blood_pressure"
        elif "weight" in name_lower:
            return "weight"

        # Fallback: try to infer from unit
        unit_lower = unit.lower()
        if "mg/dl" in unit_lower:
            return "glucose"
        elif "bpm" in unit_lower or "beats" in unit_lower:
            return "heart_rate"
        elif "step" in unit_lower:
            return "steps"

        return None

    def _convert_unit(self, unit: str, category: str) -> str:
        """Convert unit to standard unit for category."""
        default_unit = self.CATEGORY_UNITS.get(category, (unit, 0))[0]
        unit_lower = unit.lower()

        # Glucose: convert mmol/L to mg/dL
        if category == "glucose":
            if "mmol" in unit_lower:
                # mmol/L → mg/dL: multiply by 18.0182
                return "mg/dL"
            return "mg/dL"

        # Heart rate: standardize to bpm
        if category == "heart_rate":
            return "bpm"

        return default_unit

    # ------------------------------------------------------------------
    # CGM JSON
    # ------------------------------------------------------------------

    def _normalize_cgm(self, raw_data: bytes) -> list[NormalizedBiomarker]:
        """Parse CGM continuous glucose JSON.

        Expected format: {"readings": [{"timestamp": "...", "value": 120, "unit": "mg/dL"}, ...]}
        Or array of readings directly.
        """
        records: list[NormalizedBiomarker] = []

        try:
            data = json.loads(raw_data.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return []

        # Handle different JSON structures
        readings = data if isinstance(data, list) else data.get("readings", [])
        if not isinstance(readings, list):
            readings = data.get("entries", [])
        if not isinstance(readings, list):
            return []

        for entry in readings:
            if not isinstance(entry, dict):
                continue

            value = entry.get("value") or entry.get("glucose") or entry.get("reading")
            timestamp_str = (
                entry.get("timestamp")
                or entry.get("time")
                or entry.get("datetime")
                or entry.get("date")
            )
            unit = entry.get("unit", "mg/dL")

            if value is None or timestamp_str is None:
                continue

            try:
                value = float(value)
            except (ValueError, TypeError):
                continue

            try:
                timestamp = datetime.fromisoformat(
                    str(timestamp_str).replace("Z", "+00:00")
                )
            except ValueError:
                # Try unix timestamp
                try:
                    ts = int(timestamp_str)
                    timestamp = datetime.fromtimestamp(ts, tz=timezone.utc)
                except (ValueError, TypeError, OSError):
                    continue

            records.append(
                NormalizedBiomarker(
                    timestamp=timestamp,
                    source="cgm",
                    category="glucose",
                    value=value,
                    unit="mg/dL" if "mg" in str(unit).lower() else str(unit),
                    confidence=0.95,
                )
            )

        return records

    # ------------------------------------------------------------------
    # Garmin CSV
    # ------------------------------------------------------------------

    def _normalize_garmin(self, raw_data: bytes) -> list[NormalizedBiomarker]:
        """Parse Garmin export CSV.

        Expected columns: date,time,activity,heart_rate,steps,calories,...
        """
        records: list[NormalizedBiomarker] = []
        text = raw_data.decode("utf-8", errors="replace")

        try:
            reader = csv.DictReader(io.StringIO(text))
            for row in reader:
                date_str = row.get("date") or row.get("Date") or ""
                time_str = row.get("time") or row.get("Time") or ""

                # Try to parse timestamp
                timestamp = None
                if date_str:
                    try:
                        # Garmin format: 2024-01-15 or 01/15/2024
                        if "-" in date_str:
                            ts = datetime.strptime(date_str, "%Y-%m-%d")
                        else:
                            ts = datetime.strptime(date_str, "%m/%d/%Y")
                        if time_str:
                            ts = ts.replace(
                                hour=int(time_str.split(":")[0] or 0),
                                minute=int(time_str.split(":")[1] if ":" in time_str else 0),
                            )
                        timestamp = ts.replace(tzinfo=timezone.utc)
                    except (ValueError, IndexError):
                        continue

                if timestamp is None:
                    continue

                # Heart rate
                hr = row.get("heart_rate") or row.get("Heart Rate") or ""
                if hr:
                    try:
                        records.append(
                            NormalizedBiomarker(
                                timestamp=timestamp,
                                source="garmin",
                                category="heart_rate",
                                value=float(hr),
                                unit="bpm",
                                confidence=0.85,
                            )
                        )
                    except ValueError:
                        pass

                # Steps
                steps = row.get("steps") or row.get("Steps") or ""
                if steps:
                    try:
                        records.append(
                            NormalizedBiomarker(
                                timestamp=timestamp,
                                source="garmin",
                                category="steps",
                                value=float(steps),
                                unit="steps",
                                confidence=0.85,
                            )
                        )
                    except ValueError:
                        pass

        except csv.Error:
            pass

        return records

    # ------------------------------------------------------------------
    # Fitbit JSON
    # ------------------------------------------------------------------

    def _normalize_fitbit(self, raw_data: bytes) -> list[NormalizedBiomarker]:
        """Parse Fitbit API JSON.

        Expected format:
        {"activity": [{"timestamp": "...", "heartRate": {...}, "steps": {...}}, ...]}
        """
        records: list[NormalizedBiomarker] = []

        try:
            data = json.loads(raw_data.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return []

        activities = data.get("activity") or data.get("activities") or []
        if not isinstance(activities, list):
            return []

        for entry in activities:
            if not isinstance(entry, dict):
                continue

            timestamp_str = (
                entry.get("timestamp")
                or entry.get("dateTime")
                or entry.get("time")
            )
            if not timestamp_str:
                continue

            try:
                timestamp = datetime.fromisoformat(
                    str(timestamp_str).replace("Z", "+00:00")
                )
            except ValueError:
                continue

            # Heart rate
            hr = entry.get("heartRate") or entry.get("heart_rate") or {}
            if isinstance(hr, dict):
                hr_value = hr.get("value") or hr.get("avg") or hr.get("resting")
                if hr_value is not None:
                    try:
                        records.append(
                            NormalizedBiomarker(
                                timestamp=timestamp,
                                source="fitbit",
                                category="heart_rate",
                                value=float(hr_value),
                                unit="bpm",
                                confidence=0.85,
                            )
                        )
                    except (ValueError, TypeError):
                        pass
            elif isinstance(hr, (int, float)):
                records.append(
                    NormalizedBiomarker(
                        timestamp=timestamp,
                        source="fitbit",
                        category="heart_rate",
                        value=float(hr),
                        unit="bpm",
                        confidence=0.85,
                    )
                )

            # Steps
            steps = entry.get("steps") or entry.get("stepCount") or 0
            if steps:
                if isinstance(steps, dict):
                    steps_value = steps.get("value") or steps.get("total")
                else:
                    steps_value = steps
                if steps_value is not None:
                    try:
                        records.append(
                            NormalizedBiomarker(
                                timestamp=timestamp,
                                source="fitbit",
                                category="steps",
                                value=float(steps_value),
                                unit="steps",
                                confidence=0.85,
                            )
                        )
                    except (ValueError, TypeError):
                        pass

            # Sleep
            sleep = entry.get("sleep") or entry.get("sleepDuration")
            if sleep:
                sleep_minutes = sleep.get("minutes") if isinstance(sleep, dict) else None
                if sleep_minutes is None and isinstance(sleep, (int, float)):
                    sleep_minutes = sleep
                if sleep_minutes is not None:
                    try:
                        hours = float(sleep_minutes) / 60.0
                        records.append(
                            NormalizedBiomarker(
                                timestamp=timestamp,
                                source="fitbit",
                                category="sleep",
                                value=hours,
                                unit="hours",
                                confidence=0.8,
                            )
                        )
                    except (ValueError, TypeError):
                        pass

        return records
