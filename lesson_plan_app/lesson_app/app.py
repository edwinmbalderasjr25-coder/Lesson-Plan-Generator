"""
Weekly lesson plan maker – local web app.

  pip install -r requirements.txt
  set ANTHROPIC_API_KEY=...        (Windows)   |   export ANTHROPIC_API_KEY=...   (Mac/Linux)
  python app.py                    ->  open http://localhost:5000

  Try it without an API key:  MOCK_AI=1 python app.py
"""
import io, json, os, re, tempfile
from flask import Flask, jsonify, request, send_file, send_from_directory

import ai_drafter, generate_plan

HERE = os.path.dirname(os.path.abspath(__file__))
PROFILE_PATH = os.path.join(HERE, "profile.json")
app = Flask(__name__, static_folder=os.path.join(HERE, "static"))

@app.get("/")
def index():
    return send_from_directory(app.static_folder, "index.html")

@app.get("/api/config")
def config():
    """Competencies grouped by term -> domain -> group (one entry per selectable competency)."""
    out = {}
    for c in ai_drafter.DB["competencies"]:
        t = out.setdefault(c["term"], {"focus": c["focus"], "domains": {}})
        g = t["domains"].setdefault(c["domain"], {}).setdefault(c["grp"], {"id": c["grp"], "stem": c["stem"], "subs": []})
        if c["sub"]: g["subs"].append(c["sub"])
    for t in out.values():
        t["domains"] = [{"name": k, "groups": list(v.values())} for k, v in t["domains"].items()]
    return jsonify(dict(terms=out, ai_declaration=ai_drafter.DEFAULT_AI_DECLARATION,
                        mock=os.environ.get("MOCK_AI") == "1", model=ai_drafter.MODEL))

@app.get("/api/profile")
def get_profile():
    if os.path.exists(PROFILE_PATH):
        return jsonify(json.load(open(PROFILE_PATH, encoding="utf8")))
    return jsonify(dict(subject="English", grade=7, sections=[], teacher=dict(name="", position=""),
                        checker=dict(name="", position=""), noted_by=dict(name="", position="")))

@app.post("/api/profile")
def save_profile():
    json.dump(request.get_json(), open(PROFILE_PATH, "w", encoding="utf8"), ensure_ascii=False, indent=1)
    return jsonify(ok=True)

@app.post("/api/draft")
def draft():
    inputs = request.get_json()
    if not inputs.get("competency_groups"):
        return jsonify(error="Pick at least one competency."), 400
    if not any(not d.get("no_class") for d in inputs["days"]):
        return jsonify(error="At least one day must be a teaching day."), 400
    try:
        plan, warnings = ai_drafter.draft_plan(inputs)
    except Exception as e:                      # surface API / key problems to the teacher
        return jsonify(error=f"{type(e).__name__}: {e}"), 500
    return jsonify(plan=plan, warnings=warnings)

@app.post("/api/generate")
def generate():
    plan = request.get_json()
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "plan.docx")
        generate_plan.build(plan, path)
        data = open(path, "rb").read()
    first = plan["days"][0]["date"]
    name = re.sub(r"[^A-Za-z0-9_-]+", "_", f"{plan['profile']['subject']}{plan['profile']['grade']}_{plan.get('week_label') or first}")
    return send_file(io.BytesIO(data), as_attachment=True, download_name=f"Lesson_Plan_{name}.docx",
                     mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document")

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
