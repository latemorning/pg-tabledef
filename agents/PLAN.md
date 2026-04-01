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

## 참고 양식

실제 엑셀 테이블 정의서 양식 (`data/IMG_9919.HEIC`) 분석 결과:

**구성 섹션:**
1. 테이블 정보 헤더 (상단)
2. Key List (중단)
3. 컬럼 목록 (하단)

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

### DDL 파일에서 추출 불가 (빈칸 출력)

| 엑셀 항목 | 위치 | 비고 |
|----------|------|------|
| TableSpace | Row1 C | 미지원 (빈칸) |
| Sub System | Row1 F:G | 미지원 (빈칸) |
| 주제영역명 | Row1 I | 미지원 (빈칸) |
| 주제영역명약어 | Row1 K | 미지원 (빈칸) |
| 최초작성일 | Row2 C | 미지원 (빈칸) |
| 최종수정일 | Row2 F:G | 미지원 (빈칸) |
| 엔티티분류 | Row2 I | 미지원 (빈칸) |
| 오너쉽 | Row2 K | 미지원 (빈칸) |
| Entity 정의 | Row3 B:L | 미지원 (빈칸) |
| 인포타입명 | H열 | 미지원 (빈칸) |
| Attribute Type | J열 | FK → `RELATION`, 코드그룹 → `코드 그룹`, rules.json 매칭 → 고정값, 나머지 빈칸 |
| Source | L열 | 코드그룹 매칭 시 코드값 목록 (`["APLY", "TRMN"]` 형식), 나머지 빈칸 |

이후 항목 추가 가능한 확장 구조로 설계.

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
├── data/
│   └── IMG_9919.HEIC        ← 참고 양식 이미지
├── rules/                   ← J/K/L열 출력 규칙 파일
│   ├── column_attribute_rules.json  ← (column_name, attribute_name) → (attr_type, rel_val)
│   ├── dtl_code.csv         ← 코드그룹 정의 (코드그룹,설명,그룹접두사,코드값,코드명칭)
│   └── exclude_tables.txt   ← 출력에서 제외할 테이블명 목록 (줄당 1개)
├── input/                   ← IntelliJ SQL Generator로 추출한 DDL 파일
├── output/                  ← 생성된 엑셀 파일
├── requirements.txt
├── main.py
├── pg_tabledef/
│   ├── __init__.py
│   ├── models.py
│   ├── parser.py
│   ├── enricher.py              ← AI 추론으로 빈 코멘트 보완
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
| `parser.py` | pglast로 `.sql` 파일 파싱 → models 조립 (ddl-diff mapper.py 참고) |
| `writer/styles.py` | openpyxl 스타일 상수 |
| `writer/excel.py` | 엑셀 출력 |
| `main.py` | CLI 진입점 |

> ddl-diff `/Users/harry/projects/ddl-diff/ddl_diff/mapper.py` — 타입 변환·제약조건 파싱 로직 참고

---

## 입출력 경로

| 항목 | 경로 | 비고 |
|------|------|------|
| 입력 | `./input/` | 스키마 파일을 수동으로 올려두는 폴더 |
| 출력 | `./output/` | 엑셀 파일 저장 폴더 |
| 출력 파일명 | `테이블정의서.xlsx` | 고정 (덮어쓰기) |
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

샘플(`template/sample.xlsx`) 기준 레이아웃. 병합 셀 포함.

```
Row 1: [A1]Table 명 | [B1]{table_name} | [C1]TableSpace | [D1:E1]   | [F1:G1]Sub System | [H1]   | [I1]주제영역명 | [J1]  | [K1]주제영역명약어 | [L1]
Row 2: [A2]Entity 명| [B2]{comment}    | [C2]최초작성일  | [D2:E2]   | [F2:G2]최종수정일  | [H2]   | [I2]엔티티분류  | [J2]  | [K2]오너쉽        | [L2]
Row 3: [A3]Entity 정의 | [B3:L3]                                                    (빈칸, 높이 120)
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

샘플(`template/sample.xlsx`) 기준:

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
| Row 3 | Entity 정의 | 120 |
| Row 4 | Key List 헤더 | 40 |
| Row 5~11 | Key List 데이터 | 20 |
| Row 12~13 | 컬럼 헤더 | 20 |
| Row 14~ | 컬럼 데이터 | 20 |

---

## 타입 표시 포맷 (약식 표기 규칙)

이미지(`data/IMG_9920.HEIC`) 기준 약식 표기. DDL 타입명 → 엑셀 표시값:

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

## AI 추론 보완 (enricher.py)

### 개요

파싱 후 엑셀 출력 전, 빈 Entity 명 / ATTRIBUTE NAME 을 Claude API로 자동 추론.
추론된 값은 엑셀에서 **주황색 글씨** (`#CC5500`, Claude 아이콘 계열)로 출력.

### 대상 필드

| 조건 | 대상 |
|------|------|
| `table.comment == ""` | A열 Entity 명 |
| `col.attribute_name == ""` | C열 ATTRIBUTE NAME |

### models.py 추가 플래그

```python
@dataclass
class TableDef:
    ...
    comment_ai: bool = False   # True이면 AI가 추론한 comment

@dataclass
class ColumnDef:
    ...
    attribute_name_ai: bool = False  # True이면 AI가 추론한 attribute_name
```

### enricher.py 처리 흐름

```python
def enrich(tables: list[TableDef]) -> list[TableDef]:
    """빈 comment / attribute_name을 Claude API로 보완."""
```

1. **테이블 단위 배치**: 테이블 1개당 API 호출 1회
   - 입력: 테이블명, 기존 컬럼명 + attribute_name 목록 (컨텍스트)
   - 요청 항목: 빈 comment(테이블) + 빈 attribute_name(컬럼) 목록
2. **제약 조건**: 한두 단어, 최대 10자, 한글
3. **응답 파싱**: JSON 형식으로 반환 요청 (`{"table_comment": "...", "columns": {"col_name": "..."}}`
4. **플래그 설정**: 추론된 값은 `comment_ai = True` / `attribute_name_ai = True`
5. **API 키**: `ANTHROPIC_API_KEY` 환경변수. 없으면 경고 출력 후 AI 보완 건너뜀
6. **모델**: `claude-haiku-4-5-20251001` (속도/비용 최적)

### styles.py 추가 상수

```python
FONT_AI_SUGGESTED = Font(size=10, color="CC5500")  # Claude 주황색, AI 추론값용
```

### excel.py 적용

- `table.comment_ai is True` → Entity 명 셀에 `FONT_AI_SUGGESTED` 적용
- `col.attribute_name_ai is True` → ATTRIBUTE NAME 셀(C열)에 `FONT_AI_SUGGESTED` 적용
- `col.attribute_name_ai is True` → M열에 PostgreSQL COMMENT 스크립트 출력 (주황색)
  - 형식: `COMMENT ON COLUMN {table.name}.{col.name} IS '{col.attribute_name}';`
  - `attribute_name_ai is False`인 행의 M열: 빈칸

---

## 확장 방법

새 항목 추가 시:
1. `models.py` 해당 dataclass에 Optional 필드 추가
2. `parser.py` 에서 해당 DDL statement 파싱 로직 추가
3. `writer/excel.py` 에 새 섹션 또는 컬럼 추가

