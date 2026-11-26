"""Collect structured Module 2/3 exports without touching the incident database."""

import hashlib
import json
from datetime import datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from models.defense import EvaluateRequest
from response_ml.dataset import CsvText, DatasetRow, GenerationProvenance, Provenance, make_row, require_unique, write_csv
from services.evidence_service import assess_evidence
from services.file_integration_service import IntegrationValidationError, build_request
from starlette.datastructures import UploadFile


class PairEntry(BaseModel, extra="forbid"):
    module2_file: Path
    module3_file: Path
    session_id: CsvText | None = None
    scenario_id: CsvText | None = None
    incident_id: CsvText | None = None
    naive_timestamp_offset: str | None = Field(default=None, pattern=r"^[+-](?:[01]\d|2[0-3]):[0-5]\d$")
    outcome_ref: CsvText | None = None


class CollectionManifest(BaseModel, extra="forbid"):
    data_source: Literal["CONTROLLED_EXPERIMENT", "REAL_TESTBED", "UNCONFIRMED", "SYNTHETIC"]
    provenance: GenerationProvenance | None = None
    experiment_id: CsvText | None = None
    observations: list[PairEntry] = Field(min_length=1)


async def load_pair(module2_file: Path, module3_file: Path) -> tuple[EvaluateRequest, dict]:
    uploads = []
    digests = []
    for path in (module2_file, module3_file):
        path = path.resolve()
        data = path.read_bytes()
        digests.append(hashlib.sha256(data).hexdigest())
        uploads.append(UploadFile(file=BytesIO(data), filename=path.name))
    try:
        request, metadata = await build_request(*uploads)
    except IntegrationValidationError as exc:
        error = exc.as_dict()
        field = f" ({error['field']})" if "field" in error else ""
        raise ValueError(f"{error['source']} {error['error_code']}{field}: {error['message']}") from exc

    pair_digest = hashlib.sha256(":".join(digests).encode("ascii")).hexdigest()
    return request, {
        "raw_record_ref": f"paired-sha256:{pair_digest}",
        "module2_sha256": digests[0],
        "module3_sha256": digests[1],
        "match_method": metadata["match_method"],
    }


def observed_at_utc(value: str, naive_offset: str | None) -> datetime:
    observed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if observed.utcoffset() is None:
        if naive_offset is None:
            raise ValueError("Module 2 timestamp has no UTC offset. Record the known naive_timestamp_offset in the manifest.")
        offset = timedelta(hours=int(naive_offset[1:3]), minutes=int(naive_offset[4:6]))
        if naive_offset.startswith("-"):
            offset = -offset
        observed = observed.replace(tzinfo=timezone(offset))
    return observed.astimezone(timezone.utc)


async def collect_rows(manifest_path: Path) -> tuple[list[DatasetRow], dict]:
    manifest = CollectionManifest.model_validate_json(manifest_path.read_text(encoding="utf-8-sig"))
    index = []
    rows = []
    observations: set = set()
    raw_refs: set = set()
    for number, entry in enumerate(manifest.observations, start=1):
        try:
            request, receipt = await load_pair(
                manifest_path.parent / entry.module2_file, manifest_path.parent / entry.module3_file
            )
            observed_at = observed_at_utc(request.rf_context.timestamp, entry.naive_timestamp_offset)
            row = make_row(assess_evidence(request), Provenance(
                observation_id=request.rf_context.observation_id,
                incident_id=entry.incident_id,
                session_id=entry.session_id,
                experiment_id=manifest.experiment_id,
                scenario_id=entry.scenario_id,
                observed_at_utc=observed_at,
                data_source=manifest.data_source,
                provenance=manifest.provenance,
                raw_record_ref=receipt["raw_record_ref"],
            ))
            require_unique(row, observations, raw_refs)
        except (ValueError, OSError) as exc:
            raise ValueError(f"Manifest observation {number}: {exc}") from exc
        rows.append(row)
        index.append({
            **entry.model_dump(mode="json"),
            **receipt,
            "observation_id": row.observation_id,
            "observed_at_utc": row.observed_at_utc.isoformat(),
            "module2_timestamp_as_received": request.rf_context.timestamp,
        })
    return rows, {
        "manifest": str(manifest_path.resolve()),
        "data_source": manifest.data_source,
        "provenance": manifest.provenance,
        "experiment_id": manifest.experiment_id,
        "observations": index,
    }


async def export_collection(manifest_path: Path, output_dir: Path, csv_name: str = "observations.csv") -> int:
    if Path(csv_name).name != csv_name or Path(csv_name).suffix.lower() != ".csv":
        raise ValueError("Use a CSV filename without a folder for --csv-name.")
    rows, evidence_index = await collect_rows(manifest_path)
    output_dir.mkdir(parents=True)
    evidence_path = output_dir / "evidence-index.json"
    try:
        with evidence_path.open("x", encoding="utf-8") as stream:
            json.dump(evidence_index, stream, indent=2)
            stream.write("\n")
        write_csv(output_dir / csv_name, rows)
    except OSError:
        evidence_path.unlink(missing_ok=True)
        output_dir.rmdir()
        raise
    return len(rows)
