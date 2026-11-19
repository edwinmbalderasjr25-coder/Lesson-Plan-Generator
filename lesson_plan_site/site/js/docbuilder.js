/* Builds the Word file inside the browser by running py/docgen.py with Pyodide (Python compiled to WebAssembly).
   Nothing is uploaded anywhere: the plan and the template stay on the teacher's device. */
(function (root) {
  const PYODIDE_VERSION = "0.26.4";
  const BASE = `https://cdn.jsdelivr.net/pyodide/v${PYODIDE_VERSION}/full/`;
  let ready = null;

  const loadScript = (src) => new Promise((ok, fail) => {
    const s = document.createElement("script"); s.src = src; s.onload = ok; s.onerror = () => fail(new Error("Could not load " + src)); document.head.append(s);
  });

  function init(onStatus = () => {}) {
    if (ready) return ready;
    ready = (async () => {
      onStatus("loading", "Loading the Word engine (first visit only, about a minute on slow connections)...");
      await loadScript(BASE + "pyodide.js");
      const py = await loadPyodide({indexURL: BASE});
      await py.loadPackage(["micropip", "lxml", "typing-extensions"]);
      await py.pyimport("micropip").install("python-docx==1.2.0");
      const get = async (p, binary) => { const r = await fetch(p); if (!r.ok) throw new Error("Missing file " + p); return binary ? new Uint8Array(await r.arrayBuffer()) : r.text(); };
      py.FS.writeFile("/tmp/docgen.py", await get("py/docgen.py"));
      py.FS.writeFile("/tmp/template.docx", await get("data/template.docx", true));
      py.FS.writeFile("/tmp/db.json", await get("data/competencies.json"));
      py.runPython("import sys; sys.path.insert(0, '/tmp'); import docgen");
      onStatus("ready", "Word engine ready.");
      return py;
    })().catch(e => { ready = null; onStatus("failed", "The Word engine could not start: " + e.message); throw e; });
    return ready;
  }

  async function build(plan, onStatus) {
    if (root.__buildDocx) return root.__buildDocx(plan);          // test hook (used only by automated tests)
    const py = await init(onStatus);
    py.FS.writeFile("/tmp/plan.json", JSON.stringify(plan));
    py.runPython("docgen.build_from_files('/tmp/plan.json', '/tmp/template.docx', '/tmp/db.json', '/tmp/out.docx')");
    const bytes = py.FS.readFile("/tmp/out.docx");
    return new Blob([bytes], {type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document"});
  }
  root.DocBuilder = {init, build};
})(window);
