"""
AI drafting for the weekly ILAW lesson plan.

The teacher supplies: term, competencies, days, topic notes.
Claude drafts: lesson title (if blank), learner context, daily objectives (K-S-A), pre-lesson, flow,
learning resources, integration, formative assessment (chosen to match the objectives), extended
learning, reflections.  Everything is returned as editable text; the teacher approves before download.

Set ANTHROPIC_API_KEY (and optionally CLAUDE_MODEL).  MOCK_AI=1 returns the bundled example instead of
calling the API (for testing the app without a key).
"""
import copy, json, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
DB = json.load(open(os.path.join(HERE, "data", "G7_English_competencies.json"), encoding="utf8"))
EXAMPLE = json.load(open(os.path.join(HERE, "data", "example_plan.json"), encoding="utf8"))
MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-5-5")

DEFAULT_AI_DECLARATION = (
    "Artificial intelligence (Claude, by Anthropic) was used to draft the daily objectives, lesson flow, "
    "formative assessments, and learner context of this lesson plan. The teacher reviewed, edited, and "
    "approved all content before use.")

# ------------------------------------------------------------------ prompt
SYSTEM_PROMPT = """You are an instructional-design assistant for Philippine public secondary school teachers.
You draft one WEEKLY lesson plan in the DepEd ILAW format (Intentions, Learning Experiences, Assessment, Ways Forward)
under the MATATAG curriculum. A teacher will review and edit your draft, so be concrete, realistic and classroom-ready.

HARD RULES
1. Plan only for the teaching days you are given. Each session is {minutes} minutes: activities must be doable in that time.
2. Stay inside the selected competencies and the term's performance standard. Do not add competencies that were not selected.
3. For every teaching day write exactly three objectives in this order: (a) Knowledge, (b) Skill, (c) Attitude/values.
   Use measurable verbs for (a) and (b). Each objective must be reachable within one session and must come from the selected competencies.
4. ASSESSMENT: choose the assessment type from what each objective asks learners to do, and write it for each teaching day:
   - identify / recognize / classify / distinguish  -> short quiz, sorting or matching task, with the answer key
   - analyze / examine / evaluate                    -> annotated-text or criteria-based task, with a scoring guide
   - supply / transform / compose / write / revise   -> performance task with a rubric (use a table)
   - appreciate / show diligence / value (attitude)  -> observation checklist or short reflection prompt
   Every objective must be assessed by something you write. Fill the `alignment` list: one entry per (day, objective letter)
   naming the item that assesses it. Do not assess days marked no-class.
5. Never invent references, book titles, authors, links or statistics. For `references` list only what the teacher provided plus
   the Grade level Curriculum Guide / Budget of Work (DepEd MATATAG). If the teacher gave no resources, use generic items
   (teacher-made slides, worksheets, short texts the teacher will choose) and say the teacher should supply the actual texts.
6. Texts, examples and sample sentences you write must be original, age-appropriate and locally relevant (Philippine context where natural).
7. `learner_context` is a cautious, generic description based on the grade level and competencies and any notes from the teacher.
   Do not invent facts about the class (test scores, behaviour, number of learners).
8. Write in clear Philippine-school English. No emojis.

TEXT FORMAT inside every text field (it is converted to Word):
  "# Heading"      -> bold line        "- item" -> bullet       "**bold**" -> inline bold       blank line -> blank line
  Tables: rows that start with "|" become a table. The first row is the header row, e.g.
  | Criteria | 4 Points | 3 Points | 2 Points | 1 Point |
  |---|---|---|---|---|
  | Content | ... | ... | ... | ... |
  Do not use any other markdown. Do not use numbered "1." lists in objectives (the app adds a., b., c.).

HOW THE SECTIONS LOOK (follow this school's approved example closely in structure, depth and tone, but do NOT copy its content):
- pre-lesson: a 3-5 minute activity that activates prior knowledge.  prelesson_title is its short name.
- flow: "# Direct Instruction:", "# Guided Practice:" (or similar) with short bullets, then a closing "# Wrap-up/Reflection:".  flow_title names the day's focus.
- formative_assessment: one block per teaching day beginning "# DAY n: <title>", then the assessment, then the key or rubric.
- extended_learning: one short take-home task.  reflections: 2-3 teacher reflection questions as "- " bullets.
- integration: 1-3 lines linking to other subjects or values, as "**Subject:** sentence".
"""

TOOL = {
    "name": "submit_lesson_plan",
    "description": "Submit the drafted weekly ILAW lesson plan.",
    "input_schema": {
        "type": "object",
        "properties": {
            "lesson_title": {"type": "string"},
            "learner_context": {"type": "string"},
            "days": {"type": "array", "items": {"type": "object", "properties": {
                "day_number": {"type": "integer", "description": "The session number in the week (DAY n) this entry is for"},
                "title": {"type": "string", "description": "Short title of the day's lesson, no 'DAY n:' prefix"},
                "objectives": {"type": "array", "items": {"type": "string"}, "minItems": 3, "maxItems": 3},
                "prelesson_title": {"type": "string"},
                "prelesson": {"type": "string"},
                "flow_title": {"type": "string"},
                "flow": {"type": "string"}},
                "required": ["day_number", "title", "objectives", "prelesson_title", "prelesson", "flow_title", "flow"]}},
            "learning_resources": {"type": "string"},
            "integration": {"type": "string"},
            "formative_assessment": {"type": "string"},
            "extended_learning": {"type": "string"},
            "reflections": {"type": "string"},
            "references": {"type": "string"},
            "alignment": {"type": "array", "items": {"type": "object", "properties": {
                "day_number": {"type": "integer"},
                "objective": {"type": "string", "enum": ["a", "b", "c"]},
                "assessed_by": {"type": "string", "description": "Name of the assessment item in formative_assessment that checks this objective"}},
                "required": ["day_number", "objective", "assessed_by"]}},
        },
        "required": ["lesson_title", "learner_context", "days", "learning_resources", "integration",
                     "formative_assessment", "extended_learning", "reflections", "references", "alignment"],
    },
}

# ------------------------------------------------------------------ inputs -> prompt
def resolve_competencies(term, groups):
    out = []
    for gid in groups:
        rows = [c for c in DB["competencies"] if c["term"] == term and c["grp"] == gid]
        if not rows:
            raise ValueError(f"Unknown competency group {gid} for {term}")
        out.append(dict(domain=rows[0]["domain"], stem=rows[0]["stem"], focus=[r["sub"] for r in rows if r["sub"]]))
    return out

def teaching_days(inputs):
    return [(i + 1, d) for i, d in enumerate(inputs["days"]) if not d.get("no_class")]

def build_user_prompt(inputs):
    prof = inputs["profile"]
    comps = resolve_competencies(inputs["term"], inputs["competency_groups"])
    std = next(s for s in DB["standards"] if s["term"] == inputs["term"])
    focus = next(c["focus"] for c in DB["competencies"] if c["term"] == inputs["term"])
    lines = [f"Subject and grade: {prof['subject']} {prof['grade']}  |  Sections: {', '.join(prof['sections'])}",
             f"Term: {inputs['term']}  |  Text focus of the term: {focus}",
             f"Minutes per session: {inputs.get('minutes_per_session', 60)}",
             "", "SELECTED COMPETENCIES (from the DepEd Budget of Work):"]
    for c in comps:
        lines.append(f"- {c['stem']}" + (f" Specific focus: {'; '.join(c['focus'])}" if c["focus"] else ""))
    lines += ["", f"Term performance standard: {std['performance']}", "", "DAYS THIS WEEK:"]
    for i, d in enumerate(inputs["days"], 1):
        lines.append(f"- DAY {i} ({d['date']}): " + (f"NO CLASS – {d.get('reason', 'no regular classes')}" if d.get("no_class") else "teaching day"))
    lines += ["", f"Lesson title from teacher: {inputs.get('lesson_title') or '(none – propose one)'}",
              f"Topic / text focus notes from teacher: {inputs.get('topic_notes') or '(none)'}",
              f"Resources the teacher has available: {inputs.get('resources_notes') or '(none stated)'}",
              f"Notes about the learners: {inputs.get('learner_notes') or '(none)'}",
              f"References the teacher gave: {inputs.get('references') or '(none)'}",
              "", "Return the plan with the submit_lesson_plan tool. `days` must contain one entry per TEACHING day, in order, "
              "with day_number set to the DAY number above (" + ", ".join(str(n) for n, _ in teaching_days(inputs)) + ").",
              "", "APPROVED EXAMPLE FROM THIS SCHOOL (structure and depth only; different week and competencies):",
              json.dumps({k: EXAMPLE[k] for k in ("lesson_title", "learner_context", "days", "learning_resources",
                          "integration", "formative_assessment", "extended_learning", "reflections")}, ensure_ascii=False)]
    return "\n".join(lines)

# ------------------------------------------------------------------ drafting
def call_claude(inputs):
    import anthropic                      # pip install anthropic
    client = anthropic.Anthropic()        # reads ANTHROPIC_API_KEY
    resp = client.messages.create(
        model=MODEL, max_tokens=16000,
        system=SYSTEM_PROMPT.format(minutes=inputs.get("minutes_per_session", 60)),
        tools=[TOOL], tool_choice={"type": "tool", "name": TOOL["name"]},
        messages=[{"role": "user", "content": build_user_prompt(inputs)}])
    block = next(b for b in resp.content if b.type == "tool_use")
    return block.input

def mock_draft(inputs):
    """Offline stand-in: reuses the bundled example so the app can be tried without an API key."""
    ex = copy.deepcopy(EXAMPLE)
    teach = [d for d in ex["days"] if not d.get("no_class")]
    days = []
    for k, (num, _) in enumerate(teaching_days(inputs)):
        d = copy.deepcopy(teach[k % len(teach)]); d.pop("date", None); d["day_number"] = num; days.append(d)
    ex.update(days=days, alignment=[dict(day_number=d["day_number"], objective=o, assessed_by="Mock item") for d in days for o in "abc"])
    return ex

def validate(draft, inputs):
    """Return a list of warnings for the teacher; empty list = looks consistent."""
    w, need = [], [n for n, _ in teaching_days(inputs)]
    got = [d.get("day_number") for d in draft.get("days", [])]
    if got != need:
        w.append(f"The draft has days {got}; expected teaching days {need}.")
    for d in draft.get("days", []):
        if len(d.get("objectives", [])) != 3:
            w.append(f"DAY {d.get('day_number')}: expected 3 objectives (knowledge, skill, attitude).")
        for k in ("title", "prelesson", "flow"):
            if not str(d.get(k, "")).strip():
                w.append(f"DAY {d.get('day_number')}: '{k}' is empty.")
    aligned = {(a["day_number"], a["objective"]) for a in draft.get("alignment", [])}
    for n in need:
        for o in "abc":
            if (n, o) not in aligned:
                w.append(f"DAY {n} objective {o}: no assessment item is mapped to it.")
        if not re.search(rf"DAY\s*{n}\b", draft.get("formative_assessment", "")):
            w.append(f"DAY {n}: the formative assessment has no section for this day.")
    return w

def draft_plan(inputs):
    """Returns (plan_dict, warnings). plan_dict is ready for the generator and for editing in the UI."""
    raw = mock_draft(inputs) if os.environ.get("MOCK_AI") == "1" else call_claude(inputs)
    warnings = validate(raw, inputs)
    ai = {d["day_number"]: d for d in raw["days"]}
    days = []
    for i, d in enumerate(inputs["days"], 1):
        if d.get("no_class"):
            days.append(dict(date=d["date"], no_class=True, reason=d.get("reason", "No classes"), flow=""))
        else:
            x = ai.get(i, {})
            days.append(dict(date=d["date"], title=x.get("title", ""), objectives=x.get("objectives", ["", "", ""]),
                             prelesson_title=x.get("prelesson_title", ""), prelesson=x.get("prelesson", ""),
                             flow_title=x.get("flow_title", ""), flow=x.get("flow", "")))
    refs = inputs.get("references") or raw.get("references", "")
    plan = dict(
        term=inputs["term"], week_label=inputs.get("week_label", ""), minutes_per_session=inputs.get("minutes_per_session", 60),
        profile=inputs["profile"], lesson_title=inputs.get("lesson_title") or raw.get("lesson_title", ""),
        references=refs, ai_used=True, ai_declaration=DEFAULT_AI_DECLARATION,
        competency_groups=inputs["competency_groups"], learner_context=raw.get("learner_context", ""),
        days=days, learning_resources=raw.get("learning_resources", ""), integration=raw.get("integration", ""),
        formative_assessment=raw.get("formative_assessment", ""), extended_learning=raw.get("extended_learning", ""),
        reflections=raw.get("reflections", ""))
    return plan, warnings
