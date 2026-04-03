"""pg_tabledef.models: 순수 데이터 클래스."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class FKInfo:
    column: str
    ref_table: str
    ref_columns: list[str]  # 빈 리스트 허용 (참조 컬럼 생략 케이스)
    constraint_name: str = ""  # FK 제약조건명 (ALTER TABLE ... ADD CONSTRAINT {name})


@dataclass
class InferredFKInfo:
    column: str       # 로컬 컬럼명
    ref_table: str    # 참조 테이블명
    ref_column: str   # 참조 컬럼명
    source: str = ""  # "auto" (컬럼명 매칭) | "ai" (AI 추론)


@dataclass
class ColumnDef:
    no: int
    name: str               # COLUMN NAME
    attribute_name: str     # ATTRIBUTE NAME (컬럼 코멘트). 없으면 ""
    type_str: str           # 약식 표기 타입, 길이 제외 (예: VC, INT, TS)
    length: str             # 길이 숫자만 (예: "12", "200"). 없으면 ""
    not_null: bool
    is_pk: bool
    is_uk: bool
    fk_info: Optional[FKInfo]
    attribute_name_ai: bool = False  # True이면 AI가 추론한 attribute_name


@dataclass
class IndexDef:
    name: str
    columns: list[str]
    unique: bool


@dataclass
class TableDef:
    name: str
    comment: str            # 테이블 코멘트. 없으면 ""
    columns: list[ColumnDef] = field(default_factory=list)
    pk_columns: list[str] = field(default_factory=list)
    pk_constraint_name: str = ""  # PK 제약조건명 (ALTER TABLE ... ADD CONSTRAINT {name})
    indexes: list[IndexDef] = field(default_factory=list)
    fk_list: list[FKInfo] = field(default_factory=list)  # Key List 섹션용
    comment_ai: bool = False       # True이면 AI가 추론한 comment
    entity_class: str = ""              # 엔티티분류 (KEY / MAIN / ACTION)
    entity_class_ai: bool = False       # True이면 AI가 추론한 entity_class
    entity_definition: str = ""         # Entity 정의 (Row3 B:L 병합 셀)
    entity_definition_ai: bool = False  # True이면 AI가 추론한 entity_definition
    inferred_fk_list: list["InferredFKInfo"] = field(default_factory=list)  # FK 없는 컬럼 추론 관계
