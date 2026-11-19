const $ = id => document.getElementById(id);
const el = (tag, props = {}, ...kids) => { const e = Object.assign(document.createElement(tag), props); kids.forEach(k => e.append(k)); return e; };
const LS = {get: (k, d) => { try { const v = localStorage.getItem(k); return v === null ? d : JSON.parse(v); } catch (e) { return d; } },
            set: (k, v) => { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) {} },
            del: k => { try { localStorage.removeItem(k); } catch (e) {} }};
let DB = null, EXAMPLE = null, PLAN = null, LAST_INPUTS = null, LAST_PROMPT = null;

/* ---------- details (saved in this browser) ---------- */
const readProfile = () => ({subject: $("subject").value.trim(), grade: $("grade").value.trim(),
  sections: $("sections").value.split(",").map(s => s.trim()).filter(Boolean),
  teacher: {name: $("tName").value.trim(), position: $("tPos").value.trim()},
  checker: {name: $("cName").value.trim(), position: $("cPos").value.trim()},
  noted_by: {name: $("nName").value.trim(), position: $("nPos").value.trim()}});
function writeProfile(p) {
  $("subject").value = p.subject; $("grade").value = p.grade; $("sections").value = (p.sections || []).join(", ");
  $("tName").value = p.teacher.name; $("tPos").value = p.teacher.position; $("cName").value = p.checker.name;
  $("cPos").value = p.checker.position; $("nName").value = p.noted_by.name; $("nPos").value = p.noted_by.position;
}
$("saveProfile").onclick = () => { LS.set("profile", readProfile()); $("profileStatus").textContent = "Saved on this device."; setTimeout(() => $("profileStatus").textContent = "", 2500); };

/* ---------- days ---------- */
function addDay(date = "", noClass = false, reason = "") {
  if ($("days").children.length >= 4) return;
  const row = el("div", {className: "day"});
  const d = el("input", {type: "date", value: date});
  const cb = el("input", {type: "checkbox", checked: noClass});
  const why = el("input", {type: "text", className: "reason", placeholder: "Reason (e.g. Periodical Test, holiday)", value: reason});
  why.classList.toggle("hidden", !noClass); cb.onchange = () => why.classList.toggle("hidden", !cb.checked);
  const del = el("button", {className: "ghost", textContent: "Remove"});
  del.onclick = () => { if ($("days").children.length > 1) row.remove(); renumber(); };
  row.append(el("strong", {className: "dn"}), d, el("label", {className: "check", style: "margin:0"}, cb, "No regular class"), why, del);
  $("days").append(row); renumber();
}
const renumber = () => [...$("days").children].forEach((r, i) => r.querySelector(".dn").textContent = "Day " + (i + 1));
const readDays = () => [...$("days").children].map(r => {
  const d = r.querySelector("input[type=date]").value, cb = r.querySelector("input[type=checkbox]").checked, why = r.querySelector(".reason").value.trim();
  return cb ? {date: d, no_class: true, reason: why || "No classes"} : {date: d};
});
$("addDay").onclick = () => addDay();
$("fill4").onclick = () => {
  if (!$("start").value) { alert("Pick the first class day first."); return; }
  $("days").innerHTML = ""; const base = new Date($("start").value + "T00:00:00");
  for (let i = 0; i < 4; i++) { const x = new Date(base); x.setDate(base.getDate() + i); addDay(x.toISOString().slice(0, 10)); }
};

/* ---------- competencies ---------- */
function renderComps() {
  const term = $("term").value, domains = new Map();
  DB.competencies.filter(c => c.term === term).forEach(c => {
    if (!domains.has(c.domain)) domains.set(c.domain, new Map());
    const g = domains.get(c.domain); if (!g.has(c.grp)) g.set(c.grp, {id: c.grp, stem: c.stem, subs: []});
    if (c.sub) g.get(c.grp).subs.push(c.sub);
  });
  $("comps").innerHTML = "";
  domains.forEach((groups, name) => {
    $("comps").append(el("div", {className: "domain", textContent: name}));
    groups.forEach(g => $("comps").append(el("label", {className: "comp"}, el("input", {type: "checkbox", value: g.id}),
      el("span", {}, g.stem, ...(g.subs.length ? [el("small", {textContent: g.subs.join("; ")})] : [])))));
  });
}
const pickedGroups = () => [...$("comps").querySelectorAll("input:checked")].map(i => i.value);

/* ---------- AI method ---------- */
const method = () => document.querySelector("input[name=method]:checked").value;
function syncMethod() {
  $("keyBox").classList.toggle("hidden", method() !== "key");
  $("draft").textContent = method() === "key" ? "Draft with AI" : "Prepare the prompt";
  $("pasteBox").classList.add("hidden");
}
document.querySelectorAll("input[name=method]").forEach(r => r.onchange = syncMethod);
$("forgetKey").onclick = () => { LS.del("apiKey"); $("apiKey").value = ""; $("keyStatus").textContent = "Key removed from this device."; };

function collectInputs() {
  const days = readDays();
  if (days.some(d => !d.date)) throw new Error("Please fill in every date.");
  const profile = readProfile();
  if (!profile.teacher.name) throw new Error("Please fill in your details (section 1) first.");
  if (!pickedGroups().length) throw new Error("Pick at least one competency.");
  if (!days.some(d => !d.no_class)) throw new Error("At least one day must be a teaching day.");
  return {profile, term: $("term").value, week_label: $("week").value.trim(), minutes_per_session: 60, lesson_title: $("title").value.trim(),
    topic_notes: $("topic").value.trim(), resources_notes: $("resources").value.trim(), learner_notes: $("learners").value.trim(),
    references: $("refs").value.trim(), competency_groups: pickedGroups(), days};
}

$("draft").onclick = async () => {
  let inputs; try { inputs = collectInputs(); } catch (e) { alert(e.message); return; }
  LAST_INPUTS = inputs; LAST_PROMPT = Drafter.buildPrompt(DB, EXAMPLE, inputs);
  if (method() === "paste") {
    $("promptText").value = Drafter.chatPrompt(LAST_PROMPT); $("pasteBox").classList.remove("hidden");
    $("pasteBox").scrollIntoView({behavior: "smooth"}); $("draftStatus").textContent = "Prompt ready."; return;
  }
  const key = $("apiKey").value.trim(), model = $("model").value.trim() || Drafter.DEFAULT_MODEL;
  if (!key) { alert("Paste your free Google AI Studio key first (or choose the paste-in method)."); return; }
  if ($("rememberKey").checked) LS.set("apiKey", key); LS.set("model", model);
  $("draft").disabled = true; $("draftStatus").textContent = "Drafting... this can take a minute.";
  try {
    const text = await Drafter.callGemini(LAST_PROMPT, key, model);
    acceptAnswer(text, "Google Gemini");
    $("draftStatus").textContent = "Draft ready - scroll down to review.";
  } catch (e) { $("draftStatus").textContent = ""; alert("Could not draft the plan: " + e.message); }
  $("draft").disabled = false;
};
$("copyPrompt").onclick = async () => {
  try { await navigator.clipboard.writeText($("promptText").value); $("copyStatus").textContent = "Copied."; }
  catch (e) { $("promptText").select(); $("copyStatus").textContent = "Press Ctrl+C to copy."; }
  setTimeout(() => $("copyStatus").textContent = "", 3000);
};
$("useAnswer").onclick = () => {
  try { acceptAnswer($("answerText").value, $("toolName").value.trim() || "an AI chat assistant"); $("draftStatus").textContent = "Draft ready - scroll down to review."; }
  catch (e) { alert(e.message); }
};
function acceptAnswer(text, tool) {
  const draft = Drafter.extractJson(text);
  PLAN = Drafter.toPlan(draft, LAST_INPUTS, tool); showReview(Drafter.validate(draft, LAST_INPUTS));
  $("reviewSec").scrollIntoView({behavior: "smooth"});
}

/* ---------- review ---------- */
function showReview(warnings) {
  $("reviewSec").classList.remove("hidden"); $("approve").checked = false; $("generate").disabled = true; $("warnings").innerHTML = "";
  const all = [...warnings, "Learner context is a general draft. Please edit it to describe your actual class."];
  $("warnings").append(el("div", {className: "warn"}, "Please check:", el("ul", {}, ...all.map(w => el("li", {textContent: w})))));
  Object.entries({rTitle: PLAN.lesson_title, rRefs: PLAN.references, rContext: PLAN.learner_context, rRes: PLAN.learning_resources, rInt: PLAN.integration,
    rAssess: PLAN.formative_assessment, rExt: PLAN.extended_learning, rRef: PLAN.reflections, rAI: PLAN.ai_declaration}).forEach(([k, v]) => $(k).value = v);
  $("rDays").innerHTML = "";
  PLAN.days.forEach((d, i) => {
    const card = el("div", {className: "daycard"}); card.dataset.i = i; card.append(el("h3", {textContent: `Day ${i + 1} - ${d.date}`}));
    if (d.no_class) card.append(el("p", {textContent: "No regular class: " + d.reason}));
    else {
      const f = (label, cls, val, tag = "input") => { const x = el(tag, tag === "input" ? {type: "text", value: val} : {value: val}); x.className = cls; card.append(el("label", {textContent: label}), x); };
      f("Lesson title for the day", "f-title", d.title); f("Objective a (knowledge)", "f-o0", d.objectives[0]); f("Objective b (skill)", "f-o1", d.objectives[1]);
      f("Objective c (attitude)", "f-o2", d.objectives[2]); f("Pre-lesson title", "f-pt", d.prelesson_title); f("Pre-lesson", "f-p", d.prelesson, "textarea");
      f("Flow title", "f-ft", d.flow_title); f("Flow", "f-f", d.flow, "textarea");
    }
    $("rDays").append(card);
  });
}
$("approve").onchange = () => $("generate").disabled = !$("approve").checked;
function collectPlan() {
  const p = JSON.parse(JSON.stringify(PLAN));
  Object.assign(p, {lesson_title: $("rTitle").value, references: $("rRefs").value, learner_context: $("rContext").value, learning_resources: $("rRes").value,
    integration: $("rInt").value, formative_assessment: $("rAssess").value, extended_learning: $("rExt").value, reflections: $("rRef").value, ai_declaration: $("rAI").value});
  [...$("rDays").children].forEach(card => {
    const d = p.days[+card.dataset.i]; if (d.no_class) return; const q = c => card.querySelector(c).value;
    Object.assign(d, {title: q(".f-title"), objectives: [q(".f-o0"), q(".f-o1"), q(".f-o2")], prelesson_title: q(".f-pt"), prelesson: q(".f-p"), flow_title: q(".f-ft"), flow: q(".f-f")});
  });
  return p;
}
$("generate").onclick = async () => {
  $("generate").disabled = true; $("genStatus").textContent = "Building the Word file...";
  try {
    const plan = collectPlan(), blob = await DocBuilder.build(plan, setEngine);
    const name = `Lesson_Plan_${plan.profile.subject}${plan.profile.grade}_${plan.week_label || plan.days[0].date}`.replace(/[^A-Za-z0-9_-]+/g, "_") + ".docx";
    const a = el("a", {href: URL.createObjectURL(blob), download: name}); document.body.append(a); a.click(); a.remove(); $("genStatus").textContent = "Downloaded.";
  } catch (e) { $("genStatus").textContent = ""; alert("Could not build the file: " + e.message); }
  $("generate").disabled = !$("approve").checked;
};

/* ---------- start ---------- */
function setEngine(state, msg) { $("engine").textContent = msg; $("engine").className = "chip " + state; }
(async () => {
  [DB, EXAMPLE] = await Promise.all([fetch("data/competencies.json").then(r => r.json()), fetch("data/example_plan.json").then(r => r.json())]);
  [...new Set(DB.competencies.map(c => c.term))].forEach(t => $("term").append(el("option", {value: t,
    textContent: {T1: "Term 1", T2: "Term 2", T3: "Term 3"}[t] + " - " + DB.competencies.find(c => c.term === t).focus})));
  $("term").onchange = renderComps; renderComps();
  writeProfile(LS.get("profile", {subject: "English", grade: "7", sections: [], teacher: {name: "", position: ""}, checker: {name: "", position: ""}, noted_by: {name: "", position: ""}}));
  $("apiKey").value = LS.get("apiKey", ""); $("model").value = LS.get("model", Drafter.DEFAULT_MODEL); $("model").placeholder = Drafter.DEFAULT_MODEL;
  addDay(); syncMethod();
  setTimeout(() => DocBuilder.init(setEngine).catch(() => {}), 800);        // warm up the Word engine while the teacher fills the form
})();
