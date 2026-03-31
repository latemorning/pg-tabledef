import shutil
import pytest
from pathlib import Path

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_tables(tmp_path):
    """sample.sql을 파싱한 list[TableDef] fixture."""
    shutil.copy(FIXTURES_DIR / "sample.sql", tmp_path / "sample.sql")
    from pg_tabledef.parser import parse_files
    return parse_files(str(tmp_path))


@pytest.fixture
def sample_table_def(sample_tables):
    """orders 테이블 단일 TableDef fixture."""
    return next(t for t in sample_tables if t.name == "orders")


@pytest.fixture
def customers_table_def(sample_tables):
    return next(t for t in sample_tables if t.name == "customers")
