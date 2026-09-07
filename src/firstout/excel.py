"""원아 명부 엑셀 — 양식 만들기와 읽어들이기.

명부는 선생님이 주도한다. 그래서 **그 유치원의 반·차수·학원이 이미 채워진 양식**을
서버가 만들어 준다. 무엇을 적어야 하는지 설명서를 따로 볼 필요가 없어야 한다.

읽어들일 때는 절대 조용히 저장하지 않는다. 오타 하나로 150명이 잘못 들어가면
되돌리기 어렵기 때문에, 반드시 미리보기와 확인을 거친다.
"""

from __future__ import annotations

import io
import re
from dataclasses import dataclass, field

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.worksheet.datavalidation import DataValidation
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from . import service
from .config import WEEKDAYS
from .models import Academy, Child, Guardian, PlanEntry

SHEET = "원아명부"
GUIDE = "작성안내"

# 한 번에 읽을 수 있는 줄 수. 제일 큰 유치원도 수백 명이라 열 배 넉넉하다.
# 5MB 파일 하나에 13만 줄이 들어가는데, 그걸 읽는 동안 **서버가 다른 유치원 일을
# 하지 못한다.** 한 곳의 실수가 모두를 멈추게 두면 안 된다.
MAX_ROWS = 2000

HEAD = ["반", "유아명", *WEEKDAYS, "보호자1", "관계", "연락처",
        "보호자2", "관계", "연락처", "특이사항"]

_PINE = "0A6B55"
_HEADFILL = PatternFill("solid", fgColor="D6EDE6")
_THIN = Side(style="thin", color="CBD4CF")
_BOX = Border(left=_THIN, right=_THIN, top=_THIN, bottom=_THIN)


def _write_head(ws, classes) -> None:
    """머리글과 열 너비 — 양식과 내보내기가 같은 모양이어야 다시 올릴 수 있다."""
    for i, h in enumerate(HEAD, start=1):
        c = ws.cell(row=1, column=i, value=h)
        c.font = Font(bold=True, color=_PINE)
        c.fill = _HEADFILL
        c.border = _BOX
        c.alignment = Alignment(horizontal="center")

    widths = [10, 10, *([13] * len(WEEKDAYS)), 11, 7, 15, 11, 7, 15, 20]
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[ws.cell(row=1, column=i).column_letter].width = w
    ws.freeze_panes = "C2"

    # 반 이름은 목록에서 고르게 한다 — 오타가 가장 흔한 실수다
    if classes:
        dv = DataValidation(
            type="list",
            formula1='"' + ",".join(c.name for c in classes) + '"',
            allow_blank=True,
            showErrorMessage=True,
            error="설정에 등록된 반 이름만 쓸 수 있습니다.",
            errorTitle="반 이름 확인",
        )
        ws.add_data_validation(dv)
        dv.add("A2:A2000")


def _academies(db: Session, kinder_id: int) -> list[str]:
    return [
        a.name
        for a in db.scalars(
            select(Academy).where(Academy.kinder_id == kinder_id).order_by(Academy.name)
        )
    ]


def make_template(db: Session, kinder_id: int, kinder_name: str) -> bytes:
    """그 유치원 기준으로 채워진 빈 양식."""
    classes = service.classes(db, kinder_id)
    rounds = service.rounds(db, kinder_id)
    aca_names = _academies(db, kinder_id)

    wb = Workbook()
    ws = wb.active
    ws.title = SHEET
    _write_head(ws, classes)

    # 예시 두 줄 — 지우고 쓰시라고 안내한다
    r1 = rounds[0].name if rounds else "1차 개별"
    care = next((r.name for r in rounds if r.kind == "돌봄"), "돌봄")
    aca = aca_names[0] if aca_names else "태권도"
    sample = [
        [classes[0].name if classes else "", "예시-지우고 쓰세요",
         r1, r1, care, r1, "", "박영희", "모", "010-1234-5678", "", "", "", ""],
        [classes[0].name if classes else "", "예시-지우고 쓰세요",
         f"학원({aca})", r1, r1, care, "", "최지영", "모", "010-2345-6789",
         "김철수", "부", "010-3456-7890", "땅콩 알레르기"],
    ]
    for ri, row in enumerate(sample, start=2):
        for ci, v in enumerate(row, start=1):
            c = ws.cell(row=ri, column=ci, value=v)
            c.border = _BOX
            c.font = Font(color="8A9490", italic=True)

    _write_guide(wb, classes, rounds, aca_names)

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _write_guide(wb: Workbook, classes, rounds, aca_names) -> None:
    g = wb.create_sheet(GUIDE)
    g.column_dimensions["A"].width = 22
    g.column_dimensions["B"].width = 62

    def line(a: str, b: str = "", bold: bool = False) -> None:
        r = g.max_row + 1 if g.max_row > 1 or g["A1"].value else 1
        g.cell(row=r, column=1, value=a).font = Font(bold=True, color=_PINE if bold else "0D1613")
        g.cell(row=r, column=2, value=b).alignment = Alignment(wrap_text=True, vertical="top")

    line("작성 안내", "", True)
    line("", "아이 한 명이 한 줄입니다. 요일 칸에 그날의 귀가 방법을 적어주세요.")
    line("", "빈칸으로 두면 그날은 명단에 없습니다 (정규 후 귀가).")
    line("")
    line("요일 칸에 적는 값", "", True)
    for r in rounds:
        line(r.name, f"{r.kind} · {r.at_time}" + (f" ({r.note})" if r.note else ""))
    ex = aca_names[0] if aca_names else "태권도"
    line("학원(학원이름)", f"학원 차량이 데려갑니다. 예: 학원({ex})")
    line("뒤에 시각 추가", "기준과 다르면 뒤에 붙입니다. 예: " +
         (rounds[0].name + " 16:00" if rounds else "1차 개별 16:00"))
    line("")
    line("등록된 반", " · ".join(c.name for c in classes) or "(없음)")
    line("등록된 학원", " · ".join(aca_names) or "(없음)")
    line("")
    line("보호자", "", True)
    line("", "보호자1이 기본 인계자가 됩니다. 연락처는 저장되지만 화면에는 "
             "가려서 표시됩니다 (010-****-5678).")
    line("")
    line("주의", "", True)
    line("", "반 이름은 위 목록과 정확히 같아야 합니다. 올린 뒤 미리보기에서 "
             "확인하고 「등록하기」를 눌러야 저장됩니다.")


# ── 내려받기 ────────────────────────────────────────────

def _day_cell(p) -> str:
    """주간 계획 한 칸을 양식에 적히는 말로 돌려놓는다 — parse() 가 그대로 읽는다."""
    if p is None:
        return ""
    if p.academy_id and p.academy:
        return f"학원({p.academy.name})"
    if not p.round:
        return ""
    return p.round.name + (f" {p.time_override}" if p.time_override else "")


def export_roster(db: Session, kinder_id: int) -> bytes:
    """지금 등록된 명부를 양식 그대로 내보낸다.

    올릴 때 쓰는 양식과 같은 모양이라, 내려받아 고친 뒤 그대로 다시 올릴 수 있다.
    서버에 무슨 일이 생겨도 이 파일 하나면 명부와 주간 계획은 살아남는다.
    """
    classes = service.classes(db, kinder_id)
    order = {c.id: c.seq for c in classes}

    kids = list(
        db.scalars(
            select(Child)
            .where(Child.kinder_id == kinder_id, Child.active.is_(True))
            .options(
                selectinload(Child.classroom),
                selectinload(Child.guardians),
                selectinload(Child.plan).selectinload(PlanEntry.round),
                selectinload(Child.plan).selectinload(PlanEntry.academy),
            )
        )
    )
    kids.sort(key=lambda k: (order.get(k.class_id, 99), k.name))

    wb = Workbook()
    ws = wb.active
    ws.title = SHEET
    _write_head(ws, classes)

    for ri, k in enumerate(kids, start=2):
        plans = {pl.weekday: pl for pl in k.plan}
        row = [k.classroom.name if k.classroom else "", k.name]
        row += [_day_cell(plans.get(w)) for w in range(len(WEEKDAYS))]

        # 기본 인계자가 보호자1 자리에 오도록 정렬한다
        gs = sorted(k.guardians, key=lambda g: (not g.is_default, g.seq))[:2]
        for i in range(2):
            g = gs[i] if i < len(gs) else None
            row += [g.name if g else "", g.relation if g else "", g.phone if g else ""]
        row.append(k.note)

        for ci, v in enumerate(row, start=1):
            ws.cell(row=ri, column=ci, value=v).border = _BOX

    _write_guide(wb, classes, service.rounds(db, kinder_id), _academies(db, kinder_id))

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# ── 읽어들이기 ──────────────────────────────────────────

@dataclass
class RowIn:
    line: int
    cls: str = ""
    name: str = ""
    days: list[str] = field(default_factory=list)
    guardians: list[tuple[str, str, str]] = field(default_factory=list)
    note: str = ""
    problems: list[str] = field(default_factory=list)
    child_id: int | None = None        # 이미 등록된 아이면 그 번호

    @property
    def ok(self) -> bool:
        return not self.problems

    @property
    def known(self) -> bool:
        return self.child_id is not None


@dataclass
class Parsed:
    rows: list[RowIn] = field(default_factory=list)
    fatal: str = ""

    @property
    def good(self) -> list[RowIn]:
        return [r for r in self.rows if r.ok]

    @property
    def bad(self) -> list[RowIn]:
        return [r for r in self.rows if not r.ok]

    @property
    def fresh(self) -> list[RowIn]:
        """새로 들어오는 아이."""
        return [r for r in self.good if not r.known]

    @property
    def known(self) -> list[RowIn]:
        """이미 명부에 있는 아이. 그냥 더하면 같은 아이가 두 줄이 된다."""
        return [r for r in self.good if r.known]


_ACA = re.compile(r"^\s*학원\s*\(([^)]*)\)\s*(.*)$")
_TIME = re.compile(r"(\d{1,2}:\d{2})\s*$")


def _cell(v) -> str:
    return "" if v is None else str(v).strip()


def parse(data: bytes, db: Session, kinder_id: int) -> Parsed:
    """엑셀을 읽어 검사만 한다. 저장은 하지 않는다."""
    out = Parsed()
    try:
        # read_only 로 열어야 줄 단위로 흘려 읽는다. 통째로 올리면 13만 줄짜리 파일
        # 하나에 서버가 몇 초씩 붙잡혀, 그동안 다른 유치원이 아무것도 못 한다.
        wb = load_workbook(io.BytesIO(data), data_only=True, read_only=True)
    except Exception:   # noqa: BLE001 — 엑셀이 아닌 파일도 올라올 수 있다
        out.fatal = "엑셀 파일을 열 수 없습니다. xlsx 파일인지 확인해 주세요."
        return out

    ws = wb[SHEET] if SHEET in wb.sheetnames else wb.worksheets[0]
    head = [_cell(v) for v in next(ws.iter_rows(max_row=1, values_only=True), ())]
    if "유아명" not in head or "반" not in head:
        out.fatal = (
            f"머리글이 양식과 다릅니다. 「{SHEET}」 시트 첫 줄에 "
            "「반 · 유아명」이 있어야 합니다."
        )
        return out

    classes = {c.name: c for c in service.classes(db, kinder_id)}
    rounds = {r.name: r for r in service.rounds(db, kinder_id)}
    acas = {a.name for a in db.scalars(select(Academy).where(Academy.kinder_id == kinder_id))}
    seen: set[tuple[str, str]] = set()

    # 이미 등록된 아이 — 이름만으로 맞춘다. 반이 바뀌었어도 같은 아이다.
    already = {
        c.name: c.id
        for c in db.scalars(
            select(Child).where(Child.kinder_id == kinder_id, Child.active.is_(True))
        )
    }

    for i, raw in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
        if len(out.rows) >= MAX_ROWS:
            out.fatal = (
                f"한 번에 {MAX_ROWS:,}명까지 올릴 수 있습니다. "
                "파일에 빈 줄이 많이 딸려 있지 않은지 확인해 주세요."
            )
            return out
        vals = [_cell(v) for v in raw] + [""] * len(HEAD)
        cls, name = vals[0], vals[1]
        if not cls and not name:
            continue
        if name.startswith("예시"):
            continue

        r = RowIn(line=i, cls=cls, name=name)
        r.days = vals[2:2 + len(WEEKDAYS)]
        for base in (7, 10):
            gname, grel, gphone = vals[base], vals[base + 1], vals[base + 2]
            if gname:
                r.guardians.append((gname, grel or "보호자", gphone))
        r.note = vals[13]

        if not name:
            r.problems.append("유아명이 비어 있습니다")
        if not cls:
            r.problems.append("반이 비어 있습니다")
        elif cls not in classes:
            r.problems.append(f"「{cls}」 은(는) 등록된 반이 아닙니다")
        if (cls, name) in seen:
            r.problems.append("같은 반에 같은 이름이 두 번 있습니다")
        seen.add((cls, name))
        if not r.guardians:
            r.problems.append("보호자가 없습니다 — 인계할 때 곤란합니다")
        r.child_id = already.get(name)

        for wi, cell in enumerate(r.days):
            if not cell:
                continue
            problem = _check_day(cell, rounds, acas)
            if problem:
                r.problems.append(f"{WEEKDAYS[wi]}요일 「{cell}」 — {problem}")

        out.rows.append(r)

    if not out.rows:
        out.fatal = "읽어들일 원아가 없습니다. 두 번째 줄부터 채워주세요."
    return out


def _check_day(cell: str, rounds: dict, acas: set[str]) -> str:
    m = _ACA.match(cell)
    if m:
        got = m.group(1).strip()
        return "" if got in acas else f"「{got}」 은(는) 등록된 학원이 아닙니다"
    base = _TIME.sub("", cell).strip()
    if base in rounds:
        return ""
    return "이런 귀가 방법이 없습니다"


def apply(data: bytes, db: Session, kinder_id: int, mode: str = "add") -> tuple[int, int]:
    """검사를 통과한 줄만 저장한다. (새로 등록, 갱신) 수를 돌려준다.

    mode 는 세 가지다.
        add      새 아이만 넣는다. 이미 있는 아이는 건드리지 않는다.
        update   이미 있는 아이는 이번 파일 내용으로 갱신하고, 새 아이는 넣는다.
        replace  기존 명부를 모두 지우고 이번 파일로 바꾼다.

    **add 가 이미 있는 아이를 건너뛰는 것이 중요하다.** 「한 명 추가하려고 파일을
    다시 올린다」가 가장 흔한 사용법인데, 그때마다 전원이 두 줄씩 되면
    귀가 명단에 같은 아이가 두 번 나온다. 한쪽만 서명하고 다른 쪽은 남는다.
    """
    p = parse(data, db, kinder_id)
    if p.fatal:
        return (0, 0)

    classes = {c.name: c for c in service.classes(db, kinder_id)}
    rounds = {r.name: r for r in service.rounds(db, kinder_id)}
    acas = {
        a.name: a
        for a in db.scalars(select(Academy).where(Academy.kinder_id == kinder_id))
    }

    if mode == "replace":
        for old in db.scalars(select(Child).where(Child.kinder_id == kinder_id)):
            db.delete(old)
        db.flush()

    made = changed = 0
    for r in p.good:
        child = None
        if mode != "replace" and r.known:
            if mode != "update":
                continue                      # add — 이미 있는 아이는 그대로 둔다
            child = db.get(Child, r.child_id)

        if child is None:
            child = Child(kinder_id=kinder_id, name=r.name, class_id=classes[r.cls].id)
            db.add(child)
            db.flush()
            made += 1
        else:
            child.class_id = classes[r.cls].id
            child.guardians.clear()           # 이번 파일이 기준이 된다
            for old in list(child.plan):
                db.delete(old)
            db.flush()
            changed += 1

        child.note = r.note[:200]
        _write_guardians(db, child, r)
        _write_plan(db, child, r, rounds, acas)

    db.commit()
    return (made, changed)


def _write_guardians(db: Session, child: Child, r: RowIn) -> None:
    for si, (gname, grel, gphone) in enumerate(r.guardians):
        db.add(
            Guardian(
                child_id=child.id, name=gname[:40], relation=grel[:20],
                phone=gphone[:30], is_default=(si == 0), seq=si,
            )
        )


def _write_plan(db: Session, child: Child, r: RowIn, rounds: dict, acas: dict) -> None:
    for wi, cell in enumerate(r.days):
        if not cell:
            db.add(PlanEntry(child_id=child.id, weekday=wi))
            continue
        m = _ACA.match(cell)
        if m:
            aca = acas.get(m.group(1).strip())
            rnd = next((x for x in rounds.values() if x.kind == "개별"), None)
            db.add(PlanEntry(child_id=child.id, weekday=wi,
                             round_id=rnd.id if rnd else None,
                             academy_id=aca.id if aca else None))
            continue
        tm = _TIME.search(cell)
        base = _TIME.sub("", cell).strip()
        rnd = rounds.get(base)
        db.add(PlanEntry(child_id=child.id, weekday=wi,
                         round_id=rnd.id if rnd else None,
                         time_override=tm.group(1) if tm else ""))
