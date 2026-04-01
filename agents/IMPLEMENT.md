# IMPLEMENT.md — pg-tabledef 구현 담당 에이전트

## 역할

이 에이전트는 PLAN.md의 설계를 바탕으로 실제 코드를 작성합니다.
테스트 코드는 작성하지 않습니다 (TEST.md 에이전트 담당).

---

## 시작 전 필독

1. `PLAN.md` 전체를 읽고 설계를 숙지할 것
2. 기존 파일이 있으면 반드시 Read 후 수정할 것
3. ddl-diff 참고 경로: `/Users/harry/projects/ddl-diff/ddl_diff/mapper.py`
4. 구현 완료 후 `IMPLEMENT.md` 하단 **구현 현황** 섹션을 업데이트할 것

---

## 구현 규칙

- 라이브 DB 연결 없음. psycopg2 사용 금지
- `./input/` 폴더의 `.sql` 파일을 pglast로 파싱
- `./output/` 폴더에 엑셀 저장 (폴더 없으면 자동 생성)
- f-string SQL 절대 금지 (해당 없으나 문자열 조작 시 주의)
- 모든 dataclass 필드는 Python 내장 타입 + Optional 사용

---

## 파일별 구현 명세

### `requirements.txt`

```
pglast>=7.0
openpyxl>=3.1
pytest>=8.0
```

### `pg_tabledef/models.py`

```python
@dataclass
class FKInfo:
    column: str
    ref_table: str
    ref_columns: list[str]   # 빈 리스트 허용 (참조 컬럼 생략 케이스)
    constraint_name: str     # FK 제약조건명 (ALTER TABLE ... ADD CONSTRAINT {name}). 없으면 ""

@dataclass
class ColumnDef:
    no: int
    name: str                # COLUMN NAME
    attribute_name: str      # ATTRIBUTE NAME (컬럼 코멘트). 없으면 ""
    type_str: str            # 약식 표기 타입, 길이 제외 (예: VC, INT, TS)
    length: str              # 길이 숫자만 (예: "12", "200"). 없으면 ""
    not_null: bool
    is_pk: bool
    is_uk: bool
    fk_info: Optional[FKInfo]

@dataclass
class IndexDef:
    name: str
    columns: list[str]
    unique: bool

@dataclass
class TableDef:
    name: str
    comment: str             # 테이블 코멘트. 없으면 ""
    columns: list[ColumnDef]
    pk_columns: list[str]
    pk_constraint_name: str  # PK 제약조건명 (ALTER TABLE ... ADD CONSTRAINT {name}). 없으면 ""
    indexes: list[IndexDef]
    fk_list: list[FKInfo]    # Key List 섹션용
```

### `pg_tabledef/parser.py`

pglast로 `.sql` 파일을 파싱하여 `list[TableDef]`를 반환하는 단일 모듈.

**참고**: ddl-diff `mapper.py`의 `build_snapshot()`, `_map_table()`, `_map_column()`,
`_map_constraint()`, `_map_index()`, `_map_alter_table()`, `_extract_type_str()` 로직 재사용.

**ddl-diff와 다른 점 — `CommentStmt` 처리 추가 필요:**
```python
from pglast.ast import CommentStmt
from pglast.enums import ObjectType

# CommentStmt.objtype 분기
if stmt.objtype == ObjectType.OBJECT_TABLE:
    # stmt.object → 테이블명
elif stmt.objtype == ObjectType.OBJECT_COLUMN:
    # stmt.object → (테이블명, 컬럼명) 형태로 파싱
```

**처리 흐름:**
1. `./input/*.sql` 파일 목록 수집
2. pglast로 각 파일 파싱
3. Pass 1: `CreateStmt`, `IndexStmt`, `CreateSeqStmt` 처리
4. Pass 2: `AlterTableStmt` (PK, FK 제약조건) 처리
5. Pass 3: `CommentStmt` (테이블/컬럼 코멘트) 처리
6. 타입 약식 변환 (`_format_type()`) 적용
7. 알파벳 순 정렬 후 `list[TableDef]` 반환

**타입 약식 변환 (`_format_type()`):**
PLAN.md의 타입 표시 포맷 표 기준으로 변환.
`type_str`과 `length`를 분리하여 반환:
- `varchar(12)` → `type_str="VC"`, `length="12"`
- `integer` → `type_str="INT"`, `length=""`
- `numeric(10,2)` → `type_str="DEC"`, `length="10,2"`

### `pg_tabledef/writer/styles.py`

openpyxl 스타일 상수 정의:

```python
# 폰트
FONT_HEADER         = Font(bold=True, size=10)                          # 헤더 (일반 배경)
FONT_HEADER_ON_DARK = Font(bold=True, size=10, color=Color(theme=1))    # 헤더 (어두운 배경 → 흰색)
FONT_NORMAL         = Font(size=10)
FONT_PK             = Font(bold=True, size=10)

# 정렬
ALIGN_CENTER       = Alignment(horizontal="center", vertical="center")
ALIGN_LEFT         = Alignment(horizontal="left",   vertical="center", wrap_text=True)
ALIGN_LEFT_NO_WRAP = Alignment(horizontal="left",   vertical="center")

# 배경색 (theme=0 + tint=-0.35 → 어두운 헤더)
FILL_HEADER = PatternFill(fill_type="solid", fgColor=Color(theme=0, tint=-0.35))

# 테두리 (thin 전체)
BORDER_THIN = Border(...)

# 컬럼 너비 (sample.xlsx 기준)
COL_WIDTHS = {
    "A": 16.7,  # No.
    "B": 28.0,  # COLUMN NAME
    "C": 30.8,  # ATTRIBUTE NAME
    "D": 14.7,  # Type
    "E": 8.0,   # Length
    "F": 6.8,   # Null
    "G": 6.3,   # Keys
    "H": 17.0,  # 인포타입명
    "I": 21.7,  # Description
    "J": 18.0,  # Attribute Type
    "K": 25.0,  # Relation & Value
    "L": 15.0,  # Source
}
```

### `rules/entity_class_rules.json`

테이블명(소문자) → 엔티티분류(`KEY`/`MAIN`/`ACTION`) 매핑 파일.
AI 추론 결과가 자동 누적 저장됨. 구조 및 처리 흐름은 `PLAN.md` "엔티티분류" 섹션 참조.

### `rules/table_subject_rules.json`

테이블명 패턴 → H열(Sub System), J열(주제영역명), L열(주제영역명약어) 매핑 규칙 파일.
구조 및 규칙 상세는 `PLAN.md` "테이블 주제영역 매핑" 섹션 참조.

### `pg_tabledef/writer/excel.py`

`ExcelWriter` — `list[TableDef]`를 받아 `./output/테이블정의서.xlsx` 저장.

**섹션별 private 메서드:**
- `_write_table_header(ws, row, table)` → 섹션 1 (테이블 정보)
  - `_resolve_subject(table.name)` 로 H열(Sub System), J열(주제영역명), L열(주제영역명약어) 결정
- `_write_key_list(ws, row, table)` → 섹션 2 (Key List)
- `_write_columns(ws, row, table)` → 섹션 3 (컬럼 목록, PK 행 bold)
  - G열 Keys 표시: `is_pk` → `"PK"`, `is_uk` → `"UK"`, `fk_info` → `"FK"`, 복합 시 `,`로 연결 (예: `"PK,FK"`)
- `_apply_column_widths(ws)` → 컬럼 너비 적용

**주제영역 매핑 함수:**
```python
def _load_subject_rules() -> dict:
    """rules/table_subject_rules.json 로드. 파일 없으면 빈 규칙 반환."""

def _resolve_subject(table_name: str) -> tuple[str, str, str]:
    """테이블명 → (sub_system, subject_area, subject_area_abbr).
    strip_prefixes 제거 후 rules 배열 순서대로 첫 번째 매칭 반환. 없으면 ("", "", "").
    """
```

**Key List 출력 규칙 (`_write_key_list`):**

| 행 | A열 (가운데) | B:C 병합 Key Name (왼쪽) | D:L 병합 Column Name (왼쪽) |
|----|------------|------------------------|--------------------------|
| Primary Key | "Primary Key" | `pk_constraint_name` | `", ".join(pk_columns)` |
| Foreign Key | "Foreign Key" | `fk.constraint_name` (`, ` 구분) | `"col → ref_table"` (`, ` 구분) |
| Index Key | "Index Key" | `idx.name` (`, ` 구분) | `", ".join(idx.columns)` (`, ` 구분) |
| Sequence Key | "Sequence Key" | `""` | `""` |

- FK/Index 여러 개: B:C와 D:L 모두 `, `로 연결하여 한 줄로 출력
- Row 4 헤더 및 Row 9–11 Partition 행: `ALIGN_CENTER` 유지

**파서 추가 추출 항목 (`_parse_constraint`):**
- `con.conname` → 제약조건명 (PK: `TableDef.pk_constraint_name`, FK: `FKInfo.constraint_name`)

**컬럼 J/K/L 출력 우선순위 (`_write_columns`):**

1. FK (`col.fk_info` 존재) → J=`RELATION`, K=`ref_table.ref_col`, L=`""`
2. `column_attribute_rules.json` 매칭 (`(col.name, col.attribute_name)`) → J/K 고정값, L=`""`
3. `dtl_code.csv` 코드그룹 매칭 (B열 우선, C열 fallback):
   - **B열 매칭**: `col.name in _DTL_BY_NAME` → K=`IND_CD="{col.name}"`
   - **C열 매칭**: `col.attribute_name in _DTL_BY_ATTR` → K=`IND_CD="{code_group}"`
   - J=`코드 그룹`, L=`["APLY", "TRMN"]` 형식

**`rules/dtl_code.csv` 로드 (`_load_dtl_code_rules`):**
```python
# CSV 포맷: 코드그룹, 설명, 그룹접두사, 코드값, 코드명칭
# 반환:
#   by_name: {code_group: [code_value, ...]}                    # B열 매칭용
#   by_attr: {description: (code_group, [code_value, ...])}     # C열 매칭용

def _load_dtl_code_rules():
    ...
    return by_name, by_attr
```

L열 출력값: `str(code_values)` → Python 리스트 표현식 그대로, 예: `["APLY", "TRMN"]`

**전체 write 흐름:**
```python
# 출력 경로를 생성자에 전달, write()는 인수 없음
writer = ExcelWriter(output_path)   # output_path 생략 시 output/테이블정의서.xlsx
writer.write(tables)
```

### `main.py`

```python
# 사용법
python main.py

# 동작
# 1. ./input/*.sql 읽기
# 2. pglast 파싱 → list[TableDef]
# 3. ./output/테이블정의서.xlsx 저장
# 4. 완료 메시지 출력 (테이블 수, 출력 경로)
```

argparse 불필요. 입출력 경로 고정.

---

## 구현 현황

> 구현 에이전트가 작업 완료 후 이 섹션을 업데이트할 것.

| 파일 | 상태 | 비고 |
|------|------|------|
| requirements.txt | ✅ 완료 | pglast>=7.0, openpyxl>=3.1, pytest>=8.0 |
| pg_tabledef/__init__.py | ✅ 완료 | |
| pg_tabledef/models.py | ✅ 완료 | FKInfo, ColumnDef, IndexDef, TableDef |
| pg_tabledef/parser.py | ✅ 완료 | pglast 파싱, 타입 약식 변환, CommentStmt 처리 |
| pg_tabledef/writer/__init__.py | ✅ 완료 | |
| pg_tabledef/writer/styles.py | ✅ 완료 | openpyxl 스타일 상수 |
| pg_tabledef/writer/excel.py | ✅ 완료 | ExcelWriter (3섹션 레이아웃) |
| main.py | ✅ 완료 | CLI 진입점, 107테이블 출력 확인 |
| rules/entity_class_rules.json | ✅ 완료 | 엔티티분류 수동 매핑 + AI 추론값 캐시 |
| rules/table_subject_rules.json | ✅ 완료 | H/J/L열 주제영역 매핑 규칙 |
