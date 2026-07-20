"""Render the daily schedule to a self-contained HTML file."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from .config import WEB_DIR


def render(rows: list[dict], target_date: str, dates: list[str]) -> Path:
    WEB_DIR.mkdir(parents=True, exist_ok=True)

    leagues = sorted({r["league"] for r in rows})
    payload = {
        "generated_at": datetime.now().astimezone().strftime("%b %-d, %Y · %-I:%M %p %Z"),
        "date": target_date,
        "rows": rows,
        "leagues": leagues,
        "dates": dates,
    }
    html = _TEMPLATE.replace("__PAYLOAD__", json.dumps(payload))
    out = WEB_DIR / "index.html"
    out.write_text(html)
    return out


_TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Kalshi Daily Sports Schedule</title>
<link rel="stylesheet" href="https://cdn.datatables.net/2.1.8/css/dataTables.dataTables.min.css">
<style>
  body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
         margin: 24px; color: #1a1a1a; background: #fafafa; }
  h1   { font-size: 22px; margin: 0 0 4px; }
  .meta { color: #666; font-size: 13px; margin-bottom: 16px; }
  .filter-group { margin-bottom: 8px; display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }
  .filter-label { font-size: 12px; font-weight: 600; color: #666; text-transform: uppercase;
                  letter-spacing: 0.5px; margin-right: 4px; }
  .filter-group button {
    background: #fff; border: 1px solid #ccc; padding: 4px 10px;
    border-radius: 999px; cursor: pointer; font-size: 13px;
  }
  .filter-group button.active { background: #1a1a1a; color: #fff; border-color: #1a1a1a; }
  .filter-group button .count { color: #888; font-size: 11px; }
  .filter-group button.active .count { color: #bbb; }
  .tblwrap { overflow-x: auto; }
  table.dataTable { background: #fff; }
  table.dataTable th { font-weight: 600; }
  td.num { text-align: center; font-variant-numeric: tabular-nums; }
  td.time { white-space: nowrap; font-variant-numeric: tabular-nums; }
  td.ticker a { color: #1a6dd4; text-decoration: none; }
  td.ticker a:hover { text-decoration: underline; }
  td.tbd { color: #999; font-style: italic; }
  tr.past td { opacity: .45; }
  tr.now-divider td { padding: 5px 10px; color: #c2410c; font-weight: 700; font-size: 12px;
    background: #fff7ed; border-top: 2px solid #fb923c; letter-spacing: .04em;
    text-transform: uppercase; opacity: 1; }
  .rel { color: #16a34a; font-size: 11px; font-weight: 600; margin-left: 6px; }
  @media (max-width: 640px) { body { margin: 12px; } }
</style>
</head>
<body>
<h1>Kalshi Daily Sports Schedule</h1>
<div class="meta" id="meta"></div>
<div id="date-filters" class="filter-group"></div>
<div id="league-filters" class="filter-group"></div>
<div class="tblwrap">
<table id="tbl" class="display compact" style="width:100%">
  <thead>
    <tr>
      <th class="num">#</th>
      <th>Event</th>
      <th>League</th>
      <th>Date</th>
      <th>Start Time (CT)</th>
      <th>Event Ticker</th>
    </tr>
  </thead>
</table>
</div>

<script src="https://code.jquery.com/jquery-3.7.1.min.js"></script>
<script src="https://cdn.datatables.net/2.1.8/js/dataTables.min.js"></script>
<script>
const DATA = __PAYLOAD__;
const nowSec = () => Date.now() / 1000;
const esc = s => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

document.getElementById("meta").textContent =
  `Generated: ${DATA.generated_at} · ${DATA.rows.length} events`;

let table;
let activeDate = DATA.dates[0];
let activeLeagues = new Set();   // empty = All
let autoScrolled = false;

function applyFilters() {
  table.column(3).search("^" + esc(activeDate) + "$", true, false);
  const lg = activeLeagues.size
    ? "^(" + [...activeLeagues].map(esc).join("|") + ")$" : "";
  table.column(2).search(lg, true, false);
  table.draw();
  renderLeagueChips();
}

// --- Date filter ---
const dateBar = document.getElementById("date-filters");
const dateLbl = document.createElement("span");
dateLbl.className = "filter-label";
dateLbl.textContent = "Date";
dateBar.appendChild(dateLbl);

const DATE_COUNTS = DATA.rows.reduce((acc, r) => {
  acc[r.date] = (acc[r.date] || 0) + 1;
  return acc;
}, {});

DATA.dates.forEach(d => {
  const b = document.createElement("button");
  b.innerHTML = `${d} <span class="count">${DATE_COUNTS[d] || 0}</span>`;
  b.dataset.date = d;
  if (d === activeDate) b.classList.add("active");
  b.addEventListener("click", () => {
    document.querySelectorAll("#date-filters button").forEach(x => x.classList.remove("active"));
    b.classList.add("active");
    activeDate = d;
    applyFilters();
  });
  dateBar.appendChild(b);
});

// --- League filter: multi-select chips, ordered by event count on the active
// date; leagues with nothing on that date don't render a chip at all. ---
function renderLeagueChips() {
  const bar = document.getElementById("league-filters");
  bar.innerHTML = "";
  const lbl = document.createElement("span");
  lbl.className = "filter-label";
  lbl.textContent = "League";
  bar.appendChild(lbl);

  const counts = {};
  let total = 0;
  DATA.rows.forEach(r => {
    if (r.date !== activeDate) return;
    counts[r.league] = (counts[r.league] || 0) + 1;
    total++;
  });

  const mk = (label, count, on, click) => {
    const b = document.createElement("button");
    b.innerHTML = `${label} <span class="count">${count}</span>`;
    if (on) b.classList.add("active");
    b.addEventListener("click", click);
    bar.appendChild(b);
  };

  mk("All", total, activeLeagues.size === 0, () => { activeLeagues.clear(); applyFilters(); });

  DATA.leagues
    .filter(lg => counts[lg])
    .sort((a, b) => counts[b] - counts[a] || a.localeCompare(b))
    .forEach(lg => mk(lg, counts[lg], activeLeagues.has(lg), () => {
      activeLeagues.has(lg) ? activeLeagues.delete(lg) : activeLeagues.add(lg);
      applyFilters();
    }));
}

// --- "now" awareness: dim rows that already started, and (when the visible
// list is time-sorted and spans the current moment) insert a divider at NOW.
function markNow(api) {
  document.querySelectorAll("tr.now-divider").forEach(el => el.remove());
  const now = nowSec();
  let past = 0, firstFuture = null;
  api.rows({ search: "applied", order: "applied" }).every(function () {
    const d = this.data(), tr = this.node();
    const isPast = d.sort_key && d.sort_key < now;
    tr.classList.toggle("past", !!isPast);
    if (isPast) past++;
    else if (!firstFuture) firstFuture = tr;
  });
  const ord = api.order();
  const timeAsc = ord.length && ord[0][0] === 4 && ord[0][1] === "asc";
  if (timeAsc && past > 0 && firstFuture) {
    const tr = document.createElement("tr");
    tr.className = "now-divider";
    const lbl = new Date().toLocaleTimeString("en-US",
      { hour: "numeric", minute: "2-digit", timeZone: "America/Chicago" });
    tr.innerHTML = `<td colspan="5">now · ${lbl} CT</td>`;
    firstFuture.parentNode.insertBefore(tr, firstFuture);
    if (!autoScrolled) {
      autoScrolled = true;
      setTimeout(() => tr.scrollIntoView({ block: "center" }), 0);
    }
  }
}

table = new DataTable("#tbl", {
  data: DATA.rows,
  paging: false,
  order: [[4, "asc"]],
  drawCallback: function () { markNow(this.api()); },
  columns: [
    { data: null, className: "num", width: "40px", orderable: false, searchable: false,
      render: (d, t, row, meta) => meta.row + 1 },
    { data: "event",
      render: (d, t, row) => {
        if (t !== "display") return d;
        if (row.sub_title && row.sub_title !== d) return `${d} <span style="color:#888;font-size:12px">${row.sub_title}</span>`;
        return d;
      }
    },
    { data: "league" },
    { data: "date", visible: false },
    { data: "start_time", className: "time",
      render: (d, t, row) => {
        if (t === "sort" || t === "type") return row.sort_key;
        if (d === "TBD") return `<span class="tbd">TBD</span>`;
        if (t !== "display") return d;
        const dt = row.sort_key - nowSec();
        if (dt > 0 && dt < 6 * 3600) {
          const m = Math.round(dt / 60);
          const rel = m < 60 ? `in ${m}m` : `in ${Math.floor(m / 60)}h ${m % 60}m`;
          return `${d} <span class="rel">${rel}</span>`;
        }
        return d;
      }
    },
    { data: "event_ticker", className: "ticker",
      render: (d, t, row) => {
        if (t === "sort" || t === "type" || t === "filter") return d || "";
        if (!d) return "";
        return `<a href="${row.event_url}" target="_blank" rel="noopener">${d}</a>`;
      }
    },
  ],
});

// Apply initial filters (also builds the league chips)
applyFilters();

// Keep the dimming, divider position, and "in Xm" labels current
setInterval(() => table.draw(false), 60000);
</script>
</body>
</html>
"""
