# PLAN.md — pg-tabledef 설계 및 계획 담당 에이전트

## 역할

이 에이전트는 pg-tabledef의 설계 결정과 구현 계획을 담당합니다.
구현 에이전트와 테스트 에이전트가 이 파일을 참고하여 작업합니다.

---

## 프로젝트 개요

**pg-tabledef** — PostgreSQL 테이블 정의서 엑셀 출력 도구

`./input` 폴더에 올려둔 스키마 파일을 읽어 엑셀(.xlsx) 형식의 테이블 정의서를 생성하는 Python 스크립트.
라이브 DB 연결 없이 파일 기반으로 동작.

---

## 추출 항목

### DDL 파일에서 추출 가능

**테이블 정보:**

| 항목 | 엑셀 레이블 | DDL 파싱 소스 |
|------|------------|--------------|
| 테이블명 | Table 명 | `CREATE TABLE` |
| 테이블 코멘트 | Entity 설명 | `COMMENT ON TABLE` |

**Key List:**

| 항목 | DDL 파싱 소스 |
|------|--------------|
| Primary Key 컬럼 목록 | `ALTER TABLE … PRIMARY KEY` |
| Foreign Key 컬럼 + 참조 테이블/컬럼 | `ALTER TABLE … FOREIGN KEY … REFERENCES` |
| Index Key | `CREATE INDEX` / `CREATE UNIQUE INDEX` |

> 파티션 자식 테이블 제외 — `INHERITS (부모테이블)` 구문이 있는 테이블은 파싱 시 건너뜀 (`CreateStmt.inhRelations` 체크)

**컬럼 정보:**

| 엑셀 컬럼 | 설명 | DDL 파싱 소스 |
|----------|------|--------------|
| No. | 순번 | 자동 생성 |
| COLUMN NAME | 컬럼명 | `CREATE TABLE` 컬럼 정의 |
| ATTRIBUTE NAME | 한글 속성명 | `COMMENT ON COLUMN` (없으면 `""`) |
| Type | 데이터 타입 약식 (길이 제외) | `CREATE TABLE` 타입 → 약식 변환 (예: `VC`, `INT`) |
| Length | 길이 숫자만. 없으면 공백 | varchar(12) → `12`, integer → 공백 |
| Null | Null 허용 여부 | `NOT NULL` → `NN` / 없으면 빈칸 |
| Keys | PK / UK 표시 | 제약조건에서 파생 |
| Description | 설명 | 빈칸 (미사용) |
| Attribute Type | 속성 유형 | FK이면 `RELATION`, 코드그룹이면 `코드 그룹`, 나머지 빈칸 |
| Relation & Value | FK 참조 테이블.컬럼 또는 코드그룹 조건 | FK: `ref_table.ref_col` / 코드그룹: `IND_CD="컬럼명"` |
| Source | 코드 값 목록 | 코드그룹일 때 `["APLY", "TRMN"]` 형식, 나머지 빈칸 |

### DDL 파일에서 추출 불가 (빈칸 또는 규칙 기반 출력)

| 엑셀 항목 | 위치 | 비고 |
|----------|------|------|
| TableSpace | Row1 C | 빈칸 |
| Sub System | Row1 H | table_subject_rules.json 패턴 매칭 |
| 주제영역명 | Row1 J | table_subject_rules.json 패턴 매칭 |
| 주제영역명약어 | Row1 L | table_subject_rules.json 패턴 매칭 |
| 최초작성일 | Row2 C | 빈칸 |
| 최종수정일 | Row2 F:G | 빈칸 |
| 엔티티분류 | Row2 J | entity_class_rules.json 또는 AI 추론 |
| 오너쉽 | Row2 K | 빈칸 |
| Entity 정의 | Row3 B:L | entity_definition_rules.json 또는 AI 추론. 없으면 빈칸 |
| 인포타입명 | H열 | 빈칸 |
| Attribute Type | J열 | FK → `RELATION`, 코드그룹 → `코드 그룹`, rules.json 매칭 → 고정값, 나머지 빈칸 |
| Source | L열 | 코드그룹 매칭 시 코드값 목록 (`["APLY", "TRMN"]` 형식), 나머지 빈칸 |

---

## 기술 스택

- Python 3.12+
- pglast>=7.0 (PostgreSQL DDL 파서 — ddl-diff 프로젝트와 동일)
- openpyxl>=3.1
- pytest>=8.0
- anthropic>=0.25 (AI 추론 — 빈 코멘트 자동 보완)

> psycopg2 불필요 — 라이브 DB 연결 없음

---

## 디렉토리 구조

```
pg-tabledef/
├── CLAUDE.md
├── agents/
│   ├── PLAN.md              ← 이 파일 (설계 담당)
│   ├── IMPLEMENT.md         ← 구현 담당 에이전트 가이드
│   └── TEST.md              ← 테스트 담당 에이전트 가이드
├── rules/                   ← 엑셀 출력 규칙 파일
│   ├── column_attribute_rules.json  ← (column_name, attribute_name) → (attr_type, rel_val)
│   ├── dtl_code.csv                 ← 코드그룹 정의 (코드그룹,설명,그룹접두사,코드값,코드명칭)
│   ├── entity_class_rules.json      ← 테이블명 → KEY/MAIN/ACTION (AI 추론값 캐시)
│   ├── entity_definition_rules.json ← 테이블명 → Entity 정의 텍스트 (AI 추론값 캐시)
│   ├── inferred_fk_rules.json       ← 테이블명 → FK 관계 추론 (AI 추론값 캐시 + 수동 정의)
│   ├── table_subject_rules.json     ← 테이블명 패턴 → Sub System/주제영역명/약어
│   └── exclude_tables.txt           ← 출력에서 제외할 테이블명 목록 (줄당 1개)
├── input/                   ← IntelliJ SQL Generator로 추출한 DDL 파일
├── output/                  ← 생성된 엑셀 파일
├── requirements.txt
├── main.py
├── pg_tabledef/
│   ├── __init__.py
│   ├── models.py
│   ├── parser.py
│   ├── enricher.py              ← AI 추론 보완 (comment / attribute_name / entity_class / entity_definition / inferred_fk)
│   └── writer/
│       ├── __init__.py
│       ├── styles.py
│       └── excel.py
└── tests/
    ├── __init__.py
    ├── conftest.py
    ├── test_parser.py
    └── test_writer.py
```

---

## 모듈 역할

| 파일 | 역할 |
|------|------|
| `models.py` | 순수 데이터 클래스 (TableDef, ColumnDef, IndexDef, FKInfo) |
| `parser.py` | pglast로 `.sql` 파일 파싱 → models 조립, filter_excluded() |
| `enricher.py` | AI 추론 보완 (comment / attribute_name / entity_class / entity_definition / inferred_fk) |
| `writer/styles.py` | openpyxl 스타일 상수 |
| `writer/excel.py` | 엑셀 출력, _resolve_subject() 주제영역 매핑 |
| `main.py` | CLI 진입점 |

> ddl-diff `/Users/harry/projects/ddl-diff/ddl_diff/mapper.py` — 타입 변환·제약조건 파싱 로직 참고

---

## 입출력 경로

| 항목 | 경로 | 비고 |
|------|------|------|
| 입력 | `./input/` | 스키마 파일을 수동으로 올려두는 폴더 |
| 출력 | `./output/` | 파일 저장 폴더 |
| 출력 파일명 | `테이블정의서.xlsx` | 엑셀 정의서 (고정, 덮어쓰기) |
| 제외 목록 | `./rules/exclude_tables.txt` | 없으면 전체 출력 |

## 제외 테이블 (`rules/exclude_tables.txt`)

파싱 완료 후 엑셀 출력 전에 제외 목록에 있는 테이블을 필터링.

**파일 형식:**
```
# 주석은 # 으로 시작
monthly_del_cust_id
monthly_del_phub_tr_no
ph_pnt_cust_ctn_tmp
```

**처리 규칙:**
- 줄당 테이블명 1개 (앞뒤 공백 제거)
- `#`으로 시작하는 줄 및 빈 줄 무시
- 대소문자 구분 없이 비교 (소문자 정규화)
- 파일이 없으면 제외 없이 전체 출력
- 적용 시점: `parse_files()` 반환 직후, `enrich()` 호출 전 (불필요한 AI 호출 방지)
- 제외된 테이블 수 콘솔에 출력: `[INFO] 제외: N개 테이블 (exclude_tables.txt)`

**적용 위치: `main.py`**
```python
tables = parse_files(input_dir)
tables = filter_excluded(tables)   # ← rules/exclude_tables.txt 적용
tables = enrich(tables)
```

**`filter_excluded()` 위치:** `pg_tabledef/parser.py` 내 유틸 함수로 추가.

## 파싱 오류 처리

`pglast.parse_sql(sql_text)` 가 전체 파일 파싱에 실패하면, `_split_sql_statements()` 로 문장별 분리 후 재시도.

- `_split_sql_statements()`: 단일 인용부호(`'...'`), `--` 줄 주석, `/* */` 블록 주석 내부의 `;` 를 무시하고 세미콜론 기준으로 분리
- 재시도 시 각 문장을 개별 파싱 — 실패 문장만 스킵, 나머지는 정상 처리
- 스킵된 문장 수를 콘솔에 출력: `[WARN] N개 문장 스킵 (invalid SQL)`

**적용 위치:** `pg_tabledef/parser.py` — `parse_files()` 내 파일별 파싱 블록

---

## 파일 파싱 전략

### 입력 파일 형식

IntelliJ Database Tools → SQL Generator로 추출한 PostgreSQL DDL `.sql` 파일.
`ddl-diff` 프로젝트(`/Users/harry/projects/ddl-diff`)와 동일한 형식.

파일에 포함된 statement 종류:

| Statement | 예시 | 처리 여부 |
|-----------|------|---------|
| `CREATE SEQUENCE` | `create sequence seq_ba_id maxvalue 99999999 cycle;` | ✅ |
| `CREATE TABLE` | 컬럼 정의 + NOT NULL 포함 | ✅ |
| `COMMENT ON TABLE` | `comment on table t is '한글명';` | ✅ |
| `COMMENT ON COLUMN` | `comment on column t.col is '컬럼설명';` | ✅ |
| `CREATE INDEX` | `create index idx on t (col);` | ✅ |
| `CREATE UNIQUE INDEX` | `create unique index …` | ✅ |
| `ALTER TABLE … PRIMARY KEY` | `alter table t add constraint … primary key (…);` | ✅ |
| `ALTER TABLE … FOREIGN KEY` | `alter table t add constraint … foreign key (col) references ref_t;` | ✅ |

### 파서: pglast

`pglast` (ddl-diff에서 동일하게 사용 중). AST 노드 타입:

| pglast AST | 역할 |
|-----------|------|
| `CreateSeqStmt` | 시퀀스 (파싱하되 출력 안 함 — 무시) |
| `CreateStmt` | 테이블 + 컬럼 |
| `CommentStmt` | 테이블/컬럼 코멘트 |
| `IndexStmt` | 인덱스 |
| `AlterTableStmt` + `AT_AddConstraint` | PK / FK |

### 주의: COMMENT ON 처리

ddl-diff는 코멘트가 불필요해 `CommentStmt`를 무시하지만, pg-tabledef는 필수.
`CommentStmt.objtype`으로 TABLE / COLUMN 구분:
- `OBJECT_TABLE` → 테이블 코멘트
- `OBJECT_COLUMN` → 컬럼 코멘트 (ATTRIBUTE NAME에만 저장)

### 타입 표시 포맷

ddl-diff의 `_TYPE_MAP` + `_extract_type_str` 로직 재사용.
약식 표기 변환 규칙은 PLAN.md `## 타입 표시 포맷` 섹션 참고.

---

## 엑셀 시트 레이아웃

시트 1개에 모든 테이블을 순서대로 나열. 테이블 간 빈 행으로 구분.

### 섹션 1: 테이블 정보 헤더 (3행)

레이아웃. 병합 셀 포함.

```
Row 1: [A1]Table 명 | [B1]{table_name} | [C1]TableSpace | [D1:E1]   | [F1:G1]Sub System | [H1]   | [I1]주제영역명 | [J1]  | [K1]주제영역명약어 | [L1]
Row 2: [A2]Entity 명| [B2]{comment}    | [C2]최초작성일  | [D2:E2]   | [F2:G2]최종수정일  | [H2]   | [I2]엔티티분류  | [J2]  | [K2]오너쉽        | [L2]
Row 3: [A3]Entity 정의 | [B3:L3] Entity 정의 텍스트 (높이 160)
```

- `{table_name}`: 테이블명
- `{comment}`: 테이블 코멘트 (없으면 `""`). AI 추론값(`table.comment_ai is True`)이면 **주황색 글씨** (`FONT_AI_SUGGESTED`)
- 나머지 값 필드: 모두 빈칸 출력 (수동 입력 항목)

### 섹션 2: Key List

```
┌──────────────────┬──────────────────────────┬───────────────────────────────────┐
│    구분/Key List  │        Key Name           │           Column Name             │
├──────────────────┼──────────────────────────┼───────────────────────────────────┤
│   Primary Key    │ {pk_constraint_name}      │ {pk_columns}                      │
│   Foreign Key    │ {fk_constraint_name}      │ {fk_column} → {ref_table}         │
│   Index Key      │ {index_name}              │ {index_columns}                   │
│   Sequence Key   │                           │                                   │
└──────────────────┴──────────────────────────┴───────────────────────────────────┘
```

- **Key Name (B:C 병합)**: 제약조건 또는 인덱스의 이름
  - Primary Key: `ALTER TABLE ... ADD CONSTRAINT {name} PRIMARY KEY` 에서 추출한 제약조건명
  - Foreign Key: `ALTER TABLE ... ADD CONSTRAINT {name} FOREIGN KEY` 에서 추출한 제약조건명
  - Index Key: `CREATE INDEX {name}` 에서 추출한 인덱스명
- **Column Name (D:L 병합)**: 해당 키가 포함하는 컬럼 필드
  - Primary Key: `order_id` (컬럼명, 복합이면 `, ` 구분)
  - Foreign Key: `cust_id → customers` (로컬컬럼 → 참조테이블)
  - Index Key: `cust_id` (인덱스 컬럼, 복합이면 `, ` 구분)
- FK가 여러 개인 경우 Foreign Key 행의 Key Name / Column Name을 `, `로 구분하여 한 줄로 출력
- Index Key가 여러 개인 경우 동일하게 `, `로 구분하여 한 줄로 출력

**Key List 정렬 규칙:**
- A열 타이틀 ("Primary Key", "Foreign Key", "Index Key", "Sequence Key"): **가운데 정렬** (`ALIGN_CENTER`)
- B:C 병합 Key Name 값: **왼쪽 정렬** (`ALIGN_LEFT`)
- D:L 병합 Column Name 값: **왼쪽 정렬** (`ALIGN_LEFT`)
- Row 4 헤더 ("구분/Key List", "Key Name", "Column Name"), Row 9–11 Partition 행: 가운데 정렬 유지

**모델 요구사항 (Key Name 지원):**
- `TableDef.pk_constraint_name: str` — PK 제약조건명 (없으면 `""`)
- `FKInfo.constraint_name: str` — FK 제약조건명 (없으면 `""`)
- `IndexDef.name` — 인덱스명 (기존 필드 그대로 사용)

### 섹션 3: 컬럼 목록

```
┌────┬──────────────────┬──────────────────┬──────┬────────┬──────┬──────┬──────────────┬──────────────┬────────────────────┬────────┐
│ No.│ COLUMN NAME      │ ATTRIBUTE NAME   │ Type │ Length │ Null │ Keys │ 업무규칙명   │ Description  │ Attribute Info     │ Source │
│    │                  │                  │      │        │      │      │              │              ├──────────┬─────────┤        │
│    │                  │                  │      │        │      │      │              │              │Attr Type │Rel&Val  │        │
├────┼──────────────────┼──────────────────┼──────┼────────┼──────┼──────┼──────────────┼──────────────┼──────────┼─────────┼────────┤
│  1 │ IF_DD            │ 연동일자          │ VC   │      8 │ NN   │ PK   │              │              │          │         │        │
│  2 │ IF_SYS_CD        │ 연계시스템코드    │ VC   │     10 │ NN   │ PK   │              │              │          │         │        │
│  3 │ ERR_CD           │ 에러코드          │ VC   │      8 │ NN   │ PK   │              │              │          │         │        │
│  8 │ RGST_USER_ID     │ 등록자ID          │ VC   │     10 │      │      │              │              │ RELATION │사용자정보.사용자코 │        │
└────┴──────────────────┴──────────────────┴──────┴────────┴──────┴──────┴──────────────┴──────────────┴──────────┴─────────┴────────┘
```

**전체 시트 구성:**
```
[테이블 A 섹션 1: 헤더]
[테이블 A 섹션 2: Key List]
[테이블 A 섹션 3: 컬럼 목록]
(빈 행 2개)
[테이블 B 섹션 1: 헤더]
[테이블 B 섹션 2: Key List]
[테이블 B 섹션 3: 컬럼 목록]
(빈 행 2개)
...
```

추가 설정:
- 시트명: `테이블정의서` (고정)
- 테이블 정렬: 알파벳 순
- PK 행: bold 처리
- Keys 열: PK → `PK`, FK → `FK`, Unique Key → `UK`
  - 복합 표시: PK이면서 FK이면 `PK,FK`, UK이면서 FK이면 `UK,FK`
  - 우선순위: PK 먼저, 그 다음 UK, 마지막 FK (예: `PK,FK`)
- FK Relation & Value: `{참조테이블}.{참조컬럼}` 형식, Attribute Type = `RELATION`
- 코드그룹 규칙 (`rules/dtl_code.csv`): 아래 두 조건 중 하나라도 일치하면 동일하게 적용
  - **B열 매칭**: `col.name == CSV 1열(코드그룹명)` → K열 `IND_CD="{col.name}"`
  - **C열 매칭**: `col.attribute_name == CSV 2열(설명)` → K열 `IND_CD="{해당 행의 1열 코드그룹명}"`
  - J열 Attribute Type = `코드 그룹`
  - L열 Source = 해당 코드그룹의 코드값 목록, `["APLY", "TRMN"]` 형식
  - CSV 포맷: `코드그룹,설명,그룹접두사,코드값,코드명칭` (5열)
- column_attribute_rules.json 규칙: `(column_name, attribute_name)` 쌍 매칭 → J, K열 고정값 출력
- ATTRIBUTE NAME: 컬럼 코멘트 그대로 출력. AI 추론값은 주황색 글씨
- Description: 빈칸 (미사용)
- 타입 표시: 약식 표기 적용 (`VC`, `INT`, `TS` 등) — 길이는 Length 열에 별도 출력
- **M열 COMMENT SQL**: AI가 추론한 attribute_name이 있는 컬럼에만 PostgreSQL COMMENT 스크립트 출력
  - 형식: `COMMENT ON COLUMN {table_name}.{col_name} IS '{attribute_name}';`
  - AI 추론값이 아닌 경우(원래 DDL에 코멘트 있던 경우): 빈칸
  - 폰트: 주황색 (`FONT_AI_SUGGESTED`) 동일 적용

---

## 컬럼 너비

컬럼 너비 기준:

| 열 | 항목 | 너비 |
|----|------|------|
| A | No. | 16.7 |
| B | COLUMN NAME | 28.0 |
| C | ATTRIBUTE NAME | 30.8 |
| D | Type | 14.7 |
| E | Length | 8.0 |
| F | Null | 6.8 |
| G | Keys | 6.3 |
| H | 인포타입명 | 17.0 |
| I | Description | 21.7 |
| J | Attribute Type | 18.0 |
| K | Relation & Value | 25.0 |
| L | Source | 15.0 |
| M | COMMENT SQL | 60.0 |

> H열 레이블: `업무규칙명` → `인포타입명` (샘플 기준)
> M열은 AI 추론 attribute_name이 있는 행에만 출력. 헤더 셀은 다른 열과 동일한 스타일 적용

## Null 표시 규칙

| 조건 | 표시 |
|------|------|
| NOT NULL | `NN` |
| nullable | 빈칸 (공백) |

> 기존 `Y` 표시 제거 — NOT NULL인 경우만 NN, 나머지는 셀을 비움

## 행 높이

| 행 | 내용 | 높이 |
|----|------|------|
| Row 1 | 테이블 정보 Row 1 | 20 |
| Row 2 | 테이블 정보 Row 2 | 20 |
| Row 3 | Entity 정의 | 160 |
| Row 4 | Key List 헤더 | 40 |
| Row 5~11 | Key List 데이터 | 20 |
| Row 12~13 | 컬럼 헤더 | 20 |
| Row 14~ | 컬럼 데이터 | 20 |

---

## 타입 표시 포맷 (약식 표기 규칙)

DDL 타입명 → 엑셀 표시값:

| 분류 | DDL 타입명 | 엑셀 표시 | 비고 |
|------|-----------|----------|------|
| 숫자 | TINYINT | TINT | |
| | SMALLINT / int2 | SINT | |
| | BIGINT / int8 | BINT | |
| | INT / INTEGER / int4 | INT | preferred |
| | SERIAL | SR | |
| | BIGSERIAL | BSR | |
| | NUMBER | N | |
| | DECIMAL / numeric | DEC | |
| 문자 | VARCHAR / varchar | VC | preferred |
| | VARCHAR2 | VC | |
| | NVARCHAR | NVC | |
| | TEXT | TXT | |
| 대용량 | CLOB | CLB | |
| | BLOB | BLB | |
| | XML | XML | |
| 날짜/시간 | DATE / date | D | |
| | TIME / time | T | |
| | DATETIME | DT | |
| | TIMESTAMP / timestamp | TS | |
| 그 외 | — | DDL 타입명 그대로 | |

> 길이는 `ColumnDef.length` 필드에 별도 저장 — Type 열에는 약식(`VC`, `DEC`)만, Length 열에 숫자만 출력

---

## Entity 정의 (`rules/entity_definition_rules.json`)

### 개요

테이블 헤더 Row 3 B:L 병합 셀에 Entity 정의 텍스트 출력.

**형식 (3개 섹션 고정, 테이블명 없이 1.부터 시작):**
```
 1.집합적 의미
• ...
 2.기능적 의미
• ...
 3.자료발생 규칙
• ...
```

### 규칙 파일 (`rules/entity_definition_rules.json`)

```json
{
  "테이블명_소문자": " 1.집합적 의미\n• ...\n 2.기능적 의미\n• ...\n 3.자료발생 규칙\n• ..."
}
```

### 처리 흐름 (`enrich_entity_definition()` in `enricher.py`)

1. `rules/entity_definition_rules.json` 로드
2. 각 테이블명(소문자)을 JSON에서 조회
   - 있으면: `entity_definition` 설정, `entity_definition_ai = False`
   - 없으면: AI 추론 대상 목록에 추가
3. AI 추론 (`ANTHROPIC_API_KEY` 없으면 스킵)
   - 샘플 예제 few-shot + 테이블명/설명/엔티티분류/컬럼 목록 제공
   - 3개 섹션 형식으로 출력
   - `entity_definition_ai = True` 플래그 설정
4. 새 AI 추론값을 JSON 파일에 저장

### models.py 추가 필드

```python
entity_definition: str = ""         # Entity 정의 텍스트 (Row3 B:L)
entity_definition_ai: bool = False  # True이면 AI가 추론한 값
```

### excel.py 적용

- Row 3 B:L 병합 셀: `table.entity_definition` 출력 (`ALIGN_LEFT`, wrap_text)
- `entity_definition_ai is True`이면 **주황색 글씨** (`FONT_AI_SUGGESTED`)

### main.py 호출 순서

```python
tables = enrich(tables)
tables = enrich_entity_class(tables)
tables = enrich_entity_definition(tables)
```

---

## 엔티티분류 (`rules/entity_class_rules.json`)

### 개요

테이블 헤더 Row 2 J열(col 10)에 엔티티분류 값(`KEY` / `MAIN` / `ACTION`) 출력.

| 값 | 의미 |
|----|------|
| `KEY` | 기준/코드성 테이블 (코드값, 설정, 분류 기준 데이터) |
| `MAIN` | 핵심 비즈니스 엔티티 테이블 (고객, 상품, 계약 등) |
| `ACTION` | 트랜잭션/이력/로그 테이블 (_hist, _log, _ptcl 등) |

### 규칙 파일 (`rules/entity_class_rules.json`)

```json
{
  "테이블명_소문자": "KEY"
}
```

- 키: 테이블명 소문자
- 값: `KEY` / `MAIN` / `ACTION`
- AI 추론 결과가 자동으로 누적 저장됨 (이후 재실행 시 JSON 우선 사용)

### 처리 흐름 (`enrich_entity_class()` in `enricher.py`)

1. `rules/entity_class_rules.json` 로드
2. 각 테이블명(소문자)을 JSON에서 조회
   - 있으면: `entity_class` 설정, `entity_class_ai = False`
   - 없으면: AI 추론 대상 목록에 추가
3. AI 추론 (`ANTHROPIC_API_KEY` 없으면 스킵)
   - 테이블명, 테이블 설명, 컬럼 목록을 컨텍스트로 전달
   - `KEY` / `MAIN` / `ACTION` 중 하나 반환
   - `entity_class_ai = True` 플래그 설정
4. 새 AI 추론값을 JSON 파일에 저장

### models.py 추가 필드

```python
entity_class: str = ""         # 엔티티분류 (KEY / MAIN / ACTION)
entity_class_ai: bool = False  # True이면 AI가 추론한 값
```

### excel.py 적용

- Row 2 J열(col 10): `table.entity_class` 출력
- `entity_class_ai is True`이면 **주황색 글씨** (`FONT_AI_SUGGESTED`)

---

## 테이블 주제영역 매핑 (`rules/table_subject_rules.json`)

### 개요

테이블명 패턴 기반으로 섹션 1 헤더 Row 1의 값을 자동 결정.

| 엑셀 위치 | 항목 | 열 |
|----------|------|---|
| Row 1 H열 (col 8) | Sub System | `sub_system` |
| Row 1 J열 (col 10) | 주제영역명 | `subject_area` |
| Row 1 L열 (col 12) | 주제영역명약어 | `subject_area_abbr` |

### 규칙 파일 형식 (`rules/table_subject_rules.json`)

```json
{
  "strip_prefixes": ["EX_"],
  "rules": [
    { "type": "prefix",   "pattern": "ADM_",   "sub_system": "ONM",  "subject_area": "ONM",      "subject_area_abbr": "ADM"  },
    { "type": "prefix",   "pattern": "PH_",    "sub_system": "PHUB", "subject_area": "포인트허브", "subject_area_abbr": "PH"   },
    { "type": "prefix",   "pattern": "ST_",    "sub_system": "ONM",  "subject_area": "통계",      "subject_area_abbr": "ST"   },
    { "type": "contains", "pattern": "_CMPR_", "sub_system": "CMPR", "subject_area": "일대사",    "subject_area_abbr": "CMPR" },
    { "type": "prefix",   "pattern": "FP_",    "sub_system": "",     "subject_area": "패밀리포인트", "subject_area_abbr": "FP" }
  ]
}
```

### 매칭 로직 (`_resolve_subject()` in `excel.py`)

1. `strip_prefixes` 중 일치하는 접두사가 있으면 제거 후 나머지 이름으로 규칙 적용
2. `rules` 배열 순서대로 첫 번째 일치 규칙 적용
   - `type: "prefix"` → 테이블명이 해당 패턴으로 시작하면 매칭
   - `type: "contains"` → 테이블명에 해당 패턴이 포함되면 매칭
3. 매칭 없으면 세 값 모두 `""` (빈칸 출력)
4. 비교는 대소문자 무관 (내부적으로 `.upper()` 정규화)

### 적용 위치

`pg_tabledef/writer/excel.py` — `_write_table_header()` 상단에서 `_resolve_subject(table.name)` 호출 후 H/J/L열에 적용.

---

## AI 추론 보완 요약

모든 AI 추론은 `enricher.py`에서 처리. `ANTHROPIC_API_KEY` 없으면 경고 후 스킵.
추론된 값은 **주황색 글씨** (`FONT_AI_SUGGESTED`, `#CC5500`)로 출력.
AI 추론값은 각 JSON 파일에 캐시 저장 (이후 실행 시 API 호출 없이 재사용).

| enricher 함수 | 대상 | 캐시 파일 |
|--------------|------|---------|
| `enrich()` | `table.comment`, `col.attribute_name` | 없음 (매번 추론) |
| `enrich_entity_class()` | `table.entity_class` | `entity_class_rules.json` |
| `enrich_entity_definition()` | `table.entity_definition` | `entity_definition_rules.json` |
| `enrich_inferred_fk()` | `table.inferred_fk_list` | `inferred_fk_rules.json` |

## FK 관계 추론 (`rules/inferred_fk_rules.json`)

DDL에 FK 제약조건이 없는 경우 테이블 간 관계를 추론하여 `TableDef.inferred_fk_list`에 저장.
ERD 생성 등 후속 처리에서 사용.

### 처리 순서

1. **JSON 캐시 우선**: `rules/inferred_fk_rules.json` 에 있으면 그 값 사용 (null이면 "관계 없음" 확정)
2. **컬럼명 자동 매칭**: A 테이블 단일 PK 컬럼명 == B 테이블 일반 컬럼명 → B→A 관계 추론 (`source="auto"`)
3. **AI 추론**: 접미사(`_id`, `_cd`, `_no`, `_seq`, `_key`, `_code`)로 끝나는 나머지 컬럼을 AI가 추론 후 JSON 저장 (`source="ai"`)

### 모델

```python
@dataclass
class InferredFKInfo:
    column: str       # 로컬 컬럼명
    ref_table: str    # 참조 테이블명
    ref_column: str   # 참조 컬럼명
    source: str = ""  # "auto" | "ai"
```

`TableDef.inferred_fk_list: list[InferredFKInfo]` — 실제 FK(`fk_list`)와 분리하여 저장.

### JSON 캐시 형식

```json
{
  "_exclude": {
    "columns": ["rgst_user_id", "mdfy_user_id"],
    "ref_tables": ["adm_cmn_cd_d", "adm_cmn_cd_m"],
    "table_prefixes": ["EX_"]
  },
  "테이블명_소문자": {
    "컬럼명": {"ref_table": "참조테이블명", "ref_column": "참조컬럼명"},
    "컬럼명2": null
  }
}
```

- null 값: AI가 관계 없다고 판단 → 이후 재추론 스킵
- `_exclude.columns`: 추론 대상에서 제외할 컬럼명 (예: 등록자/수정자 공통 컬럼)
- `_exclude.ref_tables`: 참조 대상에서 제외할 테이블명
- `_exclude.table_prefixes`: 해당 접두어 테이블은 소스/참조 모두 제외 (예: EX_ 복사본 테이블)

**main.py 호출 순서:**
```python
tables = filter_excluded(tables)
tables = enrich(tables)
tables = enrich_entity_class(tables)
tables = enrich_entity_definition(tables)
tables = enrich_inferred_fk(tables)
```

---

## ERD 출력 (`output/erd*.md`)

`python main.py` 실행 시 엑셀과 함께 자동 생성.
Mermaid `erDiagram` 블록을 포함한 마크다운 — GitHub / Notion / VS Code에서 바로 렌더링.

### 출력 파일

| 파일 | 내용 | 목적 |
|------|------|------|
| `output/erd.md` | 전체 테이블 — 엔티티 레이블만, 관계 라인 | 전체 구조 개요 |
| `output/erd_{abbr}.md` | 주제영역별 — 컬럼 상세 포함, 외부 참조 테이블 stub | 영역별 상세 확인 |

- `abbr`: `table_subject_rules.json`의 `subject_area_abbr` (예: ONM, PHUB, ST …)
- 주제영역 미분류 테이블: `erd_기타.md`

### Mermaid 텍스트 크기 제한 대응

모든 파일 첫 줄에 `%%{init: {'maxTextSize': 200000}}%%` 추가.
전체 ERD는 컬럼 상세를 생략하여 텍스트 크기 최소화.

### 관계 표시

| 구분 | 표기 | 소스 |
|------|------|------|
| 실제 FK | `\|\|--o{` (실선) | DDL `ALTER TABLE ... FOREIGN KEY` |
| 추론 FK | `\|\|..o{` (점선) | `inferred_fk_list` (자동 매칭 + AI 추론) |

### 엔티티 레이블

`table_name["논리명 (물리명)"]` 형식으로 한 줄 표시.
코멘트가 없으면 물리명만 표시.
주제영역별 파일의 외부 참조 테이블은 레이블만 출력 (컬럼 생략).

---

## 확장 방법

새 항목 추가 시:
1. `models.py` 해당 dataclass에 Optional 필드 추가
2. `parser.py` 에서 해당 DDL statement 파싱 로직 추가
3. `writer/excel.py` 에 새 섹션 또는 컬럼 추가

