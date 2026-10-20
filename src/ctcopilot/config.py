"""Settings for the ingestion run.

The therapeutic area is configuration, not code: change `conditions` to point
the pipeline at a different disease area.
"""

from dataclasses import dataclass, field
from pathlib import Path

API_BASE_URL = "https://clinicaltrials.gov/api/v2"


@dataclass(frozen=True)
class Settings:
    # Search terms for the API's "Conditions or disease" search area (query.cond).
    conditions: list[str] = field(default_factory=lambda: ["diabetes", "obesity"])
    # Values from the API's Phase enum. A study matches if any of its phases is listed.
    phases: list[str] = field(default_factory=lambda: ["PHASE2", "PHASE3"])
    # Value from the API's StudyType enum.
    study_type: str = "INTERVENTIONAL"
    # Studies per request; the API caps this at 1000.
    page_size: int = 200
    data_dir: Path = Path("data")

    # HTTP behaviour
    base_url: str = API_BASE_URL
    timeout_s: float = 60.0
    min_request_interval_s: float = 1.0
    max_retries: int = 5
    backoff_base_s: float = 2.0

    @property
    def raw_dir(self) -> Path:
        return self.data_dir / "raw"

    @property
    def db_path(self) -> Path:
        return self.data_dir / "trials.duckdb"
