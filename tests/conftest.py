import json
from pathlib import Path
from typing import Any

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def studies_page() -> dict[str, Any]:
    """A trimmed real API page: five diabetes/obesity studies."""
    return json.loads((FIXTURES / "studies_page.json").read_text(encoding="utf-8"))
