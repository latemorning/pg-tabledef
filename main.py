"""pg-tabledef: CLI 진입점.

사용법:
    python main.py

동작:
    1. ./input/*.sql 읽기
    2. pglast 파싱 → list[TableDef]
    3. ./output/테이블정의서.xlsx 저장
    4. 완료 메시지 출력 (테이블 수, 출력 경로)
"""
from __future__ import annotations

import sys
from pathlib import Path

from pg_tabledef.parser import parse_files
from pg_tabledef.writer.excel import ExcelWriter


def main() -> None:
    input_dir = Path("input")
    if not input_dir.exists():
        print(f"[ERROR] 입력 디렉토리가 존재하지 않습니다: {input_dir.resolve()}")
        sys.exit(1)

    sql_files = list(input_dir.glob("*.sql"))
    if not sql_files:
        print(f"[WARN] {input_dir.resolve()} 에 .sql 파일이 없습니다.")
        sys.exit(0)

    print(f"[INFO] .sql 파일 {len(sql_files)}개 파싱 중...")
    tables = parse_files(input_dir)

    if not tables:
        print("[WARN] 파싱된 테이블이 없습니다.")
        sys.exit(0)

    writer = ExcelWriter()
    writer.write(tables)

    output_path = writer.output_path.resolve()
    print(f"[INFO] 완료: 테이블 {len(tables)}개 → {output_path}")


if __name__ == "__main__":
    main()
