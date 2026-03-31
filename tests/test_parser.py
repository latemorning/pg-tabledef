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
        (tmp_path / "no_comment.sql").write_text(
            "create table no_comment_table (id integer not null);"
        )
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
        """컬럼 코멘트 없으면 attribute_name = ''."""
        (tmp_path / "no_col_comment.sql").write_text(
            "create table t (id integer not null);"
        )
        col = parse_files(str(tmp_path))[0].columns[0]
        assert col.attribute_name == ""

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

    def test_varchar_type_str(self, customers_table_def):
        """varchar → type_str='VC', length별도."""
        col = next(c for c in customers_table_def.columns if c.name == "cust_id")
        assert col.type_str == "VC"

    def test_varchar_length(self, customers_table_def):
        """varchar(12) → length='12'."""
        col = next(c for c in customers_table_def.columns if c.name == "cust_id")
        assert col.length == "12"

    def test_integer_to_int(self, sample_table_def):
        col = next(c for c in sample_table_def.columns if c.name == "order_id")
        assert col.type_str == "INT"
        assert col.length == ""

    def test_timestamp_to_ts(self, sample_table_def):
        col = next(c for c in sample_table_def.columns if c.name == "order_dt")
        assert col.type_str == "TS"
        assert col.length == ""


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
        tables = parse_files(str(tmp_path))
        assert len(tables) == 1
        assert tables[0].name == "orders"


class TestMultipleFiles:
    def test_parse_multiple_sql_files(self, tmp_path):
        """input/ 에 파일이 여러 개일 때 모두 합산 파싱."""
        (tmp_path / "a.sql").write_text("create table alpha (id integer not null);")
        (tmp_path / "b.sql").write_text("create table beta (id integer not null);")
        tables = parse_files(str(tmp_path))
        names = [t.name for t in tables]
        assert "alpha" in names
        assert "beta" in names
        assert len(tables) == 2
