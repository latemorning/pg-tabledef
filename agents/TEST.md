# TEST.md — pg-tabledef 테스트 담당 에이전트

## 역할

이 에이전트는 구현된 코드에 대한 테스트를 작성하고 실행합니다.
구현 코드는 수정하지 않습니다 (버그 발견 시 IMPLEMENT.md에 기록 후 구현 에이전트에게 전달).

---

## 시작 전 필독

1. `PLAN.md` 전체를 읽고 설계 파악
2. `IMPLEMENT.md`의 구현 현황 확인 (완료된 파일만 테스트)
3. 실제 구현 파일을 Read하여 시그니처 확인 후 테스트 작성

---

## 테스트 전략

**SQL fixture 파일 기반** — 실제 PostgreSQL 불필요.
`tests/fixtures/` 에 DDL `.sql` 파일을 만들어 parser 입력으로 사용.
writer 테스트는 `tmp_path`에 엑셀을 저장 후 openpyxl로 검증.

---

## 테스트 파일 구조

```
tests/
├── __init__.py
├── conftest.py
├── fixtures/
│   └── sample.sql       ← 파서 테스트용 DDL fixture
├── test_parser.py
└── test_writer.py
```

---

## `tests/fixtures/sample.sql`

파서가 처리해야 할 모든 statement 유형을 포함한 최소 DDL:

```sql
create table customers
(
    cust_id   varchar(12)  not null,
    cust_nm   varchar(100) not null,
    rgst_dt   timestamp
);

comment on table customers is '고객정보';
comment on column customers.cust_id is '고객ID';
comment on column customers.cust_nm is '고객명';
comment on column customers.rgst_dt is '등록일시';

create unique index customers_pk
    on customers (cust_id);

alter table customers
    add constraint customers_pkey
        primary key (cust_id);

create table orders
(
    order_id  integer      not null,
    cust_id   varchar(12)  not null,
    status    varchar(20),
    order_dt  timestamp
);

comment on table orders is '주문정보';
comment on column orders.order_id is '주문ID';
comment on column orders.cust_id is '고객ID';
comment on column orders.status is '주문상태';
comment on column orders.order_dt is '주문일시';

create index orders_cust_idx
    on orders (cust_id);

alter table orders
    add constraint orders_pkey
        primary key (order_id);

alter table orders
    add constraint orders_cust_fk
        foreign key (cust_id) references customers;
```

---

## `tests/conftest.py`

```python
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
```

---

## `tests/test_parser.py` 테스트 항목

```python
from pg_tabledef.parser import parse_files

class TestParseTables:
    def test_table_count(self, sample_tables):
        """sample.sql에서 테이블 2개 파싱."""
        assert len(sample_tables) == 2

    def test_tables_sorted_alphabetically(self, sample_tables):
        """알파벳 순 정렬 확인."""
        names = [t.name for t in sample_tables]
        assert names == sorted(names)

    def test_table_comment(self, customers_table_def):
        assert customers_table_def.comment == "고객정보"

    def test_table_without_comment_is_empty_string(self, tmp_path):
        """코멘트 없는 테이블은 comment = ''."""
        sql = tmp_path / "no_comment.sql"
        sql.write_text("create table no_comment_table (id integer not null);")
        from pg_tabledef.parser import parse_files
        tables = parse_files(str(tmp_path))
        assert tables[0].comment == ""

class TestParseColumns:
    def test_column_count(self, sample_table_def):
        assert len(sample_table_def.columns) == 4

    def test_column_name(self, sample_table_def):
        assert sample_table_def.columns[0].name == "order_id"

    def test_column_attribute_name(self, sample_table_def):
        """attribute_name = 컬럼 코멘트 값."""
        assert sample_table_def.columns[0].attribute_name == "주문ID"

    def test_column_without_comment_is_empty_string(self, tmp_path):
        """컬럼 코멘트 없으면 attribute_name = '', description = ''."""
        sql = tmp_path / "no_col_comment.sql"
        sql.write_text("create table t (id integer not null);")
        from pg_tabledef.parser import parse_files
        col = parse_files(str(tmp_path))[0].columns[0]
        assert col.attribute_name == ""
        assert col.description == ""

    def test_column_description_equals_attribute_name(self, sample_table_def):
        """description은 attribute_name과 동일."""
        col = sample_table_def.columns[0]
        assert col.description == col.attribute_name

    def test_not_null(self, sample_table_def):
        """order_id는 NOT NULL."""
        col = next(c for c in sample_table_def.columns if c.name == "order_id")
        assert col.not_null is True

    def test_nullable(self, sample_table_def):
        """status는 nullable."""
        col = next(c for c in sample_table_def.columns if c.name == "status")
        assert col.not_null is False

    def test_column_numbering_starts_at_1(self, sample_table_def):
        assert sample_table_def.columns[0].no == 1

class TestParseTypeFormat:
    """_format_type 변환 규칙 검증 (PLAN.md 타입 표시 포맷 기준)."""

    def test_varchar_to_vc(self, customers_table_def):
        col = next(c for c in customers_table_def.columns if c.name == "cust_id")
        assert col.type_str == "VC"
        assert col.length == "12"

    def test_integer_to_int(self, sample_table_def):
        col = next(c for c in sample_table_def.columns if c.name == "order_id")
        assert col.type_str == "INT"

    def test_timestamp_to_ts(self, sample_table_def):
        col = next(c for c in sample_table_def.columns if c.name == "order_dt")
        assert col.type_str == "TS"

class TestParseConstraints:
    def test_pk_column_flagged(self, sample_table_def):
        col = next(c for c in sample_table_def.columns if c.name == "order_id")
        assert col.is_pk is True

    def test_non_pk_column_not_flagged(self, sample_table_def):
        col = next(c for c in sample_table_def.columns if c.name == "status")
        assert col.is_pk is False

    def test_pk_columns_list(self, sample_table_def):
        assert sample_table_def.pk_columns == ["order_id"]

    def test_fk_info_attached(self, sample_table_def):
        col = next(c for c in sample_table_def.columns if c.name == "cust_id")
        assert col.fk_info is not None
        assert col.fk_info.ref_table == "customers"

    def test_fk_list_on_table(self, sample_table_def):
        assert len(sample_table_def.fk_list) == 1
        assert sample_table_def.fk_list[0].ref_table == "customers"

class TestParseIndexes:
    def test_index_count(self, sample_table_def):
        assert len(sample_table_def.indexes) == 1

    def test_index_name(self, sample_table_def):
        assert sample_table_def.indexes[0].name == "orders_cust_idx"

    def test_index_columns(self, sample_table_def):
        assert sample_table_def.indexes[0].columns == ["cust_id"]

    def test_unique_index(self, customers_table_def):
        idx = customers_table_def.indexes[0]
        assert idx.unique is True

class TestParseSequences:
    def test_sequence_does_not_appear_in_table(self, tmp_path):
        """CREATE SEQUENCE는 파싱 오류 없이 무시됨. TableDef에 sequences 필드 없음."""
        (tmp_path / "seq.sql").write_text(
            "create sequence seq_order_id maxvalue 99999999 cycle;\n"
            "create table orders (id integer not null);\n"
        )
        from pg_tabledef.parser import parse_files
        tables = parse_files(str(tmp_path))
        assert len(tables) == 1
        assert tables[0].name == "orders"

class TestMultipleFiles:
    def test_parse_multiple_sql_files(self, tmp_path):
        """./input/ 에 파일이 여러 개일 때 모두 합산 파싱."""
        (tmp_path / "a.sql").write_text("create table a_table (id integer not null);")
        (tmp_path / "b.sql").write_text("create table b_table (id integer not null);")
        from pg_tabledef.parser import parse_files
        tables = parse_files(str(tmp_path))
        assert len(tables) == 2
```

---

## `tests/test_writer.py` 테스트 항목

```python
import openpyxl
from pg_tabledef.writer.excel import ExcelWriter

class TestSheetStructure:
    def test_single_sheet_named_tabledef(self, sample_tables, tmp_path):
        """시트 1개, 이름 = '테이블정의서'."""
        out = tmp_path / "out.xlsx"
        ExcelWriter(out).write(sample_tables)
        wb = openpyxl.load_workbook(str(out))
        assert wb.sheetnames == ["테이블정의서"]

    def test_output_dir_auto_created(self, sample_tables, tmp_path):
        """output 폴더 없어도 자동 생성."""
        out = tmp_path / "new_dir" / "out.xlsx"
        ExcelWriter(out).write(sample_tables)
        assert out.exists()

class TestTableHeader:
    def test_table_name_in_sheet(self, sample_tables, tmp_path):
        """시트 어딘가에 테이블명이 존재."""
        out = tmp_path / "out.xlsx"
        ExcelWriter(out).write(sample_tables)
        ws = openpyxl.load_workbook(str(out))["테이블정의서"]
        all_values = [ws.cell(r, c).value for r in range(1, ws.max_row+1) for c in range(1, 5)]
        assert "orders" in all_values

    def test_table_comment_in_sheet(self, sample_tables, tmp_path):
        out = tmp_path / "out.xlsx"
        ExcelWriter(out).write(sample_tables)
        ws = openpyxl.load_workbook(str(out))["테이블정의서"]
        all_values = [ws.cell(r, c).value for r in range(1, ws.max_row+1) for c in range(1, 5)]
        assert "주문정보" in all_values

class TestKeyListAlignment:
    def test_key_title_center_aligned(self, sample_tables, tmp_path):
        """Primary Key / Foreign Key / Index Key / Sequence Key 타이틀(A열)은 가운데 정렬."""
        out = tmp_path / "out.xlsx"
        ExcelWriter(out).write(sample_tables)
        ws = openpyxl.load_workbook(str(out))["테이블정의서"]
        key_titles = {"Primary Key", "Foreign Key", "Index Key", "Sequence Key"}
        for r in range(1, ws.max_row + 1):
            cell = ws.cell(r, 1)
            if cell.value in key_titles:
                assert cell.alignment.horizontal == "center", (
                    f"Row {r} '{cell.value}' should be center-aligned"
                )

    def test_key_name_left_aligned(self, sample_tables, tmp_path):
        """Key Name 값(B열)은 왼쪽 정렬."""
        out = tmp_path / "out.xlsx"
        ExcelWriter(out).write(sample_tables)
        ws = openpyxl.load_workbook(str(out))["테이블정의서"]
        for r in range(1, ws.max_row + 1):
            if ws.cell(r, 1).value == "Primary Key":
                assert ws.cell(r, 2).alignment.horizontal == "left"
                break

    def test_column_name_left_aligned(self, sample_tables, tmp_path):
        """Column Name 값(D열)은 왼쪽 정렬."""
        out = tmp_path / "out.xlsx"
        ExcelWriter(out).write(sample_tables)
        ws = openpyxl.load_workbook(str(out))["테이블정의서"]
        for r in range(1, ws.max_row + 1):
            if ws.cell(r, 1).value == "Primary Key":
                assert ws.cell(r, 4).alignment.horizontal == "left"
                break


class TestKeyListContent:
    def test_pk_constraint_name_in_key_name(self, sample_table_def, tmp_path):
        """Primary Key 행 B열에 제약조건명(orders_pkey)이 표시됨."""
        out = tmp_path / "out.xlsx"
        from pg_tabledef.writer.excel import ExcelWriter
        ExcelWriter(out).write([sample_table_def])
        ws = openpyxl.load_workbook(str(out))["테이블정의서"]
        for r in range(1, ws.max_row + 1):
            if ws.cell(r, 1).value == "Primary Key":
                assert ws.cell(r, 2).value == "orders_pkey"
                break

    def test_pk_columns_in_column_name(self, sample_table_def, tmp_path):
        """Primary Key 행 D열에 PK 컬럼명(order_id)이 표시됨."""
        out = tmp_path / "out.xlsx"
        from pg_tabledef.writer.excel import ExcelWriter
        ExcelWriter(out).write([sample_table_def])
        ws = openpyxl.load_workbook(str(out))["테이블정의서"]
        for r in range(1, ws.max_row + 1):
            if ws.cell(r, 1).value == "Primary Key":
                assert ws.cell(r, 4).value == "order_id"
                break

    def test_fk_constraint_name_in_key_name(self, sample_table_def, tmp_path):
        """Foreign Key 행 B열에 FK 제약조건명(orders_cust_fk)이 표시됨."""
        out = tmp_path / "out.xlsx"
        from pg_tabledef.writer.excel import ExcelWriter
        ExcelWriter(out).write([sample_table_def])
        ws = openpyxl.load_workbook(str(out))["테이블정의서"]
        for r in range(1, ws.max_row + 1):
            if ws.cell(r, 1).value == "Foreign Key":
                assert ws.cell(r, 2).value == "orders_cust_fk"
                break

    def test_fk_column_ref_in_column_name(self, sample_table_def, tmp_path):
        """Foreign Key 행 D열에 'cust_id → customers' 형식으로 표시됨."""
        out = tmp_path / "out.xlsx"
        from pg_tabledef.writer.excel import ExcelWriter
        ExcelWriter(out).write([sample_table_def])
        ws = openpyxl.load_workbook(str(out))["테이블정의서"]
        for r in range(1, ws.max_row + 1):
            if ws.cell(r, 1).value == "Foreign Key":
                val = ws.cell(r, 4).value or ""
                assert "cust_id" in val and "customers" in val
                break

    def test_index_name_in_key_name(self, sample_table_def, tmp_path):
        """Index Key 행 B열에 인덱스명(orders_cust_idx)이 표시됨."""
        out = tmp_path / "out.xlsx"
        from pg_tabledef.writer.excel import ExcelWriter
        ExcelWriter(out).write([sample_table_def])
        ws = openpyxl.load_workbook(str(out))["테이블정의서"]
        for r in range(1, ws.max_row + 1):
            if ws.cell(r, 1).value == "Index Key":
                assert ws.cell(r, 2).value == "orders_cust_idx"
                break

    def test_index_columns_in_column_name(self, sample_table_def, tmp_path):
        """Index Key 행 D열에 인덱스 컬럼(cust_id)이 표시됨."""
        out = tmp_path / "out.xlsx"
        from pg_tabledef.writer.excel import ExcelWriter
        ExcelWriter(out).write([sample_table_def])
        ws = openpyxl.load_workbook(str(out))["테이블정의서"]
        for r in range(1, ws.max_row + 1):
            if ws.cell(r, 1).value == "Index Key":
                assert "cust_id" in (ws.cell(r, 4).value or "")
                break

class TestColumnSection:
    def test_pk_marker_present(self, sample_tables, tmp_path):
        """PK 컬럼의 Keys 셀(G열)에 'PK' 값."""
        out = tmp_path / "out.xlsx"
        ExcelWriter(out).write(sample_tables)
        ws = openpyxl.load_workbook(str(out))["테이블정의서"]
        all_values = {ws.cell(r, c).value for r in range(1, ws.max_row+1) for c in range(1, 13)}
        assert "PK" in all_values

    def test_fk_relation_value(self, sample_tables, tmp_path):
        """FK 컬럼의 Relation & Value(K열)에 'customers' 포함."""
        out = tmp_path / "out.xlsx"
        ExcelWriter(out).write(sample_tables)
        ws = openpyxl.load_workbook(str(out))["테이블정의서"]
        col_k_values = [ws.cell(r, 11).value for r in range(1, ws.max_row+1)]
        assert any(v and "customers" in str(v) for v in col_k_values)

    def test_type_abbreviation_in_cell(self, sample_tables, tmp_path):
        """타입 셀(D열)에 약식 표기(VC, INT 등) 사용."""
        out = tmp_path / "out.xlsx"
        ExcelWriter(out).write(sample_tables)
        ws = openpyxl.load_workbook(str(out))["테이블정의서"]
        col_d_values = {ws.cell(r, 4).value for r in range(1, ws.max_row+1)}
        assert "VC" in col_d_values or "INT" in col_d_values

    def test_not_null_shows_nn(self, sample_tables, tmp_path):
        """NOT NULL 컬럼의 Null 셀(F열)에 'NN' 표시."""
        out = tmp_path / "out.xlsx"
        ExcelWriter(out).write(sample_tables)
        ws = openpyxl.load_workbook(str(out))["테이블정의서"]
        col_f_values = {ws.cell(r, 6).value for r in range(1, ws.max_row+1)}
        assert "NN" in col_f_values

class TestTableSeparation:
    def test_two_tables_both_present(self, sample_tables, tmp_path):
        """테이블 2개의 이름이 모두 시트에 존재."""
        out = tmp_path / "out.xlsx"
        ExcelWriter(out).write(sample_tables)
        ws = openpyxl.load_workbook(str(out))["테이블정의서"]
        all_values = {ws.cell(r, c).value
                      for r in range(1, ws.max_row+1) for c in range(1, 5)}
        assert "customers" in all_values
        assert "orders" in all_values
```

---

## 테스트 실행

```bash
cd /Users/harry/projects/pg-tabledef
source venv/bin/activate
pytest tests/ -v
pytest tests/test_parser.py -v
pytest tests/test_writer.py -v
```

---

## 버그 보고 형식

테스트 실패 시 IMPLEMENT.md 하단에 다음 형식으로 기록:

```
## 버그 보고 (테스트 에이전트)

### BUG-001
- 파일: pg_tabledef/parser.py
- 함수: _format_type
- 현상: varchar(12) → "VC(12)" 가 아닌 "VC" 반환 (길이 누락)
- 실패 테스트: tests/test_parser.py::TestParseTypeFormat::test_varchar_to_vc
- 재현: sample.sql의 cust_id varchar(12) 파싱
```

---

## 테스트 현황

> 테스트 에이전트가 작업 완료 후 이 섹션을 업데이트할 것.

| 파일 | 상태 | 통과/전체 |
|------|------|-----------|
| tests/conftest.py | ✅ 완료 | - |
| tests/fixtures/sample.sql | ✅ 완료 | - |
| tests/test_parser.py | ✅ 완료 | 27/27 |
| tests/test_writer.py | ✅ 완료 | 11/11 |

**버그 수정**: `parser.py::_parse_constraint` — FK 로컬 컬럼을 `con.keys` 대신 `con.fk_attrs`에서 읽도록 수정 (pglast FK AST 구조 오류).
