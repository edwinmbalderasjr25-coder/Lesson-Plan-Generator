/* Drafting logic: builds the prompt, reads the AI's answer, checks it, and turns it into an editable plan.
   Works in the browser (window.Drafter) and in Node (for tests). */
(function (root) {
  const DEFAULT_MODEL = "gemini-flash-latest";

  const RULES = `You are an instructional-design assistant for Philippine public secondary school teachers.
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
   Every objective must be assessed by something you write. Fill the "alignment" list: one entry per (day, objective letter)
   naming the item that assesses it. Do not assess days marked no-class.
5. Never invent references, book titles, authors, links or statistics. For "references" list only what the teacher provided plus
   the Grade level Curriculum Guide / Budget of Work (DepEd MATATAG). If the teacher gave no resources, use generic items
   (teacher-made slides, worksheets, short texts the teacher will choose) and say the teacher should supply the actual texts.
6. Texts, examples and sample sentences you write must be original, age-appropriate and locally relevant (Philippine context where natural).
7. "learner_context" is a cautious, generic description based on the grade level and competencies and any notes from the teacher.
   Do not invent facts about the class (test scores, behaviour, number of learners).
8. Write in clear Philippine-school English. No emojis.

TEXT FORMAT inside every text field (it is converted to Word):
  "# Heading" at the start of a line -> bold line;  "- item" -> bullet;  **bold** -> inline bold;  an empty line -> blank line.
  Tables: lines that start with "|" become a table. The first line is the header row, for example
  | Criteria | 4 Points | 3 Points | 2 Points | 1 Point |
  |---|---|---|---|---|
  | Content | ... | ... | ... | ... |
  Do not use any other markdown. Do not number the objectives (the app adds a., b., c.).
  Inside JSON strings write line breaks as \\n.

HOW THE SECTIONS LOOK (follow this school's approved example closely in structure, depth and tone, but do NOT copy its content):
- prelesson: a 3-5 minute activity that activates prior knowledge. prelesson_title is its short name.
- flow: "# Direct Instruction:", "# Guided Practice:" (or similar) with short bullets, then a closing "# Wrap-up/Reflection:". flow_title names the day's focus.
- formative_assessment: one block per teaching day beginning "# DAY n: <title>", then the assessment, then the key or rubric.
- extended_learning: one short take-home task. reflections: 2-3 teacher reflection questions as "- " bullets.
- integration: 1-3 lines linking to other subjects or values, as "**Subject:** sentence".

ANSWER FORMAT: reply with ONE JSON object and nothing else (no explanation, no code fence needed) with exactly these keys:
{
 "lesson_title": "string",
 "learner_context": "string",
 "days": [ {"day_number": 1, "title": "string", "objectives": ["a","b","c"], "prelesson_title": "string", "prelesson": "string", "flow_title": "string", "flow": "string"} ],
 "learning_resources": "string", "integration": "string", "formative_assessment": "string",
 "extended_learning": "string", "reflections": "string", "references": "string",
 "alignment": [ {"day_number": 1, "objective": "a", "assessed_by": "name of the assessment item that checks it"} ]
}
"days" has ONE entry per TEACHING day only, with day_number equal to the DAY number given by the teacher.`;

  const declaration = (tool) =>
    `Artificial intelligence (${tool || "an AI assistant"}) was used to draft the daily objectives, lesson flow, formative assessments, ` +
    `and learner context of this lesson plan. The teacher reviewed, edited, and approved all content before use.`;

  const teachingDays = (inputs) => inputs.days.map((d, i) => [i + 1, d]).filter(([, d]) => !d.no_class);

  function resolveCompetencies(db, term, groups) {
    return groups.map(gid => {
      const rows = db.competencies.filter(c => c.term === term && c.grp === gid);
      if (!rows.length) throw new Error(`Unknown competency group ${gid} for ${term}`);
      return {stem: rows[0].stem, focus: rows.map(r => r.sub).filter(Boolean)};
    });
  }

  function buildPrompt(db, example, inputs) {
    const p = inputs.profile, minutes = inputs.minutes_per_session || 60;
    const comps = resolveCompetencies(db, inputs.term, inputs.competency_groups);
    const std = db.standards.find(s => s.term === inputs.term);
    const focus = db.competencies.find(c => c.term === inputs.term).focus;
    const L = [`Subject and grade: ${p.subject} ${p.grade}  |  Sections: ${p.sections.join(", ")}`,
      `Term: ${inputs.term}  |  Text focus of the term: ${focus}`, `Minutes per session: ${minutes}`, "",
      "SELECTED COMPETENCIES (from the DepEd Budget of Work):"];
    comps.forEach(c => L.push(`- ${c.stem}` + (c.focus.length ? ` Specific focus: ${c.focus.join("; ")}` : "")));
    L.push("", `Term performance standard: ${std.performance}`, "", "DAYS THIS WEEK:");
    inputs.days.forEach((d, i) => L.push(`- DAY ${i + 1} (${d.date}): ` + (d.no_class ? `NO CLASS - ${d.reason || "no regular classes"}` : "teaching day")));
    L.push("", `Lesson title from teacher: ${inputs.lesson_title || "(none - propose one)"}`,
      `Topic / text focus notes from teacher: ${inputs.topic_notes || "(none)"}`,
      `Resources the teacher has available: ${inputs.resources_notes || "(none stated)"}`,
      `Notes about the learners: ${inputs.learner_notes || "(none)"}`,
      `References the teacher gave: ${inputs.references || "(none)"}`, "",
      `Teaching days to write (day_number values): ${teachingDays(inputs).map(([n]) => n).join(", ")}`, "",
      "APPROVED EXAMPLE FROM THIS SCHOOL (structure and depth only; different week and competencies):",
      JSON.stringify(["lesson_title", "learner_context", "days", "learning_resources", "integration", "formative_assessment",
        "extended_learning", "reflections"].reduce((o, k) => (o[k] = example[k], o), {})));
    return {system: RULES.replace("{minutes}", minutes), user: L.join("\n")};
  }

  /* One text for chat apps that have no separate "system" box. */
  const chatPrompt = (p) => p.system + "\n\n=====\nTHE TEACHER'S REQUEST\n=====\n" + p.user;

  function extractJson(text) {
    let t = String(text || "").trim();
    const fence = t.match(/```(?:json)?\s*([\s\S]*?)```/i); if (fence) t = fence[1].trim();
    const a = t.indexOf("{"), b = t.lastIndexOf("}");
    if (a < 0 || b <= a) throw new Error("I could not find the JSON answer in that text. Ask the AI to reply with the JSON object only.");
    try { return JSON.parse(t.slice(a, b + 1)); }
    catch (e) { throw new Error("The answer is not valid JSON (" + e.message + "). Ask the AI to resend it as one complete JSON object."); }
  }

  function validate(draft, inputs) {
    const w = [], need = teachingDays(inputs).map(([n]) => n);
    const days = Array.isArray(draft.days) ? draft.days : [];
    const got = days.map(d => d.day_number);
    if (JSON.stringify(got) !== JSON.stringify(need)) w.push(`The draft has days [${got}]; expected teaching days [${need}].`);
    days.forEach(d => {
      if (!Array.isArray(d.objectives) || d.objectives.length !== 3) w.push(`DAY ${d.day_number}: expected 3 objectives (knowledge, skill, attitude).`);
      ["title", "prelesson", "flow"].forEach(k => { if (!String(d[k] || "").trim()) w.push(`DAY ${d.day_number}: '${k}' is empty.`); });
    });
    const aligned = new Set((draft.alignment || []).map(a => a.day_number + a.objective));
    need.forEach(n => {
      ["a", "b", "c"].forEach(o => { if (!aligned.has(n + o)) w.push(`DAY ${n} objective ${o}: no assessment item is mapped to it.`); });
      if (!new RegExp("DAY\\s*" + n + "\\b").test(draft.formative_assessment || "")) w.push(`DAY ${n}: the formative assessment has no section for this day.`);
    });
    return w;
  }

  function toPlan(draft, inputs, tool) {
    const ai = {}; (draft.days || []).forEach(d => ai[d.day_number] = d);
    const days = inputs.days.map((d, i) => {
      if (d.no_class) return {date: d.date, no_class: true, reason: d.reason || "No classes", flow: ""};
      const x = ai[i + 1] || {};
      return {date: d.date, title: x.title || "", objectives: (x.objectives || ["", "", ""]).slice(0, 3),
        prelesson_title: x.prelesson_title || "", prelesson: x.prelesson || "", flow_title: x.flow_title || "", flow: x.flow || ""};
    });
    return {term: inputs.term, week_label: inputs.week_label || "", minutes_per_session: inputs.minutes_per_session || 60,
      profile: inputs.profile, lesson_title: inputs.lesson_title || draft.lesson_title || "",
      references: inputs.references || draft.references || "", ai_used: true, ai_declaration: declaration(tool),
      competency_groups: inputs.competency_groups, learner_context: draft.learner_context || "", days,
      learning_resources: draft.learning_resources || "", integration: draft.integration || "",
      formative_assessment: draft.formative_assessment || "", extended_learning: draft.extended_learning || "",
      reflections: draft.reflections || ""};
  }

  async function callGemini(prompt, apiKey, model) {
    const url = `https://generativelanguage.googleapis.com/v1beta/models/${encodeURIComponent(model || DEFAULT_MODEL)}:generateContent`;
    const r = await fetch(url, {method: "POST", headers: {"Content-Type": "application/json", "x-goog-api-key": apiKey},
      body: JSON.stringify({system_instruction: {parts: [{text: prompt.system}]}, contents: [{role: "user", parts: [{text: prompt.user}]}],
        generationConfig: {responseMimeType: "application/json", temperature: 0.7, maxOutputTokens: 24000}})});
    let data = {}; try { data = await r.json(); } catch (e) {}
    if (!r.ok) {
      const msg = (data.error && data.error.message) || r.statusText;
      if (r.status === 429) throw new Error("The free AI limit was reached (too many requests). Wait a minute and try again, or use the paste-in method. Details: " + msg);
      if (r.status === 400 || r.status === 403) throw new Error("Google rejected the request. Check the key and the model name. Details: " + msg);
      throw new Error(`AI error ${r.status}: ${msg}`);
    }
    const cand = (data.candidates || [])[0];
    const text = cand && cand.content && cand.content.parts ? cand.content.parts.map(p => p.text || "").join("") : "";
    if (!text) throw new Error("The AI returned no text (" + ((cand && cand.finishReason) || (data.promptFeedback && data.promptFeedback.blockReason) || "unknown reason") + ").");
    return text;
  }

  const api = {DEFAULT_MODEL, declaration, teachingDays, buildPrompt, chatPrompt, extractJson, validate, toPlan, callGemini};
  if (typeof module !== "undefined") module.exports = api; else root.Drafter = api;
})(typeof window !== "undefined" ? window : globalThis);
