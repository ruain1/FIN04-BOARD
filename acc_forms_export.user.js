// ==UserScript==
// @name         FIN04 ACC Forms -> permits.csv
// @namespace    fin04
// @version      0.1
// @description  Scrape the ACC permit Forms list into permits.csv for make_snapshot.py
// @match        https://acc.autodesk.com/*forms*
// @match        https://construction.autodesk.com/*forms*
// @grant        none
// ==/UserScript==
/*
  No API needed: this rides your logged-in ACC session and reads the rendered
  Forms list. You MUST map the three TODO selectors to your project's Forms page
  (right-click a row, Inspect, find the cells). Output columns match make_snapshot.py:
      permit_id,title,asset_tag,status,from,to
  asset_tag must equal a board asset id (e.g. FIN04.01.L0.EPOD07.DB003 or EPOD07.DB003).
*/
(function () {
  "use strict";

  function scrapeRows() {
    // TODO 1: selector for each permit row in the Forms table.
    const rows = document.querySelectorAll('SELECTOR_FOR_FORM_ROW');
    const out = [];
    rows.forEach((row) => {
      // TODO 2: pull each field from the row (adjust selectors / indexes).
      const cell = (sel) => (row.querySelector(sel)?.textContent || "").trim();
      const permit_id = cell('SELECTOR_PERMIT_NUMBER');
      const title     = cell('SELECTOR_TITLE');
      const asset_tag = cell('SELECTOR_ASSET_TAG');   // the field that holds the board tag
      const status    = cell('SELECTOR_STATUS');
      const from      = cell('SELECTOR_FROM_DATE');
      const to        = cell('SELECTOR_TO_DATE');
      if (asset_tag) out.push({ permit_id, title, asset_tag, status, from, to });
    });
    return out;
  }

  function toCsv(rows) {
    const esc = (s) => `"${String(s ?? "").replace(/"/g, '""')}"`;
    const head = ["permit_id", "title", "asset_tag", "status", "from", "to"];
    return [head.join(",")]
      .concat(rows.map((r) => head.map((h) => esc(r[h])).join(",")))
      .join("\n");
  }

  function download(text, name) {
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([text], { type: "text/csv" }));
    a.download = name;
    a.click();
  }

  const btn = document.createElement("button");
  btn.textContent = "Export permits.csv";
  Object.assign(btn.style, {
    position: "fixed", top: "12px", right: "12px", zIndex: 99999,
    padding: "8px 14px", background: "#173b5e", color: "#fff",
    border: "1px solid #2b5a86", borderRadius: "7px", cursor: "pointer",
  });
  btn.onclick = () => {
    const rows = scrapeRows();
    if (!rows.length) { alert("No rows found. Map the TODO selectors."); return; }
    download(toCsv(rows), "permits.csv");
  };
  document.body.appendChild(btn);
})();
