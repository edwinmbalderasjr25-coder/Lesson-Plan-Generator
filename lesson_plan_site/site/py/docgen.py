"""
Weekly ILAW lesson plan generator (prototype).
Fills the school's blank Word template from a JSON input and the competency database.

  python generate_plan.py plan.json out.docx

Text-field mini-markup (used in every free-text box):
  "# Heading"      -> bold line
  "- item"         -> bullet
  "**bold** text"  -> inline bold
  "| a | b |" rows -> a table (first row is the header; a |---|---| line is ignored)
  blank line       -> blank line
"""
import copy, json, os, re, sys, datetime as dt
from docx import Document
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATE = os.path.join(HERE, "data", "Blank_Ampon_NHS_DLL_Template.docx")
DB = os.path.join(HERE, "data", "G7_English_competencies.json")
NO_CLASS_MSG = "No regular classroom instruction/activities."

# ---------------------------------------------------------------- helpers
def fmt_range(dates):
    d = sorted(dt.date.fromisoformat(x) for x in dates)
    a, b = d[0], d[-1]
    if a == b:                      return f"{a.strftime('%B')} {a.day}, {a.year}"
    if a.year != b.year:            return f"{a.strftime('%B')} {a.day}, {a.year}-{b.strftime('%B')} {b.day}, {b.year}"
    if a.month != b.month:          return f"{a.strftime('%B')} {a.day}-{b.strftime('%B')} {b.day}, {a.year}"
    return f"{a.strftime('%B')} {a.day}-{b.day}, {a.year}"

def join_and(items):
    items = [i for i in items if i]
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1] if items else ""

def make_run(text, rpr_tpl, bold=False, italic=False, size=20):
    r = OxmlElement("w:r")
    rpr = copy.deepcopy(rpr_tpl) if rpr_tpl is not None else OxmlElement("w:rPr")
    for tag in ("w:b", "w:bCs", "w:i", "w:iCs"):
        for e in rpr.findall(qn(tag)): rpr.remove(e)
    # schema order: rFonts, b, bCs, i, iCs, ... sz
    pos = 1 if rpr.find(qn("w:rFonts")) is not None else 0
    if italic:
        for t in ("w:iCs", "w:i"): rpr.insert(pos, OxmlElement(t))
    if bold:
        for t in ("w:bCs", "w:b"): rpr.insert(pos, OxmlElement(t))
    if rpr.find(qn("w:rFonts")) is None:
        f = OxmlElement("w:rFonts")
        for a in ("w:ascii", "w:hAnsi", "w:cs"): f.set(qn(a), "Arial")
        rpr.insert(0, f)
    for tag in ("w:sz", "w:szCs"):                    # every filled cell is Arial 10 pt
        for e in rpr.findall(qn(tag)): rpr.remove(e)
    for tag in ("w:szCs", "w:sz"):
        e = OxmlElement(tag); e.set(qn("w:val"), str(size))
        lang = rpr.find(qn("w:lang"))
        (lang.addprevious(e) if lang is not None else rpr.append(e))
    r.append(rpr)
    t = OxmlElement("w:t"); t.text = text; t.set(qn("xml:space"), "preserve"); r.append(t)
    return r

def add_ind(ppr, left, hanging):
    for e in ppr.findall(qn("w:ind")): ppr.remove(e)
    ind = OxmlElement("w:ind"); ind.set(qn("w:left"), str(left)); ind.set(qn("w:hanging"), str(hanging))
    sp = ppr.find(qn("w:spacing"))
    if sp is not None: sp.addnext(ind)
    else:
        rpr = ppr.find(qn("w:rPr"))
        (rpr.addprevious(ind) if rpr is not None else ppr.append(ind))

def _border(tag, sz=4):
    b = OxmlElement(tag)
    b.set(qn("w:val"), "single"); b.set(qn("w:sz"), str(sz)); b.set(qn("w:space"), "0"); b.set(qn("w:color"), "000000")
    return b

def make_table(rows, width, rpr_tpl):
    """Nested Word table from markdown-style rows (first row = header)."""
    ncols = max(len(r) for r in rows)
    first = int(width * 0.22) if ncols > 2 else width // ncols
    rest = (width - first) // max(ncols - 1, 1) if ncols > 1 else width
    widths = [first] + [rest] * (ncols - 1) if ncols > 1 else [width]
    tbl = OxmlElement("w:tbl")
    pr = OxmlElement("w:tblPr")
    w = OxmlElement("w:tblW"); w.set(qn("w:w"), str(sum(widths))); w.set(qn("w:type"), "dxa"); pr.append(w)
    bd = OxmlElement("w:tblBorders")
    for t in ("w:top", "w:left", "w:bottom", "w:right", "w:insideH", "w:insideV"): bd.append(_border(t))
    pr.append(bd)
    lay = OxmlElement("w:tblLayout"); lay.set(qn("w:type"), "fixed"); pr.append(lay)
    mar = OxmlElement("w:tblCellMar")
    for side in ("w:top", "w:left", "w:bottom", "w:right"):
        m = OxmlElement(side); m.set(qn("w:w"), "40" if side in ("w:top", "w:bottom") else "70"); m.set(qn("w:type"), "dxa"); mar.append(m)
    pr.append(mar)
    tbl.append(pr)
    grid = OxmlElement("w:tblGrid")
    for wd in widths:
        g = OxmlElement("w:gridCol"); g.set(qn("w:w"), str(wd)); grid.append(g)
    tbl.append(grid)
    for ri, row in enumerate(rows):
        tr = OxmlElement("w:tr")
        trpr = OxmlElement("w:trPr"); cs = OxmlElement("w:cantSplit"); trpr.append(cs); tr.append(trpr)
        for ci in range(ncols):
            txt = row[ci] if ci < len(row) else ""
            tc = OxmlElement("w:tc"); tcpr = OxmlElement("w:tcPr")
            tw = OxmlElement("w:tcW"); tw.set(qn("w:w"), str(widths[ci])); tw.set(qn("w:type"), "dxa"); tcpr.append(tw)
            if ri == 0:
                sh = OxmlElement("w:shd"); sh.set(qn("w:val"), "clear"); sh.set(qn("w:color"), "auto"); sh.set(qn("w:fill"), "D9D9D9"); tcpr.append(sh)
            tc.append(tcpr)
            p = OxmlElement("w:p"); ppr = OxmlElement("w:pPr")
            sp = OxmlElement("w:spacing"); sp.set(qn("w:after"), "0"); sp.set(qn("w:line"), "240"); sp.set(qn("w:lineRule"), "auto"); ppr.append(sp)
            jc = OxmlElement("w:jc"); jc.set(qn("w:val"), "left"); ppr.append(jc)
            p.append(ppr)
            for i, seg in enumerate(re.split(r"\*\*(.+?)\*\*", txt)):
                if seg: p.append(make_run(seg, rpr_tpl, bold=(ri == 0 or i % 2 == 1), size=18))
            tc.append(p); tr.append(tc)
        tbl.append(tr)
    return tbl

def fill_cell(cell, text, force_bold=False, force_italic=False):
    """Replace a cell's content with marked-up text, keeping the cell's own paragraph/run formatting."""
    tc = cell._tc
    paras = tc.findall(qn("w:p"))
    p0 = paras[0]
    ppr_tpl = p0.find(qn("w:pPr"))
    rpr_tpl = ppr_tpl.find(qn("w:rPr")) if ppr_tpl is not None else None
    for p in paras: tc.remove(p)
    tcw = tc.tcPr.find(qn("w:tcW")) if tc.tcPr is not None else None
    avail = (int(tcw.get(qn("w:w"))) if tcw is not None else 6000) - 216
    lines = text.split("\n") if text else [""]
    tbl_rows = []

    def flush_table():
        if tbl_rows:
            tc.append(make_table(list(tbl_rows), avail, rpr_tpl))
            p = OxmlElement("w:p"); ppr = copy.deepcopy(ppr_tpl) if ppr_tpl is not None else OxmlElement("w:pPr")
            for tag in ("w:numPr", "w:ind"):
                for e in ppr.findall(qn(tag)): ppr.remove(e)
            p.append(ppr); tc.append(p)
            tbl_rows.clear()

    for line in lines:
        if line.strip().startswith("|"):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if not all(re.fullmatch(r":?-{2,}:?", c) for c in cells if c):   # skip |---|---| separator rows
                tbl_rows.append(cells)
            continue
        flush_table()
        bullet = line.startswith("- ")
        head = line.startswith("# ")
        body = line[2:] if (bullet or head) else line
        p = OxmlElement("w:p")
        ppr = copy.deepcopy(ppr_tpl) if ppr_tpl is not None else OxmlElement("w:pPr")
        for tag in ("w:numPr", "w:ind"):
            for e in ppr.findall(qn(tag)): ppr.remove(e)
        if bullet: add_ind(ppr, 300, 220)
        p.append(ppr)
        if bullet: p.append(make_run("•\u00a0", rpr_tpl, bold=force_bold, italic=force_italic))
        for i, seg in enumerate(re.split(r"\*\*(.+?)\*\*", body)):
            if seg:
                p.append(make_run(seg, rpr_tpl, bold=(head or force_bold or i % 2 == 1), italic=force_italic))
        tc.append(p)
    flush_table()
    if tc.findall(qn("w:p")) == []:                     # a cell must end with a paragraph
        tc.append(OxmlElement("w:p"))

def set_par_text(p, text):
    runs = p.runs
    runs[0].text = text
    for r in runs[1:]: r._r.getparent().remove(r._r)

def resize_days(table, n, label_w, total_w):
    """Rebuild a table whose rows have 1 label column + 4 day columns so it has n day columns."""
    day_w = (total_w - label_w) // n
    tbl = table._tbl
    grid = tbl.find(qn("w:tblGrid"))
    for g in list(grid): grid.remove(g)
    for w in [label_w] + [day_w] * n:
        g = OxmlElement("w:gridCol"); g.set(qn("w:w"), str(w)); grid.append(g)
    tblw = tbl.tblPr.find(qn("w:tblW"))
    if tblw is not None and tblw.get(qn("w:type")) == "dxa": tblw.set(qn("w:w"), str(total_w))
    for tr in tbl.findall(qn("w:tr")):
        tcs = tr.findall(qn("w:tc"))
        def setw(tc, w):
            tcw = tc.tcPr.find(qn("w:tcW")); tcw.set(qn("w:w"), str(w)); tcw.set(qn("w:type"), "dxa")
        spans = [tc.tcPr.find(qn("w:gridSpan")) for tc in tcs]
        if len(tcs) == 1 and spans[0] is not None:               # full-width banner row
            spans[0].set(qn("w:val"), str(1 + n)); setw(tcs[0], total_w)
        elif len(tcs) == 2 and spans[1] is not None:             # label + merged value
            setw(tcs[0], label_w)
            if n == 1: tcs[1].tcPr.remove(spans[1])
            else:      spans[1].set(qn("w:val"), str(n))
            setw(tcs[1], total_w - label_w)
        else:                                                     # label + 4 day cells
            setw(tcs[0], label_w)
            for tc in tcs[1 + n:]: tr.remove(tc)
            for tc in tcs[1:1 + n]: setw(tc, day_w)

def no_split(row):
    """Keep a table row on one page (Word moves the whole row to the next page if it does not fit)."""
    tr = row._tr
    trpr = tr.find(qn("w:trPr"))
    if trpr is None:
        trpr = OxmlElement("w:trPr")
        pre = tr.find(qn("w:tblPrEx"))
        (pre.addnext(trpr) if pre is not None else tr.insert(0, trpr))
    if trpr.find(qn("w:cantSplit")) is None:
        cs = OxmlElement("w:cantSplit")
        h = trpr.find(qn("w:trHeight"))
        (h.addprevious(cs) if h is not None else trpr.insert(0, cs))

def keep_with_next(row):
    """Stop a grey banner row (e.g. 'Learning Experience.') from being stranded at the bottom of a page."""
    for p in row._tr.iter(qn("w:p")):
        ppr = p.find(qn("w:pPr"))
        if ppr is None:
            ppr = OxmlElement("w:pPr"); p.insert(0, ppr)
        if ppr.find(qn("w:keepNext")) is None:
            kn = OxmlElement("w:keepNext")
            ps = ppr.find(qn("w:pStyle"))
            (ps.addnext(kn) if ps is not None else ppr.insert(0, kn))

# ---------------------------------------------------------------- main
def build(plan, out_path, template=TEMPLATE, db_path=DB):
    db = json.load(open(db_path, encoding="utf8"))
    prof, days = plan["profile"], plan["days"]
    n = len(days)
    assert 1 <= n <= 4, "A week has 1 to 4 sessions"
    minutes = plan.get("minutes_per_session", 60)

    doc = Document(template)
    t0, t1, t2, t3 = doc.tables

    # --- title + date
    subject_line = f"{prof['subject']} {prof['grade']}"
    date_text = fmt_range([d["date"] for d in days])
    for p in doc.paragraphs:
        if p.text.startswith("LESSON PLAN IN"):
            set_par_text(p, f"LESSON PLAN IN {subject_line.upper()}")
        elif p.text.strip() == "Date":
            set_par_text(p, date_text)

    # --- header table
    sessions_txt = f"{n} Session{'s' if n > 1 else ''} ({minutes} Minutes per session)"
    sections = join_and(prof["sections"])
    vals = [plan["lesson_title"], f"{prof['subject']} {prof['grade']}",
            f"{prof['teacher']['name']} ({prof['teacher']['position']})",
            f"Grade {prof['grade']} – {sections}", sessions_txt, date_text,
            plan["references"], plan["ai_declaration"] if plan.get("ai_used", True) else "No AI tools were used in preparing this lesson plan."]
    for row, v in zip(t0.rows, vals): fill_cell(row.cells[1], v)

    # --- fit the day columns
    resize_days(t1, n, 1555, 14395)
    resize_days(t2, n, 1526, 14393)

    # --- Intentions: competencies (from DB) + standard (from term)
    comps = [c for c in db["competencies"] if c["term"] == plan["term"]]
    lines = []
    for gid in plan["competency_groups"]:
        g = [c for c in comps if c["grp"] == gid]
        assert g, f"unknown competency group {gid} for {plan['term']}"
        subs = "; ".join(c["sub"] for c in g if c["sub"])
        lines.append(f"- **Competency:** {g[0]['stem']} {subs}".rstrip())
    std = next(s for s in db["standards"] if s["term"] == plan["term"])
    lines.append(f"- **Performance Standard:** {std['performance']}")
    fill_cell(t1.rows[1].cells[1], "\n".join(lines))
    fill_cell(t1.rows[3].cells[1], plan["learner_context"])

    # --- per-day cells
    for i, d in enumerate(days):
        label = f"DAY {i + 1}"
        obj_c, pre_c, flow_c = t1.rows[2].cells[1 + i], t2.rows[1].cells[1 + i], t2.rows[2].cells[1 + i]
        if d.get("no_class"):
            reason = d.get("reason", "No classes")
            fill_cell(obj_c, f"# {label}: {reason}\n- {NO_CLASS_MSG}", force_bold=True, force_italic=False)
            fill_cell(pre_c, f"# {label}: {reason}\n{NO_CLASS_MSG}")
            extra = d.get("flow", "").strip()
            fill_cell(flow_c, f"# {label}: {reason}\n" + (f"- **Class Routine:**\n{extra}" if extra else NO_CLASS_MSG))
            continue
        objs = "\n".join(f"{chr(97 + k)}. {o}" for k, o in enumerate(d["objectives"]))
        fill_cell(obj_c, f"# {label}: {d['title']}\n{objs}")
        fill_cell(pre_c, f"# {label} ({d['prelesson_title']}):\n\n{d['prelesson']}")
        fill_cell(flow_c, f"# {label}: {d['flow_title']}\n{d['flow']}")

    fill_cell(t2.rows[3].cells[1], plan["learning_resources"])
    fill_cell(t2.rows[4].cells[1], plan["integration"])
    fill_cell(t3.rows[1].cells[1], plan["formative_assessment"])
    fill_cell(t3.rows[3].cells[1], plan["extended_learning"])
    fill_cell(t3.rows[4].cells[1], plan["reflections"])

    # --- signatories (Prepared / Checked / Noted)
    paras = doc.paragraphs
    for label, person in (("Prepared by:", prof["teacher"]), ("Checked by:", prof["checker"]), ("Noted by:", prof["noted_by"])):
        k = next(i for i, p in enumerate(paras) if p.text.strip() == label)
        nxt = [p for p in paras[k + 1:k + 6] if p.text.strip()][:2]
        set_par_text(nxt[0], person["name"].upper()); set_par_text(nxt[1], person["position"])
    first = next(i for i, p in enumerate(paras) if p.text.strip() == "Prepared by:")
    last = max(i for i, p in enumerate(paras) if p.text.strip() == prof["noted_by"]["position"])
    for p in paras[first:last]:                      # every paragraph except the very last
        ppr = p._p.get_or_add_pPr()
        if ppr.find(qn("w:keepNext")) is None:
            kn = OxmlElement("w:keepNext"); ps = ppr.find(qn("w:pStyle"))
            (ps.addnext(kn) if ps is not None else ppr.insert(0, kn))

    # --- page-break behaviour: short rows stay whole, banners stay with the row below
    for tb, rows in ((t1, (1, 2, 3)), (t2, (1, 3, 4)), (t3, (1, 3, 4))):
        for r in rows: no_split(tb.rows[r])
    for tb, rows in ((t1, (0,)), (t2, (0,)), (t3, (0, 2))):
        for r in rows: keep_with_next(tb.rows[r])

    doc.save(out_path)
    return out_path

if __name__ == "__main__":
    build(json.load(open(sys.argv[1], encoding="utf8")), sys.argv[2])


def build_from_files(plan_path, template_path, db_path, out_path):
    """Entry point used by the browser (Pyodide): everything is passed as file paths in the in-memory filesystem."""
    return build(json.load(open(plan_path, encoding="utf8")), out_path, template=template_path, db_path=db_path)
