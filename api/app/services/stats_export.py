"""The usage page as a workbook, with charts Excel treats as its own.

Not pictures of charts. openpyxl writes the chart XML, so each one points at
a range on a sheet: change a number and the chart follows, add a series or
re-colour it in Excel and it behaves like one somebody drew there. That is the
difference between a file to look at and a file to work in.

Labels arrive already translated from a small map here rather than from the
browser, the same arrangement the weekly digest uses — the file is built on
the server and has to read correctly whoever asked for it.
"""

from dataclasses import dataclass
from datetime import date
from io import BytesIO
from typing import Protocol

from openpyxl import Workbook
from openpyxl.chart import BarChart, LineChart, Reference
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

# The page's chart palette, without the leading "#" that Excel does not want.
CHART_COLORS = ("0B9488", "D97706", "4F46E5")

HEADER_FILL = PatternFill("solid", fgColor="F0EFEB")
HEADER_FONT = Font(bold=True, color="46465A")
TITLE_FONT = Font(bold=True, size=14)


class HasKpis(Protocol):
    active_users: int
    chat_sessions: int
    chat_messages: int
    unanswered: int
    unanswered_pct: float
    board_items: int
    comments: int
    likes: int
    files_uploaded: int


@dataclass
class ExportInput:
    lang: str
    range_days: int
    scope: str  # "platform" | "municipality"
    title: str
    kpis: HasKpis
    series: list  # SeriesPoint
    breakdown: list  # BreakdownRow
    unanswered: list | None  # UnansweredRow


COPY = {
    "he": {
        "summary": "סיכום",
        "over_time": "לאורך זמן",
        "by_group": "לפי רשות",
        "by_group_dept": "לפי מחלקה",
        "unanswered": "שאלות ללא מענה",
        "metric": "מדד",
        "value": "ערך",
        "date": "תאריך",
        "question": "שאלה",
        "municipality": "רשות",
        "department": "מחלקה",
        "range": "טווח",
        "days": "{n} ימים",
        "active_users": "משתמשים פעילים",
        "chat_sessions": "שיחות",
        "chat_messages": "שאלות שנשאלו",
        "unanswered_count": "ללא מענה",
        "unanswered_pct": "% ללא מענה",
        "board_items": "פריטים שפורסמו",
        "comments": "תגובות",
        "likes": "לייקים",
        "files_uploaded": "קבצים שהועלו",
        "chart_active": "משתמשים פעילים לאורך זמן",
        "chart_volume": "נפח שאלות לאורך זמן",
        "chart_compare": "השוואה בין רשויות",
        "chart_compare_dept": "השוואה בין מחלקות",
    },
    "en": {
        "summary": "Summary",
        "over_time": "Over time",
        "by_group": "By municipality",
        "by_group_dept": "By department",
        "unanswered": "Unanswered questions",
        "metric": "Metric",
        "value": "Value",
        "date": "Date",
        "question": "Question",
        "municipality": "Municipality",
        "department": "Department",
        "range": "Range",
        "days": "{n} days",
        "active_users": "Active users",
        "chat_sessions": "Chat sessions",
        "chat_messages": "Questions asked",
        "unanswered_count": "Unanswered",
        "unanswered_pct": "% unanswered",
        "board_items": "Board items",
        "comments": "Comments",
        "likes": "Likes",
        "files_uploaded": "Files uploaded",
        "chart_active": "Active users over time",
        "chart_volume": "Questions over time",
        "chart_compare": "By municipality",
        "chart_compare_dept": "By department",
    },
}


def _header(ws: Worksheet, row: int, values: list[str]) -> None:
    for col, value in enumerate(values, start=1):
        cell = ws.cell(row=row, column=col, value=value)
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.alignment = Alignment(vertical="center")


def _autosize(ws: Worksheet, widths: list[int]) -> None:
    for i, width in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = width


def build_workbook(data: ExportInput) -> bytes:
    t = COPY.get(data.lang, COPY["he"])
    grouping = t["municipality"] if data.scope == "platform" else t["department"]
    by_group = t["by_group"] if data.scope == "platform" else t["by_group_dept"]
    compare_title = (
        t["chart_compare"] if data.scope == "platform" else t["chart_compare_dept"]
    )

    wb = Workbook()

    # --- summary
    ws = wb.active
    ws.title = t["summary"]
    # Right-to-left is a property of the sheet, not something to fake with
    # alignment: Excel moves column A to the right and reverses the chart axes.
    ws.sheet_view.rightToLeft = data.lang == "he"
    ws["A1"] = data.title
    ws["A1"].font = TITLE_FONT
    ws["A2"] = t["range"]
    ws["B2"] = t["days"].format(n=data.range_days)
    _header(ws, 4, [t["metric"], t["value"]])
    rows = [
        (t["active_users"], data.kpis.active_users),
        (t["chat_sessions"], data.kpis.chat_sessions),
        (t["chat_messages"], data.kpis.chat_messages),
        (t["unanswered_count"], data.kpis.unanswered),
        (t["unanswered_pct"], data.kpis.unanswered_pct),
        (t["board_items"], data.kpis.board_items),
        (t["comments"], data.kpis.comments),
        (t["likes"], data.kpis.likes),
        (t["files_uploaded"], data.kpis.files_uploaded),
    ]
    for i, (label, value) in enumerate(rows, start=5):
        ws.cell(row=i, column=1, value=label)
        ws.cell(row=i, column=2, value=value)
    _autosize(ws, [26, 14])

    # --- over time, with a line chart per measure
    ws = wb.create_sheet(t["over_time"])
    ws.sheet_view.rightToLeft = data.lang == "he"
    _header(ws, 1, [t["date"], t["active_users"], t["chat_messages"]])
    for i, point in enumerate(data.series, start=2):
        ws.cell(row=i, column=1, value=point.day)
        ws.cell(row=i, column=2, value=point.active_users)
        ws.cell(row=i, column=3, value=point.chat_messages)
    _autosize(ws, [14, 20, 20])
    last = len(data.series) + 1

    if data.series:
        days = Reference(ws, min_col=1, min_row=2, max_row=last)
        for offset, (col, title) in enumerate(
            ((2, t["chart_active"]), (3, t["chart_volume"]))
        ):
            chart = LineChart()
            chart.title = title
            chart.height = 7
            chart.width = 18
            # One series, so the legend would only repeat the title.
            chart.legend = None
            chart.add_data(
                Reference(ws, min_col=col, min_row=1, max_row=last), titles_from_data=True
            )
            chart.set_categories(days)
            chart.series[0].graphicalProperties.line.solidFill = CHART_COLORS[offset * 2]
            chart.series[0].graphicalProperties.line.width = 20000  # EMU, ~2pt
            chart.series[0].smooth = False
            ws.add_chart(chart, f"E{2 + offset * 15}")

    # --- one row per municipality or department, with a bar chart beside it
    ws = wb.create_sheet(by_group)
    ws.sheet_view.rightToLeft = data.lang == "he"
    _header(
        ws,
        1,
        [
            grouping,
            t["active_users"],
            t["chat_sessions"],
            t["chat_messages"],
            t["unanswered_count"],
            t["unanswered_pct"],
            t["board_items"],
            t["comments"],
            t["likes"],
            t["files_uploaded"],
        ],
    )
    for i, row in enumerate(data.breakdown, start=2):
        k = row.kpis
        for col, value in enumerate(
            [
                row.name,
                k.active_users,
                k.chat_sessions,
                k.chat_messages,
                k.unanswered,
                k.unanswered_pct,
                k.board_items,
                k.comments,
                k.likes,
                k.files_uploaded,
            ],
            start=1,
        ):
            ws.cell(row=i, column=col, value=value)
    _autosize(ws, [28, 18, 12, 18, 14, 14, 18, 12, 10, 18])

    if data.breakdown:
        end = len(data.breakdown) + 1
        chart = BarChart()
        chart.type = "bar"  # horizontal: municipality names need the room
        chart.title = compare_title
        chart.height = 9
        chart.width = 20
        # Questions, board items and files: three unlike things, so they are
        # grouped side by side rather than stacked into one meaningless total.
        chart.grouping = "clustered"
        chart.add_data(
            Reference(ws, min_col=4, min_row=1, max_row=end), titles_from_data=True
        )
        chart.add_data(
            Reference(ws, min_col=7, min_row=1, max_row=end), titles_from_data=True
        )
        chart.add_data(
            Reference(ws, min_col=10, min_row=1, max_row=end), titles_from_data=True
        )
        chart.set_categories(Reference(ws, min_col=1, min_row=2, max_row=end))
        for series, color in zip(chart.series, CHART_COLORS, strict=False):
            series.graphicalProperties.solidFill = color
            series.graphicalProperties.line.solidFill = color
        ws.add_chart(chart, "L2")

    # --- what the material did not cover
    if data.unanswered:
        ws = wb.create_sheet(t["unanswered"])
        ws.sheet_view.rightToLeft = data.lang == "he"
        _header(ws, 1, [t["question"], t["municipality"], t["date"]])
        for i, row in enumerate(data.unanswered, start=2):
            ws.cell(row=i, column=1, value=row.question)
            ws.cell(row=i, column=2, value=row.municipality_name or "")
            value = row.created_at
            ws.cell(row=i, column=3, value=value if isinstance(value, date) else str(value))
        _autosize(ws, [70, 24, 14])

    out = BytesIO()
    wb.save(out)
    return out.getvalue()
