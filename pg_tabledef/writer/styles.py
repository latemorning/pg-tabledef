"""pg_tabledef.writer.styles: openpyxl 스타일 상수 (template/sample.xlsx 기준)."""
from openpyxl.styles import Font, Alignment, Border, Side, PatternFill
from openpyxl.styles.colors import Color

# ──────────────────────────────────────────────────────────────────────────────
# 폰트
# ──────────────────────────────────────────────────────────────────────────────
FONT_HEADER         = Font(bold=True, size=10)                              # 헤더 레이블 (일반 배경)
FONT_HEADER_ON_DARK = Font(bold=True, size=10, color=Color(theme=1))        # 헤더 레이블 (어두운 배경 → 흰색)
FONT_NORMAL         = Font(size=10)
FONT_PK             = Font(bold=True, size=10)                              # PK 컬럼 행

# ──────────────────────────────────────────────────────────────────────────────
# 정렬
# ──────────────────────────────────────────────────────────────────────────────
ALIGN_CENTER      = Alignment(horizontal="center", vertical="center")
ALIGN_LEFT        = Alignment(horizontal="left",   vertical="center", wrap_text=True)
ALIGN_LEFT_NO_WRAP = Alignment(horizontal="left",  vertical="center")
ALIGN_RIGHT       = Alignment(horizontal="right",  vertical="center")

# ──────────────────────────────────────────────────────────────────────────────
# 배경색 (template/sample.xlsx: theme0 + tint -0.35 = 어두운 헤더)
# ──────────────────────────────────────────────────────────────────────────────
FILL_HEADER = PatternFill(fill_type="solid", fgColor=Color(theme=0, tint=-0.35))

# ──────────────────────────────────────────────────────────────────────────────
# 테두리 (thin 전체)
# ──────────────────────────────────────────────────────────────────────────────
_THIN = Side(style="thin")
BORDER_THIN = Border(left=_THIN, right=_THIN, top=_THIN, bottom=_THIN)

# ──────────────────────────────────────────────────────────────────────────────
# 컬럼 너비 (sample.xlsx 기준)
# ──────────────────────────────────────────────────────────────────────────────
COL_WIDTHS: dict[str, float] = {
    "A": 16.7,   # No.
    "B": 28.0,   # COLUMN NAME
    "C": 30.8,   # ATTRIBUTE NAME
    "D": 14.7,   # Type
    "E": 8.0,    # Length
    "F": 6.8,    # Null
    "G": 6.3,    # Keys
    "H": 17.0,   # 인포타입명
    "I": 21.7,   # Description
    "J": 18.0,   # Attribute Type
    "K": 25.0,   # Relation & Value
    "L": 15.0,   # Source
}

# ──────────────────────────────────────────────────────────────────────────────
# 행 높이
# ──────────────────────────────────────────────────────────────────────────────
ROW_HEIGHT_DEFAULT    = 20.0
ROW_HEIGHT_ENTITY_DEF = 120.0   # Entity 정의 행 (Row 3)
ROW_HEIGHT_KEY_HEADER = 40.0    # Key List 헤더 행 (Row 4)
