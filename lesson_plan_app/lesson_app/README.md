# Weekly Lesson Plan Maker (ILAW) – Grade 7 English prototype

AI drafts the daily objectives, lesson flow and assessments from the competencies you pick.
You review and edit, then download a print-ready Word file built on the Ampon NHS template.

## Run it on your computer
1. Install Python 3.10+ from python.org.
2. Open a terminal in this folder and run:  `pip install -r requirements.txt`
3. Set your Claude API key (get one at console.anthropic.com):
   - Windows:   `set ANTHROPIC_API_KEY=your-key-here`
   - Mac/Linux: `export ANTHROPIC_API_KEY=your-key-here`
4. Start the app:  `python app.py`   then open http://localhost:5000

To try the screens without a key (stored example, no AI):  `MOCK_AI=1 python app.py`
(Windows: `set MOCK_AI=1` then `python app.py`).

## Files
- `app.py` – the web server (profile, competency list, draft, Word download)
- `ai_drafter.py` – the prompt, the assessment-selection rules, validation of the AI draft
- `generate_plan.py` – fills the Word template (1 to 4 day columns, rubric tables, signatories)
- `static/index.html` – the screens
- `data/G7_English_competencies.json` – competency database (edit the .xlsx version, then regenerate)
- `data/Blank_Ampon_NHS_DLL_Template.docx` – the school template
- `data/example_plan.json` – the approved Week 7 sample used as the style example for the AI

## Settings
- `CLAUDE_MODEL` – model name (default in `ai_drafter.py`)
- Your saved details are stored in `profile.json` next to `app.py`.

## Known limits of this version
- Grade 7 English only; local use only (not yet a hosted site with logins).
- The live Claude call has not been run by its author (no network access when it was built). Test one plan first.
- Rubric tables are typed as lines starting with `|` in the review screen.
- Always check the AI-use declaration wording against the school's requirement.
