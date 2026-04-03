# CLAUDE.md

This file provides guidance to Claude Code when working with code in this repository.

## Project Overview

**pg-tabledef** — PostgreSQL 테이블 정의서 엑셀 출력 도구

PostgreSQL 데이터베이스의 테이블 구조(컬럼, 타입, 제약조건, 코멘트 등)를 추출하여 엑셀(.xlsx) 형식의 테이블 정의서를 생성하는 스크립트입니다.

## Status

구현 완료. 운영 중.

---

## 에이전트 관리

이 프로젝트는 세 가지 전담 에이전트로 작업을 분리합니다.
각 에이전트는 해당 MD 파일을 읽고 시작해야 합니다.
사용자가 계획서 업데이트해줘 라고 하면 CLAUDE.md 및 아래 3개 에이전트 파일을 업데이트 합니다.

| 에이전트 | 파일 | 역할 |
|----------|------|------|
| Plan | `agents/PLAN.md` | 설계 결정, 쿼리 전략, 모듈 구조 |
| Implement | `agents/IMPLEMENT.md` | 코드 구현 (테스트 제외) |
| Test | `agents/TEST.md` | 테스트 작성 및 실행 |

### 에이전트 실행 순서

```
Plan 에이전트 → Implement 에이전트 → Test 에이전트
```

### 에이전트별 참고 파일

- **Implement 에이전트**: `agents/PLAN.md` + `agents/IMPLEMENT.md`
- **Test 에이전트**: `agents/PLAN.md` + `agents/IMPLEMENT.md` + `agents/TEST.md`

### 진행 현황 확인

- 구현 현황: `agents/IMPLEMENT.md` 하단 **구현 현황** 섹션
- 테스트 현황: `agents/TEST.md` 하단 **테스트 현황** 섹션

## Stack

- Python 3.12+
- pglast>=7.0 (PostgreSQL DDL 파서)
- openpyxl>=3.1 (엑셀 출력)
- anthropic>=0.25 (AI 추론 — 빈 코멘트·엔티티분류·FK 관계 자동 보완)

## Running

```bash
cd pg-tabledef
source venv/bin/activate
python main.py
```

## Tests

```bash
cd pg-tabledef
pytest tests/ -v
```
