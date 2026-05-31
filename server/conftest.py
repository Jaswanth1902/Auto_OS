import pytest
from pathlib import Path

@pytest.fixture(scope="session")
def mock_site_dir():
    base_dir = Path(__file__).parent / "tests" / "mock_site"
    return str(base_dir.absolute())
