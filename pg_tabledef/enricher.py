"""pg_tabledef.enricher: 빈 comment / attribute_name을 Claude API로 자동 보완."""
from __future__ import annotations

import json
import os

from .models import TableDef


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
