"""pg_tabledef.enricher: 빈 comment / attribute_name을 Claude API로 자동 보완."""
from __future__ import annotations

import json
import os
from pathlib import Path

from .models import TableDef

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
