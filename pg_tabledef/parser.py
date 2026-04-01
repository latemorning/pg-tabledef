"""pg_tabledef.parser: pglast로 .sql 파일을 파싱하여 list[TableDef]를 반환."""
from __future__ import annotations

import re
from pathlib import Path

import pglast
from pglast.ast import (
    CreateStmt, IndexStmt, CreateSeqStmt,
    AlterTableStmt, ColumnDef as PgColumnDef, Constraint,
    TypeName, A_Const, Integer, Float, String, CommentStmt,
)
from pglast.enums import ConstrType, AlterTableType, ObjectType

from .models import TableDef, ColumnDef, FKInfo, IndexDef

# ──────────────────────────────────────────────────────────────────────────────
# 내부 PostgreSQL 타입명 → SQL 정식명 매핑 (ddl-diff mapper.py 기반)
# ──────────────────────────────────────────────────────────────────────────────
_PG_TYPE_MAP: dict[str, str] = {
    "int4": "integer",
    "int8": "bigint",
    "int2": "smallint",
    "float4": "real",
    "float8": "double precision",
    "bool": "boolean",
    "bpchar": "char",
    "varchar": "varchar",
    "text": "text",
    "timestamptz": "timestamp with time zone",
    "timetz": "time with time zone",
    "numeric": "numeric",
    "date": "date",
    "time": "time",
    "timestamp": "timestamp",
    "bytea": "bytea",
    "json": "json",
    "jsonb": "jsonb",
    "uuid": "uuid",
    "oid": "oid",
    "name": "name",
    "xml": "xml",
}

# DDL 정식 타입명 → 약식 표기 (PLAN.md 타입 표시 포맷 기준)
_ABBR_MAP: dict[str, str] = {
    "tinyint": "TINT",
    "smallint": "SINT",
    "int2": "SINT",
    "bigint": "BINT",
    "int8": "BINT",
    "integer": "INT",
    "int": "INT",
    "int4": "INT",
    "serial": "SR",
    "bigserial": "BSR",
    "number": "N",
    "decimal": "DEC",
    "numeric": "DEC",
    "varchar": "VC",
    "varchar2": "VC",
    "character varying": "VC",
    "nvarchar": "NVC",
    "text": "TXT",
    "clob": "CLB",
    "blob": "BLB",
    "xml": "XML",
    "date": "D",
    "time": "T",
    "time without time zone": "T",
    "time with time zone": "T",
    "datetime": "DT",
    "timestamp": "TS",
    "timestamp without time zone": "TS",
    "timestamp with time zone": "TS",
    "char": "C",
    "character": "C",
    "boolean": "BOOL",
    "bool": "BOOL",
    "real": "REAL",
    "float4": "REAL",
    "double precision": "DBL",
    "float8": "DBL",
    "bytea": "BYTEA",
    "json": "JSON",
    "jsonb": "JSONB",
    "uuid": "UUID",
}


def _extract_raw_type(tn: TypeName) -> tuple[str, list[int]]:
    """TypeName AST 노드에서 (base_type_str, mods) 추출."""
    base = None
    if tn.names:
        for n in reversed(tn.names):
            if isinstance(n, String) and n.sval != "pg_catalog":
                base = n.sval
                break
    if base is None:
        base = "unknown"

    base = _PG_TYPE_MAP.get(base, base)

    mods: list[int] = []
    if tn.typmods:
        for tm in tn.typmods:
            if isinstance(tm, A_Const):
                v = tm.val
                if isinstance(v, Integer):
                    mods.append(v.ival)
                elif isinstance(v, Float):
                    try:
                        mods.append(int(float(v.fval)))
                    except Exception:
                        pass
            elif isinstance(tm, Integer):
                mods.append(tm.ival)

    return base, mods


def _format_type(tn: TypeName) -> tuple[str, str]:
    """TypeName → (type_str 약식, length 문자열).

    Returns:
        type_str: 약식 표기 (예: VC, INT, TS). 매핑 없으면 원본 대문자.
        length:   길이 숫자 문자열 (예: "12", "10,2"). 없으면 "".
    """
    base, mods = _extract_raw_type(tn)

    # 배열 타입
    array_suffix = ""
    if tn.arrayBounds:
        array_suffix = "[]"

    # 길이/정밀도 추출
    length = ""
    normalized_base = base.lower()

    if normalized_base in ("varchar", "character varying", "char", "character"):
        if mods:
            # pglast가 varchar(n)을 n+4 로 저장하는 경우가 있음 — 실제 값 그대로 사용
            length = str(mods[0])
    elif normalized_base == "numeric":
        if len(mods) >= 2:
            length = f"{mods[0]},{mods[1]}"
        elif len(mods) == 1:
            length = str(mods[0])
    elif normalized_base in ("timestamp", "timestamp without time zone",
                              "timestamp with time zone",
                              "time", "time without time zone",
                              "time with time zone"):
        if mods and mods[0] != -1:
            length = str(mods[0])

    # 약식 표기 변환
    abbr = _ABBR_MAP.get(normalized_base)
    if abbr is None:
        abbr = base.upper()

    abbr += array_suffix

    return abbr, length


def _parse_column(col: PgColumnDef, no: int) -> ColumnDef:
    """pglast ColumnDef AST → pg_tabledef ColumnDef."""
    name = col.colname

    type_str = "unknown"
    length = ""
    if col.typeName:
        try:
            type_str, length = _format_type(col.typeName)
        except Exception:
            pass

    not_null = bool(col.is_not_null)
    is_pk = False
    is_uk = False

    if col.constraints:
        for con in col.constraints:
            ct = con.contype
            if ct == ConstrType.CONSTR_NOTNULL:
                not_null = True
            elif ct == ConstrType.CONSTR_PRIMARY:
                is_pk = True
                not_null = True
            elif ct == ConstrType.CONSTR_UNIQUE:
                is_uk = True

    return ColumnDef(
        no=no,
        name=name,
        attribute_name="",
        type_str=type_str,
        length=length,
        not_null=not_null,
        is_pk=is_pk,
        is_uk=is_uk,
        fk_info=None,
    )


def _parse_constraint(con: Constraint) -> dict | None:
    """Constraint AST → dict with keys: contype, columns, ref_table, ref_columns."""
    ct = con.contype
    if ct == ConstrType.CONSTR_PRIMARY:
        contype = "PK"
    elif ct == ConstrType.CONSTR_UNIQUE:
        contype = "UK"
    elif ct == ConstrType.CONSTR_FOREIGN:
        contype = "FK"
    else:
        return None

    columns: list[str] = []
    ref_table = None
    ref_columns: list[str] = []

    if contype == "FK":
        # FOREIGN KEY: local columns in fk_attrs, referenced columns in pk_attrs
        if con.fk_attrs:
            columns = [k.sval for k in con.fk_attrs if isinstance(k, String)]
        if con.pktable:
            ref_table = con.pktable.relname
        if con.pk_attrs:
            ref_columns = [a.sval for a in con.pk_attrs if isinstance(a, String)]
    else:
        # PRIMARY KEY / UNIQUE: columns in keys
        if con.keys:
            columns = [k.sval for k in con.keys if isinstance(k, String)]

    conname = con.conname if con.conname else ""

    return {
        "contype": contype,
        "conname": conname,
        "columns": columns,
        "ref_table": ref_table,
        "ref_columns": ref_columns,
    }


def _split_sql_statements(sql_text: str) -> list[str]:
    """SQL 텍스트를 세미콜론 기준으로 분리. 문자열 리터럴·주석 내부의 세미콜론 무시."""
    statements: list[str] = []
    current: list[str] = []
    i = 0
    in_single_quote = False
    in_line_comment = False
    in_block_comment = False

    while i < len(sql_text):
        ch = sql_text[i]
        if in_line_comment:
            current.append(ch)
            if ch == "\n":
                in_line_comment = False
        elif in_block_comment:
            current.append(ch)
            if ch == "*" and i + 1 < len(sql_text) and sql_text[i + 1] == "/":
                i += 1
                current.append(sql_text[i])
                in_block_comment = False
        elif in_single_quote:
            current.append(ch)
            if ch == "'":
                if i + 1 < len(sql_text) and sql_text[i + 1] == "'":
                    i += 1
                    current.append(sql_text[i])  # escaped ''
                else:
                    in_single_quote = False
        else:
            if ch == "'":
                in_single_quote = True
                current.append(ch)
            elif ch == "-" and i + 1 < len(sql_text) and sql_text[i + 1] == "-":
                in_line_comment = True
                current.append(ch)
            elif ch == "/" and i + 1 < len(sql_text) and sql_text[i + 1] == "*":
                in_block_comment = True
                current.append(ch)
            elif ch == ";":
                stmt = "".join(current).strip()
                if stmt:
                    statements.append(stmt + ";")
                current = []
            else:
                current.append(ch)
        i += 1

    tail = "".join(current).strip()
    if tail:
        statements.append(tail)
    return statements


def parse_files(input_dir: str | Path = "input") -> list[TableDef]:
    """input_dir 의 .sql 파일을 파싱하여 알파벳 순 정렬된 list[TableDef]를 반환."""
    input_path = Path(input_dir)
    sql_files = sorted(input_path.glob("*.sql"))

    if not sql_files:
        return []

    # 중간 저장소
    tables: dict[str, TableDef] = {}
    # 컬럼 인덱스 추적 (테이블명 → 현재 컬럼 번호)
    col_counters: dict[str, int] = {}

    # Raw constraints from CREATE TABLE (table-level)
    table_constraints: dict[str, list[dict]] = {}

    for sql_file in sql_files:
        sql_text = sql_file.read_text(encoding="utf-8")
        try:
            parsed = pglast.parse_sql(sql_text)
        except Exception as e:
            print(f"[WARN] {sql_file.name} 전체 파싱 실패 ({e}) — 문장별 재시도")
            all_stmts: list = []
            skipped = 0
            for stmt_text in _split_sql_statements(sql_text):
                try:
                    result = pglast.parse_sql(stmt_text)
                    if result:
                        all_stmts.extend(result)
                except Exception:
                    skipped += 1
            if skipped:
                print(f"[WARN] {skipped}개 문장 스킵 (invalid SQL)")
            parsed = all_stmts if all_stmts else None

        if parsed is None:
            continue

        alter_stmts: list[tuple] = []
        comment_stmts: list[tuple] = []

        # Pass 1: CreateStmt, IndexStmt (CreateSeqStmt は無視)
        for stmt_wrapper in parsed:
            stmt = stmt_wrapper.stmt

            if isinstance(stmt, CreateStmt):
                # INHERITS 절이 있는 테이블은 파티션 자식 테이블 — 제외
                if stmt.inhRelations:
                    continue
                tname = stmt.relation.relname
                if tname not in tables:
                    tables[tname] = TableDef(name=tname, comment="")
                    col_counters[tname] = 0
                    table_constraints[tname] = []

                if stmt.tableElts:
                    for elt in stmt.tableElts:
                        if isinstance(elt, PgColumnDef):
                            col_counters[tname] += 1
                            try:
                                col = _parse_column(elt, col_counters[tname])
                                tables[tname].columns.append(col)
                            except Exception as e:
                                print(f"[WARN] Column parse error in {tname}: {e}")
                        elif isinstance(elt, Constraint):
                            try:
                                con_dict = _parse_constraint(elt)
                                if con_dict:
                                    table_constraints[tname].append(con_dict)
                            except Exception:
                                pass

            elif isinstance(stmt, IndexStmt):
                tname = stmt.relation.relname
                idx_name = stmt.idxname or "unnamed_index"
                columns = []
                if stmt.indexParams:
                    for p in stmt.indexParams:
                        if p.name:
                            columns.append(p.name)
                unique = bool(stmt.unique)
                idx = IndexDef(name=idx_name, columns=columns, unique=unique)
                if tname in tables:
                    tables[tname].indexes.append(idx)
                # IndexStmt가 CreateStmt보다 먼저 나오는 경우는 없다고 가정

            elif isinstance(stmt, AlterTableStmt):
                alter_stmts.append(stmt)

            elif isinstance(stmt, CommentStmt):
                comment_stmts.append(stmt)

            # CreateSeqStmt는 무시

        # Pass 2: AlterTableStmt — PK, FK 제약조건
        for stmt in alter_stmts:
            tname = stmt.relation.relname
            if tname not in tables or not stmt.cmds:
                continue
            for cmd in stmt.cmds:
                if cmd.subtype == AlterTableType.AT_AddConstraint:
                    try:
                        con_dict = _parse_constraint(cmd.def_)
                        if con_dict:
                            table_constraints[tname].append(con_dict)
                    except Exception:
                        pass

        # Pass 3: CommentStmt — 테이블/컬럼 코멘트
        for stmt in comment_stmts:
            try:
                obj_type = stmt.objtype
                if obj_type == ObjectType.OBJECT_TABLE:
                    # stmt.object: 테이블명 (String 노드 또는 리스트)
                    tname = _extract_comment_table_name(stmt.object)
                    if tname and tname in tables:
                        comment_text = _extract_comment_str(stmt.comment)
                        tables[tname].comment = comment_text
                elif obj_type == ObjectType.OBJECT_COLUMN:
                    # stmt.object: (테이블명, 컬럼명) 형태
                    tname, colname = _extract_comment_column_name(stmt.object)
                    if tname and colname and tname in tables:
                        comment_text = _extract_comment_str(stmt.comment)
                        for col in tables[tname].columns:
                            if col.name == colname:
                                col.attribute_name = comment_text
                                break
            except Exception as e:
                print(f"[WARN] Comment parse error: {e}")

    # 제약조건 적용: PK, FK, UK를 각 테이블에 반영
    for tname, con_list in table_constraints.items():
        table = tables[tname]
        for con_dict in con_list:
            contype = con_dict["contype"]
            columns = con_dict["columns"]
            ref_table = con_dict.get("ref_table")
            ref_columns = con_dict.get("ref_columns", [])

            conname = con_dict.get("conname", "")

            if contype == "PK":
                table.pk_columns = columns
                table.pk_constraint_name = conname
                # 컬럼에 is_pk 표시
                for col in table.columns:
                    if col.name in columns:
                        col.is_pk = True
                        col.not_null = True

            elif contype == "UK":
                for col in table.columns:
                    if col.name in columns:
                        col.is_uk = True

            elif contype == "FK":
                if columns and ref_table:
                    for fk_col_name in columns:
                        fk_info = FKInfo(
                            column=fk_col_name,
                            ref_table=ref_table,
                            ref_columns=ref_columns,
                            constraint_name=conname,
                        )
                        # 컬럼에 fk_info 연결
                        for col in table.columns:
                            if col.name == fk_col_name:
                                col.fk_info = fk_info
                                break
                        # Key List 섹션용 fk_list에도 추가
                        table.fk_list.append(fk_info)

    # 알파벳 순 정렬
    return sorted(tables.values(), key=lambda t: t.name.lower())


def _extract_comment_str(comment_node) -> str:
    """CommentStmt.comment 노드에서 문자열 추출."""
    if comment_node is None:
        return ""
    if isinstance(comment_node, String):
        return comment_node.sval
    if isinstance(comment_node, str):
        return comment_node
    # A_Const with String val
    if isinstance(comment_node, A_Const):
        v = comment_node.val
        if isinstance(v, String):
            return v.sval
    return str(comment_node)


def _extract_comment_table_name(obj_node) -> str | None:
    """COMMENT ON TABLE의 object 노드에서 테이블명 추출."""
    if obj_node is None:
        return None
    # pglast는 단순 테이블명을 String 노드로, 스키마 수식이 있으면 리스트로 반환
    if isinstance(obj_node, String):
        return obj_node.sval
    if hasattr(obj_node, "__iter__"):
        parts = list(obj_node)
        if parts:
            last = parts[-1]
            if isinstance(last, String):
                return last.sval
    return None


def filter_excluded(tables: list) -> list:
    """rules/exclude_tables.txt 에 등록된 테이블을 제외하고 반환.

    파일이 없으면 원본 반환. # 주석 및 빈 줄 무시. 대소문자 구분 없이 비교.
    """
    rules_path = Path(__file__).parent.parent / "rules" / "exclude_tables.txt"
    if not rules_path.exists():
        return tables

    excluded: set[str] = set()
    for line in rules_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            excluded.add(line.lower())

    before = len(tables)
    result = [t for t in tables if t.name.lower() not in excluded]
    removed = before - len(result)
    if removed:
        print(f"[INFO] 제외: {removed}개 테이블 (exclude_tables.txt)")
    return result


def _extract_comment_column_name(obj_node) -> tuple[str | None, str | None]:
    """COMMENT ON COLUMN의 object 노드에서 (테이블명, 컬럼명) 추출.

    pglast는 COMMENT ON COLUMN t.col 을 [String('t'), String('col')] 형태로 반환.
    스키마가 있으면 [String('schema'), String('t'), String('col')].
    """
    if obj_node is None:
        return None, None
    parts = list(obj_node)
    str_parts = [p.sval for p in parts if isinstance(p, String)]
    if len(str_parts) >= 2:
        return str_parts[-2], str_parts[-1]
    return None, None
