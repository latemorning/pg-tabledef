"""pg_tabledef.enricher: 빈 comment / attribute_name을 Claude API로 자동 보완."""
from __future__ import annotations

import json
import os
from pathlib import Path

from .models import TableDef, InferredFKInfo

_RULES_DIR = Path(__file__).parent.parent / "rules"


def enrich(tables: list[TableDef]) -> list[TableDef]:
    """빈 table.comment / col.attribute_name을 Claude API로 추론하여 채운다.

    ANTHROPIC_API_KEY 환경변수가 없으면 경고 출력 후 원본 반환.
    테이블당 API 호출 1회 (배치 요청).
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        print("[WARN] ANTHROPIC_API_KEY 없음 — AI 보완 건너뜀")
        return tables

    try:
        import anthropic
    except ImportError:
        print("[WARN] anthropic 패키지 없음 — AI 보완 건너뜀")
        return tables

    client = anthropic.Anthropic(api_key=api_key)

    for table in tables:
        _enrich_table(client, table)

    return tables


def _enrich_table(client, table: TableDef) -> None:
    """테이블 1개에 대해 API 1회 호출로 빈 필드를 보완."""
    need_table_comment = table.comment == ""
    empty_cols = [col for col in table.columns if col.attribute_name == ""]

    if not need_table_comment and not empty_cols:
        return

    # 컨텍스트: 이미 코멘트가 있는 컬럼 목록
    context_pairs = [
        f"{col.name}: {col.attribute_name}"
        for col in table.columns
        if col.attribute_name
    ]
    context_str = "\n".join(context_pairs) if context_pairs else "없음"

    # 요청 항목 구성
    request_items: dict[str, str] = {}
    if need_table_comment:
        request_items["__table__"] = table.name
    for col in empty_cols:
        request_items[col.name] = col.type_str

    prompt = f"""PostgreSQL 테이블의 한글 설명을 추론해주세요.

테이블명: {table.name}
기존 컬럼 설명 (참고용):
{context_str}

아래 항목의 한글 설명을 추론하세요:
{json.dumps(request_items, ensure_ascii=False, indent=2)}

규칙:
- 한글로만 작성 (영어 금지)
- 한두 단어, 최대 10자
- 컬럼명/테이블명의 약어를 참고해 의미를 파악
- 기존 컬럼 설명과 일관된 스타일 유지

반드시 아래 JSON 형식만 반환하세요 (설명 없이):
{{"__table__": "테이블설명", "컬럼명": "한글설명", ...}}
__table__ 키는 테이블 설명이 필요한 경우에만 포함."""

    try:
        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = message.content[0].text.strip()
        # JSON 블록 추출 (```json ... ``` 형식 대응)
        if "```" in raw:
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        result: dict[str, str] = json.loads(raw)
    except Exception as e:
        print(f"[WARN] AI 추론 실패 ({table.name}): {e}")
        return

    if need_table_comment and "__table__" in result:
        val = str(result["__table__"])[:10]
        table.comment = val
        table.comment_ai = True

    for col in empty_cols:
        if col.name in result:
            val = str(result[col.name])[:10]
            col.attribute_name = val
            col.attribute_name_ai = True


# ──────────────────────────────────────────────────────────────────────────────
# 엔티티분류 (KEY / MAIN / ACTION) 보완
# ──────────────────────────────────────────────────────────────────────────────

_VALID_CLASSES = {"KEY", "MAIN", "ACTION"}


def enrich_entity_class(tables: list[TableDef]) -> list[TableDef]:
    """테이블 엔티티분류(KEY/MAIN/ACTION)를 rules/entity_class_rules.json + AI로 결정.

    JSON에 있으면 그 값을 사용. 없으면 AI 추론 후 JSON에 저장.
    AI 추론값은 entity_class_ai = True 플래그로 표시.
    """
    rules_path = _RULES_DIR / "entity_class_rules.json"

    # JSON 로드 (없으면 빈 dict)
    if rules_path.exists():
        with rules_path.open(encoding="utf-8") as f:
            rules: dict[str, str] = {
                k: v for k, v in json.load(f).items()
                if not k.startswith("_")  # _comment 등 메타키 제외
            }
    else:
        rules = {}

    # JSON 매칭
    tables_needing_ai: list[TableDef] = []
    for table in tables:
        val = rules.get(table.name.lower())
        if val and val.upper() in _VALID_CLASSES:
            table.entity_class = val.upper()
            table.entity_class_ai = False
        else:
            tables_needing_ai.append(table)

    if not tables_needing_ai:
        return tables

    # AI 추론
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        print(f"[WARN] ANTHROPIC_API_KEY 없음 — 엔티티분류 AI 추론 건너뜀 ({len(tables_needing_ai)}개)")
        return tables

    try:
        import anthropic
    except ImportError:
        print("[WARN] anthropic 패키지 없음 — 엔티티분류 AI 추론 건너뜀")
        return tables

    client = anthropic.Anthropic(api_key=api_key)
    new_entries: dict[str, str] = {}

    for table in tables_needing_ai:
        result = _infer_entity_class(client, table)
        if result:
            table.entity_class = result
            table.entity_class_ai = True
            new_entries[table.name.lower()] = result

    # 새 항목 JSON에 저장
    if new_entries:
        all_rules: dict = {}
        if rules_path.exists():
            with rules_path.open(encoding="utf-8") as f:
                all_rules = json.load(f)
        all_rules.update(new_entries)
        with rules_path.open("w", encoding="utf-8") as f:
            json.dump(all_rules, f, ensure_ascii=False, indent=2)
        print(f"[INFO] 엔티티분류 {len(new_entries)}개 AI 추론 완료 → entity_class_rules.json 저장")

    return tables


def _infer_entity_class(client, table: TableDef) -> str:
    """테이블 1개의 엔티티분류를 AI로 추론. KEY/MAIN/ACTION 반환."""
    col_info = "\n".join(
        f"  - {col.name}: {col.attribute_name}" if col.attribute_name else f"  - {col.name}"
        for col in table.columns[:20]
    )
    prompt = f"""PostgreSQL 테이블의 엔티티 분류를 결정하세요.

테이블명: {table.name}
테이블 설명: {table.comment or "(없음)"}
컬럼 목록:
{col_info}

분류 기준:
- KEY: 기준/코드성 테이블 (코드값, 설정, 분류 기준 데이터)
- MAIN: 핵심 비즈니스 엔티티 테이블 (고객, 상품, 계약 등 주요 데이터)
- ACTION: 트랜잭션/이력/로그 테이블 (_hist, _log, _ptcl, 이력, 처리내역 등)

KEY, MAIN, ACTION 중 하나만 반환하세요 (다른 텍스트 없이):"""

    try:
        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=10,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = message.content[0].text.strip().upper()
        for val in _VALID_CLASSES:
            if val in raw:
                return val
    except Exception as e:
        print(f"[WARN] 엔티티분류 AI 추론 실패 ({table.name}): {e}")
    return ""


# ──────────────────────────────────────────────────────────────────────────────
# Entity 정의 보완 (Row 3 B:L 병합 셀)
# ──────────────────────────────────────────────────────────────────────────────

_ENTITY_DEF_EXAMPLE = """\
아래는 Entity 정의 작성 샘플입니다. 반드시 이 형식 그대로 작성하세요 (테이블명 없이 1.부터 시작).

 1.집합적 의미
• 시스템 전반에 걸친 구분자 집합이다.
 2.기능적 의미
• 구분 코드의 변경이나 명칭의 변경에 유연하게 대응할 수 있다.
• 위 내용의 변경사항이 발생시 소스의 변화는 없다.
 3.자료발생 규칙
• ONM에서 등록 관리한다.
• 신규 개발이나 도메인 생성시 발생하는 분류코드를 등록한다.

---

 1.집합적 의미
• 거래가 완료된 정보 집합이다.(거래원장)
 2.기능적 의미
• 거래정보를 저장하여 정산 및 일대사 자료로 이용된다.
 3.자료발생 규칙
• 거래가 성공적으로 완료시 등록된다.

---

 1.집합적 의미
• 일/포인트별 거래성공 정보 집합이다.
 2.기능적 의미
• 일일 거래정보를 조회할 수 있다.(총거래/일치/불일치 건수)
 3.자료발생 규칙
• 배치 프로그램 작동시 백그라운드로 등록된다."""


def enrich_entity_definition(tables: list[TableDef]) -> list[TableDef]:
    """Entity 정의(Row3 B:L)를 rules/entity_definition_rules.json + AI로 결정.

    JSON에 있으면 그 값을 사용. 없으면 AI 추론 후 JSON에 저장.
    AI 추론값은 entity_definition_ai = True 플래그로 표시.
    """
    rules_path = _RULES_DIR / "entity_definition_rules.json"

    if rules_path.exists():
        with rules_path.open(encoding="utf-8") as f:
            rules: dict[str, str] = {
                k: v for k, v in json.load(f).items()
                if not k.startswith("_")
            }
    else:
        rules = {}

    tables_needing_ai: list[TableDef] = []
    for table in tables:
        val = rules.get(table.name.lower())
        if val:
            table.entity_definition = val
            table.entity_definition_ai = False
        else:
            tables_needing_ai.append(table)

    if not tables_needing_ai:
        return tables

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        print(f"[WARN] ANTHROPIC_API_KEY 없음 — Entity 정의 AI 추론 건너뜀 ({len(tables_needing_ai)}개)")
        return tables

    try:
        import anthropic
    except ImportError:
        print("[WARN] anthropic 패키지 없음 — Entity 정의 AI 추론 건너뜀")
        return tables

    client = anthropic.Anthropic(api_key=api_key)
    new_entries: dict[str, str] = {}

    for table in tables_needing_ai:
        result = _infer_entity_definition(client, table)
        if result:
            table.entity_definition = result
            table.entity_definition_ai = True
            new_entries[table.name.lower()] = result

    if new_entries:
        all_rules: dict = {}
        if rules_path.exists():
            with rules_path.open(encoding="utf-8") as f:
                all_rules = json.load(f)
        all_rules.update(new_entries)
        with rules_path.open("w", encoding="utf-8") as f:
            json.dump(all_rules, f, ensure_ascii=False, indent=2)
        print(f"[INFO] Entity 정의 {len(new_entries)}개 AI 추론 완료 → entity_definition_rules.json 저장")

    return tables


def _infer_entity_definition(client, table: TableDef) -> str:
    """테이블 1개의 Entity 정의를 AI로 추론."""
    col_info = "\n".join(
        f"  - {col.name}: {col.attribute_name}" if col.attribute_name else f"  - {col.name}"
        for col in table.columns[:20]
    )
    entity_class_hint = {
        "KEY": "기준/코드성 테이블",
        "MAIN": "핵심 비즈니스 엔티티 테이블",
        "ACTION": "트랜잭션/이력/로그 테이블",
    }.get(table.entity_class, "")

    prompt = f"""{_ENTITY_DEF_EXAMPLE}

---
위 샘플과 동일한 형식으로 아래 테이블의 Entity 정의를 작성하세요.

테이블명: {table.name}
테이블 설명(Entity 명): {table.comment or "(없음)"}
엔티티 분류: {table.entity_class or "(미정)"}{f" ({entity_class_hint})" if entity_class_hint else ""}
컬럼 목록:
{col_info}

규칙:
- 반드시 3개 섹션(1.집합적 의미 / 2.기능적 의미 / 3.자료발생 규칙)으로 작성
- 각 항목은 • 로 시작
- 한국어로 작성
- 섹션별 1~3개 항목
- 형식 외 다른 텍스트 없이 정의 내용만 반환

Entity 정의:"""

    try:
        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}],
        )
        return message.content[0].text.strip()
    except Exception as e:
        print(f"[WARN] Entity 정의 AI 추론 실패 ({table.name}): {e}")
    return ""


# ──────────────────────────────────────────────────────────────────────────────
# FK 관계 추론 (DDL에 FK 제약조건이 없는 경우)
# ──────────────────────────────────────────────────────────────────────────────

# AI 추론 후보 컬럼 접미사
_FK_CANDIDATE_SUFFIXES = ("_id", "_cd", "_no", "_seq", "_key", "_code")


def enrich_inferred_fk(tables: list[TableDef]) -> list[TableDef]:
    """FK 없는 컬럼의 테이블 간 관계를 추론하여 TableDef.inferred_fk_list에 저장.

    처리 순서:
    1. rules/inferred_fk_rules.json 로드 (AI 추론 캐시 + 수동 정의) — 최우선
    2. 컬럼명 자동 매칭 (A테이블 단일 PK == B테이블 일반 컬럼명 → B→A 관계)
    3. 나머지 후보 컬럼(_id/_cd/_no 등 접미사) AI 추론 후 JSON 저장

    제외 설정 (inferred_fk_rules.json의 _exclude 키):
    - columns: 추론 대상에서 제외할 컬럼명 목록
    - ref_tables: 참조 대상에서 제외할 테이블명 목록
    - table_prefixes: 해당 접두어를 가진 테이블은 소스/참조 대상 모두 제외
    """
    rules_path = _RULES_DIR / "inferred_fk_rules.json"

    raw_rules: dict = {}
    if rules_path.exists():
        with rules_path.open(encoding="utf-8") as f:
            raw_rules = json.load(f)

    # 제외 설정 로드
    exclude_cfg = raw_rules.get("_exclude", {})
    exclude_columns: set[str] = {c.lower() for c in exclude_cfg.get("columns", [])}
    exclude_ref_tables: set[str] = {t.lower() for t in exclude_cfg.get("ref_tables", [])}
    exclude_prefixes: list[str] = [p.upper() for p in exclude_cfg.get("table_prefixes", [])]

    def _is_excluded_table(name: str) -> bool:
        return any(name.upper().startswith(p) for p in exclude_prefixes)

    cached_rules: dict[str, dict] = {
        k: v for k, v in raw_rules.items()
        if not k.startswith("_")
    }

    # 단일 PK 컬럼명 → 테이블명 맵 (자동 매칭용, 제외 테이블 제거)
    pk_col_map: dict[str, str] = {}
    for t in tables:
        if len(t.pk_columns) == 1 and not _is_excluded_table(t.name):
            if t.name.lower() not in exclude_ref_tables:
                pk_col_map[t.pk_columns[0]] = t.name

    # 전체 테이블 PK 목록 (AI 컨텍스트용, 제외 테이블 제거)
    table_pk_context: dict[str, list[str]] = {
        t.name: t.pk_columns
        for t in tables
        if t.pk_columns
        and not _is_excluded_table(t.name)
        and t.name.lower() not in exclude_ref_tables
    }

    tables_needing_ai: list[TableDef] = []
    ai_candidates: dict[str, list] = {}  # table_name → [ColumnDef, ...]

    for table in tables:
        # 소스 테이블 자체가 제외 대상이면 스킵
        if _is_excluded_table(table.name):
            continue

        existing_fk_cols = {fk.column for fk in table.fk_list}
        cached_table: dict = cached_rules.get(table.name.lower(), {})

        for col in table.columns:
            if col.name in existing_fk_cols or col.is_pk:
                continue
            # 제외 컬럼 스킵
            if col.name.lower() in exclude_columns:
                continue

            # 1. JSON 캐시 우선 (null이면 "관계 없음"으로 확정 — 재추론 스킵)
            if col.name in cached_table:
                entry = cached_table[col.name]
                if entry:
                    table.inferred_fk_list.append(InferredFKInfo(
                        column=col.name,
                        ref_table=entry["ref_table"],
                        ref_column=entry["ref_column"],
                        source="ai",
                    ))
                continue

            # 2. 컬럼명 자동 매칭
            if col.name in pk_col_map and pk_col_map[col.name] != table.name:
                table.inferred_fk_list.append(InferredFKInfo(
                    column=col.name,
                    ref_table=pk_col_map[col.name],
                    ref_column=col.name,
                    source="auto",
                ))
                continue

            # 3. AI 후보 수집 (접미사 기반 필터)
            if any(col.name.lower().endswith(s) for s in _FK_CANDIDATE_SUFFIXES):
                if table.name not in ai_candidates:
                    ai_candidates[table.name] = []
                    tables_needing_ai.append(table)
                ai_candidates[table.name].append(col)

    if not tables_needing_ai:
        return tables

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        print(f"[WARN] ANTHROPIC_API_KEY 없음 — FK 관계 AI 추론 건너뜀 ({len(tables_needing_ai)}개 테이블)")
        return tables

    try:
        import anthropic
    except ImportError:
        print("[WARN] anthropic 패키지 없음 — FK 관계 AI 추론 건너뜀")
        return tables

    client = anthropic.Anthropic(api_key=api_key)
    new_entries: dict[str, dict] = {}

    for table in tables_needing_ai:
        candidates = ai_candidates[table.name]
        result = _infer_fk_ai(client, table, candidates, table_pk_context)

        table_entry: dict[str, dict | None] = {}
        for col in candidates:
            entry = result.get(col.name)
            if entry and isinstance(entry, dict) and "ref_table" in entry:
                table.inferred_fk_list.append(InferredFKInfo(
                    column=col.name,
                    ref_table=entry["ref_table"],
                    ref_column=entry["ref_column"],
                    source="ai",
                ))
                table_entry[col.name] = entry
            else:
                table_entry[col.name] = None  # null → 이후 재추론 스킵

        if table_entry:
            new_entries[table.name.lower()] = table_entry

    if new_entries:
        all_rules: dict = {}
        if rules_path.exists():
            with rules_path.open(encoding="utf-8") as f:
                all_rules = json.load(f)
        all_rules.update(new_entries)
        with rules_path.open("w", encoding="utf-8") as f:
            json.dump(all_rules, f, ensure_ascii=False, indent=2)

        inferred_count = sum(
            1 for t_entries in new_entries.values()
            for v in t_entries.values() if v is not None
        )
        print(f"[INFO] FK 관계 AI 추론 {inferred_count}개 완료 → inferred_fk_rules.json 저장")

    return tables


def _infer_fk_ai(client, table: TableDef, candidates: list, table_pk_context: dict) -> dict:
    """candidates 컬럼들의 FK 관계를 AI로 추론. {col_name: {ref_table, ref_column} | null} 반환."""
    table_list = "\n".join(
        f"  - {tname}: PK=({', '.join(pks)})"
        for tname, pks in sorted(table_pk_context.items())
    )
    col_list = "\n".join(
        f"  - {col.name}: {col.attribute_name or '(설명없음)'}"
        for col in candidates
    )
    prompt = f"""PostgreSQL 테이블의 외래키 관계를 추론하세요.

테이블명: {table.name}
테이블 설명: {table.comment or "(없음)"}

추론 대상 컬럼:
{col_list}

전체 테이블 목록 (테이블명: PK 컬럼):
{table_list}

각 컬럼이 위 테이블 목록 중 어느 테이블을 참조하는지 추론하세요.
- 명확한 참조 관계가 있으면 ref_table, ref_column 반환
- 명확하지 않으면 null 반환
- 자신의 테이블({table.name})은 제외

반드시 아래 JSON 형식만 반환 (설명 없이):
{{"컬럼명": {{"ref_table": "참조테이블명", "ref_column": "참조컬럼명"}}, "컬럼명2": null}}"""

    try:
        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = message.content[0].text.strip()
        if "```" in raw:
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw)
    except Exception as e:
        print(f"[WARN] FK 관계 AI 추론 실패 ({table.name}): {e}")
        return {}
