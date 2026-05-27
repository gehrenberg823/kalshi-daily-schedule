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
        "generated_at": datetime.now().isoformat(timespec="seconds"),
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
  table.dataTable { background: #fff; }
  table.dataTable th { font-weight: 600; }
  td.num { text-align: center; font-variant-numeric: tabular-nums; }
  td.time { white-space: nowrap; font-variant-numeric: tabular-nums; }
  td.ticker a { color: #1a6dd4; text-decoration: none; }
  td.ticker a:hover { text-decoration: underline; }
  td.tbd { color: #999; font-style: italic; }
</style>
</head>
<body>
<h1>Kalshi Daily Sports Schedule</h1>
<div class="meta" id="meta"></div>
<div id="date-filters" class="filter-group"></div>
<div id="league-filters" class="filter-group"></div>
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

<script src="https://code.jquery.com/jquery-3.7.1.min.js"></script>
<script src="https://cdn.datatables.net/2.1.8/js/dataTables.min.js"></script>
<script>
const DATA = __PAYLOAD__;

document.getElementById("meta").textContent =
  `Generated: ${DATA.generated_at} · ${DATA.rows.length} events`;

let table;
let activeDate = DATA.dates[0];
let activeLeague = "All";

function applyFilters() {
  const dateRegex = "^" + activeDate.replace(/[.*+?^${}()|[\]\\]/g, "\\$&") + "$";
  table.column(3).search(dateRegex, true, false);

  const leagueRegex = activeLeague === "All" ? "" : "^" + activeLeague.replace(/[.*+?^${}()|[\]\\]/g, "\\$&") + "$";
  table.column(2).search(leagueRegex, true, false);

  table.draw();

  // Update league counts for the active date
  const visibleRows = table.rows({search: "applied"}).data().toArray();
  document.querySelectorAll("#league-filters button").forEach(b => {
    const lg = b.dataset.league;
    let count;
    if (lg === "All") {
      count = DATA.rows.filter(r => r.date === activeDate).length;
    } else {
      count = DATA.rows.filter(r => r.date === activeDate && r.league === lg).length;
    }
    b.querySelector(".count").textContent = count;
  });
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
  const count = DATE_COUNTS[d] || 0;
  b.innerHTML = `${d} <span class="count" style="color:#888;font-size:11px">${count}</span>`;
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

// --- League filter ---
const leagueBar = document.getElementById("league-filters");
const lgLbl = document.createElement("span");
lgLbl.className = "filter-label";
lgLbl.textContent = "League";
leagueBar.appendChild(lgLbl);

const LEAGUES = ["All", ...DATA.leagues];

LEAGUES.forEach(lg => {
  const b = document.createElement("button");
  const count = lg === "All"
    ? DATA.rows.filter(r => r.date === activeDate).length
    : DATA.rows.filter(r => r.date === activeDate && r.league === lg).length;
  b.innerHTML = `${lg} <span class="count" style="color:#888;font-size:11px">${count}</span>`;
  b.dataset.league = lg;
  if (lg === "All") b.classList.add("active");
  b.addEventListener("click", () => {
    document.querySelectorAll("#league-filters button").forEach(x => x.classList.remove("active"));
    b.classList.add("active");
    activeLeague = lg;
    applyFilters();
  });
  leagueBar.appendChild(b);
});

table = new DataTable("#tbl", {
  data: DATA.rows,
  paging: false,
  order: [[4, "asc"]],
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

// Apply initial date filter
applyFilters();
</script>
</body>
</html>
"""
