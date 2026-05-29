"""Assembles index.html by inlining data.json. Both tabs are now dynamic."""
from pathlib import Path

BASE = Path("/Users/danielyanezalbuja/Library/CloudStorage/OneDrive-Maresa/Marketing/2026/Análisis de tráfico/2026/Abril/panel-trafico")
data_json = (BASE / "data.json").read_text(encoding="utf-8").strip()
safe_data = data_json.replace("</script>", "<\\/script>")

HTML = r"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Dashboard Tráfico DY — ORGU / Maresa</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/chartjs-plugin-datalabels@2.2.0/dist/chartjs-plugin-datalabels.min.js"></script>
<style>
  :root{
    --ford:#003478; --ford-2:#2e5090; --bg:#f3f5f8; --card:#fff;
    --ink:#1c2434; --muted:#6b7280;
    --pos:#155724; --neg:#c62828; --zoom:#8b0000; --yellow:#f9a825;
    --green-bg:#c8e6c9; --green-tx:#2e7d32;
    --yellow-bg:#fff9c4; --yellow-tx:#f57f17;
    --red-bg:#ffcdd2; --red-tx:#c62828;
    --grey-bg:#f5f5f5; --grey-tx:#999;
  }
  *{box-sizing:border-box}
  html,body{margin:0;padding:0}
  body{font-family:Inter,system-ui,-apple-system,"Segoe UI",Roboto,Arial,sans-serif;color:var(--ink);background:var(--bg);font-size:14px;line-height:1.45}
  header.topbar{background:var(--ford);color:#fff;padding:18px 28px;box-shadow:0 2px 8px rgba(0,0,0,.15)}
  header.topbar h1{margin:0;font-size:20px;letter-spacing:.3px;font-weight:700}
  header.topbar .sub{font-size:12px;opacity:.82;margin-top:2px}
  nav.tabs{display:flex;gap:8px;padding:14px 28px 0;background:#f3f5f8;position:sticky;top:0;z-index:5;border-bottom:1px solid #e5e7eb}
  .tab-btn{background:#fff;border:1px solid #d1d5db;color:var(--ink);padding:9px 18px;border-radius:999px;cursor:pointer;font:inherit;font-weight:600;font-size:13px;transition:all .15s}
  .tab-btn:hover{border-color:var(--ford-2)}
  .tab-btn.active{background:var(--ford);color:#fff;border-color:var(--ford)}
  main{padding:22px 28px 48px;max-width:1400px;margin:0 auto;box-sizing:border-box;width:100%}
  *{box-sizing:border-box}
  body{overflow-x:hidden}
  /* Garantiza que cualquier sección esté contenida al ancho del viewport */
  .tab-panel{max-width:100%;overflow-x:hidden}
  .ford-section{max-width:100%;overflow:hidden}
  /* Pero permitimos scroll en contenedores que explícitamente lo necesitan */
  .tab-panel .ford-section [style*="overflow-x:auto"],
  .tab-panel .ford-section .table-scroll{overflow-x:auto !important}
  .tab-panel{display:none}
  .tab-panel.active{display:block}

  .filter-bar{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:10px;background:#fff;border:1px solid #e5e7eb;border-radius:12px;padding:12px 14px;margin-bottom:18px;box-shadow:0 1px 2px rgba(0,0,0,.03)}
  .filter-bar label{display:flex;flex-direction:column;font-size:11px;text-transform:uppercase;letter-spacing:.6px;color:var(--muted);font-weight:600}
  .filter-bar select{margin-top:4px;padding:8px 10px;border:1px solid #d1d5db;border-radius:8px;font:inherit;background:#fff}
  .filter-bar .reset{align-self:end;background:#fff;border:1px solid #d1d5db;border-radius:8px;padding:8px 12px;cursor:pointer;font:inherit;font-weight:600}
  .filter-bar .reset:hover{background:#f3f4f6}

  .kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:12px;margin-bottom:18px}
  .kpi{background:#fff;border:1px solid #e5e7eb;border-radius:12px;padding:14px 16px;box-shadow:0 1px 3px rgba(0,0,0,.04)}
  .kpi .label{font-size:11px;text-transform:uppercase;letter-spacing:.7px;color:var(--muted);font-weight:600}
  .kpi .num{font-size:28px;font-weight:800;color:var(--ford);margin-top:4px;line-height:1.05}
  .kpi .hint{font-size:12px;color:var(--muted);margin-top:4px}
  .kpi.accent .num{color:var(--ford-2)}

  .grid-2{display:grid;grid-template-columns:1fr 1fr;gap:14px}
  .grid-3{display:grid;grid-template-columns:1.15fr 1fr 1fr;gap:14px}
  @media (max-width:900px){.grid-2,.grid-3{grid-template-columns:1fr}}

  .card{background:#fff;border:1px solid #e5e7eb;border-radius:12px;padding:14px 16px;box-shadow:0 1px 3px rgba(0,0,0,.04);margin-bottom:14px}
  .card h3{margin:0 0 10px;font-size:14px;color:var(--ford-2);font-weight:700;letter-spacing:.2px}
  .card h3 .sub{font-size:11px;color:var(--muted);font-weight:500;margin-left:6px}
  .card .chart-wrap{position:relative;height:280px}
  .card.tall .chart-wrap{height:360px}

  table.comp{width:100%;border-collapse:collapse;font-size:13px}
  table.comp th{background:var(--ford-2);color:#fff;font-weight:600;padding:7px 8px;text-align:center;font-size:11px;letter-spacing:.4px;text-transform:uppercase}
  table.comp th:first-child,table.comp th.left{text-align:left}
  table.comp th.sortable{cursor:pointer;user-select:none}
  table.comp th.sortable:hover{background:#3b5fa8}
  table.comp th.sortable.asc::after{content:' ▲';opacity:.7}
  table.comp th.sortable.desc::after{content:' ▼';opacity:.7}
  table.comp td{padding:6px 8px;border-bottom:1px solid #eef0f3;vertical-align:middle;text-align:center}
  table.comp td:first-child{text-align:left;font-weight:600}
  table.comp td.left{text-align:left;font-weight:600}
  table.comp td.num{font-variant-numeric:tabular-nums;font-weight:600;white-space:nowrap}
  table.comp td.ctr{text-align:center;font-variant-numeric:tabular-nums}
  table.comp tr.total{font-weight:700;background:#e8edf3}
  table.comp tr.total td{border-top:2px solid var(--ford-2)}

  .bar-cell{min-width:120px;width:28%}
  .bar-outer{background:#eef1f5;border-radius:6px;height:9px;overflow:hidden;margin-top:2px;position:relative}
  .bar-inner{height:100%;border-radius:6px;background:linear-gradient(90deg,#3b5fa8,#5c84d6);transition:width .5s ease}
  .bar-inner.marzo{background:linear-gradient(90deg,#9aa8c1,#c9d2e1)}
  .bar-dual{display:flex;flex-direction:column;gap:3px}
  .bar-dual .row{display:flex;align-items:center;gap:6px;font-size:11px;color:var(--muted)}
  .bar-dual .row span{width:46px;text-align:right;font-weight:600;color:var(--ink)}
  .delta-pos{color:var(--pos);font-weight:700}
  .delta-neg{color:var(--neg);font-weight:700}
  .delta-zero{color:var(--muted)}

  .funnel-wrap{display:flex;flex-direction:column;gap:6px;padding:2px 4px}
  .funnel-row{display:flex;align-items:center;gap:10px;font-size:13px}
  .funnel-row .fname{width:110px;font-weight:600;color:var(--ink)}
  .funnel-row .fbar{flex:1;background:#eef1f5;border-radius:6px;height:22px;overflow:hidden;position:relative}
  .funnel-row .finner{height:100%;background:linear-gradient(90deg,#003478,#2e5090);color:#fff;font-size:11px;font-weight:700;display:flex;align-items:center;padding:0 8px;border-radius:6px}
  .funnel-row .fpct{width:70px;text-align:right;font-size:12px;color:var(--muted);font-variant-numeric:tabular-nums}

  .zoom-card{border-top:4px solid var(--zoom)}
  .zoom-card h3{color:var(--zoom)}
  .zoom-sub-grid{display:grid;grid-template-columns:1fr 1fr 1fr 1fr;gap:10px}
  @media (max-width:900px){.zoom-sub-grid{grid-template-columns:1fr 1fr}}
  .zoom-sub-grid .mini{background:#fafbfd;border:1px solid #eef0f3;border-radius:10px;padding:10px 12px}
  .zoom-sub-grid .mini h4{margin:0 0 8px;font-size:11px;text-transform:uppercase;letter-spacing:.6px;color:var(--muted);font-weight:700}
  .zoom-sub-grid .mini ul{list-style:none;margin:0;padding:0;font-size:12.5px}
  .zoom-sub-grid .mini ul li{display:flex;justify-content:space-between;gap:8px;padding:3px 0;border-bottom:1px dashed #eef0f3}
  .zoom-sub-grid .mini ul li:last-child{border:0}
  .zoom-sub-grid .mini ul li .v{font-variant-numeric:tabular-nums;font-weight:700;color:var(--ford-2)}

  .tag{display:inline-block;background:#fff3d6;color:#8a6a00;padding:1px 8px;border-radius:999px;font-size:11px;font-weight:600;margin-left:6px}
  .footer-note{color:var(--muted);font-size:11px;text-align:center;margin-top:16px}

  /* === FORD TAB === */
  .ford-section{background:#fff;border:1px solid #e5e7eb;border-radius:12px;padding:16px 20px;margin-bottom:14px;box-shadow:0 1px 3px rgba(0,0,0,.04)}
  .ford-section h3{margin:0 0 12px;color:var(--ford-2);font-size:14px;font-weight:700;border-bottom:2px solid var(--ford-2);padding-bottom:6px}
  .ford-section h3 .sub{font-size:11px;color:var(--muted);font-weight:500;margin-left:6px}

  /* Ford hero */
  .ford-hero{
    display:grid;grid-template-columns:320px 1fr;gap:18px;
    background:linear-gradient(135deg,#fff 0%,#f4f7fc 100%);
    border:1px solid #e5e7eb;border-radius:14px;padding:22px 24px;margin-bottom:16px;
    box-shadow:0 2px 8px rgba(0,52,120,.06);
  }
  @media (max-width:900px){.ford-hero{grid-template-columns:1fr}}
  .ford-hero .gauge-wrap{position:relative;display:flex;flex-direction:column;align-items:center;justify-content:center}
  .ford-hero .gauge-canvas{width:260px;height:260px;position:relative}
  .ford-hero .gauge-center{position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;pointer-events:none;text-align:center}
  .ford-hero .gauge-center .big{font-size:46px;font-weight:800;line-height:1;color:var(--ford)}
  .ford-hero .gauge-center .mid{font-size:13px;color:var(--muted);margin-top:6px;font-weight:600;text-transform:uppercase;letter-spacing:.6px}
  .ford-hero .gauge-center .tag{margin-top:10px;font-size:12px;font-weight:700;padding:3px 10px;border-radius:999px}
  .ford-hero .hero-side{display:grid;grid-template-columns:1fr 1fr;gap:12px;align-content:center}
  .hero-stat{background:#fff;border:1px solid #e5e7eb;border-radius:10px;padding:12px 14px;position:relative;overflow:hidden}
  .hero-stat::before{content:'';position:absolute;left:0;top:0;bottom:0;width:4px;background:var(--ford-2)}
  .hero-stat.good::before{background:#2e7d32}
  .hero-stat.warn::before{background:#f57f17}
  .hero-stat.bad::before{background:#c62828}
  .hero-stat .lbl{font-size:10px;color:var(--muted);text-transform:uppercase;letter-spacing:.6px;font-weight:600}
  .hero-stat .val{font-size:22px;font-weight:800;color:var(--ink);margin-top:2px;line-height:1.1}
  .hero-stat .delta{font-size:11px;margin-top:3px;color:var(--muted)}
  .hero-progress{grid-column:1/-1;background:#fff;border:1px solid #e5e7eb;border-radius:10px;padding:12px 14px}
  .hero-progress .head{display:flex;justify-content:space-between;align-items:baseline;font-size:11px;text-transform:uppercase;letter-spacing:.5px;color:var(--muted);font-weight:600;margin-bottom:6px}
  .hero-progress .head .v{color:var(--ink);font-size:12px;font-weight:700;text-transform:none;letter-spacing:0}
  .hero-progress .track{position:relative;background:#eef1f5;height:14px;border-radius:7px;overflow:hidden}
  .hero-progress .fill-proj{position:absolute;inset:0;height:100%;background:linear-gradient(90deg,#003478,#5c84d6);border-radius:7px;transition:width .6s ease}
  .hero-progress .fill-meta{position:absolute;top:0;bottom:0;width:2px;background:#f57f17}
  .hero-progress .fill-actual{position:absolute;top:0;bottom:0;background:rgba(46,80,144,.35);border-radius:7px 0 0 7px}
  .hero-progress .labels{display:flex;justify-content:space-between;margin-top:6px;font-size:10px;color:var(--muted)}

  .ford-filter-summary{
    display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin:-4px 0 10px;font-size:12px;color:var(--muted)
  }
  .ford-filter-summary .chip{background:#003478;color:#fff;padding:3px 10px;border-radius:999px;font-weight:600;font-size:11px;display:inline-flex;align-items:center;gap:6px}
  .ford-filter-summary .chip button{background:none;border:0;color:#fff;cursor:pointer;font-size:14px;line-height:1;padding:0;opacity:.7}
  .ford-filter-summary .chip button:hover{opacity:1}

  .proj-bar{position:relative;height:6px;background:#eef1f5;border-radius:3px;margin-top:4px;overflow:hidden}
  .proj-bar .pb-fill{position:absolute;top:0;left:0;bottom:0;border-radius:3px}
  .proj-bar .pb-meta{position:absolute;top:-2px;bottom:-2px;width:2px;background:#f57f17;z-index:2}
  .proj-bar .pb-fill.green{background:linear-gradient(90deg,#2e7d32,#66bb6a)}
  .proj-bar .pb-fill.yellow{background:linear-gradient(90deg,#f57f17,#ffb74d)}
  .proj-bar .pb-fill.red{background:linear-gradient(90deg,#c62828,#ef5350)}

  .risk-row{display:flex;align-items:center;gap:10px;margin-bottom:6px;font-size:12.5px}
  .risk-row .rname{min-width:120px;font-weight:700}
  .risk-row .rbar{flex:1;position:relative;height:16px;background:#f6e5b8;border-radius:4px;overflow:hidden}
  .risk-row .rbar .fill{position:absolute;inset:0;background:linear-gradient(90deg,#c62828,#ef5350);border-radius:4px;color:#fff;font-size:10px;font-weight:700;display:flex;align-items:center;padding:0 6px}
  .risk-row .rneed{min-width:110px;text-align:right;color:#c62828;font-weight:700;font-size:12px}

  .cell-with-count{display:flex;flex-direction:column;align-items:center;gap:1px;line-height:1.1}
  .cell-with-count .ct{font-size:9px;color:rgba(0,0,0,.45);font-weight:500}

  /* Sparkline mini-cards (Evolución multi-mes) */
  .ev-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:12px;margin-top:6px}
  .ev-card{background:#fafbfd;border:1px solid #eef0f3;border-radius:10px;padding:10px 12px;border-top:3px solid #9aa8c1;transition:transform .15s,box-shadow .15s}
  .ev-card:hover{transform:translateY(-1px);box-shadow:0 3px 10px rgba(0,0,0,.06)}
  .ev-card.up{border-top-color:#2e7d32}
  .ev-card.down{border-top-color:#c62828}
  .ev-card.flat{border-top-color:#f9a825}
  .ev-card-head{display:flex;justify-content:space-between;align-items:baseline;margin-bottom:4px;gap:8px}
  .ev-name{font-weight:700;font-size:13px;color:var(--ink);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
  .ev-badge{font-size:11px;font-weight:700;padding:2px 7px;border-radius:999px;flex-shrink:0}
  .ev-badge.up{background:var(--green-bg);color:var(--green-tx)}
  .ev-badge.down{background:var(--red-bg);color:var(--red-tx)}
  .ev-badge.flat{background:#fff3d6;color:#8a6a00}
  .ev-spark{display:block;width:100%;height:46px;margin:4px 0 4px}
  .ev-spark .ln{fill:none;stroke-width:2}
  .ev-spark .ar{fill-opacity:.15}
  .ev-spark .pt{stroke:#fff;stroke-width:1.5}
  .ev-foot{display:flex;justify-content:space-between;font-size:11px;color:var(--muted);font-variant-numeric:tabular-nums;padding-top:2px}
  .ev-foot strong{color:var(--ink)}
  .ev-foot .seq{display:flex;gap:6px;flex-wrap:wrap}
  .ev-foot .seq span{font-size:10px}

  /* Donut + tabla side-by-side (Ford zonas, Brand agencias). Stack en mobile. */
  .donut-with-table{display:grid;grid-template-columns:220px 1fr;gap:18px;align-items:center}
  /* Brand selector filter bar: Marca (1fr) + controles secundarios (auto) */
  .filter-bar-brand{grid-template-columns:1fr auto;gap:14px}

  .mov-bar-row{display:grid;grid-template-columns:110px 1fr 100px;gap:10px;align-items:center;font-size:13px;padding:4px 0}
  .mov-bar-row .mname{font-weight:700;color:var(--ink)}
  .mov-bar-row .mbar{position:relative;background:#eef1f5;border-radius:6px;height:18px;overflow:hidden}
  .mov-bar-row .mbar .mfill{height:100%;border-radius:6px;display:flex;align-items:center;padding:0 6px;font-size:10px;color:#fff;font-weight:700}
  .mov-bar-row .mbar .mfill.pos{background:linear-gradient(90deg,#2e7d32,#66bb6a)}
  .mov-bar-row .mbar .mfill.neg{background:linear-gradient(90deg,#c62828,#ef5350)}
  .mov-bar-row .mval{text-align:right;font-variant-numeric:tabular-nums;font-weight:600;font-size:12px;color:var(--muted)}
  .mov-bar-row .mval strong{color:var(--ink)}

  table.ford{width:100%;border-collapse:collapse;font-size:12.5px}
  table.ford thead th{background:var(--ford-2);color:#fff;padding:7px 8px;text-align:center;font-weight:600;font-size:11px;letter-spacing:.3px;text-transform:uppercase}
  table.ford thead th.left{text-align:left}
  table.ford thead th.sortable{cursor:pointer;user-select:none}
  table.ford thead th.sortable:hover{background:#3b5fa8}
  table.ford thead th.sortable.asc::after{content:' ▲';opacity:.7}
  table.ford thead th.sortable.desc::after{content:' ▼';opacity:.7}
  table.ford tbody td{padding:6px 8px;border-bottom:1px solid #eef0f3;text-align:center;font-variant-numeric:tabular-nums}
  table.ford tbody td.left{text-align:left;font-weight:600}
  table.ford tbody tr:nth-child(even){background:#fafbfd}
  table.ford tbody tr:hover{background:#eef4fb;cursor:default}
  table.ford tbody tr.clickable{cursor:pointer}
  table.ford tbody tr.highlighted{background:#fff3d6 !important}
  table.ford tr.total{background:#e8edf3 !important;font-weight:700}
  table.ford tr.total td{border-top:2px solid var(--ford-2)}
  .cumpl{padding:4px 6px;border-radius:3px;font-weight:700;display:inline-block;min-width:42px}
  .cumpl.green{background:var(--green-bg);color:var(--green-tx)}
  .cumpl.yellow{background:var(--yellow-bg);color:var(--yellow-tx)}
  .cumpl.red{background:var(--red-bg);color:var(--red-tx)}
  .cumpl.grey{background:var(--grey-bg);color:var(--grey-tx)}
  .heat td.cell{padding:7px 6px;font-size:11px;font-weight:700}
  .heat td.cell.green{background:var(--green-bg);color:var(--green-tx)}
  .heat td.cell.yellow{background:var(--yellow-bg);color:var(--yellow-tx)}
  .heat td.cell.red{background:var(--red-bg);color:var(--red-tx)}
  .heat td.cell.grey{background:var(--grey-bg);color:var(--grey-tx)}
  .heat td.cell.dash{color:var(--grey-tx)}
  .legend{font-size:11px;color:var(--muted);margin-top:6px}

  .action-box{background:#fffde7;border-left:4px solid var(--yellow);padding:14px 18px;margin-bottom:14px;border-radius:0 10px 10px 0}
  .action-box .h{font-weight:700;color:#f57f17;font-size:13px;margin-bottom:8px}
  .action-box p{margin:10px 0 4px;font-weight:700;font-size:12px}
  .action-box ul{margin:0 0 6px;padding-left:18px;font-size:12.5px;list-style:none}
  .action-box li{margin-bottom:2px}

  .movements-list{margin:0;padding-left:18px;font-size:12.5px;column-count:2;column-gap:24px}
  @media (max-width:700px){.movements-list{column-count:1}}
  .movements-list li{break-inside:avoid;margin-bottom:3px}

  .ford-subgrid{display:grid;grid-template-columns:1.2fr 1fr;gap:14px}
  @media (max-width:1000px){.ford-subgrid{grid-template-columns:1fr}}

  .pill{display:inline-block;padding:2px 8px;border-radius:999px;font-size:10px;font-weight:700;letter-spacing:.3px;text-transform:uppercase;margin-left:6px}
  .pill.active-filter{background:#ffe4b3;color:#8a4a00}

  /* Password gate */
  .pw-gate{max-width:420px;margin:60px auto;background:#fff;border:1px solid #e5e7eb;border-radius:14px;padding:30px 28px;box-shadow:0 4px 20px rgba(0,0,0,.06);text-align:center}
  .pw-gate .icon{font-size:42px;margin-bottom:12px}
  .pw-gate h2{margin:0 0 6px;color:var(--ford);font-size:18px}
  .pw-gate p{margin:0 0 18px;color:var(--muted);font-size:13px}
  .pw-gate input{width:100%;padding:11px 14px;border:1px solid #d1d5db;border-radius:8px;font:inherit;font-size:14px;margin-bottom:10px}
  .pw-gate input:focus{outline:none;border-color:var(--ford-2)}
  .pw-gate button{width:100%;padding:11px;background:var(--ford);color:#fff;border:0;border-radius:8px;font:inherit;font-weight:600;cursor:pointer;font-size:14px}
  .pw-gate button:hover{background:#002659}
  .pw-gate .err{color:var(--neg);font-size:12px;margin-top:8px;min-height:16px;font-weight:600}
  .pw-gate .logout{margin-top:14px;font-size:11px;color:var(--muted)}
  .pw-gate .logout a{color:var(--ford-2);cursor:pointer;text-decoration:underline}

  /* Otros tab content */
  #tab-otros .otros-header{background:linear-gradient(135deg,#003478 0%,#2e5090 100%);color:#fff;padding:18px 22px;border-radius:12px;margin-bottom:16px;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:12px}
  #tab-otros .otros-header h2{margin:0;font-size:18px}
  #tab-otros .otros-header .sub{font-size:12px;opacity:.85;margin-top:2px}
  #tab-otros .otros-header .logout-btn{background:rgba(255,255,255,.15);color:#fff;border:1px solid rgba(255,255,255,.3);padding:6px 12px;border-radius:6px;font:inherit;font-size:11px;cursor:pointer}
  #tab-otros .otros-header .logout-btn:hover{background:rgba(255,255,255,.25)}

  /* Big stat card */
  .stat-hero{display:grid;grid-template-columns:1.2fr 1fr 1fr;gap:14px;margin-bottom:16px}
  @media(max-width:768px){.stat-hero{grid-template-columns:1fr 1fr}}
  .stat-hero .card-big{background:#fff;border:1px solid #e5e7eb;border-radius:12px;padding:16px 20px;box-shadow:0 1px 3px rgba(0,0,0,.04)}
  .stat-hero .card-big .lbl{font-size:10px;text-transform:uppercase;letter-spacing:.7px;color:var(--muted);font-weight:600}
  .stat-hero .card-big .val{font-size:32px;font-weight:800;color:var(--ford);margin-top:4px;line-height:1.05}
  .stat-hero .card-big .val.neg{color:var(--neg)}
  .stat-hero .card-big .val.pos{color:var(--pos)}
  .stat-hero .card-big .val.warn{color:#f57f17}
  .stat-hero .card-big .hint{font-size:12px;color:var(--muted);margin-top:6px}

  table.analysis{width:100%;border-collapse:collapse;font-size:13px}
  table.analysis th{background:var(--ford-2);color:#fff;padding:8px 10px;text-align:center;font-size:11px;letter-spacing:.4px;text-transform:uppercase;font-weight:600}
  table.analysis th:first-child,table.analysis th.left{text-align:left}
  table.analysis td{padding:8px 10px;border-bottom:1px solid #eef0f3;vertical-align:middle;text-align:center}
  table.analysis td:first-child{text-align:left;font-weight:600}
  table.analysis td.left{text-align:left;font-weight:600}
  table.analysis td.num{font-variant-numeric:tabular-nums;font-weight:600}
  table.analysis tr.total{background:#e8edf3;font-weight:700}
  table.analysis tr.total td{border-top:2px solid var(--ford-2)}
  table.analysis .bar-cell{min-width:140px}
  .meta-bar{position:relative;background:#eef1f5;height:18px;border-radius:5px;overflow:hidden;margin-top:3px}
  .meta-bar .fill{position:absolute;top:0;left:0;bottom:0;border-radius:5px;display:flex;align-items:center;justify-content:flex-end;padding:0 6px;font-size:10px;font-weight:700;color:#fff;min-width:24px}
  .meta-bar .fill.green{background:linear-gradient(90deg,#2e7d32,#66bb6a)}
  .meta-bar .fill.yellow{background:linear-gradient(90deg,#f57f17,#ffb74d);color:#fff}
  .meta-bar .fill.red{background:linear-gradient(90deg,#c62828,#ef5350)}
  .meta-bar .marker{position:absolute;top:-2px;bottom:-2px;width:2px;background:#1c2434;z-index:2}

  .insight-card{background:#fff;border:1px solid #e5e7eb;border-radius:12px;padding:14px 18px;margin-bottom:12px;border-left:4px solid var(--ford-2)}
  .insight-card.warn{border-left-color:var(--yellow)}
  .insight-card.bad{border-left-color:var(--neg)}
  .insight-card.good{border-left-color:var(--pos)}
  .insight-card.critical{border-left-color:#c62828;background:#fff5f5}
  .insight-card.info{border-left-color:#1976d2;background:#f3f9ff}

  /* Status pills usado en tabla de inventario */
  .status-pill{display:inline-block;padding:3px 9px;border-radius:999px;font-size:11px;font-weight:700;letter-spacing:.2px;white-space:nowrap}
  .status-pill.red{background:#ffebee;color:#c62828}
  .status-pill.yellow{background:#fff8e1;color:#a36307}
  .status-pill.orange{background:#fff3e0;color:#ef6c00}
  .status-pill.green{background:#e8f5e9;color:#2e7d32}
  .status-pill.blue{background:#e3f2fd;color:#1565c0}

  /* Cards de versiones (cola por versión) */
  .version-cards-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:14px;margin-top:6px}
  .version-card{background:#fff;border:1px solid #e5e7eb;border-radius:10px;padding:14px 16px}
  .version-card .vc-head{display:flex;justify-content:space-between;align-items:baseline;margin-bottom:12px;padding-bottom:8px;border-bottom:1px solid #eef0f3}
  .version-card .vc-head .name{font-weight:700;color:var(--ford-2);font-size:14px}
  .version-card .vc-head .total{font-weight:800;color:var(--ink);font-size:18px;font-variant-numeric:tabular-nums}
  .version-card .vc-head .total-lbl{font-size:10px;color:var(--muted);text-transform:uppercase;letter-spacing:.5px;margin-right:5px}
  .version-card .vc-row{display:grid;grid-template-columns:1fr 38px 30px;gap:8px;align-items:center;margin-bottom:6px;font-size:12px}
  .version-card .vc-row:last-child{margin-bottom:0}
  .version-card .vc-row .label{color:var(--ink);line-height:1.3}
  .version-card .vc-row .count{font-weight:700;text-align:right;font-variant-numeric:tabular-nums}
  .version-card .vc-row .pct{color:var(--muted);font-size:11px;text-align:right;font-variant-numeric:tabular-nums}
  .version-card .vc-bar{grid-column:1/-1;height:4px;background:#eef0f3;border-radius:2px;overflow:hidden;margin-top:2px;margin-bottom:8px}
  .version-card .vc-bar .fill{height:100%;background:linear-gradient(90deg,var(--ford-2),var(--ford));border-radius:2px}
  .version-card .vc-empty{color:var(--muted);font-size:12px;text-align:center;padding:20px}

  /* Stat-hero con 4 columnas — responsive */
  .stat-hero-4{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-bottom:16px}
  @media(max-width:768px){.stat-hero-4{grid-template-columns:1fr 1fr;gap:10px}}
  @media(max-width:480px){.stat-hero-4{grid-template-columns:1fr 1fr;gap:8px}}

  /* KPI grid con N columnas — responsive */
  .kpi-row-4{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}
  .kpi-row-5{display:grid;grid-template-columns:repeat(5,1fr);gap:10px}
  @media(max-width:768px){
    .kpi-row-4,.kpi-row-5{grid-template-columns:repeat(3,1fr);gap:8px}
  }
  @media(max-width:480px){
    .kpi-row-4,.kpi-row-5{grid-template-columns:1fr 1fr;gap:8px}
  }

  /* Inventario responsive */
  @media(max-width:768px){
    #tab-inv .stat-hero{grid-template-columns:1fr 1fr !important}
    #tab-inv .kpi-grid-inv{grid-template-columns:repeat(3,1fr) !important}
    #tab-inv .kpi .num{font-size:20px}
  }
  @media(max-width:480px){
    #tab-inv .kpi-grid-inv{grid-template-columns:repeat(2,1fr) !important}
  }

  /* Conversión responsive — KPI cards y tablas */
  @media(max-width:768px){
    #tab-conv .stat-hero .val{font-size:24px}
    #tab-conv .stat-hero .hint{font-size:11px}
    #tab-conv table.analysis{font-size:11px}
    #tab-conv table.analysis th,#tab-conv table.analysis td{padding:6px 5px}
    #tab-conv h3{font-size:13px}
    #tab-conv h3 .sub{display:block;font-size:11px;margin-top:3px;margin-left:0}
  }
  @media(max-width:480px){
    #tab-conv .stat-hero .val{font-size:20px;line-height:1.1}
    #tab-conv .stat-hero .lbl{font-size:9px}
  }

  /* Otros — heatmap del cruce: celdas más pequeñas en mobile */
  @media(max-width:768px){
    #an-tbl-cruce-heat th,#an-tbl-cruce-heat td{padding:5px 3px !important;min-width:60px !important}
    #an-tbl-cruce-heat td>div:first-child{font-size:14px !important}
    #an-tbl-cruce-heat td>div:nth-child(2){font-size:13px !important}
    #an-tbl-cruce-heat td>div:nth-child(3){font-size:8px !important}
  }
  @media(max-width:480px){
    #an-tbl-cruce-heat th,#an-tbl-cruce-heat td{padding:4px 2px !important;min-width:50px !important}
    #an-tbl-cruce-heat td>div:first-child{font-size:12px !important}
    #an-tbl-cruce-heat td>div:nth-child(2){font-size:11px !important}
    #an-tbl-cruce-heat td>div:nth-child(3){display:none !important}
  }

  /* Tiempo de espera — leyenda más compacta en mobile */
  @media(max-width:768px){
    #tab-otros table.analysis td:has(div[style*="height:16px"]){min-width:120px}
  }

  /* ─────────── MODAL DE DETALLE (tap-to-show en mobile) ─────────── */
  .cell-detail-overlay{
    position:fixed; inset:0; background:rgba(0,0,0,.55); z-index:9999;
    display:flex; align-items:center; justify-content:center; padding:18px;
    animation:fadeIn .15s ease-out;
  }
  @keyframes fadeIn{from{opacity:0}to{opacity:1}}
  .cell-detail-content{
    background:#fff; border-radius:14px; padding:22px 22px 18px;
    max-width:420px; width:100%; max-height:85vh; overflow-y:auto;
    box-shadow:0 12px 40px rgba(0,0,0,.25); position:relative;
  }
  .cell-detail-close{
    position:absolute; top:10px; right:14px; background:none; border:0;
    font-size:26px; line-height:1; color:var(--muted); cursor:pointer;
    padding:0; width:32px; height:32px; border-radius:50%;
  }
  .cell-detail-close:hover{background:#f3f4f6;color:var(--ink)}
  .cell-detail-body{
    font-size:13px; line-height:1.55; color:var(--ink); white-space:pre-wrap;
    word-wrap:break-word; padding-right:28px;
  }
  .cell-detail-body strong{color:var(--ford-2);display:block;margin-bottom:4px}

  /* En mobile, hacemos clickables las celdas con title; cursor pointer hint */
  @media(max-width:768px){
    td[title]{cursor:pointer;-webkit-tap-highlight-color:rgba(0,0,0,.08)}
  }

  /* ─────────── MEJORAS MOBILE GENERALES ─────────── */
  @media(max-width:768px){
    /* Tablas: padding y fuente más compactos */
    table.analysis{font-size:11.5px}
    table.analysis th,table.analysis td{padding:6px 5px}
    table.analysis th{font-size:10px;letter-spacing:.2px}

    /* Indicador visual de scroll horizontal en tablas largas */
    .ford-section .table-wrap-mobile::after{
      content:"← desliza para ver más →"; display:block; text-align:center;
      font-size:10px; color:var(--muted); padding:4px 0 2px; font-style:italic;
    }

    /* Filter-bar — 1 sola columna en mobile pequeño + selects al 100% */
    .filter-bar{padding:10px;gap:8px;grid-template-columns:1fr 1fr !important}
    .filter-bar label{font-size:11px;display:flex;flex-direction:column;min-width:0}
    .filter-bar select{font-size:12px;padding:6px 8px;width:100%;min-width:0;max-width:100%}
    .filter-bar button{font-size:12px;padding:6px 10px}

    /* Cards de versiones más compactas */
    .version-cards-grid{grid-template-columns:1fr}
    .version-card{padding:12px 14px}
    .version-card .vc-head .name{font-size:13px}
    .version-card .vc-head .total{font-size:16px}

    /* Stat-hero card-big más compacta */
    .stat-hero .card-big{padding:12px 14px}
    .stat-hero .card-big .val{font-size:22px}
    .stat-hero .card-big .lbl{font-size:9px;letter-spacing:.4px}
    .stat-hero .card-big .hint{font-size:10px}

    /* H3 sections — título y subtítulo en líneas separadas */
    .ford-section h3{font-size:13px;line-height:1.4}
    .ford-section h3 .sub{display:block;font-size:11px;color:var(--muted);
                          font-weight:400;margin-left:0;margin-top:3px}

    /* Otros header — más compacto */
    #tab-otros .otros-header,#tab-conv .otros-header,#tab-inv .otros-header{
      padding:14px 16px;gap:8px;
    }
    #tab-otros .otros-header h2,#tab-conv .otros-header h2,#tab-inv .otros-header h2{font-size:15px}
    #tab-otros .otros-header .sub,#tab-conv .otros-header .sub,#tab-inv .otros-header .sub{font-size:11px}

    /* Tabla detalle del cruce: sticky primera columna para scroll horizontal */
    #an-tbl-cruce th:first-child,#an-tbl-cruce td:first-child,
    #an-tbl-cruce-heat th:first-child,#an-tbl-cruce-heat td:first-child{
      position:sticky;left:0;background:#fff;z-index:2;
    }
    #an-tbl-cruce-heat th:first-child{background:var(--ford-2);color:#fff}
    #inv-tbl-cob th:first-child,#inv-tbl-cob td:first-child,
    #inv-tbl-cola-agencia th:first-child,#inv-tbl-cola-agencia td:first-child,
    #inv-tbl-matrix th:first-child,#inv-tbl-matrix td:first-child{
      position:sticky;left:0;background:#fff;z-index:2;
    }
    #inv-tbl-cob th:first-child,#inv-tbl-cola-agencia th:first-child,
    #inv-tbl-matrix th:first-child{background:var(--ford-2);color:#fff}
  }
  @media(max-width:480px){
    table.analysis{font-size:11px}
    table.analysis th,table.analysis td{padding:5px 4px}
    .stat-hero .card-big{padding:10px 12px}
    .stat-hero .card-big .val{font-size:18px}
    /* Filtros: 1 sola columna en phones */
    .filter-bar{grid-template-columns:1fr !important;padding:8px}
    .filter-bar select{font-size:13px;padding:7px 8px}
    /* Headers de pestañas más pequeñas */
    header.topbar{padding:12px 14px}
    header.topbar h1{font-size:16px}
    main{padding:10px 8px 24px}
    /* Pestañas: navegación más compacta */
    nav.tabs{padding:8px 8px 0}
    .tab-btn{padding:6px 10px;font-size:11px}
  }
  .insight-card h4{margin:0 0 6px;font-size:13px;color:var(--ford-2)}
  .insight-card p{margin:0;font-size:13px;color:var(--ink);line-height:1.5}
  .insight-card .data{font-weight:700;color:var(--ink);font-variant-numeric:tabular-nums}

  /* ============================ RESPONSIVE ============================ */
  @media (max-width:768px){
    body{font-size:13px}
    header.topbar{padding:14px 16px}
    header.topbar h1{font-size:17px}
    header.topbar .sub{font-size:11px}

    nav.tabs{padding:10px 12px 0;overflow-x:auto;-webkit-overflow-scrolling:touch;scrollbar-width:thin}
    nav.tabs::-webkit-scrollbar{height:4px}
    .tab-btn{padding:7px 12px;font-size:12px;white-space:nowrap;flex-shrink:0}

    main{padding:14px 12px 32px}

    .filter-bar{padding:10px;gap:8px;margin-bottom:12px;grid-template-columns:repeat(auto-fit,minmax(140px,1fr))}
    .filter-bar-brand{grid-template-columns:1fr !important;gap:10px}
    .filter-bar-brand>div{flex-wrap:wrap;width:100%;gap:8px}
    .filter-bar-brand>div>label{flex:1 1 calc(50% - 4px);min-width:0}
    .filter-bar-brand>div>label select{min-width:0 !important;width:100%}
    .filter-bar-brand>div>.reset{flex:1 1 100%}
    .filter-bar select,.filter-bar .reset{padding:7px 10px;font-size:13px}
    .filter-bar label{font-size:10px}

    .kpis{gap:10px;margin-bottom:12px;grid-template-columns:1fr 1fr}
    .kpi{padding:11px 13px}
    .kpi .num{font-size:22px}
    .kpi .label{font-size:10px}
    .kpi .hint{font-size:11px}

    /* Hero stacks */
    .ford-hero{grid-template-columns:1fr;padding:14px;gap:14px}
    .ford-hero .gauge-canvas{width:200px;height:200px}
    .ford-hero .gauge-center .big{font-size:36px}
    .ford-hero .gauge-center .mid{font-size:11px}
    .ford-hero .hero-side{gap:10px}
    .hero-stat{padding:10px 12px}
    .hero-stat .val{font-size:18px}
    .hero-stat .lbl{font-size:9px}
    .hero-stat .delta{font-size:10px}
    .hero-progress{padding:10px 12px}
    .hero-progress .head{font-size:10px}
    .hero-progress .head .v{font-size:11px}

    /* Sections más compactas */
    .ford-section{padding:12px 14px;margin-bottom:12px}
    .ford-section h3{font-size:13px}
    .ford-section h3 .sub{font-size:10px;display:block;margin-left:0;margin-top:2px;font-weight:400}

    /* Charts más bajos */
    .card{padding:12px 14px;margin-bottom:12px}
    .card h3{font-size:13px}
    .card h3 .sub{font-size:10px;display:block;margin-left:0;margin-top:2px}
    .card .chart-wrap{height:220px}
    .card.tall .chart-wrap{height:280px}

    /* Stack subgrids */
    .ford-subgrid{grid-template-columns:1fr;gap:12px}
    .donut-with-table{grid-template-columns:1fr;gap:12px}

    /* Movements: stack mval */
    .mov-bar-row{grid-template-columns:80px 1fr;gap:6px;font-size:12px;padding:6px 0}
    .mov-bar-row .mval{grid-column:1/-1;text-align:right;font-size:11px;margin-top:-2px}

    /* Tablas más densas */
    table.ford,table.comp{font-size:11px}
    table.ford td,table.ford th,table.comp td,table.comp th{padding:5px 6px}
    table.ford thead th{font-size:10px;padding:6px 5px}
    .heat td.cell{padding:5px 4px;font-size:10px}
    .heat td.cell .ct{font-size:8px}

    /* Proyección por modelo/agencia: ocultar Δ (col 4) y Meta (col 5) en mobile */
    #ff-proj-model th:nth-child(4),#ff-proj-model td:nth-child(4),
    #ff-proj-model th:nth-child(5),#ff-proj-model td:nth-child(5),
    #ff-proj-agency th:nth-child(4),#ff-proj-agency td:nth-child(4),
    #ff-proj-agency th:nth-child(5),#ff-proj-agency td:nth-child(5),
    #br-proj-model th:nth-child(4),#br-proj-model td:nth-child(4),
    #br-proj-model th:nth-child(5),#br-proj-model td:nth-child(5),
    #br-proj-agency th:nth-child(4),#br-proj-agency td:nth-child(4),
    #br-proj-agency th:nth-child(5),#br-proj-agency td:nth-child(5){display:none}

    /* Filter summary */
    .ford-filter-summary{font-size:11px}
    .ford-filter-summary .chip{padding:2px 8px;font-size:10px}

    /* Evolución cards */
    .ev-grid{grid-template-columns:1fr 1fr;gap:10px}
    .ev-card{padding:8px 10px}
    .ev-name{font-size:12px}
    .ev-badge{font-size:10px;padding:1px 6px}
    .ev-spark{height:38px}
    .ev-foot{font-size:10px}
    .ev-mode-btn,.ev-norm-btn{padding:5px 8px;font-size:11px}

    /* Risk row stacks */
    .risk-row{flex-wrap:wrap;font-size:11px;gap:6px}
    .risk-row .rname{min-width:100%;font-size:12px}
    .risk-row .rbar{min-width:0;flex:1}
    .risk-row .rneed{min-width:auto;font-size:11px}

    /* Zoom dashboard sub-grid stacks 2 */
    .zoom-sub-grid{grid-template-columns:1fr 1fr}

    .footer-note{font-size:10px;padding:0 6px}
    .pill{font-size:9px}
    .legend{font-size:10px}

    /* Action box */
    .action-box{padding:12px 14px}
    .action-box .h{font-size:12px}
    .action-box p{font-size:11px}
    .action-box ul{font-size:11px}
  }

  @media (max-width:480px){
    /* Phones muy pequeños */
    header.topbar{padding:12px 14px}
    header.topbar h1{font-size:16px}
    main{padding:12px 10px 28px}

    .ford-hero{padding:14px 12px}
    .ford-hero .gauge-canvas{width:170px;height:170px}
    .ford-hero .gauge-center .big{font-size:30px}
    .ford-hero .hero-side{grid-template-columns:1fr}

    .filter-bar{grid-template-columns:1fr 1fr}
    .kpis{grid-template-columns:1fr 1fr}
    .kpi .num{font-size:20px}

    .ev-grid{grid-template-columns:1fr}
    .zoom-sub-grid{grid-template-columns:1fr}

    .card .chart-wrap{height:200px}
    .card.tall .chart-wrap{height:240px}
    .ford-section h3{font-size:12px}
  }
</style>
</head>
<body>

<header class="topbar">
  <h1>Dashboard de Tráfico - Orgu</h1>
  <div class="sub" id="topbar-sub">Marzo 2026 (cierre) vs Abril 2026 (cierre 30/04)</div>
</header>

<nav class="tabs" role="tablist">
  <button class="tab-btn active" data-tab="ford">T - Reporte Ford Mensual</button>
  <button class="tab-btn" data-tab="brand">T - Reporte Marcas Mensual</button>
  <button class="tab-btn" data-tab="comp">Comparativo de Tráfico</button>
  <button class="tab-btn" data-tab="otros">Análisis General de Tráfico</button>
  <button class="tab-btn" data-tab="conv">Conversión</button>
  <button class="tab-btn" data-tab="inv">📦 Inventario Orgu</button>
  <button class="tab-btn" data-tab="xiy">💰 Inversión Digital</button>
  <button class="tab-btn" data-tab="comp-imp">🔒 Inventario Competencia</button>
  <button class="tab-btn" data-tab="embudo">🫙 Embudo</button>
  <button class="tab-btn" data-tab="dash">Dashboard</button>
</nav>

<main>

  <!-- ======================= TAB DASHBOARD ======================= -->
  <section id="tab-dash" class="tab-panel">
    <div class="filter-bar">
      <label>Marca<select id="f-marca"><option value="">Todas</option></select></label>
      <label>Modelo<select id="f-modelo"><option value="">Todos</option></select></label>
      <label>Agencia<select id="f-agencia"><option value="">Todas</option></select></label>
      <button class="reset" id="btn-reset" type="button">↺ Limpiar filtros</button>
    </div>

    <div class="kpis">
      <div class="kpi"><div class="label">Marzo (cierre)</div><div class="num" id="kpi-marzo">—</div><div class="hint" id="kpi-marzo-hint"></div></div>
      <div class="kpi accent"><div class="label">Abril (cierre 30/04)</div><div class="num" id="kpi-abril">—</div><div class="hint" id="kpi-abril-hint"></div></div>
      <div class="kpi"><div class="label">Proyección Abril</div><div class="num" id="kpi-proj">—</div><div class="hint" id="kpi-proj-hint"></div></div>
      <div class="kpi"><div class="label">Meta mensual (Ford)</div><div class="num" id="kpi-meta">313</div><div class="hint" id="kpi-meta-hint">Abril · agencias Ford</div></div>
    </div>

    <div class="card">
      <h3>Comparativo por agencia <span class="sub">Marzo cierre vs Abril corte — barras proporcionales</span></h3>
      <div style="overflow-x:auto">
      <table class="comp" id="tbl-agencias">
        <thead>
          <tr><th>Agencia</th><th class="num">Marzo</th><th class="num">Abril</th><th class="num">Δ</th><th>Avance visual (Marzo vs Abril)</th></tr>
        </thead>
        <tbody></tbody>
      </table>
      </div>
    </div>

    <div class="grid-2">
      <div class="card tall"><h3>Distribución por canal <span class="sub">Abril</span></h3><div class="chart-wrap"><canvas id="chart-canales"></canvas></div></div>
      <div class="card tall"><h3>Funnel de conversión <span class="sub">Abril</span></h3><div class="funnel-wrap" id="funnel"></div>
        <div style="margin-top:12px;font-size:12px;color:var(--muted)"><strong>Tasa de cierre:</strong> <span id="funnel-rate">—</span> · <strong>Entrega/Cotización:</strong> <span id="funnel-delivery">—</span></div>
      </div>
    </div>

    <div class="grid-2">
      <div class="card tall"><h3>Tendencia acumulada <span class="sub">día a día — Abril vs Marzo</span></h3><div class="chart-wrap"><canvas id="chart-trend"></canvas></div></div>
      <div class="card tall"><h3>Top modelos <span class="sub">Abril</span></h3><div class="chart-wrap"><canvas id="chart-modelos"></canvas></div></div>
    </div>

    <div class="card zoom-card">
      <h3>Zoom por agencia <span class="sub">Selecciona una agencia para ver su corte: canal, asesor, campaña, modelo</span></h3>
      <div style="display:flex;gap:10px;align-items:center;margin-bottom:12px;flex-wrap:wrap">
        <label style="font-size:12px;color:var(--muted);font-weight:600;text-transform:uppercase;letter-spacing:.6px">Agencia
          <select id="zoom-agencia" style="margin-left:8px;padding:7px 10px;border:1px solid #d1d5db;border-radius:8px;font:inherit;min-width:160px"></select>
        </label>
        <span class="tag" id="zoom-badge">—</span>
      </div>
      <div class="zoom-sub-grid">
        <div class="mini"><h4>Por canal</h4><ul id="zoom-canal"></ul></div>
        <div class="mini"><h4>Top asesores</h4><ul id="zoom-asesor"></ul></div>
        <div class="mini"><h4>Top campañas</h4><ul id="zoom-campana"></ul></div>
        <div class="mini"><h4>Por modelo</h4><ul id="zoom-modelo"></ul></div>
      </div>
      <div style="margin-top:12px;font-size:12px;color:var(--muted)">Funnel agencia: <span id="zoom-funnel"></span></div>
    </div>

    <div class="footer-note">Fuente: BD Marzo (cierre 31/03) y BD Abril (cierre 30/04). Datos agregados sin PII. · Reporte oficial Ford en la pestaña <strong>Reporte Ford</strong>.</div>
  </section>

  <!-- ======================= TAB FORD ======================= -->
  <section id="tab-ford" class="tab-panel active">

    <!-- FILTROS FORD -->
    <div class="filter-bar">
      <label>Mes<select id="ff-month"></select></label>
      <label>Zona<select id="ff-zona"><option value="">Todas</option></select></label>
      <label>Agencia<select id="ff-agencia"><option value="">Todas</option></select></label>
      <label>Modelo<select id="ff-modelo"><option value="">Todos</option></select></label>
      <button class="reset" id="ff-reset" type="button">↺ Limpiar filtros Ford</button>
    </div>

    <!-- ACTIVE FILTER CHIPS -->
    <div class="ford-filter-summary" id="ff-filter-summary"></div>

    <!-- HERO: gauge + stats + progress bar -->
    <div class="ford-hero">
      <div class="gauge-wrap">
        <div class="gauge-canvas">
          <canvas id="ff-gauge"></canvas>
          <div class="gauge-center">
            <div class="big" id="ff-gauge-value">—</div>
            <div class="mid">Cumplimiento<br>Proyectado</div>
            <div class="tag" id="ff-gauge-tag">—</div>
          </div>
        </div>
      </div>
      <div class="hero-side">
        <div class="hero-stat" id="hs-total"><div class="lbl">Tráfico actual</div><div class="val" id="hs-total-v">—</div><div class="delta" id="hs-total-d"></div></div>
        <div class="hero-stat" id="hs-delta"><div class="lbl">Δ vs corte anterior</div><div class="val" id="hs-delta-v">—</div><div class="delta" id="hs-delta-d"></div></div>
        <div class="hero-stat" id="hs-vel"><div class="lbl">Velocidad</div><div class="val" id="hs-vel-v">—</div><div class="delta" id="hs-vel-d">registros / día</div></div>
        <div class="hero-stat" id="hs-proj"><div class="lbl">Proyección cierre</div><div class="val" id="hs-proj-v">—</div><div class="delta" id="hs-proj-d"></div></div>
        <div class="hero-progress">
          <div class="head">
            <span>Avance del mes</span>
            <span class="v" id="hm-summary">—</span>
          </div>
          <div class="track">
            <div id="hm-fill" style="position:absolute;top:0;left:0;bottom:0;background:linear-gradient(90deg,#003478,#5c84d6);border-radius:7px;width:0;transition:width .5s ease"></div>
          </div>
          <div class="labels">
            <span>Día 1</span>
            <span id="hm-labels">Día —</span>
          </div>
        </div>
        <div class="hero-progress">
          <div class="head">
            <span>Proyección vs Meta</span>
            <span class="v" id="hp-summary">—</span>
          </div>
          <div class="track" id="hp-track">
            <div class="fill-actual" id="hp-actual"></div>
            <div class="fill-proj" id="hp-proj"></div>
            <div class="fill-meta" id="hp-meta"></div>
          </div>
          <div class="labels">
            <span>0</span>
            <span id="hp-labels"></span>
          </div>
        </div>
      </div>
    </div>

    <!-- AVANCE DÍA A DÍA -->
    <div class="ford-section">
      <h3>📈 Avance día a día <span class="sub">acumulado real vs ritmo ideal hacia meta · barra =  diario</span></h3>
      <div style="position:relative;height:300px"><canvas id="ff-chart-pace"></canvas></div>
      <div id="ff-pace-summary" style="margin-top:10px;font-size:12.5px;color:var(--muted);text-align:center"></div>
    </div>

    <!-- MOVIMIENTOS — chart de impacto -->
    <div class="ford-section">
      <h3>📊 Movimientos vs corte anterior <span class="sub" id="ff-mov-sub">17/04 → 20/04 · magnitud del cambio por modelo</span></h3>
      <div id="ff-movements"></div>
    </div>


    <div class="ford-subgrid">
      <!-- COMPARATIVO POR ZONA con donut -->
      <div class="ford-section">
        <h3>🗺️ Comparativo por zona <span class="sub">Ford · click fila para filtrar</span></h3>
        <div class="donut-with-table">
          <div style="position:relative;height:220px"><canvas id="ff-chart-zone"></canvas></div>
          <table class="ford" id="ff-zonas" style="font-size:11.5px">
            <thead><tr>
              <th class="left">Zona</th>
              <th>Anterior</th><th>Actual</th><th>Δ</th><th>%</th>
            </tr></thead>
            <tbody></tbody>
          </table>
        </div>
      </div>

      <!-- RANKING POR MODELO -->
      <div class="ford-section">
        <h3>🏆 Ranking por modelo <span class="sub">click fila para filtrar</span></h3>
        <table class="ford" id="ff-ranking">
          <thead><tr>
            <th>#</th><th class="left sortable" data-k="model">Modelo</th>
            <th class="sortable" data-k="curr">Actual</th>
            <th class="sortable" data-k="pct">% Total</th>
            <th class="sortable" data-k="delta">Δ</th>
          </tr></thead>
          <tbody></tbody>
        </table>
      </div>
    </div>

    <!-- PROYECCIÓN POR MODELO -->
    <div class="ford-section">
      <h3>🔮 Proyección de cierre — por modelo <span class="sub">click fila para filtrar</span></h3>
      <table class="ford" id="ff-proj-model">
        <thead><tr>
          <th class="left sortable" data-k="model">Modelo</th>
          <th class="sortable" data-k="prev">Anterior</th>
          <th class="sortable" data-k="curr">Actual</th>
          <th class="sortable" data-k="delta">Δ</th>
          <th class="sortable" data-k="meta">Meta</th>
          <th class="sortable" data-k="proj">Proyección</th>
          <th class="sortable" data-k="cumpl">Cumpl.Proy.</th>
        </tr></thead>
        <tbody></tbody>
      </table>
    </div>

    <!-- DISTRIBUCIÓN POR CANAL -->
    <div class="ford-section">
      <h3>📡 Distribución por canal <span class="sub">Tráfico + share · respeta filtros activos</span></h3>
      <div style="position:relative;height:240px"><canvas id="ff-chart-channels"></canvas></div>
    </div>

    <!-- PROYECCIÓN POR AGENCIA -->
    <div class="ford-section">
      <h3>🔮 Proyección de cierre — por agencia <span class="sub">click fila para filtrar</span></h3>
      <table class="ford" id="ff-proj-agency">
        <thead><tr>
          <th class="left sortable" data-k="agency">Agencia</th>
          <th class="sortable" data-k="prev">Anterior</th>
          <th class="sortable" data-k="curr">Actual</th>
          <th class="sortable" data-k="delta">Δ</th>
          <th class="sortable" data-k="meta">Meta</th>
          <th class="sortable" data-k="proj">Proyección</th>
          <th class="sortable" data-k="cumpl">Cumpl.Proy.</th>
        </tr></thead>
        <tbody></tbody>
      </table>
    </div>

    <!-- HEAT MAP MODELO × AGENCIA -->
    <div class="ford-section">
      <h3>⚠ Cumplimiento al ritmo del día — modelo × agencia <span class="sub">% del día · pequeño: avance del mes (cnt / meta total) · click celda = filtro</span></h3>
      <div style="overflow-x:auto">
      <table class="ford heat" id="ff-heatmap">
        <thead id="ff-heat-head"></thead>
        <tbody></tbody>
      </table>
      </div>
      <div class="legend">🟢 ≥100% al ritmo &nbsp;|&nbsp; 🟡 ≥70% &nbsp;|&nbsp; 🔴 &lt;70% &nbsp;|&nbsp; — sin tráfico ni meta &nbsp;|&nbsp; N/A sin meta, con tráfico. <em>Hover para ver ambos valores.</em></div>
    </div>

    <!-- ACCIÓN INMEDIATA -->
    <div class="action-box" id="ff-action">
      <div class="h">⚡ Acción inmediata</div>
      <p>Modelos en riesgo (proyección &lt;100%):</p>
      <ul id="ff-risk-models"></ul>
      <p>Agencias en riesgo:</p>
      <ul id="ff-risk-agencies"></ul>
      <p style="margin-top:8px">Canal dominante: <span id="ff-channel"></span></p>
    </div>

    <div class="footer-note">Reporte Ford — lógica replicada de <code>ford_traffic_generator.py</code>: MARCA=FORD, dedupe por CEDULA, canales válidos (Showroom/Hubspot/Ferias/Llamada In), mapeo SUCURSAL×Agencia oficial.</div>
  </section>

  <!-- ======================= TAB BRAND (otras marcas) ======================= -->
  <section id="tab-brand" class="tab-panel">

    <!-- Brand selector (obligatorio) -->
    <div class="filter-bar filter-bar-brand">
      <label style="font-size:12px;text-transform:uppercase;letter-spacing:.6px;color:var(--muted);font-weight:600">
        Marca <span style="color:#c62828">*</span>
        <select id="br-marca" style="margin-top:4px;padding:10px 12px;border:1px solid #d1d5db;border-radius:8px;font:inherit;font-size:14px;font-weight:600;background:#fff">
          <option value="">— Selecciona una marca para ver el reporte —</option>
        </select>
      </label>
      <div style="display:flex;gap:8px;align-items:end;flex-wrap:wrap">
        <label style="font-size:11px;text-transform:uppercase;letter-spacing:.6px;color:var(--muted);font-weight:600">
          Mes<select id="br-month" style="margin-top:4px;padding:8px 10px;border:1px solid #d1d5db;border-radius:8px;font:inherit;min-width:130px"></select>
        </label>
        <label style="font-size:11px;text-transform:uppercase;letter-spacing:.6px;color:var(--muted);font-weight:600">
          Agencia<select id="br-agencia" style="margin-top:4px;padding:8px 10px;border:1px solid #d1d5db;border-radius:8px;font:inherit;min-width:140px"><option value="">Todas</option></select>
        </label>
        <label style="font-size:11px;text-transform:uppercase;letter-spacing:.6px;color:var(--muted);font-weight:600">
          Modelo<select id="br-modelo" style="margin-top:4px;padding:8px 10px;border:1px solid #d1d5db;border-radius:8px;font:inherit;min-width:140px"><option value="">Todos</option></select>
        </label>
        <button class="reset" id="br-reset" type="button">↺ Limpiar</button>
      </div>
    </div>

    <!-- Empty state (antes de elegir marca) -->
    <div id="br-empty" class="ford-section" style="text-align:center;padding:60px 20px">
      <div style="font-size:48px;margin-bottom:12px;opacity:.5">🏷️</div>
      <div style="font-size:16px;font-weight:700;color:var(--ford-2);margin-bottom:6px">Selecciona una marca para comenzar</div>
      <div style="font-size:13px;color:var(--muted)">DongFeng · Chery · Mazda · RAM</div>
    </div>

    <!-- Content (se muestra al elegir marca) -->
    <div id="br-content" style="display:none">

      <div class="ford-filter-summary" id="br-filter-summary"></div>

      <!-- HERO -->
      <div class="ford-hero">
        <div class="gauge-wrap">
          <div class="gauge-canvas">
            <canvas id="br-gauge"></canvas>
            <div class="gauge-center">
              <div class="big" id="br-gauge-value">—</div>
              <div class="mid">Cumplimiento<br>Proyectado</div>
              <div class="tag" id="br-gauge-tag">—</div>
            </div>
          </div>
        </div>
        <div class="hero-side">
          <div class="hero-stat"><div class="lbl">Tráfico actual</div><div class="val" id="br-hs-total">—</div><div class="delta" id="br-hs-total-d"></div></div>
          <div class="hero-stat" id="br-hs-delta"><div class="lbl">Δ vs corte anterior</div><div class="val" id="br-hs-delta-v">—</div><div class="delta" id="br-hs-delta-d"></div></div>
          <div class="hero-stat"><div class="lbl">Velocidad</div><div class="val" id="br-hs-vel">—</div><div class="delta">registros / día</div></div>
          <div class="hero-stat"><div class="lbl">Proyección cierre</div><div class="val" id="br-hs-proj">—</div><div class="delta" id="br-hs-proj-d"></div></div>
          <div class="hero-progress">
            <div class="head"><span>Avance del mes</span><span class="v" id="br-hm-summary">—</span></div>
            <div class="track">
              <div id="br-hm-fill" style="position:absolute;top:0;left:0;bottom:0;background:linear-gradient(90deg,#003478,#5c84d6);border-radius:7px;width:0;transition:width .5s ease"></div>
            </div>
            <div class="labels"><span>Día 1</span><span id="br-hm-labels">Día —</span></div>
          </div>
          <div class="hero-progress">
            <div class="head"><span>Proyección vs Meta</span><span class="v" id="br-hp-summary">—</span></div>
            <div class="track">
              <div class="fill-actual" id="br-hp-actual"></div>
              <div class="fill-proj" id="br-hp-proj"></div>
              <div class="fill-meta" id="br-hp-meta"></div>
            </div>
            <div class="labels"><span>0</span><span id="br-hp-labels"></span></div>
          </div>
        </div>
      </div>

      <!-- AVANCE DÍA A DÍA -->
      <div class="ford-section">
        <h3>📈 Avance día a día <span class="sub">acumulado real vs ritmo ideal hacia meta · barra = diario</span></h3>
        <div style="position:relative;height:300px"><canvas id="br-chart-pace"></canvas></div>
        <div id="br-pace-summary" style="margin-top:10px;font-size:12.5px;color:var(--muted);text-align:center"></div>
      </div>

      <!-- MOVIMIENTOS -->
      <div class="ford-section">
        <h3>📊 Movimientos vs corte anterior <span class="sub" id="br-mov-sub">17/04 → 20/04</span></h3>
        <div id="br-movements"></div>
      </div>

      <!-- DISTRIBUCIÓN POR AGENCIA (donut) + RANKING POR MODELO -->
      <div class="ford-subgrid">
        <div class="ford-section">
          <h3>🏢 Distribución por agencia <span class="sub">click fila / segmento para filtrar</span></h3>
          <div class="donut-with-table">
            <div style="position:relative;height:200px"><canvas id="br-chart-agency"></canvas></div>
            <table class="ford" id="br-agencies" style="font-size:11.5px">
              <thead><tr><th class="left">Agencia</th><th>Anterior</th><th>Actual</th><th>Δ</th><th>%</th></tr></thead>
              <tbody></tbody>
            </table>
          </div>
        </div>
        <div class="ford-section">
          <h3>🏆 Ranking por modelo <span class="sub">click fila para filtrar</span></h3>
          <table class="ford" id="br-ranking">
            <thead><tr><th>#</th><th class="left">Modelo</th><th>Actual</th><th>% Total</th><th>Δ</th></tr></thead>
            <tbody></tbody>
          </table>
        </div>
      </div>

      <!-- PROYECCIÓN POR MODELO -->
      <div class="ford-section">
        <h3>🔮 Proyección de cierre — por modelo <span class="sub">click fila para filtrar</span></h3>
        <table class="ford" id="br-proj-model">
          <thead><tr>
            <th class="left">Modelo</th>
            <th>Anterior</th><th>Actual</th><th>Δ</th>
            <th>Meta</th><th>Proyección</th><th>Cumpl.Proy.</th>
          </tr></thead>
          <tbody></tbody>
        </table>
      </div>

      <!-- DISTRIBUCIÓN POR CANAL -->
      <div class="ford-section">
        <h3>📡 Distribución por canal <span class="sub">Tráfico + share · respeta filtros activos</span></h3>
        <div style="position:relative;height:240px"><canvas id="br-chart-channels"></canvas></div>
      </div>

      <!-- PROYECCIÓN POR AGENCIA -->
      <div class="ford-section">
        <h3>🔮 Proyección de cierre — por agencia <span class="sub">click fila para filtrar</span></h3>
        <table class="ford" id="br-proj-agency">
          <thead><tr>
            <th class="left">Agencia</th>
            <th>Anterior</th><th>Actual</th><th>Δ</th>
            <th>Meta</th><th>Proyección</th><th>Cumpl.Proy.</th>
          </tr></thead>
          <tbody></tbody>
        </table>
      </div>

      <!-- HEAT MAP MODELO × AGENCIA -->
      <div class="ford-section">
        <h3>⚠ Cumplimiento al ritmo del día — modelo × agencia <span class="sub">% del día · pequeño: avance del mes (cnt / meta total) · click celda = filtro</span></h3>
        <div style="overflow-x:auto">
        <table class="ford heat" id="br-heatmap">
          <thead id="br-heat-head"></thead>
          <tbody></tbody>
        </table>
        </div>
        <div class="legend">🟢 ≥100% al ritmo &nbsp;|&nbsp; 🟡 ≥70% &nbsp;|&nbsp; 🔴 &lt;70% &nbsp;|&nbsp; — sin tráfico ni meta &nbsp;|&nbsp; N/A sin meta, con tráfico. <em>Hover para ver ambos valores.</em></div>
      </div>

      <!-- ACCIÓN INMEDIATA -->
      <div class="action-box" id="br-action">
        <div class="h">⚡ Acción inmediata</div>
        <p>Modelos en riesgo (proyección &lt;100%):</p>
        <ul id="br-risk-models"></ul>
        <p>Agencias en riesgo:</p>
        <ul id="br-risk-agencies"></ul>
        <p style="margin-top:8px">Canal dominante: <span id="br-channel"></span></p>
      </div>

      <div class="footer-note">Fuente: <code>BD_ABR_20_04_26.xlsx</code> (MARCA={marca seleccionada}, dedupe CEDULA, canales válidos). Metas desde <code>ABR_NUEVO_AI_MARCAS.xlsx</code> → sección "PRESUPUESTO DE TRÁFICO".</div>
    </div>
  </section>

  <!-- ======================= TAB COMPARATIVO ======================= -->
  <section id="tab-comp" class="tab-panel">

    <div class="filter-bar">
      <label>Mes A (anterior)<select id="cp-monthA"></select></label>
      <label>Mes B (posterior)<select id="cp-monthB"></select></label>
      <label>Marca<select id="cp-marca"></select></label>
      <label>Agencia<select id="cp-agencia"><option value="">Todas</option></select></label>
      <label>Modelo<select id="cp-modelo"><option value="">Todos</option></select></label>
      <button class="reset" id="cp-reset" type="button">↺ Limpiar filtros</button>
    </div>

    <div class="ford-filter-summary" id="cp-filter-summary"></div>

    <!-- EVOLUCIÓN MULTI-MES -->
    <div class="ford-section">
      <h3>📊 Evolución multi-mes <span class="sub">trayectoria a través de todos los meses · Mes A/B no aplica · respeta Marca/Agencia/Modelo</span></h3>
      <div style="display:flex;gap:14px;align-items:center;flex-wrap:wrap;margin-bottom:10px;font-size:12px">
        <div style="display:flex;gap:4px;background:#eef1f5;padding:3px;border-radius:8px">
          <button class="ev-mode-btn" data-mode="total" style="padding:5px 12px;border:0;background:#003478;color:#fff;border-radius:6px;font:inherit;font-weight:600;cursor:pointer">Total</button>
          <button class="ev-mode-btn" data-mode="model" style="padding:5px 12px;border:0;background:transparent;color:var(--ink);border-radius:6px;font:inherit;font-weight:600;cursor:pointer">Por modelo</button>
          <button class="ev-mode-btn" data-mode="agency" style="padding:5px 12px;border:0;background:transparent;color:var(--ink);border-radius:6px;font:inherit;font-weight:600;cursor:pointer">Por agencia</button>
        </div>
        <div style="display:flex;gap:4px;background:#eef1f5;padding:3px;border-radius:8px">
          <button class="ev-norm-btn" data-norm="abs" style="padding:5px 12px;border:0;background:#003478;color:#fff;border-radius:6px;font:inherit;font-weight:600;cursor:pointer">Absoluto</button>
          <button class="ev-norm-btn" data-norm="day" style="padding:5px 12px;border:0;background:transparent;color:var(--ink);border-radius:6px;font:inherit;font-weight:600;cursor:pointer">Por día lab.</button>
        </div>
        <span id="cp-ev-summary" style="margin-left:auto;color:var(--muted)"></span>
      </div>
      <div id="cp-evolution-line" style="position:relative;height:330px"><canvas id="cp-chart-evolution"></canvas></div>
      <div id="cp-evolution-cards" class="ev-grid" style="display:none"></div>
    </div>

    <!-- AVANCE DIARIO COMPARADO -->
    <div class="ford-section">
      <h3>📅 Avance diario comparado <span class="sub">tráfico al día N · sólo Mes A vs Mes B · respeta Marca/Agencia/Modelo</span></h3>
      <div style="display:flex;gap:14px;align-items:center;flex-wrap:wrap;margin-bottom:10px;font-size:12px">
        <div style="display:flex;gap:4px;background:#eef1f5;padding:3px;border-radius:8px">
          <button class="dc-mode-btn" data-mode="cum" style="padding:5px 12px;border:0;background:#003478;color:#fff;border-radius:6px;font:inherit;font-weight:600;cursor:pointer">Acumulado</button>
          <button class="dc-mode-btn" data-mode="daily" style="padding:5px 12px;border:0;background:transparent;color:var(--ink);border-radius:6px;font:inherit;font-weight:600;cursor:pointer">Diario</button>
        </div>
        <span id="cp-dc-summary" style="margin-left:auto;color:var(--muted)"></span>
      </div>
      <div style="position:relative;height:340px"><canvas id="cp-chart-daily"></canvas></div>
    </div>

    <!-- KPIs comparativos -->
    <div class="kpis">
      <div class="kpi"><div class="label" id="cp-kpi-a-lbl">Mes A</div><div class="num" id="cp-kpi-a">—</div><div class="hint" id="cp-kpi-a-hint">tráfico</div></div>
      <div class="kpi accent"><div class="label" id="cp-kpi-b-lbl">Mes B</div><div class="num" id="cp-kpi-b">—</div><div class="hint" id="cp-kpi-b-hint">tráfico</div></div>
      <div class="kpi" id="cp-kpi-delta-card"><div class="label">Δ Tráfico</div><div class="num" id="cp-kpi-delta">—</div><div class="hint" id="cp-kpi-delta-hint"></div></div>
      <div class="kpi"><div class="label">Velocidad</div><div class="num" id="cp-kpi-vel">—</div><div class="hint" id="cp-kpi-vel-hint"></div></div>
    </div>

    <!-- Top movers -->
    <div class="ford-subgrid">
      <div class="ford-section">
        <h3>📈 Mejor desempeño <span class="sub">por modelo / agencia / canal</span></h3>
        <ul id="cp-top-up" style="list-style:none;padding:0;margin:0;font-size:13px"></ul>
      </div>
      <div class="ford-section">
        <h3>📉 Peor desempeño <span class="sub">por modelo / agencia / canal</span></h3>
        <ul id="cp-top-down" style="list-style:none;padding:0;margin:0;font-size:13px"></ul>
      </div>
    </div>

    <!-- Comparativo por modelo -->
    <div class="ford-section">
      <h3>🚗 Por modelo <span class="sub">A (gris) vs B (azul) — números al final · click fila tabla = filtra</span></h3>
      <div style="position:relative;height:300px"><canvas id="cp-chart-model"></canvas></div>
      <div style="overflow-x:auto;margin-top:14px">
        <table class="ford" id="cp-tbl-model">
          <thead><tr><th class="left">Modelo</th><th id="cp-tbl-model-h-a">A</th><th id="cp-tbl-model-h-b">B</th><th>Δ</th><th>Δ %</th><th>Tendencia</th></tr></thead>
          <tbody></tbody>
        </table>
      </div>
    </div>

    <!-- Comparativo por agencia -->
    <div class="ford-section">
      <h3>🏢 Por agencia <span class="sub">A vs B</span></h3>
      <div style="position:relative;height:280px"><canvas id="cp-chart-agency"></canvas></div>
      <div style="overflow-x:auto;margin-top:14px">
        <table class="ford" id="cp-tbl-agency">
          <thead><tr><th class="left">Agencia</th><th id="cp-tbl-agency-h-a">A</th><th id="cp-tbl-agency-h-b">B</th><th>Δ</th><th>Δ %</th><th>Tendencia</th></tr></thead>
          <tbody></tbody>
        </table>
      </div>
    </div>

    <!-- Comparativo por canal -->
    <div class="ford-section">
      <h3>📡 Por canal <span class="sub">A vs B</span></h3>
      <div style="position:relative;height:260px"><canvas id="cp-chart-channel"></canvas></div>
    </div>

    <!-- Heat map Δ modelo × agencia -->
    <div class="ford-section">
      <h3>🔥 Δ tráfico modelo × agencia <span class="sub">verde = creció · rojo = cayó · grueso de número = magnitud absoluta</span></h3>
      <div style="overflow-x:auto">
      <table class="ford heat" id="cp-heatmap">
        <thead id="cp-heat-head"></thead>
        <tbody></tbody>
      </table>
      </div>
      <div class="legend">🟢 Δ ≥ 5 &nbsp;|&nbsp; 🟡 ±5 &nbsp;|&nbsp; 🔴 Δ ≤ −5 &nbsp;|&nbsp; — sin tráfico en ambos meses</div>
    </div>

    <div class="footer-note">Compara dos meses cualesquiera de los disponibles. Datos = lógica oficial del reporte (dedupe CEDULA, canales válidos, mapeo SUCURSAL × Agencia).</div>
  </section>

  <!-- ======================= TAB INVENTARIO ======================= -->
  <section id="tab-inv" class="tab-panel">
    <div class="otros-header" style="background:linear-gradient(135deg,#1565c0 0%,#003478 100%)">
      <div>
        <h2>📦 Inventario · Oferta vs Demanda</h2>
        <div class="sub" id="inv-sub">Cobertura por modelo, reservas en cola y pipeline · snapshot del archivo</div>
      </div>
    </div>

    <!-- FILTROS -->
    <div class="filter-bar">
      <label>Marca
        <select id="inv-marca">
          <option value="FORD">Ford</option>
          <option value="DONGFENG_ORGU">DongFeng</option>
          <option value="CHERY_ORGU">Chery</option>
          <option value="MAZDA_ORGU">Mazda</option>
          <option value="RAM_ORGU">RAM</option>
        </select>
      </label>
    </div>

    <!-- HERO KPIs -->
    <div class="stat-hero stat-hero-4" style="margin-top:14px">
      <div class="card-big"><div class="lbl">Disponible total</div><div class="val" id="inv-k-disp">—</div><div class="hint" id="inv-k-disp-hint"></div></div>
      <div class="card-big"><div class="lbl">Reservado (con VIN)</div><div class="val" id="inv-k-res">—</div><div class="hint">Stock comprometido</div></div>
      <div class="card-big"><div class="lbl">Reservas en cola</div><div class="val" id="inv-k-cola">—</div><div class="hint" id="inv-k-cola-hint">Demanda diferida</div></div>
      <div class="card-big"><div class="lbl">Pipeline (USA + Nac)</div><div class="val" id="inv-k-pipe">—</div><div class="hint">Próximas llegadas</div></div>
    </div>

    <!-- COBERTURA por modelo -->
    <div class="ford-section" style="margin-top:18px">
      <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:14px;flex-wrap:wrap">
        <h3 style="margin:0">📊 Cobertura <span id="inv-cob-title-suffix">por modelo</span> <span class="sub">— ¿alcanza el inventario para el ritmo de ventas?</span></h3>
        <!-- Segmented control: modelo / versión -->
        <div class="inv-cob-toggle" role="tablist" aria-label="Vista de cobertura"
             style="display:inline-flex;border:1px solid #d9dde6;border-radius:8px;overflow:hidden;background:#f5f7fb;font-size:12px;flex-shrink:0">
          <button type="button" class="inv-cob-toggle-btn active" data-view="modelo" role="tab" aria-selected="true"
                  style="padding:7px 14px;background:transparent;border:0;cursor:pointer;font-weight:600;color:var(--ford-2)">📦 Por modelo</button>
          <button type="button" class="inv-cob-toggle-btn" data-view="version" role="tab" aria-selected="false"
                  style="padding:7px 14px;background:transparent;border:0;cursor:pointer;font-weight:600;color:var(--muted);border-left:1px solid #d9dde6">🔧 Por versión</button>
        </div>
      </div>
      <div style="font-size:12px;color:var(--muted);margin:10px 0" id="inv-cob-sub">MOS = disponible / ventas mensuales (últ 3 meses cerrados) · ⚠️ junto a Ventas/mes = ritmo limitado por falta de stock · 🟥 déficit (&lt;1 mes) · 🟡 ajustado (1-2) · 🟢 sano (2-4) · 🟥 sobre-stock (&gt;4 meses)</div>
      <div style="overflow-x:auto">
        <table class="analysis" id="inv-tbl-cob">
          <thead><tr>
            <th id="inv-cob-col-row">Modelo</th>
            <th class="num">Disp. en agencia</th>
            <th class="num" title="Tránsito interno (ya en inventario disponible) + Pipeline (USA + nacionalización, aún no disponible)">En camino</th>
            <th class="num">Disp. total</th>
            <th class="num">Reservado VIN</th>
            <th class="num">Cola</th>
            <th class="num">Ventas/mes</th>
            <th class="num" id="inv-cob-th-trafico">Tráfico mes</th>
            <th class="num">MOS</th>
            <th>Estado</th>
          </tr></thead>
          <tbody></tbody>
        </table>
      </div>
    </div>
    <style>
      .inv-cob-toggle-btn.active { background:#fff !important; color:var(--ford-2) !important; box-shadow:inset 0 -2px 0 var(--ford-2); }
      .inv-cob-toggle-btn:hover:not(.active) { background:#eef1f7; color:var(--ford-2); }
      #inv-tbl-cob tr.version-group-head td { background:#eef1f7; font-size:11px; text-transform:uppercase; letter-spacing:.5px; color:var(--ford-2); font-weight:700; padding:6px 10px; }
      #inv-tbl-cob tr.version-row td:first-child { padding-left:22px; }
    </style>

    <!-- RESERVAS POR CONCESIONARIO × MODELO -->
    <div class="ford-section" style="margin-top:18px">
      <h3>🏬 Reservas por concesionario × modelo <span class="sub">¿Dónde está concentrada la cola y de qué modelo?</span></h3>
      <div style="overflow-x:auto">
        <table class="analysis" id="inv-tbl-cola-agencia">
          <thead></thead>
          <tbody></tbody>
        </table>
      </div>
    </div>

    <!-- COLA POR VERSIÓN -->
    <div class="ford-section" style="margin-top:18px">
      <h3>📋 Reservas por versión <span class="sub">Desglose por la versión específica solicitada</span></h3>
      <div id="inv-version-cards" class="version-cards-grid"></div>
    </div>

    <!-- TIEMPO DE ESPERA: RESERVA → FACTURA -->
    <div class="ford-section" style="margin-top:18px">
      <h3>⏱️ Tiempo de espera del cliente <span class="sub" id="inv-wait-period">Días desde reserva hasta facturación</span></h3>
      <div style="font-size:12px;color:var(--muted);margin-bottom:10px" id="inv-wait-sub">
        La <strong>mediana</strong> es la métrica más representativa porque ignora outliers (un cliente que esperó 1 año no debe dominar el promedio). P75 = 75% de clientes esperaron menos de ese tiempo.
      </div>
      <div style="display:flex;flex-wrap:wrap;gap:14px;font-size:11px;color:var(--ink);margin-bottom:14px;padding:8px 12px;background:#f5f7fb;border-radius:6px;border:1px solid #e5e7eb">
        <strong style="font-size:11px;text-transform:uppercase;letter-spacing:.4px;color:var(--ford-2)">Tramos de espera:</strong>
        <span style="display:inline-flex;align-items:center;gap:5px"><span style="display:inline-block;width:14px;height:10px;background:#2e7d32;border-radius:2px"></span>&lt;1 mes</span>
        <span style="display:inline-flex;align-items:center;gap:5px"><span style="display:inline-block;width:14px;height:10px;background:#7cb342;border-radius:2px"></span>1-2 meses</span>
        <span style="display:inline-flex;align-items:center;gap:5px"><span style="display:inline-block;width:14px;height:10px;background:#fbc02d;border-radius:2px"></span>2-3 meses</span>
        <span style="display:inline-flex;align-items:center;gap:5px"><span style="display:inline-block;width:14px;height:10px;background:#ef6c00;border-radius:2px"></span>3-6 meses</span>
        <span style="display:inline-flex;align-items:center;gap:5px"><span style="display:inline-block;width:14px;height:10px;background:#c62828;border-radius:2px"></span>&gt;6 meses</span>
      </div>
      <div class="kpi-grid-inv kpi-row-4" style="margin-bottom:18px">
        <div class="kpi"><div class="label">Mediana</div><div class="num" id="inv-wait-median">—</div></div>
        <div class="kpi"><div class="label">Promedio</div><div class="num" id="inv-wait-mean">—</div></div>
        <div class="kpi"><div class="label">P75 (75% espera ≤)</div><div class="num" id="inv-wait-p75">—</div></div>
        <div class="kpi"><div class="label">N facturas</div><div class="num" id="inv-wait-n">—</div></div>
      </div>
      <div style="overflow-x:auto">
        <table class="analysis" id="inv-tbl-wait">
          <thead><tr>
            <th>Modelo</th>
            <th class="num">N facturas</th>
            <th class="num">Mediana</th>
            <th class="num">Promedio</th>
            <th class="num">P75</th>
            <th class="num">Máx</th>
            <th class="num" title="Tiempo logístico posterior: días desde la facturación hasta la entrega física al cliente">F→E (mediana)</th>
            <th>Distribución</th>
          </tr></thead>
          <tbody></tbody>
        </table>
      </div>
    </div>

    <!-- MATRIZ disponibles por modelo × agencia -->
    <div class="ford-section" style="margin-top:18px">
      <h3>🏬 Stock disponible por modelo × agencia <span class="sub">Vehículos listos para venta · excluye reservados</span></h3>
      <div style="overflow-x:auto">
        <table class="analysis" id="inv-tbl-matrix">
          <thead></thead>
          <tbody></tbody>
        </table>
      </div>
    </div>

    <!-- RESERVAS EN COLA — aging + top modelos esperando -->
    <div class="ford-section" style="margin-top:18px">
      <h3>⏳ Reservas en cola — demanda diferida sin facturar <span class="sub">Clientes que reservaron pero aún no se factura</span></h3>
      <div class="kpi-grid-inv kpi-row-5" style="margin:10px 0 16px">
        <div class="kpi"><div class="label">≤30 días</div><div class="num" id="inv-aging-30">—</div></div>
        <div class="kpi"><div class="label">31-60</div><div class="num" id="inv-aging-60">—</div></div>
        <div class="kpi"><div class="label">61-90</div><div class="num" id="inv-aging-90">—</div></div>
        <div class="kpi"><div class="label">&gt;90 días</div><div class="num" id="inv-aging-old">—</div></div>
        <div class="kpi"><div class="label">Sin VIN</div><div class="num" id="inv-aging-sinvin">—</div></div>
      </div>
      <h4 style="margin:6px 0 8px 0;font-size:13px;color:var(--ford-2)">Top 12 reservas más antiguas</h4>
      <div style="overflow-x:auto">
        <table class="analysis" id="inv-tbl-aging">
          <thead><tr>
            <th>Modelo</th>
            <th>Agencia</th>
            <th>Cliente</th>
            <th>Asesor</th>
            <th class="num">Fecha</th>
            <th class="num">Aging</th>
            <th class="num">Valor</th>
            <th>Modalidad</th>
            <th>VIN</th>
          </tr></thead>
          <tbody></tbody>
        </table>
      </div>
    </div>

    <!-- INSIGHTS automáticos -->
    <div class="ford-section" style="margin-top:18px">
      <h3>💡 Insights automáticos</h3>
      <div id="inv-insights"></div>
    </div>
  </section>

  <!-- ======================= TAB INVERSIÓN XIY ======================= -->
  <section id="tab-xiy" class="tab-panel">
    <div class="otros-header" style="background:linear-gradient(135deg,#b58105 0%,#003478 100%)">
      <div>
        <h2>💰 Inversión Digital 2026</h2>
        <div class="sub" id="xiy-source">Pauta digital Ford · cruzada con tráfico y ventas del panel</div>
      </div>
    </div>

    <div style="font-size:12px;color:var(--muted);margin:12px 0;line-height:1.5">
      Inversión <strong>amount</strong> (con IVA) extraída de Xiy.today. Cada línea Xiy
      se atribuye al modelo Ford normalizado (RANGER agrupa XLT/XL/Exonerados; ESCAPE
      agrupa todas sus variantes). El tráfico y ventas con que se cruza viene de
      <em>conversion_data.FORD.por_modelo</em> (acumulado 2026 YTD).
    </div>

    <!-- HERO KPIs -->
    <div class="stat-hero" style="grid-template-columns:repeat(4,1fr);margin-top:14px">
      <div class="card-big"><div class="lbl" id="xiy-k-total-lbl">Inversión total</div><div class="val" id="xiy-k-total">—</div><div class="hint" id="xiy-k-total-hint">USD con IVA · todos los meses</div></div>
      <div class="card-big"><div class="lbl">Modelo con mayor inversión</div><div class="val" id="xiy-k-top">—</div><div class="hint" id="xiy-k-top-hint"></div></div>
      <div class="card-big"><div class="lbl" title="Costo Por Visita: inversión digital ÷ visitas marketing">CPV (Costo por visita)</div><div class="val" id="xiy-k-cpv">—</div><div class="hint" id="xiy-k-cpv-hint">Inversión ÷ tráfico marketing</div></div>
      <div class="card-big"><div class="lbl" title="Costo de Adquisición de Cliente: inversión digital ÷ ventas atribuidas">CAC (Costo por venta)</div><div class="val" id="xiy-k-cac">—</div><div class="hint" id="xiy-k-cac-hint">Inversión ÷ ventas atribuidas</div></div>
    </div>

    <!-- FILTROS -->
    <div class="ford-section" style="margin-top:18px;background:#f9fafb">
      <h3>🔍 Filtros <span class="sub">Aplican a todas las tablas de abajo</span></h3>
      <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:10px">
        <div>
          <label style="display:block;font-size:11px;color:var(--muted);margin-bottom:3px">Mes</label>
          <select id="xiy-f-mes" style="width:100%;padding:7px;border:1px solid #d1d5db;border-radius:6px"></select>
        </div>
        <div>
          <label style="display:block;font-size:11px;color:var(--muted);margin-bottom:3px">Modelo</label>
          <select id="xiy-f-modelo" style="width:100%;padding:7px;border:1px solid #d1d5db;border-radius:6px"></select>
        </div>
        <div>
          <label style="display:block;font-size:11px;color:var(--muted);margin-bottom:3px">Agencia</label>
          <select id="xiy-f-agencia" style="width:100%;padding:7px;border:1px solid #d1d5db;border-radius:6px"></select>
        </div>
      </div>
      <div style="margin-top:10px;font-size:12px;color:var(--muted);display:flex;align-items:center;gap:14px">
        <span id="xiy-f-summary">—</span>
        <button id="xiy-f-clear" type="button" style="padding:5px 10px;border:1px solid #d1d5db;background:white;border-radius:6px;cursor:pointer;font-size:12px">Limpiar filtros</button>
      </div>
    </div>

    <!-- TABLA 1: matriz modelo × mes -->
    <div class="ford-section" style="margin-top:18px">
      <h3>📅 Inversión por modelo × mes <span class="sub">USD por modelo Ford y mes · Solo inversión atribuible</span></h3>
      <div style="overflow-x:auto">
        <table class="analysis" id="xiy-tbl-modelo-mes">
          <thead><tr id="xiy-tbl-modelo-mes-head">
            <th>Modelo</th>
            <!-- columnas de meses se inyectan dinámicamente -->
            <th class="num">Total</th>
          </tr></thead>
          <tbody></tbody>
          <tfoot></tfoot>
        </table>
      </div>
    </div>

    <!-- TABLA 2: ROAS / CPV / CAC por modelo -->
    <div class="ford-section" style="margin-top:18px">
      <h3>🎯 Cruce con tráfico y ventas <span class="sub">Inversión Digital vs tráfico ATRIBUIBLE a marketing (YTD 2026)</span></h3>
      <div style="font-size:12px;color:var(--muted);margin-bottom:8px;background:#fff8e1;padding:10px;border-radius:6px">
        <strong>Tráfico Ford</strong> ya está filtrado a canales atribuibles a marketing: <em>Showroom · Hubspot · Ferias · Llamada In · Mailing</em>. Quedan FUERA: Referidos, Recompra, Gestión Externa, Talleres, Redes Sociales Propias, Empleado, Prospección.<br>
        <strong>CPV real</strong> = inversión digital / visitas marketing ·
        <strong>CAC real</strong> = inversión digital / ventas atribuidas (1 cliente = 1 venta).
      </div>
      <div style="overflow-x:auto">
        <table class="analysis" id="xiy-tbl-roas">
          <thead><tr>
            <th>Modelo</th>
            <th class="num">Inversión Digital</th>
            <th class="num">Tráfico Ford</th>
            <th class="num">Ventas atribuidas</th>
            <th class="num">% conversión</th>
            <th class="num" title="Inversión / Tráfico">CPV real</th>
            <th class="num" title="Inversión / Ventas atribuidas">CAC real</th>
          </tr></thead>
          <tbody></tbody>
          <tfoot></tfoot>
        </table>
      </div>
    </div>

    <!-- GRÁFICO: Evolución mensual de Tráfico / Ventas / CAC / Conversión -->
    <div class="ford-section" style="margin-top:18px">
      <h3>📈 Evolución mensual: Tráfico · Ventas · CAC · Conversión <span class="sub">Tendencia mes a mes 2026 · usa chips para alternar modelos</span></h3>
      <div style="font-size:12px;color:var(--muted);margin-bottom:8px;background:#fafbfc;padding:10px;border-radius:6px">
        <strong>Tráfico</strong> = Visitas marketing del mes (Showroom + Hubspot + Ferias + Llamada In + Mailing).
        <strong>Ventas</strong> = Clientes únicos que cerraron compra atribuidos a tráfico.
        <strong>CAC</strong> = Inversión digital / ventas atribuidas.
        <strong>Conversión</strong> = Ventas / Tráfico × 100.
        <br>Tráfico/ventas usan <strong>first_ym</strong> (mes del primer toque del cliente).
        <br><em>Si un mes tiene 0 ventas, el CAC queda indefinido y la línea se dibuja saltándose ese mes.</em>
      </div>
      <!-- Chips de modelo -->
      <div id="xiy-evo-chips" style="display:flex;flex-wrap:wrap;gap:6px;margin-bottom:12px"></div>
      <!-- Toggles de métrica -->
      <div style="display:flex;gap:14px;margin-bottom:10px;font-size:13px;flex-wrap:wrap">
        <label style="cursor:pointer;display:flex;align-items:center;gap:5px">
          <input type="checkbox" id="xiy-evo-show-traf" checked> <span style="color:#0369a1;font-weight:600">Tráfico</span>
        </label>
        <label style="cursor:pointer;display:flex;align-items:center;gap:5px">
          <input type="checkbox" id="xiy-evo-show-vent" checked> <span style="color:#f59e0b;font-weight:600">Ventas</span>
        </label>
        <label style="cursor:pointer;display:flex;align-items:center;gap:5px">
          <input type="checkbox" id="xiy-evo-show-cac"> <span style="color:#be185d;font-weight:600">CAC</span>
        </label>
        <label style="cursor:pointer;display:flex;align-items:center;gap:5px">
          <input type="checkbox" id="xiy-evo-show-conv" checked> <span style="color:#16a34a;font-weight:600">Conversión</span>
        </label>
      </div>
      <div style="position:relative;height:380px">
        <canvas id="xiy-evo-chart"></canvas>
      </div>
      <div id="xiy-evo-summary" style="margin-top:10px;font-size:12px;color:var(--muted);text-align:center"></div>
    </div>

    <!-- TABLA 2B: Performance vs Awareness -->
    <div class="ford-section" style="margin-top:18px">
      <h3>⚖️ Etapa del Funnel por modelo <span class="sub">Distribución del presupuesto por etapa del embudo · clasificado por nombre de campaña</span></h3>
      <div style="font-size:12px;color:var(--muted);margin-bottom:8px;background:#f0f9ff;padding:10px;border-radius:6px">
        <strong>🎯 Performance</strong> = "LEADS AON ..." / Renting / campañas genéricas de modelo (Territory, Escape) · busca lead directo (bottom funnel).<br>
        <strong>🤔 Consideración</strong> = Posicionamiento producto / Utilidades / Blindados / Open House / Race Weekend / PowerDays · mid funnel + activación.<br>
        <strong>📢 Awareness</strong> = AYF Regional / Branding / Lanzamientos / Incremento Seguidores / Renovation · construye marca (top funnel).
      </div>
      <div style="overflow-x:auto">
        <table class="analysis" id="xiy-tbl-perfaware-modelo">
          <thead><tr>
            <th>Modelo</th>
            <th class="num">Performance</th>
            <th class="num">Awareness</th>
            <th class="num">Consideración</th>
            <th class="num">Total</th>
            <th class="num">% Perf</th>
          </tr></thead>
          <tbody></tbody>
          <tfoot></tfoot>
        </table>
      </div>
    </div>

    <!-- TABLA 3: por Agencia -->
    <div class="ford-section" style="margin-top:18px">
      <h3>🏢 Inversión por Agencia <span class="sub">Atribución según audience geográfica · regional repartida entre agencias de la zona</span></h3>
      <div style="overflow-x:auto">
        <table class="analysis" id="xiy-tbl-agencia">
          <thead><tr>
            <th>Agencia</th>
            <th class="num">Inversión Digital</th>
            <th class="num">% del total</th>
            <th class="num" title="Tráfico Ford acumulado 2026 desde el panel">Tráfico Ford</th>
            <th class="num" title="Ventas atribuidas a tráfico (panel)">Ventas atrib.</th>
            <th class="num" title="Inversión / Tráfico">CPV real</th>
            <th class="num" title="Inversión / Ventas atribuidas">CAC real</th>
          </tr></thead>
          <tbody></tbody>
          <tfoot></tfoot>
        </table>
      </div>
      <div class="footer-note" style="margin-top:8px">
        <strong>Cómo se atribuye:</strong> audiencias con mención directa (TUMBACO, LA Y, CJA, MANTA, MACHALA, ORELLANA, PORTOVIEJO) van 100% a esa agencia. Las regionales ("Concesionarios Sierra/Costa/Manabí") se reparten en partes iguales entre las agencias ORGU de la región. Las nacionales o sin clasificar quedan fuera (USD <span id="xiy-multi-nacional">—</span> en bucket Multi/Nacional).
      </div>
    </div>

    <!-- TABLA 4: por Medio -->
    <div class="ford-section" style="margin-top:18px">
      <h3>📱 Inversión por Medio <span class="sub">Plataforma publicitaria · Meta / Google / TikTok / etc.</span></h3>
      <div style="overflow-x:auto">
        <table class="analysis" id="xiy-tbl-medio">
          <thead><tr>
            <th>Medio</th>
            <th class="num">Inversión Digital</th>
            <th class="num">% del total</th>
            <th class="num" title="Una 'línea' es una fila de inversión dentro de una campaña Xiy. Una campaña típicamente tiene varias líneas (una por audiencia geográfica o demográfica).">N° líneas <span style="cursor:help;opacity:.5">ⓘ</span></th>
            <th>Distribución por objetivo</th>
          </tr></thead>
          <tbody></tbody>
          <tfoot></tfoot>
        </table>
      </div>
    </div>

    <!-- TABLA 5: NO atribuible a modelo -->
    <div class="ford-section" style="margin-top:18px">
      <h3>🏷️ Inversión NO atribuida a modelo <span class="sub">Awareness regional, marca, activación · no se puede asociar a un solo modelo Ford</span></h3>
      <div style="overflow-x:auto">
        <table class="analysis" id="xiy-tbl-nonmodelo">
          <thead><tr>
            <th>Iniciativa</th>
            <th class="num">Inversión Digital</th>
            <th class="num" title="Una 'línea' es una fila de inversión dentro de una campaña Xiy. Una campaña típicamente tiene varias líneas (una por audiencia geográfica o demográfica).">N° líneas <span style="cursor:help;opacity:.5">ⓘ</span></th>
            <th class="num">% del total</th>
          </tr></thead>
          <tbody></tbody>
          <tfoot></tfoot>
        </table>
      </div>
    </div>

    <div class="footer-note" id="xiy-footer">Fuente: Xiy.today (extraído vía xiy_extractor.py). Tráfico y ventas de la BD interna ORGU cruzada con DATOS de inventario (status FACTURADO).</div>
  </section>

  <!-- ======================= TAB CONVERSIÓN (con password gate compartido) ======================= -->
  <section id="tab-conv" class="tab-panel">
    <div id="conv-gate" class="pw-gate" style="display:none">
      <div class="icon">🔒</div>
      <h2>Acceso restringido</h2>
      <p>Ingresa la contraseña para ver el análisis de conversión.</p>
      <input type="password" id="conv-pw" placeholder="Contraseña" autocomplete="off">
      <button id="conv-pw-btn" type="button">Acceder</button>
      <div class="err" id="conv-pw-err"></div>
    </div>

    <div id="conv-content">
      <div class="otros-header" style="background:linear-gradient(135deg,#1b5e20 0%,#003478 100%)">
        <div>
          <h2>🎯 Conversión Tráfico → Venta</h2>
          <div class="sub">Solo Ford · clientes únicos atribuidos a tráfico que terminaron en factura</div>
        </div>
        <button class="logout-btn" id="conv-logout" style="display:none">Cerrar sesión</button>
      </div>

      <div style="font-size:12px;color:var(--muted);margin:12px 0;line-height:1.5">
        <strong>Período: 2026 (Ene a hoy).</strong> Contamos <strong>personas únicas</strong> que tocaron BD tráfico (GUC) por primera vez en 2026. Cada persona cuenta 1 sin importar cuántas veces vino. Identidad robusta: cédula natural ↔ RUC del titular ↔ mismo email/celular. Atribuimos al canal/modelo/agencia/asesor de su <strong>primer toque</strong>. <em>Nota: el conteo de "tráfico" en la pestaña Otros (2,216) usa otra metodología — cuenta atenciones mensuales y duplica clientes que vinieron en varios meses.</em>
      </div>

      <!-- FILTROS -->
      <div class="filter-bar">
        <label>Mes (1er toque)
          <select id="conv-f-mes">
            <option value="">YTD 2026</option>
            <option value="2026-01">Enero</option>
            <option value="2026-02">Febrero</option>
            <option value="2026-03">Marzo</option>
            <option value="2026-04">Abril</option>
            <option value="2026-05">Mayo</option>
          </select>
        </label>
        <label>Agencia
          <select id="conv-f-agencia">
            <option value="">Todas</option>
            <option value="CJA">CJA</option>
            <option value="Orellana">Orellana</option>
            <option value="La Y">La Y</option>
            <option value="Tumbaco">Tumbaco</option>
            <option value="Manta">Manta</option>
            <option value="Machala">Machala</option>
            <option value="Portoviejo">Portoviejo</option>
            <option value="Gestión Externa">Gestión Externa (B2B)</option>
          </select>
        </label>
        <label>Zona
          <select id="conv-f-zona">
            <option value="">Todas</option>
            <option value="Quito">Quito</option>
            <option value="Guayaquil">Guayaquil</option>
            <option value="Manta">Manta</option>
            <option value="Machala">Machala</option>
          </select>
        </label>
        <label>Modelo<select id="conv-f-modelo"><option value="">Todos</option></select></label>
        <label>Canal<select id="conv-f-canal"><option value="">Todos</option></select></label>
        <button class="reset" id="conv-f-reset" type="button">↺ Limpiar</button>
      </div>

      <!-- HERO KPIs -->
      <div class="stat-hero stat-hero-4" style="margin-top:14px">
        <div class="card-big"><div class="lbl">Personas únicas (tráfico)</div><div class="val" id="conv-k-traf">—</div><div class="hint">1er toque en 2026 · identidad robusta</div></div>
        <div class="card-big"><div class="lbl">Cerraron compra</div><div class="val pos" id="conv-k-cerr">—</div><div class="hint" id="conv-k-cerr-hint"></div></div>
        <div class="card-big"><div class="lbl">% Conversión</div><div class="val" id="conv-k-rate">—</div><div class="hint">Personas que compraron / personas únicas</div></div>
        <div class="card-big"><div class="lbl" title="Días desde el primer toque del cliente en BD tráfico hasta que se le facturó el vehículo">Tiempo cliente → factura</div><div class="val" id="conv-k-ciclo">—</div><div class="hint" id="conv-k-ciclo-hint">Mediana de días entre 1er toque y factura</div></div>
      </div>

      <!-- EVOLUCIÓN MENSUAL DE CONVERSIÓN -->
      <div class="ford-section" style="margin-top:18px">
        <h3>📈 Evolución mensual de conversión <span class="sub" id="conv-evol-sub">% de personas con 1er toque en cada mes que terminaron facturando</span></h3>
        <div style="font-size:12px;color:var(--muted);margin-bottom:8px">
          Los meses más recientes muestran % menor porque su cohorte está aún en pipeline (no ha terminado el ciclo de venta).
        </div>
        <div style="position:relative;height:320px">
          <canvas id="conv-chart-evol"></canvas>
        </div>
      </div>

      <!-- POR CANAL -->
      <div class="ford-section" style="margin-top:18px">
        <h3>📡 Conversión por canal de primer toque <span class="sub">¿Qué canal trae el lead que más cierra?</span></h3>
        <div style="overflow-x:auto">
          <table class="analysis" id="conv-tbl-canal">
            <thead><tr>
              <th>Canal</th>
              <th class="num">Clientes únicos</th>
              <th class="num">Cerraron</th>
              <th class="num" title="Vehículos facturados (un cliente puede comprar varios)">Vehículos</th>
              <th class="num">% conversión</th>
              <th>Visual</th>
            </tr></thead>
            <tbody></tbody>
          </table>
        </div>
      </div>

      <!-- POR MODELO -->
      <div class="ford-section" style="margin-top:18px">
        <h3>🚗 Conversión por modelo de primer toque <span class="sub">¿Qué modelo se vende vs cuál se queda en cotización?</span></h3>
        <div style="overflow-x:auto">
          <table class="analysis" id="conv-tbl-modelo">
            <thead><tr>
              <th>Modelo</th>
              <th class="num">Clientes únicos</th>
              <th class="num">Cerraron</th>
              <th class="num" title="Vehículos facturados (un cliente puede comprar varios)">Vehículos</th>
              <th class="num">% conversión</th>
              <th>Visual</th>
            </tr></thead>
            <tbody></tbody>
          </table>
        </div>
      </div>

      <!-- EVOLUCIÓN MENSUAL POR MODELO -->
      <div class="ford-section" style="margin-top:18px">
        <h3>📈 Evolución mensual de conversión por modelo <span class="sub">% conversión mes a mes — una línea por modelo</span></h3>
        <div style="font-size:12px;color:var(--muted);margin-bottom:8px">
          Cohorte = clientes con 1er toque en cada mes. Click en los chips para mostrar/ocultar modelos en el gráfico.
        </div>
        <div id="conv-modelos-chips" style="display:flex;flex-wrap:wrap;gap:6px;margin-bottom:14px"></div>
        <div style="position:relative;height:360px">
          <canvas id="conv-chart-modelos"></canvas>
        </div>
      </div>

      <!-- POR AGENCIA -->
      <div class="ford-section" style="margin-top:18px">
        <h3>🏬 Conversión por agencia de primer toque <span class="sub">¿Qué agencia cierra más de lo que trae?</span></h3>
        <div style="overflow-x:auto">
          <table class="analysis" id="conv-tbl-agencia">
            <thead><tr>
              <th>Agencia</th>
              <th class="num">Clientes únicos</th>
              <th class="num">Cerraron</th>
              <th class="num" title="Vehículos facturados (un cliente puede comprar varios)">Vehículos</th>
              <th class="num">% conversión</th>
              <th>Visual</th>
            </tr></thead>
            <tbody></tbody>
          </table>
        </div>
      </div>

      <!-- TOP ASESORES -->
      <div class="ford-section" style="margin-top:18px">
        <h3>🏆 Top asesores — ranking por cierres <span class="sub">Solo asesores con ≥5 clientes en tráfico (filtra ruido)</span></h3>
        <div style="overflow-x:auto">
          <table class="analysis" id="conv-tbl-asesor">
            <thead><tr>
              <th>#</th>
              <th>Asesor</th>
              <th class="num">Clientes únicos</th>
              <th class="num">Cerraron</th>
              <th class="num" title="Vehículos facturados (un cliente puede comprar varios)">Vehículos</th>
              <th class="num">% conversión</th>
              <th>Visual</th>
            </tr></thead>
            <tbody></tbody>
          </table>
        </div>
      </div>

      <div class="footer-note">Conversión calculada cruzando BDs históricos de tráfico contra DATOS de inventario (status FACTURADO). Atribución al primer toque (asesor/canal/modelo del primer registro del cliente).</div>
    </div>
  </section>

  <!-- ======================= TAB COMPETENCIA (con password gate compartido) ======================= -->
  <section id="tab-comp-imp" class="tab-panel">
    <div id="comp-imp-gate" class="pw-gate">
      <div class="icon">🔒</div>
      <h2>Acceso restringido</h2>
      <p>Ingresa la contraseña para ver el análisis competitivo.</p>
      <input type="password" id="comp-imp-pw" placeholder="Contraseña" autocomplete="off">
      <button id="comp-imp-pw-btn" type="button">Acceder</button>
      <div class="err" id="comp-imp-pw-err"></div>
    </div>

    <div id="comp-imp-content" style="display:none">
      <div class="otros-header" style="background:linear-gradient(135deg,#6a1b9a 0%,#003478 100%)">
        <div>
          <h2>🚗 Competencia · Importaciones Ford</h2>
          <div class="sub" id="comp-imp-source">ORGU (AUTOSHARECORP) vs QM (Quito Motors)</div>
        </div>
        <button class="logout-btn" id="comp-imp-logout">Cerrar sesión</button>
      </div>

      <div style="font-size:12px;color:var(--muted);margin:12px 0;line-height:1.5">
        Datos de importaciones Ford a Ecuador (2 distribuidores autorizados: ORGU/AUTOSHARECORP y QM/Quito Motors). Cada registro aduanero = 1 vehículo. Histórico 2024 · 2025 · 2026 (parcial, ene–may).
      </div>

      <!-- HERO KPIs -->
      <div class="stat-hero" style="grid-template-columns:repeat(4,1fr)">
        <div class="card-big"><div class="lbl">Total 2025 (12 meses)</div><div class="val" id="comp-k-2025">—</div><div class="hint" id="comp-k-2025-hint"></div></div>
        <div class="card-big"><div class="lbl">Total 2026 (parcial)</div><div class="val" id="comp-k-2026">—</div><div class="hint" id="comp-k-2026-hint"></div></div>
        <div class="card-big"><div class="lbl">Share ORGU 2025</div><div class="val" id="comp-k-share25">—</div><div class="hint">vs QM</div></div>
        <div class="card-big"><div class="lbl">Share ORGU 2026</div><div class="val pos" id="comp-k-share26">—</div><div class="hint" id="comp-k-delta"></div></div>
      </div>

      <!-- TENDENCIA 3 AÑOS + CIF -->
      <div class="ford-section" style="margin-top:18px">
        <h3>📊 Evolución del share ORGU (3 años) <span class="sub">unidades importadas · ORGU vs QM</span></h3>
        <div id="comp-3yr" style="display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin-bottom:12px"></div>
        <div id="comp-cif" style="font-size:13px;color:var(--muted);background:#faf5ff;padding:12px;border-radius:8px"></div>
      </div>

      <!-- VENTAS Y MARGEN ESTIMADO -->
      <div class="ford-section" style="margin-top:18px">
        <h3>💰 Ventas y margen estimado <span class="sub">unidades importadas × precio neto y margen del PBD Ford 2026</span></h3>
        <div style="font-size:12px;color:var(--muted);margin-bottom:10px">Estimación: cada unidad importada valorizada con el precio neto y el <em>Gross Margin (Tier 1)</em> del PBD Ford Portafolio 2026 (BP 2026). 2024/2025 se valorizan a precios constantes 2026. Asume que lo importado se vende a precio de lista.</div>
        <div style="margin-bottom:12px">
          <label style="font-size:12px;color:var(--muted)">Año:
            <select id="comp-margen-anio" style="font:inherit;font-size:13px;padding:6px 10px;border-radius:6px;border:1px solid #d1d5db;margin-left:8px">
              <option value="2026" selected>2026 (ene–may)</option>
              <option value="2025">2025</option>
              <option value="2024">2024</option>
            </select>
          </label>
        </div>
        <div id="comp-margen-cards" style="display:grid;grid-template-columns:repeat(2,1fr);gap:14px;margin-bottom:14px"></div>
        <div style="overflow-x:auto">
          <table class="analysis" id="comp-margen-tbl">
            <thead><tr>
              <th rowspan="2">Modelo</th>
              <th rowspan="2" class="num">Margen/u</th>
              <th colspan="3" style="text-align:center">ORGU</th>
              <th colspan="3" style="text-align:center">QM</th>
              <th rowspan="2" class="num">Ventas total</th>
            </tr><tr>
              <th class="num">u</th><th class="num">Ventas</th><th class="num">Margen</th>
              <th class="num">u</th><th class="num">Ventas</th><th class="num">Margen</th>
            </tr></thead>
            <tbody></tbody>
            <tfoot></tfoot>
          </table>
        </div>
      </div>

      <!-- ORIGEN USA (alto margen) -->
      <div class="ford-section" style="margin-top:18px">
        <h3>🇺🇸 Origen de importación: USA = alto margen <span class="sub">% de unidades importadas desde Estados Unidos (Explorer, Expedition, Bronco, F-150)</span></h3>
        <div style="font-size:12px;color:var(--muted);margin-bottom:10px">Los vehículos de fuente USA son los de mayor margen del portafolio. Un mayor % USA indica enfoque en gama premium/rentable vs volumen de bajo costo (China/Tailandia/Argentina).</div>
        <div style="overflow-x:auto">
          <table class="analysis" id="comp-usa-tbl">
            <thead><tr>
              <th>Año</th>
              <th class="num">ORGU · % USA</th>
              <th class="num">ORGU · u. USA</th>
              <th class="num">QM · % USA</th>
              <th class="num">QM · u. USA</th>
              <th class="num">Ventaja ORGU</th>
            </tr></thead>
            <tbody></tbody>
          </table>
        </div>
      </div>

      <!-- SWING DE SHARE POR MODELO -->
      <div class="ford-section" style="margin-top:18px">
        <h3>🔄 Swing de share ORGU por modelo (2025 → 2026) <span class="sub">qué modelos recuperó o cedió ORGU vs QM</span></h3>
        <div style="overflow-x:auto">
          <table class="analysis" id="comp-swing-tbl">
            <thead><tr>
              <th>Modelo</th>
              <th class="num">Share ORGU 2025</th>
              <th class="num">Share ORGU 2026</th>
              <th class="num">Δ swing</th>
              <th class="num">2025 (O/QM)</th>
              <th class="num">2026 (O/QM)</th>
            </tr></thead>
            <tbody></tbody>
          </table>
        </div>
      </div>

      <!-- TABLA POR MODELO -->
      <div class="ford-section" style="margin-top:18px">
        <h3>📋 Importaciones por modelo (ordenado por volumen total) <span class="sub">Cada celda es unidades importadas</span></h3>
        <div style="overflow-x:auto">
          <table class="analysis" id="comp-tbl">
            <thead><tr>
              <th rowspan="2">Modelo</th>
              <th colspan="3" style="text-align:center">2025 (12 m)</th>
              <th colspan="3" style="text-align:center">2026 (5 m)</th>
              <th rowspan="2" class="num">Total</th>
              <th rowspan="2" class="num">Share ORGU 2026</th>
              <th rowspan="2" class="num">Δ share</th>
            </tr><tr>
              <th class="num">ORGU</th><th class="num">QM</th><th class="num">Total</th>
              <th class="num">ORGU</th><th class="num">QM</th><th class="num">Total</th>
            </tr></thead>
            <tbody></tbody>
          </table>
        </div>
      </div>

      <!-- EVOLUCIÓN MENSUAL POR MODELO -->
      <div class="ford-section" style="margin-top:18px">
        <h3>📈 Evolución mensual por modelo <span class="sub">Selecciona un modelo para ver su trayectoria ORGU vs QM</span></h3>
        <div style="margin-bottom:12px;display:flex;gap:18px;flex-wrap:wrap;align-items:center">
          <label style="font-size:12px;color:var(--muted)">Modelo:
            <select id="comp-imp-modelo" style="font:inherit;font-size:13px;padding:6px 10px;border-radius:6px;border:1px solid #d1d5db;margin-left:8px;min-width:200px">
            </select>
          </label>
          <label style="font-size:12px;color:var(--muted)">Año:
            <select id="comp-imp-anio" style="font:inherit;font-size:13px;padding:6px 10px;border-radius:6px;border:1px solid #d1d5db;margin-left:8px">
              <option value="">Todos (2024–2026)</option>
              <option value="2024">2024</option>
              <option value="2025">2025</option>
              <option value="2026">2026</option>
            </select>
          </label>
        </div>
        <div style="position:relative;height:300px">
          <canvas id="comp-imp-chart"></canvas>
        </div>
      </div>

      <div class="footer-note">Datos del archivo BDD IMPORTACIONES (importaciones Ford a Ecuador). Solo refleja importaciones por distribuidor — no equivale a ventas al consumidor final.</div>
    </div>
  </section>

  <!-- ======================= TAB EMBUDO ======================= -->
  <section id="tab-embudo" class="tab-panel">
    <div class="otros-header" style="background:linear-gradient(135deg,#0f766e 0%,#003478 100%)">
      <div>
        <h2>🫙 Embudo de ventas por modelo</h2>
        <div class="sub" id="embudo-source">Prospectos por etapa del embudo · por modelo y concesionario</div>
      </div>
    </div>

    <div style="margin:14px 0;display:flex;gap:18px;flex-wrap:wrap;align-items:center">
      <label style="font-size:12px;color:var(--muted)">Concesionario:
        <select id="embudo-agencia" style="font:inherit;font-size:13px;padding:6px 10px;border-radius:6px;border:1px solid #d1d5db;margin-left:8px"></select>
      </label>
      <label style="font-size:12px;color:var(--muted)">Modelo:
        <select id="embudo-modelo" style="font:inherit;font-size:13px;padding:6px 10px;border-radius:6px;border:1px solid #d1d5db;margin-left:8px;min-width:160px"><option value="">Todos los modelos</option></select>
      </label>
    </div>
    <div style="margin:10px 0;font-size:12px;color:var(--muted)">
      Meses <span style="font-size:11px">(clic para sumar varios)</span>:
      <span id="embudo-meses-chips" style="display:inline-flex;flex-wrap:wrap;gap:6px;margin-left:8px;vertical-align:middle"></span>
    </div>

    <!-- EMBUDO VISUAL -->
    <div class="ford-section">
      <h3>📉 Embudo general <span class="sub" id="embudo-sub-general"></span></h3>
      <div id="embudo-funnel" style="max-width:760px;margin:0 auto"></div>
    </div>

    <!-- TABLA POR MODELO -->
    <div class="ford-section" style="margin-top:18px">
      <h3>📋 Prospectos por modelo y etapa <span class="sub">negocios únicos en cada etapa del embudo</span></h3>
      <div style="overflow-x:auto">
        <table class="analysis" id="embudo-tbl">
          <thead><tr id="embudo-tbl-head"><th>Modelo</th></tr></thead>
          <tbody></tbody>
          <tfoot></tfoot>
        </table>
      </div>
      <div class="footer-note" style="margin-top:8px">Cada celda = negocios únicos (por cédula/id) interesados en ese modelo en esa etapa. Un negocio que cotiza varios modelos cuenta en cada uno. <strong>Cierre = ventas facturadas reales del inventario</strong> (no el archivo de pre-facturación). Etapas Solicitud/Aprobación aplican solo a ventas con crédito; las de contado saltan directo a Cierre.</div>
    </div>

    <!-- TABLA POR ASESOR -->
    <div class="ford-section" style="margin-top:18px">
      <h3>👤 Prospectos por asesor comercial y etapa <span class="sub">negocios únicos gestionados por cada asesor · respeta meses seleccionados</span></h3>
      <div style="overflow-x:auto">
        <table class="analysis" id="embudo-asesor-tbl">
          <thead><tr id="embudo-asesor-head"><th>Asesor</th></tr></thead>
          <tbody></tbody>
          <tfoot></tfoot>
        </table>
      </div>
      <div class="footer-note" style="margin-top:8px">El asesor del Cierre se toma del ASESOR_FACTURACION del inventario (matcheado por nombre con el asesor del embudo). El % de cierre mide la efectividad de cada asesor para convertir cotizaciones en ventas.</div>
    </div>

    <!-- INSIGHTS AUTOMÁTICOS -->
    <div class="ford-section" style="margin-top:18px">
      <h3>💡 Hallazgos automáticos <span class="sub">se recalculan según los filtros de meses y modelo</span></h3>
      <div id="embudo-insights"></div>
    </div>
  </section>

  <!-- ======================= TAB OTROS (con password gate) ======================= -->
  <section id="tab-otros" class="tab-panel">
    <!-- Gate de password (desactivado - acceso libre) -->
    <div id="otros-gate" class="pw-gate" style="display:none">
      <div class="icon">🔒</div>
      <h2>Acceso restringido</h2>
      <p>Ingresa la contraseña para ver los análisis privados.</p>
      <input type="password" id="otros-pw" placeholder="Contraseña" autocomplete="off">
      <button id="otros-pw-btn" type="button">Acceder</button>
      <div class="err" id="otros-pw-err"></div>
    </div>

    <!-- Contenido (siempre visible) -->
    <div id="otros-content">
      <div class="otros-header">
        <div>
          <h2>📊 Análisis privados</h2>
          <div class="sub">Análisis profundos por modelo y marca · Sólo acceso autorizado</div>
        </div>
        <button class="logout-btn" id="otros-logout" style="display:none">Cerrar sesión</button>
      </div>

      <!-- FILTROS DEL INFORME -->
      <div class="filter-bar">
        <label>Vista
          <select id="an-view">
            <option value="ytd">YTD 2026 (acumulado)</option>
            <option value="enero_2026">Enero 2026</option>
            <option value="febrero_2026">Febrero 2026</option>
            <option value="marzo_2026">Marzo 2026</option>
            <option value="abril_2026">Abril 2026</option>
            <option value="mayo_2026">Mayo 2026</option>
          </select>
        </label>
        <label>Modelo<select id="an-modelo"><option value="">Todos</option></select></label>
        <label>Agencia<select id="an-agencia"><option value="">Todas</option></select></label>
        <label>Tipo canal
          <select id="an-canal">
            <option value="marketing">Sólo marketing (~80%)</option>
            <option value="asesor">Sólo asesor comercial (~20%)</option>
            <option value="all">Todos los canales</option>
          </select>
        </label>
        <button class="reset" id="an-reset" type="button">↺ Limpiar</button>
      </div>

      <div class="ford-filter-summary" id="an-filter-summary"></div>

      <!-- HERO KPIs -->
      <div class="stat-hero">
        <div class="card-big"><div class="lbl" id="an-k1-lbl">Cumplimiento</div><div class="val" id="an-k1">—</div><div class="hint" id="an-k1-hint"></div></div>
        <div class="card-big"><div class="lbl">Tráfico real</div><div class="val" id="an-k2">—</div><div class="hint" id="an-k2-hint"></div></div>
        <div class="card-big"><div class="lbl">Meta</div><div class="val" id="an-k3">—</div><div class="hint" id="an-k3-hint"></div></div>
      </div>

      <!-- POR MODELO -->
      <div class="ford-section">
        <h3>🚗 Por modelo <span class="sub" id="an-mod-sub">acumulado YTD 2026</span></h3>
        <table class="analysis" id="an-tbl-modelo">
          <thead><tr><th>Modelo</th><th class="num">Real</th><th class="num">Meta</th><th class="num">Cumpl.</th><th>Avance</th><th class="num">Gap</th></tr></thead>
          <tbody></tbody>
        </table>
      </div>

      <!-- POR AGENCIA -->
      <div class="ford-section">
        <h3>🏢 Por agencia <span class="sub" id="an-ag-sub">acumulado YTD 2026</span></h3>
        <table class="analysis" id="an-tbl-agencia">
          <thead><tr><th>Agencia</th><th class="num">Real</th><th class="num">Meta</th><th class="num">Cumpl.</th><th>Avance</th><th class="num">Gap</th></tr></thead>
          <tbody></tbody>
        </table>
      </div>

      <!-- POR CANAL -->
      <div class="ford-section">
        <h3>📡 Por canal <span class="sub" id="an-ch-sub">distribución del tráfico filtrado</span></h3>
        <table class="analysis" id="an-tbl-canal">
          <thead><tr><th>Canal</th><th class="num">Tráfico</th><th class="num">Share</th><th>Distribución</th></tr></thead>
          <tbody></tbody>
        </table>
      </div>

      <!-- HEAT MAP MODELO × AGENCIA -->
      <div class="ford-section">
        <h3>🔥 Cumplimiento modelo × agencia <span class="sub" id="an-heat-sub">% de meta (acumulado YTD)</span></h3>
        <div style="overflow-x:auto">
          <table class="ford heat" id="an-heatmap">
            <thead id="an-heat-head"></thead>
            <tbody></tbody>
          </table>
        </div>
        <div class="legend">🟢 ≥100% &nbsp;|&nbsp; 🟡 ≥70% &nbsp;|&nbsp; 🔴 &lt;70% &nbsp;|&nbsp; — sin tráfico ni meta &nbsp;|&nbsp; N/A sin meta</div>
      </div>

      <!-- EVOLUCIÓN MES A MES -->
      <div class="ford-section">
        <h3>📅 Evolución mes a mes <span class="sub" id="an-evo-sub">scope filtrado</span></h3>
        <table class="analysis" id="an-tbl-mes">
          <thead><tr><th>Mes</th><th class="num">Real</th><th class="num">Meta</th><th class="num">Cumpl.</th><th>Avance</th><th class="num">Δ vs mes ant.</th></tr></thead>
          <tbody></tbody>
        </table>
      </div>

      <!-- CRUCE TRÁFICO × INVENTARIO × RESERVAS -->
      <div class="ford-section">
        <h3>📊 Cruce tráfico × inventario × reservas <span class="sub">¿La caída de tráfico está justificada por reservas pre-mes con inventario que las respalde?</span></h3>
        <div style="font-size:12px;color:var(--muted);margin-bottom:12px">
          El número grande de cada celda es el <strong>% cumplimiento de tráfico</strong> (tráfico real / meta de tráfico). El <strong>color del fondo</strong> indica si ese cumplimiento es bueno o malo en contexto — considera ventas reales, stock disponible y reservas. <strong>Pasa el mouse</strong> sobre la celda para ver todos los números.
        </div>
        <!-- Heatmap mes × modelo -->
        <div style="overflow-x:auto;margin-bottom:14px">
          <table class="analysis" id="an-tbl-cruce-heat">
            <thead></thead>
            <tbody></tbody>
          </table>
        </div>
        <!-- Leyenda de diagnóstico -->
        <div style="display:flex;flex-wrap:wrap;gap:14px;font-size:12px;margin-bottom:14px;padding:10px 14px;background:#f5f7fb;border-radius:6px;border:1px solid #e5e7eb;line-height:1.8">
          <strong style="text-transform:uppercase;letter-spacing:.4px;color:var(--ford-2);font-size:11px;width:100%">Cómo leer el color del fondo:</strong>
          <span><span style="display:inline-block;width:14px;height:14px;background:#c8e6c9;border-radius:3px;vertical-align:-2px"></span> ✅ <strong>verde</strong>: tráfico cumple meta Y se está vendiendo · o tráfico bajo está justificado por reservas con stock</span>
          <span><span style="display:inline-block;width:14px;height:14px;background:#fff59d;border-radius:3px;vertical-align:-2px"></span> ⚠️ <strong>amarillo</strong>: tráfico parcial (60-85% meta)</span>
          <span><span style="display:inline-block;width:14px;height:14px;background:#ffcc80;border-radius:3px;vertical-align:-2px"></span> ⚠️ <strong>naranja</strong>: tráfico cumplió pero hay sobre-stock y no se vende — problema comercial</span>
          <span><span style="display:inline-block;width:14px;height:14px;background:#ffcdd2;border-radius:3px;vertical-align:-2px"></span> 🟥 <strong>rojo</strong>: 📦 sin stock · 🟥 sobre-stock crónico · 📉 caída real sin explicación</span>
          <span><span style="display:inline-block;width:14px;height:14px;background:#eceff1;border-radius:3px;vertical-align:-2px"></span> <strong>gris</strong>: sin meta o mes en curso</span>
        </div>
        <!-- Tabla detalle del modelo activo (filtro arriba) -->
        <h4 style="font-size:13px;margin:14px 0 8px 0;color:var(--ford-2)" id="an-cruce-detail-title">Detalle por mes — Todos los modelos Ford</h4>
        <div style="overflow-x:auto">
          <table class="analysis" id="an-tbl-cruce">
            <thead><tr>
              <th>Mes</th>
              <th class="num" title="Tráfico real / meta tráfico">Tráfico</th>
              <th class="num">Cumpl tráfico</th>
              <th class="num" title="Facturas en el mes / meta de ventas">Ventas</th>
              <th class="num" title="Stock disponible al primer día del mes">Disp inicio</th>
              <th class="num" title="Stock disponible al último día del mes">Disp cierre</th>
              <th class="num" title="VINs con cliente asignado al inicio del mes">Reservas</th>
              <th>Diagnóstico</th>
            </tr></thead>
            <tbody></tbody>
          </table>
        </div>
      </div>

      <!-- INSIGHTS -->
      <div class="ford-section">
        <h3>🔎 Insights automáticos</h3>
        <div id="an-insights"></div>
      </div>

      <div class="footer-note">Informe dinámico. Cambia los filtros para ver vistas específicas (un modelo, una agencia, un mes). Se actualiza al subir nuevos cortes y metas.</div>
    </div>
  </section>

</main>

<!-- Modal de detalle (para mostrar info que en desktop es tooltip al hover) -->
<div id="cell-detail-modal" class="cell-detail-overlay" style="display:none">
  <div class="cell-detail-content">
    <button class="cell-detail-close" type="button" aria-label="Cerrar">×</button>
    <div class="cell-detail-body"></div>
  </div>
</div>

<script id="data" type="application/json">__DATA_JSON__</script>
<script>
(function(){
  const DATA = JSON.parse(document.getElementById('data').textContent);
  const MARZO = DATA.marzo, ABRIL = DATA.abril, META = DATA.meta;
  let FORD = DATA.ford;
  const FORD_MONTHS = DATA.ford_months || {};
  const BRANDS_MONTHS = DATA.brands_months || {};
  const MONTHS_CONFIG = DATA.months_config || [];
  let currentMonthFF = DATA.default_month_key || (MONTHS_CONFIG[MONTHS_CONFIG.length-1]||{}).key || '';
  let currentMonthBR = currentMonthFF;

  // ---------- TAB SWITCH ----------
  function tabSubtitle(tab){
    if(tab === 'dash'){
      return MARZO.label + ' vs ' + ABRIL.label;
    }
    if(tab === 'ford'){
      const c = MONTHS_CONFIG.find(x=>x.key===currentMonthFF);
      return (c?c.label:'Mes') + ' · corte al ' + (FORD.cut_date || '—');
    }
    if(tab === 'brand'){
      const c = MONTHS_CONFIG.find(x=>x.key===currentMonthBR);
      const sample = Object.values(BRANDS_DATA||{})[0];
      return (c?c.label:'Mes') + ' · corte al ' + (sample?.cut_date || '—');
    }
    if(tab === 'comp'){
      const a = MONTHS_CONFIG.find(x=>x.key===(cpstate?.monthA))?.label;
      const b = MONTHS_CONFIG.find(x=>x.key===(cpstate?.monthB))?.label;
      return (a&&b) ? `${a} vs ${b}` : 'Comparativo entre meses';
    }
    if(tab === 'inv'){
      const snap = (DATA.inventario && DATA.inventario.snapshot_date) || '—';
      return 'Oferta vs demanda · snapshot ' + snap;
    }
    if(tab === 'conv'){
      const g = DATA.conversion_data?.FORD?.global;
      return g ? `${g.n_ventas_atribuidas} de ${g.n_ventas_clientes_total} ventas atribuidas a tráfico (${g.cov_rate_pct}%)` : 'Conversión tráfico → venta';
    }
    if(tab === 'comp-imp'){
      const c = DATA.competencia_data;
      return c ? `Importaciones Ford · ORGU ${c.totales.orgu_share_2025}% → ${c.totales.orgu_share_2026}% (${c.totales.delta_share_total>=0?'+':''}${c.totales.delta_share_total} pts)` : 'Competencia';
    }
    if(tab === 'xiy'){
      const x = DATA.xiy;
      if(!x) return 'Inversión Digital · datos no disponibles';
      const meses = (x.months_order && x.months_order.length)
        ? `${x.months_order[0]}-${x.months_order[x.months_order.length-1]}`
        : 'Ene-Abr';
      const tot = x.total_general || 0;
      return `Inversión Digital · ${meses} 2026 · USD ${tot.toLocaleString('es-EC',{maximumFractionDigits:0})} total`;
    }
    if(tab === 'otros'){
      return 'Análisis privados · acceso restringido';
    }
    if(tab === 'embudo'){
      const e = DATA.embudo_data;
      if(!e) return 'Embudo de ventas · datos no disponibles';
      return 'Embudo de ventas por modelo y concesionario';
    }
    return '';
  }
  function setTopbarSub(tab){
    const el = document.getElementById('topbar-sub');
    if(el) el.textContent = tabSubtitle(tab);
  }
  document.querySelectorAll('.tab-btn').forEach(btn=>{
    btn.addEventListener('click',()=>{
      document.querySelectorAll('.tab-btn').forEach(b=>b.classList.remove('active'));
      document.querySelectorAll('.tab-panel').forEach(p=>p.classList.remove('active'));
      btn.classList.add('active');
      const tab = btn.dataset.tab;
      document.getElementById('tab-'+tab).classList.add('active');
      setTopbarSub(tab);
    });
  });
  // Initial subtitle (matches initial active tab)
  setTopbarSub(document.querySelector('.tab-btn.active')?.dataset.tab || 'dash');

  // ─────────── MODAL DE DETALLE (tap-to-show en mobile) ───────────
  // En desktop el atributo title="" muestra tooltip nativo al hover.
  // En mobile no hay hover — interceptamos el click en celdas con title
  // y mostramos el contenido en un modal flotante.
  const isTouchDevice = (window.matchMedia && window.matchMedia('(hover: none)').matches)
                        || ('ontouchstart' in window);
  const cellModal     = document.getElementById('cell-detail-modal');
  const cellModalBody = cellModal.querySelector('.cell-detail-body');

  function openCellDetail(htmlOrText, isHtml){
    if(isHtml){ cellModalBody.innerHTML = htmlOrText; }
    else { cellModalBody.textContent = htmlOrText; }
    cellModal.style.display = 'flex';
  }
  function closeCellDetail(){ cellModal.style.display = 'none'; cellModalBody.textContent = ''; }
  cellModal.addEventListener('click', e=>{ if(e.target === cellModal) closeCellDetail(); });
  cellModal.querySelector('.cell-detail-close').addEventListener('click', closeCellDetail);
  document.addEventListener('keydown', e=>{ if(e.key==='Escape' && cellModal.style.display!=='none') closeCellDetail(); });

  // Detectar tap en celdas/elementos con title attribute en mobile.
  // En desktop dejamos el comportamiento default (tooltip nativo).
  if(isTouchDevice){
    document.body.addEventListener('click', e=>{
      let el = e.target;
      // Subir hasta encontrar un elemento con title
      while(el && el !== document.body && !el.hasAttribute('title')) el = el.parentElement;
      if(!el || el === document.body) return;
      const titleText = el.getAttribute('title');
      if(!titleText || titleText.length < 4) return;
      // Excluir formularios/links
      if(['INPUT','SELECT','BUTTON','A'].includes(el.tagName)) return;
      e.preventDefault();
      // Quitar temporalmente para que no se muestre tooltip nativo después
      el.dataset._titleBackup = titleText;
      el.removeAttribute('title');
      setTimeout(()=>{ if(el.dataset._titleBackup){ el.setAttribute('title', el.dataset._titleBackup); delete el.dataset._titleBackup; } }, 200);
      openCellDetail(titleText, false);
    }, true);
  }

  // ---------- HELPERS ----------
  const fmt = n => (n==null||isNaN(n))?'—':Number(n).toLocaleString('es-EC');
  const pct = (a,b)=> b>0? (100*a/b).toFixed(1)+'%':'—';
  const CLEAN_MODEL = m => m && m !== 'NAN' && m !== 'nan';
  const CLEAN_BRAND = b => b && b !== 'nan';
  const deltaCell = d => d>0?`<span class="delta-pos">▲ ${d}</span>`:d<0?`<span class="delta-neg">▼ ${Math.abs(d)}</span>`:`<span class="delta-zero">— 0</span>`;
  const cumplClass = p => p>=100?'green':p>=70?'yellow':'red';
  function topN(obj,n,filter){
    let e = Object.entries(obj||{});
    if(filter) e = e.filter(([k])=>filter(k));
    return e.sort((a,b)=>b[1]-a[1]).slice(0,n);
  }
  function fillSelect(id, items){
    const el = document.getElementById(id);
    items.forEach(v=>{ const o=document.createElement('option'); o.value=v; o.textContent=v; el.appendChild(o); });
  }

  // =========================================================
  //                DASHBOARD (tab 1) — UNCHANGED
  // =========================================================
  const marcas = Array.from(new Set([...Object.keys(MARZO.byBrand),...Object.keys(ABRIL.byBrand)])).filter(CLEAN_BRAND).sort();
  const modelos = Array.from(new Set([...Object.keys(MARZO.byModel),...Object.keys(ABRIL.byModel)])).filter(CLEAN_MODEL).sort();
  const agencias = Array.from(new Set([...Object.keys(MARZO.byAgency),...Object.keys(ABRIL.byAgency)])).sort();
  fillSelect('f-marca', marcas); fillSelect('f-modelo', modelos); fillSelect('f-agencia', agencias);

  const zoomAgList = Object.entries(ABRIL.byAgency).sort((a,b)=>b[1]-a[1]).map(e=>e[0]);
  zoomAgList.forEach(ag=>{ const o=document.createElement('option'); o.value=ag; o.textContent=ag; document.getElementById('zoom-agencia').appendChild(o); });

  const state = { marca:'', modelo:'', agencia:'' };
  function setFilters(){
    state.marca = document.getElementById('f-marca').value;
    state.modelo = document.getElementById('f-modelo').value;
    state.agencia = document.getElementById('f-agencia').value;
    renderAll();
  }
  ['f-marca','f-modelo','f-agencia'].forEach(id=>document.getElementById(id).addEventListener('change',setFilters));
  document.getElementById('btn-reset').addEventListener('click',()=>{
    ['f-marca','f-modelo','f-agencia'].forEach(id=>document.getElementById(id).value='');
    setFilters();
  });

  function filteredTotal(p){
    if(state.agencia){
      const det = (p.agencyDetail||{})[state.agencia]; if(!det) return 0;
      if(state.modelo){ return ((p.agencyModel||{})[state.agencia]||{})[state.modelo]||0; }
      return det.total||0;
    }
    if(state.modelo) return (p.byModel||{})[state.modelo]||0;
    if(state.marca)  return (p.byBrand||{})[state.marca]||0;
    return p.total||0;
  }
  function filteredByAgency(p){
    if(state.modelo){
      const out={}; Object.entries(p.agencyModel||{}).forEach(([ag,m])=>out[ag]=m[state.modelo]||0); return out;
    }
    if(state.marca){
      const share = (p.byBrand?.[state.marca]||0) / (p.total||1);
      const out={}; Object.entries(p.byAgency||{}).forEach(([ag,v])=>out[ag]=Math.round(v*share)); return out;
    }
    return p.byAgency||{};
  }
  const filteredByChannel = p => state.agencia? (p.agencyChannel||{})[state.agencia]||{} : (p.byChannel||{});
  const filteredByModel = p => state.agencia? (p.agencyModel||{})[state.agencia]||{} : (p.byModel||{});
  const filteredByStatus = p => state.agencia? (p.agencyStatus||{})[state.agencia]||p.byStatus||{} : (p.byStatus||{});

  Chart.defaults.font.family = "Inter,system-ui,-apple-system,'Segoe UI',Roboto,Arial,sans-serif";
  Chart.defaults.font.size = 12;
  Chart.defaults.color = '#1c2434';
  Chart.defaults.plugins.legend.labels.boxWidth = 10;
  Chart.defaults.plugins.legend.labels.boxHeight = 10;
  // Register datalabels but disable globally; enable per-chart.
  if(window.ChartDataLabels){ Chart.register(ChartDataLabels); Chart.defaults.plugins.datalabels = { display:false }; }
  let charts = {};
  function destroy(k){ if(charts[k]){ charts[k].destroy(); delete charts[k]; } }

  function renderKpis(){
    const mTot = filteredTotal(MARZO), aTot = filteredTotal(ABRIL);
    const daysLab = META.abril.days_lab, daysTrans = META.abril.days_trans;
    const velocity = daysTrans? (aTot/daysTrans) : 0;
    const projection = Math.round(velocity * daysLab);
    document.getElementById('kpi-marzo').textContent = fmt(mTot);
    document.getElementById('kpi-marzo-hint').textContent = MARZO.label + (state.agencia||state.modelo||state.marca?' · filtrado':'');
    document.getElementById('kpi-abril').textContent = fmt(aTot);
    document.getElementById('kpi-abril-hint').textContent = ABRIL.label + ' · vel. ' + velocity.toFixed(1) + '/día';
    document.getElementById('kpi-proj').textContent = fmt(projection);
    document.getElementById('kpi-proj-hint').textContent = 'A '+daysLab+' días lab. · lineal';
    if(state.marca && state.marca !== 'FORD'){ document.getElementById('kpi-meta').textContent='—'; document.getElementById('kpi-meta-hint').textContent='No aplica · meta es sólo Ford'; }
    else if(state.agencia){ document.getElementById('kpi-meta').textContent='—'; document.getElementById('kpi-meta-hint').textContent='Ver reporte Ford por agencia'; }
    else { document.getElementById('kpi-meta').textContent = fmt(META.abril.meta_total); document.getElementById('kpi-meta-hint').textContent = 'Abril · agencias Ford (oficial)'; }
  }
  function renderAgencyTable(){
    const mar = filteredByAgency(MARZO), abr = filteredByAgency(ABRIL);
    const all = Array.from(new Set([...Object.keys(mar),...Object.keys(abr)])).sort((a,b)=>(abr[b]||0)-(abr[a]||0));
    const maxAll = Math.max(1, ...all.map(a=>Math.max(mar[a]||0,abr[a]||0)));
    document.querySelector('#tbl-agencias tbody').innerHTML = all.map(ag=>{
      const mv=mar[ag]||0, av=abr[ag]||0;
      const mw=Math.round(100*mv/maxAll), aw=Math.round(100*av/maxAll);
      return `<tr><td><strong>${ag}</strong></td><td class="num">${fmt(mv)}</td><td class="num">${fmt(av)}</td><td class="num">${deltaCell(av-mv)}</td>
        <td class="bar-cell"><div class="bar-dual">
          <div class="row"><span>Mar</span><div class="bar-outer" style="flex:1"><div class="bar-inner marzo" style="width:${mw}%"></div></div></div>
          <div class="row"><span>Abr</span><div class="bar-outer" style="flex:1"><div class="bar-inner" style="width:${aw}%"></div></div></div>
        </div></td></tr>`;
    }).join('');
  }
  function renderCanales(){
    destroy('canales');
    const ch = filteredByChannel(ABRIL);
    const entries = Object.entries(ch).filter(([,v])=>v>0).sort((a,b)=>b[1]-a[1]);
    charts.canales = new Chart(document.getElementById('chart-canales'),{
      type:'bar', data:{labels:entries.map(e=>e[0]), datasets:[{label:'Abril', data:entries.map(e=>e[1]), backgroundColor:'#2e5090', borderRadius:6, maxBarThickness:22}]},
      options:{indexAxis:'y', plugins:{legend:{display:false},tooltip:{callbacks:{label:c=>' '+fmt(c.parsed.x)+' registros'}}},
        scales:{x:{beginAtZero:true,ticks:{precision:0}},y:{ticks:{font:{size:11}}}}, maintainAspectRatio:false}
    });
  }
  function renderTrend(){
    destroy('trend');
    const a = ABRIL.daily.cum, m = MARZO.daily.cum;
    const days = Array.from(new Set([...Object.keys(a),...Object.keys(m)])).map(n=>parseInt(n)).sort((x,y)=>x-y);
    charts.trend = new Chart(document.getElementById('chart-trend'),{
      type:'line', data:{labels:days.map(String), datasets:[
        {label:'Marzo (cierre)', data:days.map(d=>m[d]!=null?m[d]:null), borderColor:'#9aa8c1', backgroundColor:'rgba(154,168,193,.15)', fill:true, tension:.25, pointRadius:2, borderWidth:2, borderDash:[4,3]},
        {label:'Abril (acum.)',  data:days.map(d=>a[d]!=null?a[d]:null), borderColor:'#003478', backgroundColor:'rgba(0,52,120,.15)', fill:true, tension:.25, pointRadius:2, borderWidth:2.5}
      ]},
      options:{plugins:{legend:{position:'bottom'},tooltip:{callbacks:{label:c=>' '+c.dataset.label+': '+(c.parsed.y==null?'—':fmt(c.parsed.y))}}},
        scales:{y:{beginAtZero:true,ticks:{precision:0}},x:{title:{display:true,text:'Día del mes',color:'#6b7280'}}}, maintainAspectRatio:false, interaction:{mode:'index',intersect:false}}
    });
  }
  function renderModelos(){
    destroy('modelos');
    const entries = topN(filteredByModel(ABRIL),10,CLEAN_MODEL);
    charts.modelos = new Chart(document.getElementById('chart-modelos'),{
      type:'bar', data:{labels:entries.map(e=>e[0]), datasets:[{label:'Abril', data:entries.map(e=>e[1]), backgroundColor:'#5c84d6', borderRadius:6, maxBarThickness:22}]},
      options:{indexAxis:'y', plugins:{legend:{display:false},tooltip:{callbacks:{label:c=>' '+fmt(c.parsed.x)+' registros'}}}, scales:{x:{beginAtZero:true,ticks:{precision:0}}}, maintainAspectRatio:false}
    });
  }
  function renderFunnel(){
    const order = ['Indagación','Cotización','Demostración','Cierre','Entrega'];
    const s = filteredByStatus(ABRIL);
    const max = Math.max(1, ...order.map(k=>s[k]||0));
    document.getElementById('funnel').innerHTML = order.map(k=>{
      const v=s[k]||0, w=Math.max(2,Math.round(100*v/max));
      return `<div class="funnel-row"><div class="fname">${k}</div><div class="fbar"><div class="finner" style="width:${w}%">${v>0?fmt(v):''}</div></div><div class="fpct">${max>0?(100*v/max).toFixed(0)+'%':'—'}</div></div>`;
    }).join('');
    document.getElementById('funnel-rate').textContent = pct(s['Cierre']||0, s['Cotización']||0);
    document.getElementById('funnel-delivery').textContent = pct(s['Entrega']||0, s['Cotización']||0);
  }
  function renderZoom(){
    const ag = document.getElementById('zoom-agencia').value || zoomAgList[0];
    if(!ag) return;
    document.getElementById('zoom-agencia').value = ag;
    const det = (ABRIL.agencyDetail||{})[ag];
    document.getElementById('zoom-badge').textContent = det? fmt(det.total)+' registros · Abril' : 'Sin datos';
    const ul = (id,obj,filter)=>{
      const list = Object.entries(obj||{}).filter(([k,v])=>v>0 && (!filter||filter(k))).sort((a,b)=>b[1]-a[1]).slice(0,8);
      document.getElementById(id).innerHTML = list.length
        ? list.map(([k,v])=>`<li><span title="${k}">${k.length>36?k.slice(0,33)+'…':k}</span><span class="v">${fmt(v)}</span></li>`).join('')
        : '<li style="color:#9aa0a6">— sin datos —</li>';
    };
    if(!det){ ['zoom-canal','zoom-asesor','zoom-campana','zoom-modelo'].forEach(id=>document.getElementById(id).innerHTML='<li style="color:#9aa0a6">— sin datos —</li>'); document.getElementById('zoom-funnel').textContent='—'; return; }
    ul('zoom-canal', det.byChannel);
    ul('zoom-asesor', det.topAdvisors);
    ul('zoom-campana', det.topCampaigns, k=> k && k!=='nan' && k!=='Ninguna');
    ul('zoom-modelo', det.byModel, CLEAN_MODEL);
    const f = det.byStatus||{};
    document.getElementById('zoom-funnel').textContent = ['Indagación','Cotización','Demostración','Cierre','Entrega'].map(k=>`${k}: ${f[k]||0}`).join(' · ');
  }
  document.getElementById('zoom-agencia').addEventListener('change',renderZoom);

  function renderAll(){ renderKpis(); renderAgencyTable(); renderCanales(); renderTrend(); renderModelos(); renderFunnel(); }
  renderAll(); renderZoom();

  // =========================================================
  //                   FORD TAB (dinámico)
  // =========================================================
  // Populate month selector (Ford)
  (function initFFMonth(){
    const sel = document.getElementById('ff-month');
    if(!sel) return;
    sel.innerHTML = MONTHS_CONFIG.map(c=>`<option value="${c.key}" ${c.key===currentMonthFF?'selected':''}>${c.label}</option>`).join('');
  })();
  // Populate Ford filters
  fillSelect('ff-zona', FORD.zone_order);
  fillSelect('ff-agencia', [...FORD.dealer_order,'Otros']);
  fillSelect('ff-modelo', FORD.model_order);

  const fstate = { zona:'', agencia:'', modelo:'',
                   sort:{proj_model:{k:'curr',dir:'desc'}, proj_agency:{k:'curr',dir:'desc'}, ranking:{k:'curr',dir:'desc'}} };

  // Helper: which agencies are active given zona filter (and optional agencia filter)
  function activeDealers(){
    const pool = fstate.zona ? (FORD.zones[fstate.zona].dealers) : FORD.dealer_order;
    return fstate.agencia ? (pool.includes(fstate.agencia)? [fstate.agencia] : []) : pool;
  }
  function includeDealer(d){ return activeDealers().includes(d); }
  function includeModel(m){ return !fstate.modelo || fstate.modelo===m; }

  // Aggregate Ford totals under current filters
  function ffAggregate(){
    // Sin filtro de zona/agencia, usar el dato canónico de FORD.models (incluye "Otros")
    // para que coincida con Movimientos y Proyección por modelo.
    const dealers = activeDealers();
    const models = fstate.modelo? [fstate.modelo] : FORD.model_order;
    const noScopeFilter = !fstate.zona && !fstate.agencia;
    let curr=0, prev=0;
    if(noScopeFilter){
      models.forEach(m=>{
        curr += FORD.models[m]?.curr || 0;
        prev += FORD.models[m]?.prev || 0;
      });
    } else {
      // Filtro de zona/agencia activo: sumar matrix_cnt y matrix_cnt_prev sobre dealers visibles
      dealers.forEach(d=>{
        models.forEach(m=>{
          curr += (FORD.matrix_cnt[m]||{})[d]||0;
          prev += (FORD.matrix_cnt_prev[m]||{})[d]||0;
        });
      });
    }
    // Meta: siempre suma de matrix_meta sobre dealers atribuidos (Otros no tiene meta)
    let meta=0;
    dealers.forEach(d=>{
      models.forEach(m=>{ meta += (FORD.matrix_meta[m]||{})[d]||0; });
    });
    const days_lab = FORD.days_lab, days_trans = FORD.days_trans;
    const vel = days_trans? curr/days_trans : 0;
    const proj = Math.round(vel * days_lab);
    const cumpl = meta>0? Math.round(100*proj/meta) : null;
    return {curr, prev, delta:curr-prev, meta, days_lab, days_trans, velocity:vel, projection:proj, cumpl_proj:cumpl};
  }

  // ----- FILTER SUMMARY CHIPS -----
  function ffRenderFilterSummary(){
    const wrap = document.getElementById('ff-filter-summary');
    const chips=[];
    if(fstate.zona)    chips.push({k:'zona',label:'Zona: '+fstate.zona});
    if(fstate.agencia) chips.push({k:'agencia',label:'Agencia: '+fstate.agencia});
    if(fstate.modelo)  chips.push({k:'modelo',label:'Modelo: '+fstate.modelo});
    wrap.innerHTML = chips.length
      ? '<span style="font-weight:600;color:var(--ink)">Filtros activos:</span> ' +
        chips.map(c=>`<span class="chip">${c.label}<button data-k="${c.k}" title="Quitar">×</button></span>`).join('')
      : '<span style="color:var(--muted)">Sin filtros — viendo todo el tráfico Ford (7 agencias, 8 modelos)</span>';
    wrap.querySelectorAll('button[data-k]').forEach(b=>b.addEventListener('click',()=>{
      fstate[b.dataset.k] = '';
      document.getElementById('ff-'+b.dataset.k).value='';
      ffRenderAll();
    }));
  }

  // ----- HERO: gauge + stats + progress -----
  function ffRenderHero(){
    const k = ffAggregate();
    // Hero stats
    document.getElementById('hs-total-v').textContent = fmt(k.curr);
    document.getElementById('hs-total-d').textContent = 'Hasta '+FORD.cut_date+' · '+filterBadge();
    const dSign = k.delta>0?'+':'';
    document.getElementById('hs-delta-v').textContent = dSign + k.delta;
    const hsDelta = document.getElementById('hs-delta');
    hsDelta.classList.remove('good','warn','bad');
    hsDelta.classList.add(k.delta>0?'good':k.delta<0?'bad':'warn');
    document.getElementById('hs-delta-d').textContent = 'vs '+(FORD.prev_date||'corte anterior');
    document.getElementById('hs-vel-v').textContent = k.velocity.toFixed(1);
    document.getElementById('hs-proj-v').textContent = fmt(k.projection);
    document.getElementById('hs-proj-d').textContent = 'A '+k.days_lab+' días lab. (lineal)';

    // Avance del mes (días laborables)
    const pctMes = k.days_lab>0 ? Math.round(100*k.days_trans/k.days_lab) : 0;
    document.getElementById('hm-summary').innerHTML =
      `Día laborable <strong>${k.days_trans}</strong> de <strong>${k.days_lab}</strong> · <strong>${pctMes}%</strong> del mes`;
    document.getElementById('hm-fill').style.width = pctMes+'%';
    document.getElementById('hm-labels').textContent = 'Día '+k.days_lab;

    // Hero progress bar: shows Actual (solid), Proyección (lighter fill), Meta (marker)
    const maxScale = Math.max(k.meta||0, k.projection||0, k.curr||0, 1);
    const pctCurr = 100*k.curr/maxScale;
    const pctProj = 100*k.projection/maxScale;
    const pctMeta = k.meta>0? 100*k.meta/maxScale : null;
    document.getElementById('hp-actual').style.width = pctCurr+'%';
    document.getElementById('hp-proj').style.width = pctProj+'%';
    document.getElementById('hp-proj').style.background = k.cumpl_proj==null?'linear-gradient(90deg,#003478,#5c84d6)'
      : k.cumpl_proj>=100?'linear-gradient(90deg,#2e7d32,#66bb6a)'
      : k.cumpl_proj>=70 ?'linear-gradient(90deg,#f57f17,#ffb74d)'
      :                    'linear-gradient(90deg,#c62828,#ef5350)';
    const meta = document.getElementById('hp-meta');
    if(pctMeta==null){ meta.style.display='none'; }
    else { meta.style.display=''; meta.style.left = pctMeta+'%'; }
    document.getElementById('hp-summary').innerHTML =
      `Actual <strong>${fmt(k.curr)}</strong> → Proyección <strong>${fmt(k.projection)}</strong>${k.meta>0?` · Meta <strong>${fmt(k.meta)}</strong>`:''}`;
    document.getElementById('hp-labels').textContent = fmt(maxScale);

    // Gauge
    ffRenderGauge(k.cumpl_proj);
    // Value in gauge center
    document.getElementById('ff-gauge-value').textContent = k.cumpl_proj==null? '—' : k.cumpl_proj+'%';
    const tag = document.getElementById('ff-gauge-tag');
    if(k.cumpl_proj==null){ tag.textContent='sin meta'; tag.style.background='#f5f5f5'; tag.style.color='#999'; }
    else if(k.cumpl_proj>=100){ tag.textContent='🟢 en meta'; tag.style.background='var(--green-bg)'; tag.style.color='var(--green-tx)'; }
    else if(k.cumpl_proj>=70){ tag.textContent='🟡 alerta'; tag.style.background='var(--yellow-bg)'; tag.style.color='var(--yellow-tx)'; }
    else{ tag.textContent='🔴 riesgo'; tag.style.background='var(--red-bg)'; tag.style.color='var(--red-tx)'; }
  }
  function ffRenderGauge(cumpl){
    destroy('ff-gauge');
    // Escala 0–100: si cumple o supera meta el arco se llena completo;
    // si está por debajo, la sección gris muestra exactamente el gap faltante.
    let val, rem;
    if(cumpl==null){ val=0; rem=100; }
    else if(cumpl>=100){ val=100; rem=0; }
    else { val=cumpl; rem=100-cumpl; }
    const color = cumpl==null?'#d1d5db'
      : cumpl>=100?'#2e7d32'
      : cumpl>=70 ?'#f57f17'
      :            '#c62828';
    charts['ff-gauge'] = new Chart(document.getElementById('ff-gauge'),{
      type:'doughnut',
      data:{labels:['Cumpl','Resto'], datasets:[{data:[val,rem], backgroundColor:[color,'#eef1f5'], borderWidth:0, circumference:270, rotation:225, cutout:'78%'}]},
      options:{plugins:{legend:{display:false},tooltip:{enabled:false},datalabels:{display:false}}, animation:{duration:600}, maintainAspectRatio:false}
    });
  }

  function filterBadge(){
    const parts=[];
    if(fstate.zona) parts.push('Zona='+fstate.zona);
    if(fstate.agencia) parts.push('Agencia='+fstate.agencia);
    if(fstate.modelo) parts.push('Modelo='+fstate.modelo);
    return parts.length? parts.join(' · ') : 'Todas las agencias Ford';
  }

  // ----- MOVEMENTS as horizontal impact bars (respeta filtros) -----
  function ffRenderMovements(){
    document.getElementById('ff-mov-sub').textContent = (FORD.prev_date||'') + ' → ' + FORD.cut_date + ' · magnitud del cambio por modelo';
    const wrap = document.getElementById('ff-movements');
    const noScopeFilter = !fstate.zona && !fstate.agencia;
    const dealers = activeDealers();
    const modelsList = (fstate.modelo? [fstate.modelo] : FORD.model_order);
    const items = modelsList.map(m=>{
      let curr, prev;
      if(noScopeFilter){
        curr = FORD.models[m]?.curr || 0;
        prev = FORD.models[m]?.prev || 0;
      } else {
        curr = dealers.reduce((s,d)=>s+((FORD.matrix_cnt[m]||{})[d]||0),0);
        prev = dealers.reduce((s,d)=>s+((FORD.matrix_cnt_prev[m]||{})[d]||0),0);
      }
      return {model:m, prev, curr, delta:curr-prev};
    });
    const maxAbs = Math.max(1, ...items.map(m=>Math.abs(m.delta)));
    items.sort((a,b)=>Math.abs(b.delta)-Math.abs(a.delta) || b.curr-a.curr);
    wrap.innerHTML = items.map(mv=>{
      const w = Math.max(2, Math.round(100*Math.abs(mv.delta)/maxAbs));
      const cls = mv.delta>0?'pos':mv.delta<0?'neg':'';
      const sign = mv.delta>0?'+':mv.delta<0?'':'';
      const pct = mv.prev>0? ` (${sign}${Math.round(100*mv.delta/mv.prev)}%)` : '';
      return `<div class="mov-bar-row">
        <div class="mname">${mv.model}</div>
        <div class="mbar">${mv.delta!==0?`<div class="mfill ${cls}" style="width:${w}%">${sign}${mv.delta}</div>`:'<div style="padding:2px 6px;font-size:10px;color:var(--muted)">sin cambio</div>'}</div>
        <div class="mval">${mv.prev} → <strong>${mv.curr}</strong>${pct}</div>
      </div>`;
    }).join('') || '<div style="color:var(--muted);text-align:center;padding:12px">Sin datos para esta selección</div>';
  }

  // ----- CHART: Proyección vs Meta por agencia -----
  function ffRenderAgencyChart(){
    destroy('ff-chart-agency');
    const pool = fstate.zona? FORD.zones[fstate.zona].dealers : FORD.dealer_order;
    const rows = pool.map(d=>{
      let curr, meta;
      if(fstate.modelo){
        curr = (FORD.matrix_cnt[fstate.modelo]||{})[d]||0;
        meta = (FORD.matrix_meta[fstate.modelo]||{})[d]||0;
      } else {
        curr = FORD.dealers[d].curr; meta = FORD.dealers[d].meta;
      }
      const proj = Math.round((FORD.days_trans? curr/FORD.days_trans:0) * FORD.days_lab);
      const cumpl = meta>0? 100*proj/meta : null;
      return {d, proj, meta, cumpl, gap: meta>0? meta-proj : 0};
    });
    rows.sort((a,b)=> b.gap - a.gap); // mayor gap (más atrás) arriba
    const labels = rows.map(r=>r.d);
    const metaVals = rows.map(r=>r.meta);
    const projVals = rows.map(r=>r.proj);
    const maxVal = Math.max(1, ...metaVals, ...projVals);
    charts['ff-chart-agency'] = new Chart(document.getElementById('ff-chart-agency'),{
      type:'bar',
      data:{labels, datasets:[
        {label:'Meta', data:metaVals, backgroundColor:'rgba(154,168,193,.45)', borderRadius:4, maxBarThickness:18, borderColor:'#9aa8c1', borderWidth:1},
        {label:'Proyección', data:projVals, backgroundColor:'#2e5090', borderRadius:4, maxBarThickness:18}
      ]},
      options:{
        indexAxis:'y', layout:{padding:{right:40}},
        plugins:{
          legend:{position:'bottom',labels:{boxWidth:10,boxHeight:10,font:{size:11}}},
          tooltip:{callbacks:{afterLabel:c=>{const r=rows[c.dataIndex]; return r.cumpl==null?'Sin meta':`Cumpl. ${r.cumpl.toFixed(0)}%`;}}},
          datalabels:{
            display:ctx=>ctx.dataset.data[ctx.dataIndex]>0,
            anchor:'end', align:'end', offset:2,
            font:{size:10,weight:'600'},
            color:ctx=>ctx.datasetIndex===1?'#2e5090':'#6b7280',
            formatter:v=>fmt(v)
          }
        },
        scales:{x:{beginAtZero:true,ticks:{precision:0},max:maxVal*1.15}, y:{ticks:{font:{size:11}}}},
        maintainAspectRatio:false, onClick:(_,els)=>{ if(els.length){ const ag=rows[els[0].index].d; fstate.agencia = fstate.agencia===ag?'':ag; document.getElementById('ff-agencia').value=fstate.agencia; ffRenderAll(); } }
      }
    });
  }

  // ----- CHART: Proyección vs Meta por modelo -----
  function ffRenderModelChart(){
    destroy('ff-chart-model');
    const models = FORD.model_order.filter(includeModel);
    const dealers = activeDealers();
    const rows = models.map(m=>{
      const curr = dealers.reduce((s,d)=>s+((FORD.matrix_cnt[m]||{})[d]||0),0);
      const meta = dealers.reduce((s,d)=>s+((FORD.matrix_meta[m]||{})[d]||0),0);
      const proj = Math.round((FORD.days_trans? curr/FORD.days_trans:0) * FORD.days_lab);
      const cumpl = meta>0? 100*proj/meta : null;
      return {m, proj, meta, cumpl, gap: meta>0? meta-proj : 0};
    });
    rows.sort((a,b)=> b.gap - a.gap);
    const labels = rows.map(r=>r.m);
    const metaVals = rows.map(r=>r.meta);
    const projVals = rows.map(r=>r.proj);
    const maxVal = Math.max(1, ...metaVals, ...projVals);
    charts['ff-chart-model'] = new Chart(document.getElementById('ff-chart-model'),{
      type:'bar',
      data:{labels, datasets:[
        {label:'Meta', data:metaVals, backgroundColor:'rgba(154,168,193,.45)', borderRadius:4, maxBarThickness:18, borderColor:'#9aa8c1', borderWidth:1},
        {label:'Proyección', data:projVals, backgroundColor:'#2e5090', borderRadius:4, maxBarThickness:18}
      ]},
      options:{indexAxis:'y', layout:{padding:{right:40}},
        plugins:{legend:{position:'bottom',labels:{boxWidth:10,boxHeight:10,font:{size:11}}},
          tooltip:{callbacks:{afterLabel:c=>{const r=rows[c.dataIndex]; return r.cumpl==null?'Sin meta':`Cumpl. ${r.cumpl.toFixed(0)}%`;}}},
          datalabels:{
            display:ctx=>ctx.dataset.data[ctx.dataIndex]>0,
            anchor:'end', align:'end', offset:2,
            font:{size:10,weight:'600'},
            color:ctx=>ctx.datasetIndex===1?'#2e5090':'#6b7280',
            formatter:v=>fmt(v)
          }
        },
        scales:{x:{beginAtZero:true,ticks:{precision:0},max:maxVal*1.15}, y:{ticks:{font:{size:11}}}},
        maintainAspectRatio:false, onClick:(_,els)=>{ if(els.length){ const m=rows[els[0].index].m; fstate.modelo = fstate.modelo===m?'':m; document.getElementById('ff-modelo').value=fstate.modelo; ffRenderAll(); } }
      }
    });
  }

  // ----- CHART: Zone donut -----
  function ffRenderZoneChart(){
    destroy('ff-chart-zone');
    const models = fstate.modelo? [fstate.modelo] : FORD.model_order;
    const rows = FORD.zone_order.map(z=>{
      const dealers = FORD.zones[z].dealers;
      let curr = 0;
      dealers.forEach(d => models.forEach(m => curr += (FORD.matrix_cnt[m]||{})[d]||0));
      return {z, curr};
    });
    const total = rows.reduce((a,b)=>a+b.curr,0) || 1;
    charts['ff-chart-zone'] = new Chart(document.getElementById('ff-chart-zone'),{
      type:'doughnut',
      data:{labels:rows.map(r=>r.z), datasets:[{data:rows.map(r=>r.curr),
        backgroundColor:['#003478','#2e5090','#5c84d6','#9aa8c1'], borderWidth:2, borderColor:'#fff'}]},
      options:{cutout:'55%',
        layout:{padding:{top:20,bottom:20,left:26,right:26}},
        plugins:{
          legend:{position:'bottom',labels:{boxWidth:8,boxHeight:8,font:{size:10},padding:6}},
          tooltip:{callbacks:{label:c=>` ${c.label}: ${c.parsed} (${(100*c.parsed/total).toFixed(1)}%)`}},
          datalabels:{
            display:ctx=>ctx.dataset.data[ctx.dataIndex]>0,
            anchor:'end', align:'end', offset:6, clamp:true,
            color:'#1c2434',
            font:{size:10,weight:'700'},
            textAlign:'center',
            backgroundColor:'rgba(255,255,255,.92)',
            borderColor:'rgba(0,52,120,.15)', borderWidth:1, borderRadius:4,
            padding:{top:1,bottom:1,left:5,right:5},
            formatter:(v,ctx)=>`${v} · ${(100*v/total).toFixed(0)}%`
          }
        },
        maintainAspectRatio:false,
        onClick:(_,els)=>{ if(els.length){ const z=rows[els[0].index].z; fstate.zona=fstate.zona===z?'':z; document.getElementById('ff-zona').value=fstate.zona; ffRenderAll(); } }
      }
    });
  }

  function ffRenderZonas(){
    const tbody = document.querySelector('#ff-zonas tbody');
    const rows = FORD.zone_order.map((z,i)=>{
      const zd = FORD.zones[z];
      let curr=0, prev=0;
      const modelsToSum = fstate.modelo? [fstate.modelo]: FORD.model_order;
      zd.dealers.forEach(d=>{
        modelsToSum.forEach(m=>{
          curr += (FORD.matrix_cnt[m]||{})[d]||0;
          prev += (FORD.matrix_cnt_prev[m]||{})[d]||0;
        });
      });
      const active = fstate.zona===z;
      return {z, prev, curr, delta:curr-prev, active};
    });
    const tCurr = rows.reduce((a,b)=>a+b.curr,0);
    const tPrev = rows.reduce((a,b)=>a+b.prev,0);
    tbody.innerHTML = rows.map(r=>{
      const pct = tCurr>0? (100*r.curr/tCurr).toFixed(1)+'%' : '—';
      return `<tr class="clickable ${r.active?'highlighted':''}" data-zona="${r.z}">
      <td class="left">${r.z}${r.active?'<span class="pill active-filter">✓</span>':''}</td>
      <td>${fmt(r.prev)}</td><td><strong>${fmt(r.curr)}</strong></td>
      <td>${deltaCell(r.delta)}</td><td>${pct}</td></tr>`;
    }).join('')
      + `<tr class="total"><td class="left">TOTAL</td><td>${fmt(tPrev)}</td><td>${fmt(tCurr)}</td><td>${deltaCell(tCurr-tPrev)}</td><td>100%</td></tr>`;
    tbody.querySelectorAll('tr.clickable').forEach(tr=>tr.addEventListener('click',()=>{
      const z = tr.dataset.zona;
      fstate.zona = fstate.zona===z?'':z;
      document.getElementById('ff-zona').value = fstate.zona;
      ffRenderAll();
    }));
  }

  function ffRenderRanking(){
    const tbody = document.querySelector('#ff-ranking tbody');
    const totCurr = ffAggregate().curr;
    const noScopeFilter = !fstate.zona && !fstate.agencia;
    const models = FORD.model_order.map(m=>{
      const curr = noScopeFilter
        ? FORD.models[m].curr
        : activeDealers().reduce((s,d)=>s+((FORD.matrix_cnt[m]||{})[d]||0),0);
      const prev = noScopeFilter
        ? FORD.models[m].prev
        : activeDealers().reduce((s,d)=>s+((FORD.matrix_cnt_prev[m]||{})[d]||0),0);
      const delta = curr - prev;
      const pct = totCurr>0? (100*curr/totCurr):0;
      return {model:m, curr, prev, delta, pct};
    });
    const s = fstate.sort.ranking;
    models.sort((a,b)=> (a[s.k]>b[s.k]?1:a[s.k]<b[s.k]?-1:0) * (s.dir==='asc'?1:-1));
    tbody.innerHTML = models.map((r,i)=>{
      const active = fstate.modelo===r.model;
      return `<tr class="clickable ${active?'highlighted':''}" data-model="${r.model}">
        <td style="color:var(--ford-2);font-weight:700">${i+1}</td>
        <td class="left">${r.model}${active?'<span class="pill active-filter">activo</span>':''}</td>
        <td><strong>${fmt(r.curr)}</strong></td>
        <td>${r.pct.toFixed(1)}%</td>
        <td>${deltaCell(r.delta)}</td></tr>`;
    }).join('');
    tbody.querySelectorAll('tr.clickable').forEach(tr=>tr.addEventListener('click',()=>{
      const m = tr.dataset.model;
      fstate.modelo = fstate.modelo===m?'':m;
      document.getElementById('ff-modelo').value = fstate.modelo;
      ffRenderAll();
    }));
    applySortIndicators('ff-ranking', s);
  }

  function ffRenderProjModel(){
    const tbody = document.querySelector('#ff-proj-model tbody');
    const noScopeFilter = !fstate.zona && !fstate.agencia;
    const rows = FORD.model_order.filter(includeModel).map(m=>{
      const curr = noScopeFilter
        ? FORD.models[m].curr
        : activeDealers().reduce((s,d)=>s+((FORD.matrix_cnt[m]||{})[d]||0),0);
      const meta = activeDealers().reduce((s,d)=>s+((FORD.matrix_meta[m]||{})[d]||0),0);
      const prev = noScopeFilter
        ? FORD.models[m].prev
        : activeDealers().reduce((s,d)=>s+((FORD.matrix_cnt_prev[m]||{})[d]||0),0);
      const delta = curr - prev;
      const vel = FORD.days_trans? curr/FORD.days_trans : 0;
      const proj = Math.round(vel * FORD.days_lab);
      const cumpl = meta>0? Math.round(100*proj/meta) : null;
      return {model:m, prev, curr, delta, meta, proj, cumpl};
    });
    const s = fstate.sort.proj_model;
    rows.sort((a,b)=>{
      let av=a[s.k], bv=b[s.k]; if(av==null) av=-1; if(bv==null) bv=-1;
      return (av>bv?1:av<bv?-1:0) * (s.dir==='asc'?1:-1);
    });
    const totals = rows.reduce((t,r)=>({
      prev:t.prev+r.prev, curr:t.curr+r.curr, meta:t.meta+r.meta
    }),{prev:0,curr:0,meta:0});
    // Recomputar proj desde total curr (no sumar valores ya redondeados de cada modelo)
    totals.proj = Math.round((FORD.days_trans? totals.curr/FORD.days_trans : 0) * FORD.days_lab);
    const totCumpl = totals.meta>0? Math.round(100*totals.proj/totals.meta) : null;
    tbody.innerHTML = rows.map(r=>{
      const active = fstate.modelo===r.model;
      return `<tr class="clickable ${active?'highlighted':''}" data-model="${r.model}">
        <td class="left">${r.model}${active?'<span class="pill active-filter">✓</span>':''}</td>
        <td>${fmt(r.prev)}</td><td><strong>${fmt(r.curr)}</strong></td>
        <td>${deltaCell(r.delta)}</td>
        <td>${r.meta>0?fmt(r.meta):'—'}</td>
        <td>${projBarCell(r.proj, r.meta, r.cumpl)}</td>
        <td>${r.cumpl==null?'<span class="cumpl grey">N/A</span>':`<span class="cumpl ${cumplClass(r.cumpl)}">${r.cumpl}%</span>`}</td>
      </tr>`;
    }).join('') + `<tr class="total">
      <td class="left">TOTAL</td><td>${fmt(totals.prev)}</td><td>${fmt(totals.curr)}</td>
      <td>${deltaCell(totals.curr-totals.prev)}</td><td>${fmt(totals.meta)}</td>
      <td>${projBarCell(totals.proj, totals.meta, totCumpl)}</td>
      <td>${totCumpl==null?'<span class="cumpl grey">N/A</span>':`<span class="cumpl ${cumplClass(totCumpl)}">${totCumpl}%</span>`}</td>
    </tr>`;
    tbody.querySelectorAll('tr.clickable').forEach(tr=>tr.addEventListener('click',()=>{
      const m = tr.dataset.model;
      fstate.modelo = fstate.modelo===m?'':m;
      document.getElementById('ff-modelo').value = fstate.modelo;
      ffRenderAll();
    }));
    applySortIndicators('ff-proj-model', s);
  }

  // small helper: inline progress cell showing projection relative to meta
  function projBarCell(proj, meta, cumpl){
    if(meta<=0) return `<div>${fmt(proj)}</div>`;
    const ratio = Math.min(1.5, proj/meta);
    const w = Math.max(2, Math.round(100*ratio/1.5));
    const metaPos = Math.round(100*1/1.5); // meta marker at 66.6% since scale 0-150%
    const cls = cumplClass(cumpl);
    return `<div style="text-align:left;min-width:110px">
      <div style="font-size:11.5px;font-weight:700;margin-bottom:1px;color:var(--ink)">${fmt(proj)} <span style="color:var(--muted);font-weight:500">/ ${fmt(meta)}</span></div>
      <div class="proj-bar"><div class="pb-fill ${cls}" style="width:${w}%"></div><div class="pb-meta" style="left:${metaPos}%"></div></div>
    </div>`;
  }

  function ffRenderProjAgency(){
    const tbody = document.querySelector('#ff-proj-agency tbody');
    const pool = fstate.zona? FORD.zones[fstate.zona].dealers : FORD.dealer_order;
    const rows = pool.map(d=>{
      const curr = fstate.modelo ? ((FORD.matrix_cnt[fstate.modelo]||{})[d]||0) : FORD.dealers[d].curr;
      const prev = fstate.modelo ? ((FORD.matrix_cnt_prev[fstate.modelo]||{})[d]||0) : FORD.dealers[d].prev;
      const meta = fstate.modelo ? ((FORD.matrix_meta[fstate.modelo]||{})[d]||0) : FORD.dealers[d].meta;
      const delta = curr - prev;
      const vel = FORD.days_trans? curr/FORD.days_trans : 0;
      const proj = Math.round(vel * FORD.days_lab);
      const cumpl = meta>0? Math.round(100*proj/meta) : null;
      return {agency:d, prev, curr, delta, meta, proj, cumpl};
    });
    // Otros (only when no zona filter)
    if(!fstate.zona){
      const d='Otros';
      const curr = fstate.modelo ? (FORD.dealers[d].byModel?.[fstate.modelo]||0) : FORD.dealers[d].curr;
      // No tenemos prev por modelo en Otros — usar otros_prev_by_model si existe
      const prev = fstate.modelo
        ? ((FORD.otros_prev_by_model||{})[fstate.modelo] || 0)
        : FORD.dealers[d].prev;
      const vel = FORD.days_trans? curr/FORD.days_trans : 0;
      const proj = Math.round(vel*FORD.days_lab);
      rows.push({agency:'Otros', prev, curr, delta:curr-prev, meta:0, proj, cumpl:null});
    }
    const s = fstate.sort.proj_agency;
    rows.sort((a,b)=>{ let av=a[s.k], bv=b[s.k]; if(av==null)av=-1; if(bv==null)bv=-1; return (av>bv?1:av<bv?-1:0)*(s.dir==='asc'?1:-1); });
    const totals = rows.reduce((t,r)=>({prev:t.prev+r.prev,curr:t.curr+r.curr,meta:t.meta+r.meta}),{prev:0,curr:0,meta:0});
    totals.proj = Math.round((FORD.days_trans? totals.curr/FORD.days_trans : 0) * FORD.days_lab);
    const totCumpl = totals.meta>0? Math.round(100*totals.proj/totals.meta) : null;
    tbody.innerHTML = rows.map(r=>{
      const active = fstate.agencia===r.agency;
      return `<tr class="clickable ${active?'highlighted':''}" data-agency="${r.agency}">
        <td class="left">${r.agency}${active?'<span class="pill active-filter">✓</span>':''}</td>
        <td>${fmt(r.prev)}</td><td><strong>${fmt(r.curr)}</strong></td>
        <td>${deltaCell(r.delta)}</td>
        <td>${r.meta>0?fmt(r.meta):'—'}</td>
        <td>${projBarCell(r.proj, r.meta, r.cumpl)}</td>
        <td>${r.cumpl==null?'<span class="cumpl grey">N/A</span>':`<span class="cumpl ${cumplClass(r.cumpl)}">${r.cumpl}%</span>`}</td>
      </tr>`;
    }).join('') + `<tr class="total"><td class="left">TOTAL</td>
      <td>${fmt(totals.prev)}</td><td>${fmt(totals.curr)}</td>
      <td>${deltaCell(totals.curr-totals.prev)}</td>
      <td>${fmt(totals.meta)}</td>
      <td>${projBarCell(totals.proj, totals.meta, totCumpl)}</td>
      <td>${totCumpl==null?'<span class="cumpl grey">N/A</span>':`<span class="cumpl ${cumplClass(totCumpl)}">${totCumpl}%</span>`}</td></tr>`;
    tbody.querySelectorAll('tr.clickable').forEach(tr=>tr.addEventListener('click',()=>{
      const a = tr.dataset.agency;
      if(a==='Otros') return;
      fstate.agencia = fstate.agencia===a?'':a;
      document.getElementById('ff-agencia').value = fstate.agencia;
      ffRenderAll();
    }));
    applySortIndicators('ff-proj-agency', s);
  }

  function ffRenderHeatmap(){
    const models = FORD.model_order.filter(includeModel);
    const dealers = activeDealers();
    const dayRatio = FORD.days_lab>0 ? FORD.days_trans/FORD.days_lab : 1;
    document.getElementById('ff-heat-head').innerHTML =
      `<tr><th class="left">Modelo</th>${dealers.map(d=>`<th>${d}</th>`).join('')}<th>Estado</th></tr>`;
    const tbody = document.querySelector('#ff-heatmap tbody');
    tbody.innerHTML = models.map(m=>{
      const cells = dealers.map(d=>{
        const cnt = (FORD.matrix_cnt[m]||{})[d]||0;
        const meta = (FORD.matrix_meta[m]||{})[d]||0;
        if(meta===0 && cnt===0) return `<td class="cell dash" title="Sin tráfico ni meta">—</td>`;
        if(meta===0 && cnt>0)  return `<td class="cell grey" title="${cnt} registros, sin meta" data-model="${m}" data-dealer="${d}" style="cursor:pointer"><div class="cell-with-count"><span>N/A</span><span class="ct">${cnt} reg.</span></div></td>`;
        const metaAlDia = meta * dayRatio;
        const pctAlDia = metaAlDia>0 ? (cnt/metaAlDia*100) : 0;
        const pctMes = 100*cnt/meta;
        const cls = pctAlDia>=100?'green':pctAlDia>=70?'yellow':'red';
        const tip = `Al ritmo del día: ${pctAlDia.toFixed(0)}% (esperado ${metaAlDia.toFixed(1)})\nAvance del mes: ${pctMes.toFixed(0)}% (${cnt} de ${meta})`;
        return `<td class="cell ${cls}" title="${tip}" data-model="${m}" data-dealer="${d}" style="cursor:pointer"><div class="cell-with-count"><span>${pctAlDia.toFixed(0)}%</span><span class="ct">${cnt}/${meta}</span></div></td>`;
      }).join('');
      const vals = dealers.map(d=>{
        const cnt=(FORD.matrix_cnt[m]||{})[d]||0, meta=(FORD.matrix_meta[m]||{})[d]||0;
        if(meta<=0) return null;
        const metaAlDia = meta*dayRatio;
        return metaAlDia>0 ? (cnt/metaAlDia*100) : null;
      }).filter(v=>v!==null);
      let estado='—';
      if(vals.length){
        const avg = vals.reduce((a,b)=>a+b,0)/vals.length;
        estado = vals.every(v=>v>=100)?'🟢': avg>=70?'🟡':'🔴';
      }
      return `<tr><td class="left">${m}${fstate.modelo===m?'<span class="pill active-filter">✓</span>':''}</td>${cells}<td style="font-weight:700">${estado}</td></tr>`;
    }).join('');
    tbody.querySelectorAll('td.cell[data-model]').forEach(td=>td.addEventListener('click',()=>{
      const m = td.dataset.model, d = td.dataset.dealer;
      // toggle: set both filters; if already that combo, clear
      if(fstate.modelo===m && fstate.agencia===d){ fstate.modelo=''; fstate.agencia=''; }
      else { fstate.modelo=m; fstate.agencia=d; }
      document.getElementById('ff-modelo').value = fstate.modelo;
      document.getElementById('ff-agencia').value = fstate.agencia;
      ffRenderAll();
    }));
  }

  function ffRenderAction(){
    // Risks respect filters
    const models = FORD.model_order.filter(includeModel);
    const dealers = activeDealers();
    // Recompute proj/meta per model and per dealer with active dealers/models
    const riskModels = [];
    models.forEach(m=>{
      const curr = dealers.reduce((s,d)=>s+((FORD.matrix_cnt[m]||{})[d]||0),0);
      const meta = dealers.reduce((s,d)=>s+((FORD.matrix_meta[m]||{})[d]||0),0);
      const proj = Math.round((FORD.days_trans? curr/FORD.days_trans : 0) * FORD.days_lab);
      const cumpl = meta>0? Math.round(100*proj/meta) : null;
      if(meta>0 && cumpl<100) riskModels.push({m, proj, meta, cumpl, needed: Math.max(0, meta-proj)});
    });
    const riskAg = [];
    dealers.forEach(d=>{
      let curr=0, meta=0;
      models.forEach(m=>{ curr += (FORD.matrix_cnt[m]||{})[d]||0; meta += (FORD.matrix_meta[m]||{})[d]||0; });
      const proj = Math.round((FORD.days_trans? curr/FORD.days_trans : 0) * FORD.days_lab);
      const cumpl = meta>0? Math.round(100*proj/meta) : null;
      if(meta>0 && cumpl<100) riskAg.push({d, proj, meta, cumpl, needed: Math.max(0, meta-proj)});
    });
    const maxNeedM = Math.max(1, ...riskModels.map(r=>r.needed));
    document.getElementById('ff-risk-models').innerHTML = riskModels.length
      ? '<div style="list-style:none;padding:0;margin:0">' + riskModels.sort((a,b)=>b.needed-a.needed).map(r=>{
          const w = Math.max(5, Math.round(100*r.needed/maxNeedM));
          return `<div class="risk-row">
            <div class="rname">${r.m}</div>
            <div class="rbar" title="Cumpl. ${r.cumpl}% · Meta ${r.meta} · Proy ${r.proj}"><div class="fill" style="width:${w}%">${r.cumpl}% cumpl.</div></div>
            <div class="rneed">+${r.needed} reg.</div>
          </div>`;
        }).join('') + '</div>'
      : '<li style="color:#2e7d32;list-style:none">✓ Todos los modelos proyectan ≥100%</li>';
    const maxNeedA = Math.max(1, ...riskAg.map(r=>r.needed));
    document.getElementById('ff-risk-agencies').innerHTML = riskAg.length
      ? '<div>' + riskAg.sort((a,b)=>b.needed-a.needed).map(r=>{
          const w = Math.max(5, Math.round(100*r.needed/maxNeedA));
          return `<div class="risk-row">
            <div class="rname">${r.d}</div>
            <div class="rbar" title="Cumpl. ${r.cumpl}% · Meta ${r.meta} · Proy ${r.proj}"><div class="fill" style="width:${w}%">${r.cumpl}% cumpl.</div></div>
            <div class="rneed">+${r.needed} reg.</div>
          </div>`;
        }).join('') + '</div>'
      : '<li style="color:#2e7d32;list-style:none">✓ Todas las agencias proyectan ≥100%</li>';
    document.getElementById('ff-channel').innerHTML = `<strong>${FORD.dominant_channel}</strong> concentra el <strong>${FORD.channel_pct}%</strong> del tráfico Ford — evaluar diversificación hacia canales digitales (Hubspot/RRSS).`;
  }

  function applySortIndicators(tableId, sort){
    document.querySelectorAll('#'+tableId+' th.sortable').forEach(th=>{
      th.classList.remove('asc','desc');
      if(th.dataset.k===sort.k) th.classList.add(sort.dir);
    });
  }

  // Sort header bindings
  function bindSortHeaders(tableId, sortKey){
    document.querySelectorAll('#'+tableId+' th.sortable').forEach(th=>{
      th.addEventListener('click',()=>{
        const k = th.dataset.k;
        const s = fstate.sort[sortKey];
        if(s.k===k) s.dir = s.dir==='asc'?'desc':'asc';
        else { s.k = k; s.dir = (['model','agency'].includes(k)?'asc':'desc'); }
        ffRenderAll();
      });
    });
  }
  bindSortHeaders('ff-proj-model', 'proj_model');
  bindSortHeaders('ff-proj-agency', 'proj_agency');
  bindSortHeaders('ff-ranking', 'ranking');

  // Month change (Ford)
  const ffMonthEl = document.getElementById('ff-month');
  if(ffMonthEl){
    ffMonthEl.addEventListener('change', e=>{
      const key = e.target.value;
      if(!FORD_MONTHS[key]) return;
      currentMonthFF = key;
      FORD = FORD_MONTHS[key];
      // Reset filters porque dealer/model order podría cambiar entre meses
      fstate.zona = ''; fstate.agencia = ''; fstate.modelo = '';
      ['ff-zona','ff-agencia','ff-modelo'].forEach(id=>{
        const el = document.getElementById(id); if(el) el.value = '';
      });
      // Repopulate selectors for the new month's data
      ['ff-zona','ff-agencia','ff-modelo'].forEach(id=>{
        const el = document.getElementById(id); if(el) el.innerHTML = '';
      });
      const z = document.getElementById('ff-zona');
      if(z){ z.innerHTML = '<option value="">Todas</option>'; (FORD.zone_order||[]).forEach(v=>{const o=document.createElement('option');o.value=v;o.textContent=v;z.appendChild(o);}); }
      const a = document.getElementById('ff-agencia');
      if(a){ a.innerHTML = '<option value="">Todas</option>'; [...(FORD.dealer_order||[]),'Otros'].forEach(v=>{const o=document.createElement('option');o.value=v;o.textContent=v;a.appendChild(o);}); }
      const mm = document.getElementById('ff-modelo');
      if(mm){ mm.innerHTML = '<option value="">Todos</option>'; (FORD.model_order||[]).forEach(v=>{const o=document.createElement('option');o.value=v;o.textContent=v;mm.appendChild(o);}); }
      ffRenderAll();
      setTopbarSub('ford');
    });
  }
  // Filter bindings
  ['ff-zona','ff-agencia','ff-modelo'].forEach(id=>{
    document.getElementById(id).addEventListener('change', e=>{
      const key = id==='ff-zona'?'zona':id==='ff-agencia'?'agencia':'modelo';
      fstate[key] = e.target.value;
      if(key==='zona' && fstate.agencia && fstate.zona){
        if(!FORD.zones[fstate.zona].dealers.includes(fstate.agencia)){
          fstate.agencia=''; document.getElementById('ff-agencia').value='';
        }
      }
      ffRenderAll();
    });
  });
  document.getElementById('ff-reset').addEventListener('click',()=>{
    fstate.zona=''; fstate.agencia=''; fstate.modelo='';
    ['ff-zona','ff-agencia','ff-modelo'].forEach(id=>document.getElementById(id).value='');
    ffRenderAll();
  });

  // ----- CHART: Avance día a día (Ford) — respeta filtros -----
  function ffRenderPace(){
    destroy('ff-chart-pace');
    const pace = FORD.pace || [];
    const days = pace.map(p=>p.day);
    const cutDay = FORD.cut_day;
    const breakdown = FORD.daily_breakdown || {};
    // Dealers + models en scope con filtros
    const includeOtros = !fstate.zona && !fstate.agencia;
    const dealersForReal = includeOtros ? [...activeDealers(), 'Otros'] : activeDealers();
    const dealersForMeta = activeDealers();  // Otros no tiene metas
    const models = fstate.modelo ? [fstate.modelo] : FORD.model_order;
    // Cum diario filtrado
    const dailyTotals = {};
    dealersForReal.forEach(d=>{
      const dd = breakdown[d] || {};
      models.forEach(m=>{
        const series = dd[m] || {};
        Object.entries(series).forEach(([day, cnt])=>{
          const dn = +day; dailyTotals[dn] = (dailyTotals[dn]||0) + cnt;
        });
      });
    });
    let cum = 0;
    const real = days.map(d=>{
      if(d > cutDay) return null;
      cum += (dailyTotals[d] || 0);
      return cum;
    });
    // Meta filtrada y ritmo ideal recalculado
    let filteredMeta = 0;
    dealersForMeta.forEach(d=>{
      models.forEach(m=>{ filteredMeta += (FORD.matrix_meta[m]||{})[d] || 0; });
    });
    const totalWd = FORD.days_lab || 1;
    const ideal = pace.map(p => filteredMeta>0 ? +(filteredMeta * p.wd / totalWd).toFixed(1) : 0);
    const todayPace = pace.find(p=>p.day===cutDay) || {wd: totalWd};
    const todayIdeal = filteredMeta>0 ? filteredMeta * todayPace.wd / totalWd : 0;
    const todayReal  = real[days.indexOf(cutDay)] ?? cum;
    const gap = todayReal - todayIdeal;
    const status = filteredMeta<=0
      ? '<span style="color:var(--muted)">sin meta para esta selección</span>'
      : (gap>0?'<span style="color:var(--pos);font-weight:700">+'+gap.toFixed(1)+' por encima del ritmo</span>'
       : gap<0?'<span style="color:var(--neg);font-weight:700">'+gap.toFixed(1)+' bajo el ritmo</span>'
       : '<span style="color:var(--muted);font-weight:700">en línea con el ritmo</span>');
    document.getElementById('ff-pace-summary').innerHTML =
      `Día ${cutDay} · acumulado real <strong>${fmt(todayReal)}</strong> vs ideal <strong>${todayIdeal.toFixed(0)}</strong>${filteredMeta>0?` (meta ${fmt(filteredMeta)})`:''} — ${status}`;

    charts['ff-chart-pace'] = new Chart(document.getElementById('ff-chart-pace'),{
      type:'line',
      data:{labels:days, datasets:[
        {type:'line', label:'Acumulado real', data:real,
          borderColor:'#003478', backgroundColor:'rgba(0,52,120,.15)', fill:true,
          tension:.2, pointRadius:2, borderWidth:2.5, spanGaps:false,
          datalabels:{
            // Solo mostrar el número en el día actual (cutDay) para no saturar
            display: ctx => +ctx.chart.data.labels[ctx.dataIndex] === cutDay && ctx.dataset.data[ctx.dataIndex] != null,
            anchor:'end', align:'top', offset:6,
            color:'#003478', font:{size:12, weight:'700'},
            formatter: v => v != null ? fmt(v) : ''
          }},
        {type:'line', label:'Ritmo ideal a meta', data:ideal,
          borderColor:'#f57f17', backgroundColor:'rgba(245,127,23,0)',
          tension:0, pointRadius:0, borderWidth:2, borderDash:[6,4],
          datalabels:{
            // Mostrar valor ideal en el día actual y al final del mes (la meta total)
            display: ctx => {
              const d = +ctx.chart.data.labels[ctx.dataIndex];
              return d === cutDay || ctx.dataIndex === ctx.dataset.data.length - 1;
            },
            anchor:'end', align:'top', offset:6,
            color:'#f57f17', font:{size:11, weight:'700'},
            formatter: v => v != null ? Math.round(v) : ''
          }},
      ]},
      options:{
        layout:{padding:{top:18}},
        plugins:{
          legend:{position:'bottom',labels:{boxWidth:10,boxHeight:10,font:{size:11}}},
          tooltip:{mode:'index',intersect:false,
            callbacks:{title:items=>'Día '+items[0].label, label:c=>' '+c.dataset.label+': '+(c.parsed.y==null?'—':fmt(c.parsed.y))}}
        },
        scales:{
          x:{title:{display:true,text:'Día de '+(['Ene','Feb','Mar','Abr','May','Jun','Jul','Ago','Sep','Oct','Nov','Dic'][FORD.month-1]||''),color:'#6b7280',font:{size:11}}},
          y:{beginAtZero:true,ticks:{precision:0},title:{display:true,text:'Tráfico acumulado',color:'#6b7280',font:{size:11}}}
        },
        interaction:{mode:'index',intersect:false},
        maintainAspectRatio:false
      }
    });
  }

  // ----- CHART: Distribución por canal (Ford) — respeta zona/agencia/modelo -----
  // En la pestaña Ford sólo mostramos canales de marketing (consistente con los KPIs).
  const FORD_TAB_MARKETING_CHANNELS = new Set((DATA.channel_categories?.marketing) || ['Showroom','Hubspot','Ferias y Eventos','Feria/Eventos','Ferias','Llamada In']);
  function ffRenderChannels(){
    destroy('ff-chart-channels');
    const dmc = FORD.dealer_model_channel || {};
    const includeOtros = !fstate.zona && !fstate.agencia;
    const dealers = includeOtros ? [...activeDealers(), 'Otros'] : activeDealers();
    const models = fstate.modelo ? [fstate.modelo] : FORD.model_order;
    const ch = {};
    dealers.forEach(d=>{
      models.forEach(m=>{
        const ms = (dmc[d]||{})[m] || {};
        Object.entries(ms).forEach(([k,v])=>{
          if(!FORD_TAB_MARKETING_CHANNELS.has(k)) return;
          ch[k] = (ch[k]||0) + (v||0);
        });
      });
    });
    const entries = Object.entries(ch).filter(([,v])=>v>0).sort((a,b)=>b[1]-a[1]);
    const total = entries.reduce((a,[,v])=>a+v,0) || 1;
    const labels = entries.map(e=>e[0]);
    const values = entries.map(e=>e[1]);
    const maxVal = Math.max(1, ...values);
    charts['ff-chart-channels'] = new Chart(document.getElementById('ff-chart-channels'),{
      type:'bar',
      data:{labels, datasets:[{label:'Tráfico', data:values, backgroundColor:'#2e5090', borderRadius:6, maxBarThickness:22}]},
      options:{indexAxis:'y', layout:{padding:{right:70}},
        plugins:{legend:{display:false},
          tooltip:{callbacks:{label:c=>' '+fmt(c.parsed.x)+' reg. ('+(100*c.parsed.x/total).toFixed(1)+'%)'}},
          datalabels:{display:ctx=>ctx.dataset.data[ctx.dataIndex]>0,
            anchor:'end',align:'end',offset:4,
            font:{size:10,weight:'600'},color:'#2e5090',
            formatter:v=>v+' · '+(100*v/total).toFixed(0)+'%'}},
        scales:{x:{beginAtZero:true,ticks:{precision:0},max:maxVal*1.28}, y:{ticks:{font:{size:11}}}},
        maintainAspectRatio:false
      }
    });
  }

  function ffRenderAll(){
    ffRenderFilterSummary();
    ffRenderHero();
    ffRenderMovements();
    ffRenderZoneChart();
    ffRenderZonas();
    ffRenderRanking();
    ffRenderProjModel();
    ffRenderProjAgency();
    ffRenderHeatmap();
    ffRenderChannels();
    ffRenderAction();
    ffRenderPace();
  }
  ffRenderAll();

  // =========================================================
  //                  BRAND TAB (DongFeng/Chery/Mazda/RAM)
  // =========================================================
  const BRANDS = DATA.brand_list || [];
  const BRAND_DISPLAY = DATA.brand_display || {};
  let BRANDS_DATA = DATA.brands || {};

  // Populate month selector (Brand)
  (function initBRMonth(){
    const sel = document.getElementById('br-month');
    if(!sel) return;
    sel.innerHTML = MONTHS_CONFIG.map(c=>`<option value="${c.key}" ${c.key===currentMonthBR?'selected':''}>${c.label}</option>`).join('');
  })();

  // Populate brand selector
  const brSel = document.getElementById('br-marca');
  BRANDS.forEach(b=>{
    const o = document.createElement('option');
    o.value = b; o.textContent = BRAND_DISPLAY[b] || b;
    brSel.appendChild(o);
  });

  const bstate = { brand:'', agencia:'', modelo:'' };

  function brCurrent(){ return bstate.brand ? BRANDS_DATA[bstate.brand] : null; }
  function brActiveDealers(){
    const B = brCurrent(); if(!B) return [];
    return bstate.agencia ? (B.dealer_order.includes(bstate.agencia)?[bstate.agencia]:[]) : B.dealer_order;
  }
  function brIncludeModel(m){ return !bstate.modelo || bstate.modelo===m; }

  function brAggregate(){
    const B = brCurrent(); if(!B) return null;
    const dealers = brActiveDealers();
    const models = bstate.modelo? [bstate.modelo] : B.model_order;
    let curr=0, meta=0, prev=0;
    dealers.forEach(d=>{
      models.forEach(m=>{
        curr += (B.matrix_cnt[m]||{})[d]||0;
        prev += (B.matrix_cnt_prev[m]||{})[d]||0;
        meta += (B.matrix_meta[m]||{})[d]||0;
      });
    });
    const vel = B.days_trans? curr/B.days_trans : 0;
    const proj = Math.round(vel * B.days_lab);
    const cumpl = meta>0? Math.round(100*proj/meta) : null;
    return {curr, prev, delta:curr-prev, meta, days_lab:B.days_lab, days_trans:B.days_trans,
            velocity:vel, projection:proj, cumpl_proj:cumpl};
  }

  function brFilterBadge(){
    const B = brCurrent(); if(!B) return '';
    const parts=[];
    if(bstate.agencia) parts.push('Agencia='+bstate.agencia);
    if(bstate.modelo)  parts.push('Modelo='+bstate.modelo);
    return parts.length? parts.join(' · ') : 'Todas las agencias de '+B.display;
  }

  function brRenderFilterSummary(){
    const B = brCurrent(); if(!B){ document.getElementById('br-filter-summary').innerHTML=''; return; }
    const wrap = document.getElementById('br-filter-summary');
    const chips = [{k:'brand',label:'Marca: '+B.display, locked:true}];
    if(bstate.agencia) chips.push({k:'agencia',label:'Agencia: '+bstate.agencia});
    if(bstate.modelo)  chips.push({k:'modelo',label:'Modelo: '+bstate.modelo});
    wrap.innerHTML = '<span style="font-weight:600;color:var(--ink)">Filtros:</span> ' +
      chips.map(c=>`<span class="chip" style="${c.locked?'opacity:.85':''}">${c.label}${c.locked?'':`<button data-k="${c.k}" title="Quitar">×</button>`}</span>`).join('');
    wrap.querySelectorAll('button[data-k]').forEach(b=>b.addEventListener('click',()=>{
      bstate[b.dataset.k] = '';
      document.getElementById('br-'+b.dataset.k).value='';
      brRenderAll();
    }));
  }

  function brRenderGauge(cumpl){
    destroy('br-gauge');
    let val, rem;
    if(cumpl==null){ val=0; rem=100; }
    else if(cumpl>=100){ val=100; rem=0; }
    else { val=cumpl; rem=100-cumpl; }
    const color = cumpl==null?'#d1d5db'
      : cumpl>=100?'#2e7d32' : cumpl>=70?'#f57f17' : '#c62828';
    charts['br-gauge'] = new Chart(document.getElementById('br-gauge'),{
      type:'doughnut',
      data:{labels:['Cumpl','Resto'],datasets:[{data:[val,rem],backgroundColor:[color,'#eef1f5'],borderWidth:0,circumference:270,rotation:225,cutout:'78%'}]},
      options:{plugins:{legend:{display:false},tooltip:{enabled:false},datalabels:{display:false}},animation:{duration:600},maintainAspectRatio:false}
    });
  }

  function brRenderHero(){
    const B = brCurrent(); const k = brAggregate(); if(!B||!k) return;
    document.getElementById('br-hs-total').textContent = fmt(k.curr);
    document.getElementById('br-hs-total-d').textContent = 'Hasta '+B.cut_date+' · '+brFilterBadge();
    const dSign = k.delta>0?'+':''; document.getElementById('br-hs-delta-v').textContent = dSign+k.delta;
    const hs = document.getElementById('br-hs-delta'); hs.classList.remove('good','warn','bad');
    hs.classList.add(k.delta>0?'good':k.delta<0?'bad':'warn');
    document.getElementById('br-hs-delta-d').textContent = 'vs '+(B.prev_date||'corte anterior');
    document.getElementById('br-hs-vel').textContent = k.velocity.toFixed(1);
    document.getElementById('br-hs-proj').textContent = fmt(k.projection);
    document.getElementById('br-hs-proj-d').textContent = 'A '+k.days_lab+' días lab.';

    // Avance del mes (días laborables)
    const pctMes = k.days_lab>0 ? Math.round(100*k.days_trans/k.days_lab) : 0;
    document.getElementById('br-hm-summary').innerHTML =
      `Día laborable <strong>${k.days_trans}</strong> de <strong>${k.days_lab}</strong> · <strong>${pctMes}%</strong> del mes`;
    document.getElementById('br-hm-fill').style.width = pctMes+'%';
    document.getElementById('br-hm-labels').textContent = 'Día '+k.days_lab;

    const maxScale = Math.max(k.meta||0, k.projection||0, k.curr||0, 1);
    document.getElementById('br-hp-actual').style.width = (100*k.curr/maxScale)+'%';
    document.getElementById('br-hp-proj').style.width = (100*k.projection/maxScale)+'%';
    document.getElementById('br-hp-proj').style.background = k.cumpl_proj==null?'linear-gradient(90deg,#003478,#5c84d6)'
      : k.cumpl_proj>=100?'linear-gradient(90deg,#2e7d32,#66bb6a)'
      : k.cumpl_proj>=70 ?'linear-gradient(90deg,#f57f17,#ffb74d)'
      :                    'linear-gradient(90deg,#c62828,#ef5350)';
    const m = document.getElementById('br-hp-meta');
    if(k.meta<=0){ m.style.display='none'; } else { m.style.display=''; m.style.left = (100*k.meta/maxScale)+'%'; }
    document.getElementById('br-hp-summary').innerHTML =
      `Actual <strong>${fmt(k.curr)}</strong> → Proyección <strong>${fmt(k.projection)}</strong>${k.meta>0?` · Meta <strong>${fmt(k.meta)}</strong>`:''}`;
    document.getElementById('br-hp-labels').textContent = fmt(maxScale);

    brRenderGauge(k.cumpl_proj);
    document.getElementById('br-gauge-value').textContent = k.cumpl_proj==null?'—': k.cumpl_proj+'%';
    const tag = document.getElementById('br-gauge-tag');
    if(k.cumpl_proj==null){ tag.textContent='sin meta'; tag.style.background='#f5f5f5'; tag.style.color='#999'; }
    else if(k.cumpl_proj>=100){ tag.textContent='🟢 en meta'; tag.style.background='var(--green-bg)'; tag.style.color='var(--green-tx)'; }
    else if(k.cumpl_proj>=70){ tag.textContent='🟡 alerta'; tag.style.background='var(--yellow-bg)'; tag.style.color='var(--yellow-tx)'; }
    else{ tag.textContent='🔴 riesgo'; tag.style.background='var(--red-bg)'; tag.style.color='var(--red-tx)'; }
  }

  function brRenderMovements(){
    const B = brCurrent(); if(!B) return;
    document.getElementById('br-mov-sub').textContent = (B.prev_date||'') + ' → ' + B.cut_date + ' · magnitud por modelo';
    const items = B.model_order.map(m=>({model:m, ...B.models[m]})).filter(mv=>!bstate.modelo || mv.model===bstate.modelo);
    const maxAbs = Math.max(1, ...items.map(m=>Math.abs(m.delta)));
    items.sort((a,b)=>Math.abs(b.delta)-Math.abs(a.delta)||b.curr-a.curr);
    document.getElementById('br-movements').innerHTML = items.map(mv=>{
      const w = Math.max(2, Math.round(100*Math.abs(mv.delta)/maxAbs));
      const cls = mv.delta>0?'pos':mv.delta<0?'neg':'';
      const sign = mv.delta>0?'+':mv.delta<0?'':'';
      const pct = mv.prev>0? ` (${sign}${Math.round(100*mv.delta/mv.prev)}%)` : '';
      return `<div class="mov-bar-row">
        <div class="mname">${mv.model}</div>
        <div class="mbar">${mv.delta!==0?`<div class="mfill ${cls}" style="width:${w}%">${sign}${mv.delta}</div>`:'<div style="padding:2px 6px;font-size:10px;color:var(--muted)">sin cambio</div>'}</div>
        <div class="mval">${mv.prev} → <strong>${mv.curr}</strong>${pct}</div>
      </div>`;
    }).join('') || '<div style="color:var(--muted);text-align:center;padding:12px">Sin datos</div>';
  }

  function brRenderAgencies(){
    const B = brCurrent(); if(!B) return;
    // Donut chart
    destroy('br-chart-agency');
    const models = bstate.modelo? [bstate.modelo] : B.model_order;
    const rows = B.dealer_order.map(d=>{
      const curr = models.reduce((s,m)=>s+((B.matrix_cnt[m]||{})[d]||0),0);
      const prev = models.reduce((s,m)=>s+((B.matrix_cnt_prev[m]||{})[d]||0),0);
      return {d, prev, curr};
    });
    const totalCurr = rows.reduce((a,b)=>a+b.curr,0) || 1;
    charts['br-chart-agency'] = new Chart(document.getElementById('br-chart-agency'),{
      type:'doughnut',
      data:{labels:rows.map(r=>r.d), datasets:[{data:rows.map(r=>r.curr),
        backgroundColor:['#003478','#2e5090','#5c84d6','#9aa8c1'], borderWidth:2, borderColor:'#fff'}]},
      options:{cutout:'55%', layout:{padding:{top:18,bottom:18,left:20,right:20}},
        plugins:{legend:{position:'bottom',labels:{boxWidth:8,boxHeight:8,font:{size:10},padding:5}},
          tooltip:{callbacks:{label:c=>` ${c.label}: ${c.parsed} (${(100*c.parsed/totalCurr).toFixed(1)}%)`}},
          datalabels:{display:ctx=>ctx.dataset.data[ctx.dataIndex]>0,
            anchor:'end',align:'end',offset:6,clamp:true,color:'#1c2434',
            font:{size:10,weight:'700'},backgroundColor:'rgba(255,255,255,.92)',
            borderColor:'rgba(0,52,120,.15)',borderWidth:1,borderRadius:4,
            padding:{top:1,bottom:1,left:5,right:5},
            formatter:(v,ctx)=>`${v} · ${(100*v/totalCurr).toFixed(0)}%`}},
        maintainAspectRatio:false,
        onClick:(_,els)=>{ if(els.length){ const ag=rows[els[0].index].d; bstate.agencia = bstate.agencia===ag?'':ag; document.getElementById('br-agencia').value=bstate.agencia; brRenderAll(); } }
      }
    });
    // Table
    const tbody = document.querySelector('#br-agencies tbody');
    tbody.innerHTML = rows.map(r=>{
      const pct = totalCurr>0? (100*r.curr/totalCurr).toFixed(1)+'%' : '—';
      const active = bstate.agencia===r.d;
      return `<tr class="clickable ${active?'highlighted':''}" data-dealer="${r.d}">
        <td class="left">${r.d}${active?'<span class="pill active-filter">✓</span>':''}</td>
        <td>${fmt(r.prev)}</td><td><strong>${fmt(r.curr)}</strong></td>
        <td>${deltaCell(r.curr-r.prev)}</td><td>${pct}</td></tr>`;
    }).join('') + `<tr class="total"><td class="left">TOTAL</td><td>${fmt(rows.reduce((a,b)=>a+b.prev,0))}</td><td>${fmt(totalCurr)}</td><td>${deltaCell(totalCurr-rows.reduce((a,b)=>a+b.prev,0))}</td><td>100%</td></tr>`;
    tbody.querySelectorAll('tr.clickable').forEach(tr=>tr.addEventListener('click',()=>{
      const d = tr.dataset.dealer;
      bstate.agencia = bstate.agencia===d?'':d;
      document.getElementById('br-agencia').value = bstate.agencia;
      brRenderAll();
    }));
  }

  function brRenderRanking(){
    const B = brCurrent(); if(!B) return;
    const totCurr = brAggregate().curr;
    const models = B.model_order.map(m=>{
      const curr = brActiveDealers().reduce((s,d)=>s+((B.matrix_cnt[m]||{})[d]||0),0);
      const prev = brActiveDealers().reduce((s,d)=>s+((B.matrix_cnt_prev[m]||{})[d]||0),0);
      return {model:m, curr, prev, delta:curr-prev, pct: totCurr>0?100*curr/totCurr:0};
    }).sort((a,b)=>b.curr-a.curr);
    const tbody = document.querySelector('#br-ranking tbody');
    tbody.innerHTML = models.map((r,i)=>{
      const active = bstate.modelo===r.model;
      return `<tr class="clickable ${active?'highlighted':''}" data-model="${r.model}">
        <td style="color:var(--ford-2);font-weight:700">${i+1}</td>
        <td class="left">${r.model}${active?'<span class="pill active-filter">✓</span>':''}</td>
        <td><strong>${fmt(r.curr)}</strong></td>
        <td>${r.pct.toFixed(1)}%</td>
        <td>${deltaCell(r.delta)}</td></tr>`;
    }).join('');
    tbody.querySelectorAll('tr.clickable').forEach(tr=>tr.addEventListener('click',()=>{
      const m = tr.dataset.model;
      bstate.modelo = bstate.modelo===m?'':m;
      document.getElementById('br-modelo').value = bstate.modelo;
      brRenderAll();
    }));
  }

  function brRenderProjModel(){
    const B = brCurrent(); if(!B) return;
    const rows = B.model_order.filter(brIncludeModel).map(m=>{
      const curr = brActiveDealers().reduce((s,d)=>s+((B.matrix_cnt[m]||{})[d]||0),0);
      const prev = brActiveDealers().reduce((s,d)=>s+((B.matrix_cnt_prev[m]||{})[d]||0),0);
      const meta = brActiveDealers().reduce((s,d)=>s+((B.matrix_meta[m]||{})[d]||0),0);
      const vel = B.days_trans? curr/B.days_trans : 0;
      const proj = Math.round(vel*B.days_lab);
      const cumpl = meta>0? Math.round(100*proj/meta) : null;
      return {model:m, prev, curr, delta:curr-prev, meta, proj, cumpl};
    });
    const t = rows.reduce((a,r)=>({prev:a.prev+r.prev,curr:a.curr+r.curr,meta:a.meta+r.meta}),{prev:0,curr:0,meta:0});
    t.proj = Math.round((B.days_trans? t.curr/B.days_trans : 0) * B.days_lab);
    const tc = t.meta>0? Math.round(100*t.proj/t.meta) : null;
    const tbody = document.querySelector('#br-proj-model tbody');
    tbody.innerHTML = rows.map(r=>{
      const active = bstate.modelo===r.model;
      return `<tr class="clickable ${active?'highlighted':''}" data-model="${r.model}">
        <td class="left">${r.model}${active?'<span class="pill active-filter">✓</span>':''}</td>
        <td>${fmt(r.prev)}</td><td><strong>${fmt(r.curr)}</strong></td>
        <td>${deltaCell(r.delta)}</td>
        <td>${r.meta>0?fmt(r.meta):'—'}</td>
        <td>${projBarCell(r.proj, r.meta, r.cumpl)}</td>
        <td>${r.cumpl==null?'<span class="cumpl grey">N/A</span>':`<span class="cumpl ${cumplClass(r.cumpl)}">${r.cumpl}%</span>`}</td>
      </tr>`;
    }).join('') + `<tr class="total"><td class="left">TOTAL</td>
      <td>${fmt(t.prev)}</td><td>${fmt(t.curr)}</td><td>${deltaCell(t.curr-t.prev)}</td>
      <td>${fmt(t.meta)}</td><td>${projBarCell(t.proj, t.meta, tc)}</td>
      <td>${tc==null?'<span class="cumpl grey">N/A</span>':`<span class="cumpl ${cumplClass(tc)}">${tc}%</span>`}</td></tr>`;
    tbody.querySelectorAll('tr.clickable').forEach(tr=>tr.addEventListener('click',()=>{
      const m = tr.dataset.model;
      bstate.modelo = bstate.modelo===m?'':m;
      document.getElementById('br-modelo').value = bstate.modelo;
      brRenderAll();
    }));
  }

  function brRenderProjAgency(){
    const B = brCurrent(); if(!B) return;
    const rows = B.dealer_order.map(d=>{
      const curr = bstate.modelo ? ((B.matrix_cnt[bstate.modelo]||{})[d]||0) : B.dealers[d].curr;
      const prev = bstate.modelo ? ((B.matrix_cnt_prev[bstate.modelo]||{})[d]||0) : B.dealers[d].prev;
      const meta = bstate.modelo ? ((B.matrix_meta[bstate.modelo]||{})[d]||0) : B.dealers[d].meta;
      const vel = B.days_trans? curr/B.days_trans : 0;
      const proj = Math.round(vel*B.days_lab);
      const cumpl = meta>0? Math.round(100*proj/meta) : null;
      return {agency:d, prev, curr, delta:curr-prev, meta, proj, cumpl};
    });
    const t = rows.reduce((a,r)=>({prev:a.prev+r.prev,curr:a.curr+r.curr,meta:a.meta+r.meta}),{prev:0,curr:0,meta:0});
    t.proj = Math.round((B.days_trans? t.curr/B.days_trans : 0) * B.days_lab);
    const tc = t.meta>0? Math.round(100*t.proj/t.meta) : null;
    const tbody = document.querySelector('#br-proj-agency tbody');
    tbody.innerHTML = rows.map(r=>{
      const active = bstate.agencia===r.agency;
      return `<tr class="clickable ${active?'highlighted':''}" data-agency="${r.agency}">
        <td class="left">${r.agency}${active?'<span class="pill active-filter">✓</span>':''}</td>
        <td>${fmt(r.prev)}</td><td><strong>${fmt(r.curr)}</strong></td>
        <td>${deltaCell(r.delta)}</td>
        <td>${r.meta>0?fmt(r.meta):'—'}</td>
        <td>${projBarCell(r.proj, r.meta, r.cumpl)}</td>
        <td>${r.cumpl==null?'<span class="cumpl grey">N/A</span>':`<span class="cumpl ${cumplClass(r.cumpl)}">${r.cumpl}%</span>`}</td>
      </tr>`;
    }).join('') + `<tr class="total"><td class="left">TOTAL</td>
      <td>${fmt(t.prev)}</td><td>${fmt(t.curr)}</td><td>${deltaCell(t.curr-t.prev)}</td>
      <td>${fmt(t.meta)}</td><td>${projBarCell(t.proj, t.meta, tc)}</td>
      <td>${tc==null?'<span class="cumpl grey">N/A</span>':`<span class="cumpl ${cumplClass(tc)}">${tc}%</span>`}</td></tr>`;
    tbody.querySelectorAll('tr.clickable').forEach(tr=>tr.addEventListener('click',()=>{
      const a = tr.dataset.agency;
      bstate.agencia = bstate.agencia===a?'':a;
      document.getElementById('br-agencia').value = bstate.agencia;
      brRenderAll();
    }));
  }

  function brRenderHeatmap(){
    const B = brCurrent(); if(!B) return;
    const models = B.model_order.filter(brIncludeModel);
    const dealers = brActiveDealers();
    const dayRatio = B.days_lab>0 ? B.days_trans/B.days_lab : 1;
    document.getElementById('br-heat-head').innerHTML =
      `<tr><th class="left">Modelo</th>${dealers.map(d=>`<th>${d}</th>`).join('')}<th>Estado</th></tr>`;
    const tbody = document.querySelector('#br-heatmap tbody');
    tbody.innerHTML = models.map(m=>{
      const cells = dealers.map(d=>{
        const cnt = (B.matrix_cnt[m]||{})[d]||0;
        const meta = (B.matrix_meta[m]||{})[d]||0;
        if(meta===0 && cnt===0) return `<td class="cell dash" title="Sin tráfico ni meta">—</td>`;
        if(meta===0 && cnt>0)  return `<td class="cell grey" title="${cnt} reg., sin meta" data-model="${m}" data-dealer="${d}" style="cursor:pointer"><div class="cell-with-count"><span>N/A</span><span class="ct">${cnt} reg.</span></div></td>`;
        const metaAlDia = meta * dayRatio;
        const pctAlDia = metaAlDia>0 ? (cnt/metaAlDia*100) : 0;
        const pctMes = 100*cnt/meta;
        const cls = pctAlDia>=100?'green':pctAlDia>=70?'yellow':'red';
        const tip = `Al ritmo del día: ${pctAlDia.toFixed(0)}% (esperado ${metaAlDia.toFixed(1)})\nAvance del mes: ${pctMes.toFixed(0)}% (${cnt} de ${meta})`;
        return `<td class="cell ${cls}" title="${tip}" data-model="${m}" data-dealer="${d}" style="cursor:pointer"><div class="cell-with-count"><span>${pctAlDia.toFixed(0)}%</span><span class="ct">${cnt}/${meta}</span></div></td>`;
      }).join('');
      const vals = dealers.map(d=>{
        const cnt=(B.matrix_cnt[m]||{})[d]||0, meta=(B.matrix_meta[m]||{})[d]||0;
        if(meta<=0) return null;
        const metaAlDia = meta*dayRatio;
        return metaAlDia>0 ? (cnt/metaAlDia*100) : null;
      }).filter(v=>v!==null);
      let estado='—';
      if(vals.length){
        const avg = vals.reduce((a,b)=>a+b,0)/vals.length;
        estado = vals.every(v=>v>=100)?'🟢': avg>=70?'🟡':'🔴';
      }
      return `<tr><td class="left">${m}${bstate.modelo===m?'<span class="pill active-filter">✓</span>':''}</td>${cells}<td style="font-weight:700">${estado}</td></tr>`;
    }).join('');
    tbody.querySelectorAll('td.cell[data-model]').forEach(td=>td.addEventListener('click',()=>{
      const m = td.dataset.model, d = td.dataset.dealer;
      if(bstate.modelo===m && bstate.agencia===d){ bstate.modelo=''; bstate.agencia=''; }
      else { bstate.modelo=m; bstate.agencia=d; }
      document.getElementById('br-modelo').value = bstate.modelo;
      document.getElementById('br-agencia').value = bstate.agencia;
      brRenderAll();
    }));
  }

  function brRenderAction(){
    const B = brCurrent(); if(!B) return;
    const models = B.model_order.filter(brIncludeModel);
    const dealers = brActiveDealers();
    const riskModels = [];
    models.forEach(m=>{
      const curr = dealers.reduce((s,d)=>s+((B.matrix_cnt[m]||{})[d]||0),0);
      const meta = dealers.reduce((s,d)=>s+((B.matrix_meta[m]||{})[d]||0),0);
      const proj = Math.round((B.days_trans? curr/B.days_trans : 0)*B.days_lab);
      const cumpl = meta>0? Math.round(100*proj/meta) : null;
      if(meta>0 && cumpl<100) riskModels.push({m,proj,meta,cumpl,needed:Math.max(0,meta-proj)});
    });
    const riskAg = [];
    dealers.forEach(d=>{
      let curr=0, meta=0;
      models.forEach(m=>{ curr += (B.matrix_cnt[m]||{})[d]||0; meta += (B.matrix_meta[m]||{})[d]||0; });
      const proj = Math.round((B.days_trans? curr/B.days_trans : 0)*B.days_lab);
      const cumpl = meta>0? Math.round(100*proj/meta) : null;
      if(meta>0 && cumpl<100) riskAg.push({d,proj,meta,cumpl,needed:Math.max(0,meta-proj)});
    });
    const maxNm = Math.max(1, ...riskModels.map(r=>r.needed));
    document.getElementById('br-risk-models').innerHTML = riskModels.length
      ? riskModels.sort((a,b)=>b.needed-a.needed).map(r=>{
          const w = Math.max(5, Math.round(100*r.needed/maxNm));
          return `<div class="risk-row"><div class="rname">${r.m}</div>
            <div class="rbar" title="Cumpl. ${r.cumpl}% · Meta ${r.meta} · Proy ${r.proj}"><div class="fill" style="width:${w}%">${r.cumpl}% cumpl.</div></div>
            <div class="rneed">+${r.needed} reg.</div></div>`;
        }).join('')
      : '<li style="color:#2e7d32;list-style:none">✓ Todos los modelos proyectan ≥100%</li>';
    const maxNa = Math.max(1, ...riskAg.map(r=>r.needed));
    document.getElementById('br-risk-agencies').innerHTML = riskAg.length
      ? riskAg.sort((a,b)=>b.needed-a.needed).map(r=>{
          const w = Math.max(5, Math.round(100*r.needed/maxNa));
          return `<div class="risk-row"><div class="rname">${r.d}</div>
            <div class="rbar" title="Cumpl. ${r.cumpl}% · Meta ${r.meta} · Proy ${r.proj}"><div class="fill" style="width:${w}%">${r.cumpl}% cumpl.</div></div>
            <div class="rneed">+${r.needed} reg.</div></div>`;
        }).join('')
      : '<li style="color:#2e7d32;list-style:none">✓ Todas las agencias proyectan ≥100%</li>';
    document.getElementById('br-channel').innerHTML = `<strong>${B.dominant_channel}</strong> concentra el <strong>${B.channel_pct}%</strong> del tráfico ${B.display}.`;
  }

  // ----- MOVEMENTS Brand (respeta filtros) -----
  function brRenderMovementsFiltered(){
    const B = brCurrent(); if(!B) return;
    document.getElementById('br-mov-sub').textContent = (B.prev_date||'') + ' → ' + B.cut_date + ' · magnitud por modelo';
    const dealers = brActiveDealers();
    const modelsList = (bstate.modelo? [bstate.modelo] : B.model_order);
    const items = modelsList.map(m=>{
      const curr = dealers.reduce((s,d)=>s+((B.matrix_cnt[m]||{})[d]||0),0);
      const prev = dealers.reduce((s,d)=>s+((B.matrix_cnt_prev[m]||{})[d]||0),0);
      return {model:m, prev, curr, delta:curr-prev};
    });
    const maxAbs = Math.max(1, ...items.map(m=>Math.abs(m.delta)));
    items.sort((a,b)=>Math.abs(b.delta)-Math.abs(a.delta)||b.curr-a.curr);
    document.getElementById('br-movements').innerHTML = items.map(mv=>{
      const w = Math.max(2, Math.round(100*Math.abs(mv.delta)/maxAbs));
      const cls = mv.delta>0?'pos':mv.delta<0?'neg':'';
      const sign = mv.delta>0?'+':mv.delta<0?'':'';
      const pct = mv.prev>0? ` (${sign}${Math.round(100*mv.delta/mv.prev)}%)` : '';
      return `<div class="mov-bar-row">
        <div class="mname">${mv.model}</div>
        <div class="mbar">${mv.delta!==0?`<div class="mfill ${cls}" style="width:${w}%">${sign}${mv.delta}</div>`:'<div style="padding:2px 6px;font-size:10px;color:var(--muted)">sin cambio</div>'}</div>
        <div class="mval">${mv.prev} → <strong>${mv.curr}</strong>${pct}</div>
      </div>`;
    }).join('') || '<div style="color:var(--muted);text-align:center;padding:12px">Sin datos</div>';
  }

  // ----- CHART: Avance día a día (Brand) — respeta filtros -----
  function brRenderPace(){
    const B = brCurrent(); if(!B) return;
    destroy('br-chart-pace');
    const pace = B.pace || [];
    const days = pace.map(p=>p.day);
    const cutDay = B.cut_day;
    const breakdown = B.daily_breakdown || {};
    const dealers = brActiveDealers();
    const models = bstate.modelo ? [bstate.modelo] : B.model_order;
    const dailyTotals = {};
    dealers.forEach(d=>{
      const dd = breakdown[d] || {};
      models.forEach(m=>{
        const series = dd[m] || {};
        Object.entries(series).forEach(([day, cnt])=>{
          const dn = +day; dailyTotals[dn] = (dailyTotals[dn]||0) + cnt;
        });
      });
    });
    let cum = 0;
    const real = days.map(d=>{
      if(d > cutDay) return null;
      cum += (dailyTotals[d] || 0);
      return cum;
    });
    let filteredMeta = 0;
    dealers.forEach(d=>{
      models.forEach(m=>{ filteredMeta += (B.matrix_meta[m]||{})[d] || 0; });
    });
    const totalWd = B.days_lab || 1;
    const ideal = pace.map(p => filteredMeta>0 ? +(filteredMeta * p.wd / totalWd).toFixed(1) : 0);
    const todayPace = pace.find(p=>p.day===cutDay) || {wd: totalWd};
    const todayIdeal = filteredMeta>0 ? filteredMeta * todayPace.wd / totalWd : 0;
    const todayReal  = real[days.indexOf(cutDay)] ?? cum;
    const gap = todayReal - todayIdeal;
    const status = filteredMeta<=0
      ? '<span style="color:var(--muted)">sin meta para esta selección</span>'
      : (gap>0?'<span style="color:var(--pos);font-weight:700">+'+gap.toFixed(1)+' por encima del ritmo</span>'
       : gap<0?'<span style="color:var(--neg);font-weight:700">'+gap.toFixed(1)+' bajo el ritmo</span>'
       : '<span style="color:var(--muted);font-weight:700">en línea con el ritmo</span>');
    document.getElementById('br-pace-summary').innerHTML =
      `Día ${cutDay} · acumulado real <strong>${fmt(todayReal)}</strong> vs ideal <strong>${todayIdeal.toFixed(0)}</strong>${filteredMeta>0?` (meta ${fmt(filteredMeta)})`:''} — ${status}`;

    charts['br-chart-pace'] = new Chart(document.getElementById('br-chart-pace'),{
      type:'line',
      data:{labels:days, datasets:[
        {type:'line', label:'Acumulado real', data:real,
          borderColor:'#003478', backgroundColor:'rgba(0,52,120,.15)', fill:true,
          tension:.2, pointRadius:2, borderWidth:2.5, spanGaps:false,
          datalabels:{
            display: ctx => +ctx.chart.data.labels[ctx.dataIndex] === cutDay && ctx.dataset.data[ctx.dataIndex] != null,
            anchor:'end', align:'top', offset:6,
            color:'#003478', font:{size:12, weight:'700'},
            formatter: v => v != null ? fmt(v) : ''
          }},
        {type:'line', label:'Ritmo ideal a meta', data:ideal,
          borderColor:'#f57f17', backgroundColor:'rgba(245,127,23,0)',
          tension:0, pointRadius:0, borderWidth:2, borderDash:[6,4],
          datalabels:{
            display: ctx => {
              const d = +ctx.chart.data.labels[ctx.dataIndex];
              return d === cutDay || ctx.dataIndex === ctx.dataset.data.length - 1;
            },
            anchor:'end', align:'top', offset:6,
            color:'#f57f17', font:{size:11, weight:'700'},
            formatter: v => v != null ? Math.round(v) : ''
          }},
      ]},
      options:{
        layout:{padding:{top:18}},
        plugins:{
          legend:{position:'bottom',labels:{boxWidth:10,boxHeight:10,font:{size:11}}},
          tooltip:{mode:'index',intersect:false,
            callbacks:{title:items=>'Día '+items[0].label, label:c=>' '+c.dataset.label+': '+(c.parsed.y==null?'—':fmt(c.parsed.y))}}
        },
        scales:{
          x:{title:{display:true,text:'Día de '+(['Ene','Feb','Mar','Abr','May','Jun','Jul','Ago','Sep','Oct','Nov','Dic'][B.month-1]||''),color:'#6b7280',font:{size:11}}},
          y:{beginAtZero:true,ticks:{precision:0},title:{display:true,text:'Tráfico acumulado',color:'#6b7280',font:{size:11}}}
        },
        interaction:{mode:'index',intersect:false},
        maintainAspectRatio:false
      }
    });
  }

  // ----- CHART: Distribución por canal (Brand) — respeta agencia/modelo -----
  function brRenderChannels(){
    const B = brCurrent(); if(!B) return;
    destroy('br-chart-channels');
    const dmc = B.dealer_model_channel || {};
    const dealers = brActiveDealers();
    const models = bstate.modelo ? [bstate.modelo] : B.model_order;
    const ch = {};
    dealers.forEach(d=>{
      models.forEach(m=>{
        const ms = (dmc[d]||{})[m] || {};
        Object.entries(ms).forEach(([k,v])=>{
          // En la pestaña Reporte Marcas sólo mostramos canales marketing (consistente con KPIs).
          if(!FORD_TAB_MARKETING_CHANNELS.has(k)) return;
          ch[k] = (ch[k]||0) + (v||0);
        });
      });
    });
    const entries = Object.entries(ch).filter(([,v])=>v>0).sort((a,b)=>b[1]-a[1]);
    const total = entries.reduce((a,[,v])=>a+v,0) || 1;
    const labels = entries.map(e=>e[0]);
    const values = entries.map(e=>e[1]);
    const maxVal = Math.max(1, ...values);
    charts['br-chart-channels'] = new Chart(document.getElementById('br-chart-channels'),{
      type:'bar',
      data:{labels, datasets:[{label:'Tráfico', data:values, backgroundColor:'#2e5090', borderRadius:6, maxBarThickness:22}]},
      options:{indexAxis:'y', layout:{padding:{right:70}},
        plugins:{legend:{display:false},
          tooltip:{callbacks:{label:c=>' '+fmt(c.parsed.x)+' reg. ('+(100*c.parsed.x/total).toFixed(1)+'%)'}},
          datalabels:{display:ctx=>ctx.dataset.data[ctx.dataIndex]>0,
            anchor:'end',align:'end',offset:4,
            font:{size:10,weight:'600'},color:'#2e5090',
            formatter:v=>v+' · '+(100*v/total).toFixed(0)+'%'}},
        scales:{x:{beginAtZero:true,ticks:{precision:0},max:maxVal*1.28}, y:{ticks:{font:{size:11}}}},
        maintainAspectRatio:false
      }
    });
  }

  function brRenderAll(){
    const hasBrand = !!bstate.brand;
    document.getElementById('br-empty').style.display = hasBrand? 'none':'block';
    document.getElementById('br-content').style.display = hasBrand? 'block':'none';
    if(!hasBrand){ ['br-agencia','br-modelo'].forEach(id=>{ document.getElementById(id).innerHTML='<option value="">'+(id.endsWith('agencia')?'Todas':'Todos')+'</option>'; }); return; }
    const B = brCurrent();
    // Rebuild agency/model option lists for this brand
    const elA = document.getElementById('br-agencia'); const elM = document.getElementById('br-modelo');
    elA.innerHTML = '<option value="">Todas</option>' + B.dealer_order.map(d=>`<option value="${d}" ${bstate.agencia===d?'selected':''}>${d}</option>`).join('');
    elM.innerHTML = '<option value="">Todos</option>' + B.model_order.map(m=>`<option value="${m}" ${bstate.modelo===m?'selected':''}>${m}</option>`).join('');
    brRenderFilterSummary();
    brRenderHero();
    brRenderMovementsFiltered();
    brRenderAgencies();
    brRenderRanking();
    brRenderProjModel();
    brRenderProjAgency();
    brRenderHeatmap();
    brRenderChannels();
    brRenderAction();
    brRenderPace();
  }

  // Month change (Brand)
  const brMonthEl = document.getElementById('br-month');
  if(brMonthEl){
    brMonthEl.addEventListener('change', e=>{
      const key = e.target.value;
      if(!BRANDS_MONTHS[key]) return;
      currentMonthBR = key;
      BRANDS_DATA = BRANDS_MONTHS[key];
      // Reset sub-filters; brand selection persists
      bstate.agencia = ''; bstate.modelo = '';
      ['br-agencia','br-modelo'].forEach(id=>{ const el=document.getElementById(id); if(el) el.value=''; });
      brRenderAll();
      setTopbarSub('brand');
    });
  }
  // Brand filter bindings
  document.getElementById('br-marca').addEventListener('change', e=>{
    bstate.brand = e.target.value;
    bstate.agencia = ''; bstate.modelo = '';
    brRenderAll();
  });
  ['br-agencia','br-modelo'].forEach(id=>{
    document.getElementById(id).addEventListener('change', e=>{
      const key = id.endsWith('agencia')?'agencia':'modelo';
      bstate[key] = e.target.value;
      brRenderAll();
    });
  });
  document.getElementById('br-reset').addEventListener('click',()=>{
    bstate.agencia=''; bstate.modelo='';
    document.getElementById('br-agencia').value='';
    document.getElementById('br-modelo').value='';
    brRenderAll();
  });

  brRenderAll();

  // =========================================================
  //                     COMPARATIVO TAB
  // =========================================================
  const cpstate = {
    monthA: MONTHS_CONFIG[0]?.key || '',
    monthB: MONTHS_CONFIG[MONTHS_CONFIG.length-1]?.key || cpstateInitB(),
    marca:  'FORD',
    agencia:'',
    modelo: '',
  };
  function cpstateInitB(){ return MONTHS_CONFIG[0]?.key || ''; }

  // Populate selectors
  (function initCP(){
    const a = document.getElementById('cp-monthA');
    const b = document.getElementById('cp-monthB');
    if(a) a.innerHTML = MONTHS_CONFIG.map(c=>`<option value="${c.key}" ${c.key===cpstate.monthA?'selected':''}>${c.label}</option>`).join('');
    if(b) b.innerHTML = MONTHS_CONFIG.map(c=>`<option value="${c.key}" ${c.key===cpstate.monthB?'selected':''}>${c.label}</option>`).join('');
    const m = document.getElementById('cp-marca');
    if(m){
      const opts = [{val:'FORD', label:'Ford'}, ...BRANDS.map(b=>({val:b, label:BRAND_DISPLAY[b]||b}))];
      m.innerHTML = opts.map(o=>`<option value="${o.val}" ${o.val===cpstate.marca?'selected':''}>${o.label}</option>`).join('');
    }
  })();

  function cpGetData(monthKey){
    if(cpstate.marca === 'FORD') return FORD_MONTHS[monthKey];
    return (BRANDS_MONTHS[monthKey] || {})[cpstate.marca];
  }
  function cpModelOrder(){
    const A = cpGetData(cpstate.monthA);
    const B = cpGetData(cpstate.monthB);
    const set = new Set([...((A?.model_order)||[]), ...((B?.model_order)||[])]);
    return Array.from(set);
  }
  function cpDealerOrder(){
    const A = cpGetData(cpstate.monthA);
    const B = cpGetData(cpstate.monthB);
    const set = new Set([...((A?.dealer_order)||[]), ...((B?.dealer_order)||[])]);
    return Array.from(set);
  }
  function cpRefreshSubFilters(){
    // Repopulate agency and model selects for current marca
    const ag = document.getElementById('cp-agencia');
    const mo = document.getElementById('cp-modelo');
    if(ag){
      const dealers = cpDealerOrder();
      ag.innerHTML = '<option value="">Todas</option>' + dealers.map(d=>`<option value="${d}" ${cpstate.agencia===d?'selected':''}>${d}</option>`).join('');
      if(!dealers.includes(cpstate.agencia)) cpstate.agencia = '';
    }
    if(mo){
      const models = cpModelOrder();
      mo.innerHTML = '<option value="">Todos</option>' + models.map(m=>`<option value="${m}" ${cpstate.modelo===m?'selected':''}>${m}</option>`).join('');
      if(!models.includes(cpstate.modelo)) cpstate.modelo = '';
    }
  }

  // Compute filtered totals from a monthData snapshot
  function cpAggregate(monthData){
    if(!monthData) return null;
    const dealers = cpstate.agencia ? [cpstate.agencia] : (monthData.dealer_order || []);
    const models  = cpstate.modelo  ? [cpstate.modelo]  : (monthData.model_order  || []);
    let curr=0, meta=0;
    dealers.forEach(d=>{
      models.forEach(m=>{
        curr += (monthData.matrix_cnt[m]||{})[d]||0;
        meta += (monthData.matrix_meta[m]||{})[d]||0;
      });
    });
    // For Ford, include Otros if no agency filter
    if(cpstate.marca==='FORD' && !cpstate.agencia){
      models.forEach(m=>{
        curr += ((monthData.matrix_cnt['Otros']||monthData.dealers?.['Otros']?.byModel)?.[m] ?? 0);
      });
      // Actually Ford doesn't have matrix_cnt['Otros']. Use dealers['Otros'].byModel.
      // The above line is for safety; let's recompute properly:
    }
    // Correct Otros handling:
    if(cpstate.marca==='FORD' && !cpstate.agencia && monthData.dealers?.['Otros']){
      const otros = monthData.dealers['Otros'];
      // Reset and recompute (otros not in matrix_cnt)
      curr = 0;
      dealers.forEach(d=>{
        models.forEach(m=>{ curr += (monthData.matrix_cnt[m]||{})[d]||0; });
      });
      models.forEach(m=>{ curr += (otros.byModel||{})[m] || 0; });
    }
    const days_lab = monthData.days_lab || 0, days_trans = monthData.days_trans || 0;
    const vel = days_trans? curr/days_trans : 0;
    return {curr, meta, days_lab, days_trans, vel};
  }

  function cpRenderFilterSummary(){
    const wrap = document.getElementById('cp-filter-summary');
    const cA = MONTHS_CONFIG.find(c=>c.key===cpstate.monthA)?.label || '?';
    const cB = MONTHS_CONFIG.find(c=>c.key===cpstate.monthB)?.label || '?';
    const marca = cpstate.marca==='FORD'? 'Ford' : (BRAND_DISPLAY[cpstate.marca]||cpstate.marca);
    const chips = [
      {k:'_', label:`${cA} → ${cB}`, locked:true},
      {k:'marca', label:`Marca: ${marca}`, locked:true},
    ];
    if(cpstate.agencia) chips.push({k:'agencia', label:'Agencia: '+cpstate.agencia});
    if(cpstate.modelo)  chips.push({k:'modelo', label:'Modelo: '+cpstate.modelo});
    wrap.innerHTML = '<span style="font-weight:600;color:var(--ink)">Comparando:</span> ' +
      chips.map(c=>`<span class="chip" ${c.locked?'style="opacity:.85"':''}>${c.label}${c.locked?'':`<button data-k="${c.k}" title="Quitar">×</button>`}</span>`).join('');
    wrap.querySelectorAll('button[data-k]').forEach(b=>b.addEventListener('click',()=>{
      cpstate[b.dataset.k]=''; document.getElementById('cp-'+b.dataset.k).value=''; cpRenderAll();
    }));
  }

  function cpRenderKpis(){
    const A = cpGetData(cpstate.monthA);
    const B = cpGetData(cpstate.monthB);
    const ka = cpAggregate(A) || {curr:0,vel:0};
    const kb = cpAggregate(B) || {curr:0,vel:0};
    const cA = MONTHS_CONFIG.find(c=>c.key===cpstate.monthA)?.label || '?';
    const cB = MONTHS_CONFIG.find(c=>c.key===cpstate.monthB)?.label || '?';
    document.getElementById('cp-kpi-a-lbl').textContent = cA;
    document.getElementById('cp-kpi-b-lbl').textContent = cB;
    document.getElementById('cp-kpi-a').textContent = fmt(ka.curr);
    document.getElementById('cp-kpi-b').textContent = fmt(kb.curr);
    document.getElementById('cp-kpi-a-hint').textContent = (A?.cut_date||'')+' · '+ka.days_trans+' días lab.';
    document.getElementById('cp-kpi-b-hint').textContent = (B?.cut_date||'')+' · '+kb.days_trans+' días lab.';
    const delta = kb.curr - ka.curr;
    const deltaPct = ka.curr>0 ? (100*delta/ka.curr) : null;
    const deltaEl = document.getElementById('cp-kpi-delta');
    deltaEl.textContent = (delta>0?'+':'')+delta;
    deltaEl.style.color = delta>0?'var(--pos)':delta<0?'var(--neg)':'var(--muted)';
    document.getElementById('cp-kpi-delta-hint').textContent = deltaPct==null?'—' : ((delta>0?'+':'')+deltaPct.toFixed(1)+'% vs '+cA);
    document.getElementById('cp-kpi-vel').textContent = ka.vel.toFixed(1)+' → '+kb.vel.toFixed(1);
    const dvel = kb.vel - ka.vel;
    document.getElementById('cp-kpi-vel-hint').textContent = (dvel>0?'+':'')+dvel.toFixed(1)+' reg/día';
  }

  function cpRenderTopMovers(){
    const A = cpGetData(cpstate.monthA);
    const B = cpGetData(cpstate.monthB);
    if(!A || !B){ document.getElementById('cp-top-up').innerHTML='<li style="color:var(--muted)">—</li>'; document.getElementById('cp-top-down').innerHTML='<li style="color:var(--muted)">—</li>'; return; }
    const movers = [];
    // by model
    cpModelOrder().filter(m=>!cpstate.modelo||cpstate.modelo===m).forEach(m=>{
      const a = ((A.matrix_cnt||{})[m] && cpstate.agencia ? (A.matrix_cnt[m]||{})[cpstate.agencia] : null);
      let av, bv;
      if(cpstate.agencia){
        av = (A.matrix_cnt[m]||{})[cpstate.agencia]||0;
        bv = (B.matrix_cnt[m]||{})[cpstate.agencia]||0;
      } else {
        av = A.models?.[m]?.curr || 0;
        bv = B.models?.[m]?.curr || 0;
      }
      if(av || bv) movers.push({type:'modelo', name:m, a:av, b:bv, delta:bv-av});
    });
    // by dealer (only if no agency filter, otherwise it's just one)
    if(!cpstate.agencia){
      cpDealerOrder().forEach(d=>{
        let av, bv;
        if(cpstate.modelo){
          av = (A.matrix_cnt[cpstate.modelo]||{})[d]||0;
          bv = (B.matrix_cnt[cpstate.modelo]||{})[d]||0;
        } else {
          av = A.dealers?.[d]?.curr || 0;
          bv = B.dealers?.[d]?.curr || 0;
        }
        if(av || bv) movers.push({type:'agencia', name:d, a:av, b:bv, delta:bv-av});
      });
    }
    const ups = movers.filter(m=>m.delta>0).sort((a,b)=>b.delta-a.delta).slice(0,5);
    const downs = movers.filter(m=>m.delta<0).sort((a,b)=>a.delta-b.delta).slice(0,5);
    const fmtMover = mv => `<li style="padding:6px 0;border-bottom:1px dashed #eef0f3;display:flex;justify-content:space-between;gap:10px">
      <span><span style="font-size:10px;color:var(--muted);text-transform:uppercase">${mv.type}</span>&nbsp;<strong>${mv.name}</strong></span>
      <span style="font-variant-numeric:tabular-nums">${mv.a} → <strong>${mv.b}</strong> <span style="color:${mv.delta>0?'var(--pos)':'var(--neg)'};font-weight:700">(${mv.delta>0?'+':''}${mv.delta})</span></span>
    </li>`;
    document.getElementById('cp-top-up').innerHTML = ups.length? ups.map(fmtMover).join('') : '<li style="color:var(--muted);padding:10px 0">Sin mejoras en esta selección</li>';
    document.getElementById('cp-top-down').innerHTML = downs.length? downs.map(fmtMover).join('') : '<li style="color:var(--muted);padding:10px 0">Sin caídas en esta selección</li>';
  }

  function cpRenderModelChart(){
    destroy('cp-chart-model');
    const A = cpGetData(cpstate.monthA);
    const B = cpGetData(cpstate.monthB);
    if(!A || !B) return;
    const models = cpModelOrder().filter(m=>!cpstate.modelo||cpstate.modelo===m);
    const dealers = cpstate.agencia ? [cpstate.agencia] : null;
    const rows = models.map(m=>{
      let av, bv;
      if(dealers){
        av = (A.matrix_cnt[m]||{})[dealers[0]]||0;
        bv = (B.matrix_cnt[m]||{})[dealers[0]]||0;
      } else {
        av = A.models?.[m]?.curr || 0;
        bv = B.models?.[m]?.curr || 0;
      }
      return {model:m, a:av, b:bv, delta:bv-av};
    }).filter(r=>r.a||r.b).sort((a,b)=>(b.a+b.b)-(a.a+a.b));
    const cA = MONTHS_CONFIG.find(c=>c.key===cpstate.monthA)?.label || 'A';
    const cB = MONTHS_CONFIG.find(c=>c.key===cpstate.monthB)?.label || 'B';
    const labels = rows.map(r=>r.model);
    const aVals = rows.map(r=>r.a), bVals = rows.map(r=>r.b);
    const maxVal = Math.max(1, ...aVals, ...bVals);
    charts['cp-chart-model'] = new Chart(document.getElementById('cp-chart-model'),{
      type:'bar',
      data:{labels, datasets:[
        {label:cA, data:aVals, backgroundColor:'rgba(154,168,193,.55)', borderColor:'#9aa8c1', borderWidth:1, borderRadius:4, maxBarThickness:18},
        {label:cB, data:bVals, backgroundColor:'#2e5090', borderRadius:4, maxBarThickness:18},
      ]},
      options:{indexAxis:'y', layout:{padding:{right:60}},
        plugins:{
          legend:{position:'bottom',labels:{boxWidth:10,boxHeight:10,font:{size:11}}},
          tooltip:{callbacks:{afterLabel:c=>{const r=rows[c.dataIndex]; return 'Δ '+(r.delta>0?'+':'')+r.delta;}}},
          datalabels:{display:ctx=>ctx.dataset.data[ctx.dataIndex]>0,
            anchor:'end',align:'end',offset:2,
            font:{size:10,weight:'600'},
            color:ctx=>ctx.datasetIndex===1?'#2e5090':'#6b7280',
            formatter:v=>fmt(v)}
        },
        scales:{x:{beginAtZero:true,ticks:{precision:0},max:maxVal*1.18}, y:{ticks:{font:{size:11}}}},
        maintainAspectRatio:false
      }
    });
    // Table
    const tbody = document.querySelector('#cp-tbl-model tbody');
    document.getElementById('cp-tbl-model-h-a').textContent = cA;
    document.getElementById('cp-tbl-model-h-b').textContent = cB;
    rows.sort((a,b)=>b.delta-a.delta);
    tbody.innerHTML = rows.map(r=>{
      const dPct = r.a>0 ? (100*r.delta/r.a) : (r.b>0?Infinity:0);
      const dPctStr = isFinite(dPct) ? ((r.delta>0?'+':'')+dPct.toFixed(0)+'%') : (r.b>0?'nuevo':'—');
      const trend = r.delta>0?'<span style="color:var(--pos);font-weight:700">▲</span>':r.delta<0?'<span style="color:var(--neg);font-weight:700">▼</span>':'<span style="color:var(--muted)">—</span>';
      return `<tr><td class="left">${r.model}</td>
        <td>${fmt(r.a)}</td><td><strong>${fmt(r.b)}</strong></td>
        <td>${deltaCell(r.delta)}</td><td>${dPctStr}</td><td>${trend}</td></tr>`;
    }).join('');
  }

  function cpRenderAgencyChart(){
    destroy('cp-chart-agency');
    const A = cpGetData(cpstate.monthA);
    const B = cpGetData(cpstate.monthB);
    if(!A || !B) return;
    const dealers = (cpstate.agencia ? [cpstate.agencia] : cpDealerOrder()).filter(d=>d);
    const rows = dealers.map(d=>{
      let av, bv;
      if(cpstate.modelo){
        av = (A.matrix_cnt[cpstate.modelo]||{})[d]||0;
        bv = (B.matrix_cnt[cpstate.modelo]||{})[d]||0;
      } else {
        av = A.dealers?.[d]?.curr || 0;
        bv = B.dealers?.[d]?.curr || 0;
      }
      return {dealer:d, a:av, b:bv, delta:bv-av};
    }).filter(r=>r.a||r.b).sort((a,b)=>(b.a+b.b)-(a.a+a.b));
    const cA = MONTHS_CONFIG.find(c=>c.key===cpstate.monthA)?.label || 'A';
    const cB = MONTHS_CONFIG.find(c=>c.key===cpstate.monthB)?.label || 'B';
    const labels = rows.map(r=>r.dealer);
    const aVals = rows.map(r=>r.a), bVals = rows.map(r=>r.b);
    const maxVal = Math.max(1, ...aVals, ...bVals);
    charts['cp-chart-agency'] = new Chart(document.getElementById('cp-chart-agency'),{
      type:'bar',
      data:{labels, datasets:[
        {label:cA, data:aVals, backgroundColor:'rgba(154,168,193,.55)', borderColor:'#9aa8c1', borderWidth:1, borderRadius:4, maxBarThickness:18},
        {label:cB, data:bVals, backgroundColor:'#2e5090', borderRadius:4, maxBarThickness:18},
      ]},
      options:{indexAxis:'y', layout:{padding:{right:60}},
        plugins:{legend:{position:'bottom',labels:{boxWidth:10,boxHeight:10,font:{size:11}}},
          tooltip:{callbacks:{afterLabel:c=>{const r=rows[c.dataIndex]; return 'Δ '+(r.delta>0?'+':'')+r.delta;}}},
          datalabels:{display:ctx=>ctx.dataset.data[ctx.dataIndex]>0, anchor:'end',align:'end',offset:2,
            font:{size:10,weight:'600'}, color:ctx=>ctx.datasetIndex===1?'#2e5090':'#6b7280', formatter:v=>fmt(v)}},
        scales:{x:{beginAtZero:true,ticks:{precision:0},max:maxVal*1.18}, y:{ticks:{font:{size:11}}}},
        maintainAspectRatio:false
      }
    });
    const tbody = document.querySelector('#cp-tbl-agency tbody');
    document.getElementById('cp-tbl-agency-h-a').textContent = cA;
    document.getElementById('cp-tbl-agency-h-b').textContent = cB;
    rows.sort((a,b)=>b.delta-a.delta);
    tbody.innerHTML = rows.map(r=>{
      const dPct = r.a>0 ? (100*r.delta/r.a) : (r.b>0?Infinity:0);
      const dPctStr = isFinite(dPct) ? ((r.delta>0?'+':'')+dPct.toFixed(0)+'%') : (r.b>0?'nuevo':'—');
      const trend = r.delta>0?'<span style="color:var(--pos);font-weight:700">▲</span>':r.delta<0?'<span style="color:var(--neg);font-weight:700">▼</span>':'<span style="color:var(--muted)">—</span>';
      return `<tr><td class="left">${r.dealer}</td>
        <td>${fmt(r.a)}</td><td><strong>${fmt(r.b)}</strong></td>
        <td>${deltaCell(r.delta)}</td><td>${dPctStr}</td><td>${trend}</td></tr>`;
    }).join('');
  }

  function cpRenderChannelChart(){
    destroy('cp-chart-channel');
    const A = cpGetData(cpstate.monthA);
    const B = cpGetData(cpstate.monthB);
    if(!A || !B) return;
    function aggCh(month){
      const dmc = month.dealer_model_channel || {};
      const dealers = cpstate.agencia ? [cpstate.agencia] : Object.keys(dmc);
      const models = cpstate.modelo ? [cpstate.modelo] : (month.model_order||[]);
      const out = {};
      dealers.forEach(d=>{
        models.forEach(m=>{
          const ms = (dmc[d]||{})[m] || {};
          Object.entries(ms).forEach(([k,v])=>{
            // Comparativo: sólo canales marketing (consistente con matrix_cnt en KPIs).
            if(!FORD_TAB_MARKETING_CHANNELS.has(k)) return;
            out[k] = (out[k]||0) + (v||0);
          });
        });
      });
      return out;
    }
    const a = aggCh(A), b = aggCh(B);
    const labels = Array.from(new Set([...Object.keys(a),...Object.keys(b)]))
      .sort((x,y)=>((b[y]||0)+(a[y]||0)) - ((b[x]||0)+(a[x]||0)));
    const aVals = labels.map(l=>a[l]||0), bVals = labels.map(l=>b[l]||0);
    const cA = MONTHS_CONFIG.find(c=>c.key===cpstate.monthA)?.label || 'A';
    const cB = MONTHS_CONFIG.find(c=>c.key===cpstate.monthB)?.label || 'B';
    const maxVal = Math.max(1, ...aVals, ...bVals);
    charts['cp-chart-channel'] = new Chart(document.getElementById('cp-chart-channel'),{
      type:'bar',
      data:{labels, datasets:[
        {label:cA, data:aVals, backgroundColor:'rgba(154,168,193,.55)', borderColor:'#9aa8c1', borderWidth:1, borderRadius:4, maxBarThickness:20},
        {label:cB, data:bVals, backgroundColor:'#2e5090', borderRadius:4, maxBarThickness:20},
      ]},
      options:{indexAxis:'y', layout:{padding:{right:60}},
        plugins:{legend:{position:'bottom',labels:{boxWidth:10,boxHeight:10,font:{size:11}}},
          tooltip:{callbacks:{afterLabel:c=>'Δ '+((bVals[c.dataIndex]-aVals[c.dataIndex])>0?'+':'')+(bVals[c.dataIndex]-aVals[c.dataIndex])}},
          datalabels:{display:ctx=>ctx.dataset.data[ctx.dataIndex]>0, anchor:'end',align:'end',offset:2,
            font:{size:10,weight:'600'}, color:ctx=>ctx.datasetIndex===1?'#2e5090':'#6b7280', formatter:v=>fmt(v)}},
        scales:{x:{beginAtZero:true,ticks:{precision:0},max:maxVal*1.18}, y:{ticks:{font:{size:11}}}},
        maintainAspectRatio:false
      }
    });
  }

  function cpRenderHeatmap(){
    const A = cpGetData(cpstate.monthA);
    const B = cpGetData(cpstate.monthB);
    if(!A || !B){ document.getElementById('cp-heat-head').innerHTML=''; document.querySelector('#cp-heatmap tbody').innerHTML=''; return; }
    const models = cpModelOrder().filter(m=>!cpstate.modelo||cpstate.modelo===m);
    const dealers = (cpstate.agencia? [cpstate.agencia] : cpDealerOrder()).filter(Boolean);
    document.getElementById('cp-heat-head').innerHTML =
      `<tr><th class="left">Modelo</th>${dealers.map(d=>`<th>${d}</th>`).join('')}<th>Total Δ</th></tr>`;
    const tbody = document.querySelector('#cp-heatmap tbody');
    tbody.innerHTML = models.map(m=>{
      let rowDelta = 0;
      const cells = dealers.map(d=>{
        const av = (A.matrix_cnt[m]||{})[d]||0;
        const bv = (B.matrix_cnt[m]||{})[d]||0;
        const delta = bv-av;
        rowDelta += delta;
        if(av===0 && bv===0) return `<td class="cell dash" title="Sin tráfico en ambos meses">—</td>`;
        const cls = delta>=5?'green':delta<=-5?'red':'yellow';
        const sign = delta>0?'+':'';
        return `<td class="cell ${cls}" title="${m} en ${d}: ${av} → ${bv} (Δ ${sign}${delta})"><div class="cell-with-count"><span>${sign}${delta}</span><span class="ct">${av}→${bv}</span></div></td>`;
      }).join('');
      const tcls = rowDelta>=5?'green':rowDelta<=-5?'red':rowDelta===0?'grey':'yellow';
      const tsign = rowDelta>0?'+':'';
      const totalCell = `<td class="cell ${tcls}" style="font-weight:800">${tsign}${rowDelta}</td>`;
      return `<tr><td class="left">${m}</td>${cells}${totalCell}</tr>`;
    }).join('');
  }

  // ---- EVOLUCIÓN MULTI-MES ----
  const evstate = { mode: 'total', norm: 'abs' };
  const EV_PALETTE = ['#003478','#2e5090','#5c84d6','#9aa8c1','#f57f17','#2e7d32','#c62828','#8b0000','#6b7280','#5c84d6'];

  function cpEvFilteredValueForMonth(monthData, scopeKey){
    // Returns the filtered traffic count for a given (month, scopeKey)
    // scopeKey can be: 'TOTAL', a model name, or 'AG:dealerName'
    if(!monthData) return 0;
    const dealersAll = monthData.dealer_order || [];
    const modelsAll = monthData.model_order || [];
    const filterAg = cpstate.agencia ? [cpstate.agencia] : dealersAll;
    const filterMd = cpstate.modelo ? [cpstate.modelo] : modelsAll;
    if(scopeKey === 'TOTAL'){
      let s = 0;
      filterAg.forEach(d=>{
        filterMd.forEach(m=>{ s += (monthData.matrix_cnt[m]||{})[d]||0; });
      });
      // Otros for Ford if no agency filter
      if(cpstate.marca==='FORD' && !cpstate.agencia && monthData.dealers?.['Otros']){
        filterMd.forEach(m=>{ s += (monthData.dealers['Otros'].byModel||{})[m] || 0; });
      }
      return s;
    }
    if(scopeKey.startsWith('AG:')){
      const d = scopeKey.slice(3);
      let s = 0;
      filterMd.forEach(m=>{ s += (monthData.matrix_cnt[m]||{})[d]||0; });
      return s;
    }
    // Model scope
    const m = scopeKey;
    let s = 0;
    filterAg.forEach(d=>{ s += (monthData.matrix_cnt[m]||{})[d]||0; });
    if(cpstate.marca==='FORD' && !cpstate.agencia && monthData.dealers?.['Otros']){
      s += (monthData.dealers['Otros'].byModel||{})[m] || 0;
    }
    return s;
  }

  function cpEvBuildSparkline(values, color){
    // Build inline SVG sparkline: width 220, height 46
    const W = 220, H = 46, pad = 4;
    const n = values.length;
    if(!n) return '';
    const maxV = Math.max(1, ...values);
    const xStep = n>1 ? (W - pad*2)/(n-1) : 0;
    const pts = values.map((v,i)=>{
      const x = pad + i*xStep;
      const y = H - pad - (v/maxV)*(H - pad*2 - 2);
      return [x, y];
    });
    const lineD = pts.map((p,i)=>(i===0?'M':'L')+p[0].toFixed(1)+','+p[1].toFixed(1)).join(' ');
    const areaD = lineD + ` L${pts[pts.length-1][0].toFixed(1)},${(H-pad).toFixed(1)} L${pts[0][0].toFixed(1)},${(H-pad).toFixed(1)} Z`;
    const dots = pts.map((p,i)=>`<circle class="pt" cx="${p[0].toFixed(1)}" cy="${p[1].toFixed(1)}" r="${i===n-1?3.5:2.5}" fill="${color}"/>`).join('');
    return `<svg class="ev-spark" viewBox="0 0 ${W} ${H}" preserveAspectRatio="none">
      <path class="ar" d="${areaD}" fill="${color}"/>
      <path class="ln" d="${lineD}" stroke="${color}"/>
      ${dots}
    </svg>`;
  }

  function cpRenderEvolution(){
    destroy('cp-chart-evolution');
    const labels = MONTHS_CONFIG.map(c=>c.label);
    const labelsShort = MONTHS_CONFIG.map(c=>c.label.split(' ')[0].slice(0,3));
    const monthDatas = MONTHS_CONFIG.map(c => (cpstate.marca==='FORD' ? FORD_MONTHS[c.key] : (BRANDS_MONTHS[c.key]||{})[cpstate.marca]));
    const daysLab = monthDatas.map(d => d?.days_lab || 1);
    const norm = evstate.norm === 'day';
    const normVal = (v, i) => norm ? +(v / daysLab[i]).toFixed(2) : v;

    const lineDiv = document.getElementById('cp-evolution-line');
    const cardsDiv = document.getElementById('cp-evolution-cards');

    // Header summary (always)
    const totals = monthDatas.map((md,i) => normVal(cpEvFilteredValueForMonth(md, 'TOTAL'), i));
    const first = totals[0]||0, last = totals[totals.length-1]||0;
    const dPctTot = first>0 ? (100*(last-first)/first) : null;
    const trendTxt = dPctTot==null ? '—'
      : dPctTot>0 ? `<span style="color:var(--pos);font-weight:700">▲ +${dPctTot.toFixed(1)}%</span> de ${labels[0]} a ${labels[labels.length-1]}`
      : dPctTot<0 ? `<span style="color:var(--neg);font-weight:700">▼ ${dPctTot.toFixed(1)}%</span> de ${labels[0]} a ${labels[labels.length-1]}`
      : `sin cambio neto`;
    document.getElementById('cp-ev-summary').innerHTML = trendTxt + (norm?' · normalizado por día lab.':'');

    if(evstate.mode === 'total'){
      lineDiv.style.display = '';
      cardsDiv.style.display = 'none';
      charts['cp-chart-evolution'] = new Chart(document.getElementById('cp-chart-evolution'),{
        type:'line',
        data:{labels, datasets:[{
          label:'Tráfico'+(norm?' / día':''),
          data: totals,
          borderColor:'#003478', backgroundColor:'rgba(0,52,120,.15)',
          fill:true, tension:.25, pointRadius:5, pointBackgroundColor:'#003478', borderWidth:2.5,
        }]},
        options:{
          layout:{padding:{top:28}},  // espacio para que el datalabel del punto más alto no se corte
          plugins:{
            legend:{display:false},
            tooltip:{callbacks:{label:c=>' '+(c.parsed.y==null?'—':fmt(c.parsed.y))+(norm?' / día':' reg.')}},
            datalabels:{display:true, anchor:'end',align:'top',offset:6, clip:false,
              font:{size:12,weight:'700'}, color:'#003478', formatter:v=>fmt(v)}
          },
          scales:{
            y:{beginAtZero:true, grace:'10%', ticks:{precision:norm?1:0},
               title:{display:true,text:norm?'Tráfico / día laborable':'Tráfico total',color:'#6b7280',font:{size:11}}},
            x:{ticks:{font:{size:12}}}
          },
          interaction:{mode:'index',intersect:false},
          maintainAspectRatio:false
        }
      });
      return;
    }

    // Mode 'model' or 'agency': render mini-cards grid
    lineDiv.style.display = 'none';
    cardsDiv.style.display = '';

    let items;  // [{name, values[], color}]
    if(evstate.mode === 'model'){
      const allModels = Array.from(new Set(monthDatas.flatMap(md => md?.model_order || [])));
      const filtered = cpstate.modelo ? [cpstate.modelo] : allModels;
      items = filtered.map((m, i)=>({
        name: m,
        values: monthDatas.map((md,j)=> normVal(cpEvFilteredValueForMonth(md, m), j)),
        color: EV_PALETTE[i % EV_PALETTE.length],
      }));
    } else {
      // agency
      const allDealers = Array.from(new Set(monthDatas.flatMap(md => md?.dealer_order || [])));
      const filtered = cpstate.agencia ? [cpstate.agencia] : allDealers;
      items = filtered.map((d, i)=>({
        name: d,
        values: monthDatas.map((md,j)=> normVal(cpEvFilteredValueForMonth(md, 'AG:'+d), j)),
        color: EV_PALETTE[i % EV_PALETTE.length],
      }));
    }

    // Sort: highest total volume first
    items.forEach(it=>{ it.total = it.values.reduce((a,b)=>a+b,0); });
    items.sort((a,b)=>b.total-a.total);
    // Filter empty
    items = items.filter(it => it.total > 0);

    if(items.length === 0){
      cardsDiv.innerHTML = '<div style="grid-column:1/-1;text-align:center;color:var(--muted);padding:40px">Sin datos para esta selección</div>';
      return;
    }

    cardsDiv.innerHTML = items.map(it=>{
      const a = it.values[0]||0, b = it.values[it.values.length-1]||0;
      const dAbs = b - a;
      const dPct = a>0 ? (100*dAbs/a) : (b>0?Infinity:0);
      const cls = dPct >= 5 ? 'up' : dPct <= -5 ? 'down' : 'flat';
      const sign = dAbs>0?'+':'';
      const dPctStr = isFinite(dPct) ? `${sign}${dPct.toFixed(0)}%` : (b>0?'nuevo':'—');
      const arrow = dPct >= 5 ? '▲' : dPct <= -5 ? '▼' : '→';
      const sparkColor = cls==='up'?'#2e7d32' : cls==='down'?'#c62828' : '#9aa8c1';
      const seqRow = it.values.map((v,j)=>{
        const fmtVal = norm ? v.toFixed(1) : fmt(v);
        return `<span><strong>${fmtVal}</strong> <span style="color:var(--muted)">${labelsShort[j]}</span></span>`;
      }).join(' · ');
      return `<div class="ev-card ${cls}" title="${it.name}: ${a} → ${b}">
        <div class="ev-card-head">
          <span class="ev-name">${it.name}</span>
          <span class="ev-badge ${cls}">${arrow} ${dPctStr}</span>
        </div>
        ${cpEvBuildSparkline(it.values, sparkColor)}
        <div class="ev-foot">
          <div class="seq">${seqRow}</div>
        </div>
      </div>`;
    }).join('');
  }

  // ---- AVANCE DIARIO COMPARADO ----
  const dcstate = { mode: 'cum' };  // 'cum' or 'daily'

  function cpDailySeriesForMonth(monthData){
    if(!monthData) return [];
    const breakdown = monthData.daily_breakdown || {};
    const dealersAll = monthData.dealer_order || [];
    const modelsAll = monthData.model_order || [];
    const filterAg = cpstate.agencia ? [cpstate.agencia] : dealersAll;
    const filterMd = cpstate.modelo ? [cpstate.modelo] : modelsAll;
    const includeOtros = cpstate.marca === 'FORD' && !cpstate.agencia;
    const dealersWithOtros = includeOtros ? [...filterAg, 'Otros'] : filterAg;
    const dailyTotals = {};
    dealersWithOtros.forEach(d => {
      const dd = breakdown[d] || {};
      filterMd.forEach(m => {
        const series = dd[m] || {};
        Object.entries(series).forEach(([day, cnt]) => {
          const dn = +day;
          dailyTotals[dn] = (dailyTotals[dn] || 0) + cnt;
        });
      });
    });
    return dailyTotals;  // {day: count}
  }

  function cpRenderDailyCompare(){
    destroy('cp-chart-daily');
    // Sólo los 2 meses seleccionados (Mes A y Mes B)
    const cfgA = MONTHS_CONFIG.find(c=>c.key===cpstate.monthA) || MONTHS_CONFIG[0];
    const cfgB = MONTHS_CONFIG.find(c=>c.key===cpstate.monthB) || MONTHS_CONFIG[MONTHS_CONFIG.length-1];
    const dataA = cpstate.marca==='FORD' ? FORD_MONTHS[cfgA.key] : (BRANDS_MONTHS[cfgA.key]||{})[cpstate.marca];
    const dataB = cpstate.marca==='FORD' ? FORD_MONTHS[cfgB.key] : (BRANDS_MONTHS[cfgB.key]||{})[cpstate.marca];
    const months = [
      {cfg: cfgA, data: dataA, role: 'A'},
      {cfg: cfgB, data: dataB, role: 'B'},
    ];
    const maxDays = Math.max(...months.map(m => (m.data?.pace?.length || 31)));
    const labels = Array.from({length: maxDays}, (_, i) => String(i+1));

    const datasets = [];
    months.forEach((m, idx) => {
      if(!m.data) return;
      const dailyTotals = cpDailySeriesForMonth(m.data);
      const monthLen = (m.data.pace || []).length || 31;
      const series = [];
      let running = 0;
      for(let d=1; d<=maxDays; d++){
        if(d > monthLen){
          series.push(null);
        } else if(dcstate.mode === 'cum'){
          running += dailyTotals[d] || 0;
          series.push(running);
        } else {
          series.push(dailyTotals[d] || 0);
        }
      }
      // A = referencia (gris/punteado), B = principal (azul/sólido)
      const isB = m.role === 'B';
      const color = isB ? '#003478' : '#9aa8c1';
      datasets.push({
        label: m.cfg.label,
        data: series,
        borderColor: color,
        backgroundColor: isB ? 'rgba(0,52,120,.18)' : 'rgba(154,168,193,.10)',
        fill: dcstate.mode==='cum',
        tension: dcstate.mode==='cum' ? .25 : 0,
        pointRadius: isB ? 3.5 : 2.5,
        pointBackgroundColor: color,
        borderWidth: isB ? 3 : 2,
        borderDash: isB ? [] : [5, 4],
        spanGaps: false,
      });
    });

    // Summary text: comparación al día actual del mes B vs mismo día del mes A
    if(dataA && dataB){
      const cutDay = dataB.cut_day || (dataB.pace || []).length;
      const dailyA = cpDailySeriesForMonth(dataA);
      const dailyB = cpDailySeriesForMonth(dataB);
      const monthLenA = (dataA.pace || []).length || 31;
      // Comparar al min(cutDay, monthLenA) para que sea válido en el mes A
      const compareDay = Math.min(cutDay, monthLenA);
      let cumA = 0, cumB = 0;
      for(let d=1; d<=compareDay; d++){
        cumA += dailyA[d] || 0;
        cumB += dailyB[d] || 0;
      }
      const delta = cumB - cumA;
      const dPct = cumA > 0 ? (100 * delta / cumA) : null;
      const arrow = delta>0?'▲':delta<0?'▼':'—';
      const color = delta>0?'var(--pos)':delta<0?'var(--neg)':'var(--muted)';
      const pctStr = dPct==null ? '' : ` (${delta>0?'+':''}${dPct.toFixed(1)}%)`;
      const labelA = cfgA.label.split(' ')[0];
      const labelB = cfgB.label.split(' ')[0];
      document.getElementById('cp-dc-summary').innerHTML =
        `Al día ${compareDay} · ${labelB} <strong>${fmt(cumB)}</strong> vs ${labelA} <strong>${fmt(cumA)}</strong> ` +
        `<span style="color:${color};font-weight:700">${arrow} ${delta>0?'+':''}${delta}${pctStr}</span>`;
    } else {
      document.getElementById('cp-dc-summary').textContent = '';
    }

    charts['cp-chart-daily'] = new Chart(document.getElementById('cp-chart-daily'),{
      type:'line',
      data:{ labels, datasets },
      options:{
        layout:{padding:{top:24, bottom:8}},
        plugins:{
          legend:{position:'bottom',labels:{boxWidth:10,boxHeight:10,font:{size:11},padding:8}},
          tooltip:{mode:'index',intersect:false,
            callbacks:{
              title: items => 'Día ' + items[0].label,
              label: c => ' '+c.dataset.label+': '+(c.parsed.y==null?'—':fmt(c.parsed.y))
            }},
          datalabels:{
            display: function(ctx){
              const v = ctx.dataset.data[ctx.dataIndex];
              return v != null && v > 0;
            },
            anchor: 'end',
            align: function(ctx){ return ctx.datasetIndex === 1 ? 'top' : 'bottom'; },
            offset: 4,
            font: function(ctx){ return {size: 10, weight: '700'}; },
            color: function(ctx){ return ctx.datasetIndex === 1 ? '#003478' : '#6b7280'; },
            formatter: function(v){ return fmt(v); }
          }
        },
        scales:{
          y:{beginAtZero:true,ticks:{precision:0},
             title:{display:true,text:dcstate.mode==='cum'?'Tráfico acumulado':'Tráfico diario',color:'#6b7280',font:{size:11}}},
          x:{ticks:{font:{size:10}, autoSkip:true, maxTicksLimit:15},
             title:{display:true,text:'Día del mes',color:'#6b7280',font:{size:11}}}
        },
        interaction:{mode:'index',intersect:false},
        maintainAspectRatio:false
      }
    });
  }

  // Toggle bindings
  document.querySelectorAll('.dc-mode-btn').forEach(btn=>{
    btn.addEventListener('click', ()=>{
      dcstate.mode = btn.dataset.mode;
      document.querySelectorAll('.dc-mode-btn').forEach(b=>{
        const active = b.dataset.mode===dcstate.mode;
        b.style.background = active ? '#003478':'transparent';
        b.style.color = active ? '#fff':'var(--ink)';
      });
      cpRenderDailyCompare();
    });
  });

  document.querySelectorAll('.ev-mode-btn').forEach(btn=>{
    btn.addEventListener('click', ()=>{
      evstate.mode = btn.dataset.mode;
      document.querySelectorAll('.ev-mode-btn').forEach(b=>{
        const active = b.dataset.mode===evstate.mode;
        b.style.background = active ? '#003478':'transparent';
        b.style.color = active ? '#fff':'var(--ink)';
      });
      cpRenderEvolution();
    });
  });
  document.querySelectorAll('.ev-norm-btn').forEach(btn=>{
    btn.addEventListener('click', ()=>{
      evstate.norm = btn.dataset.norm;
      document.querySelectorAll('.ev-norm-btn').forEach(b=>{
        const active = b.dataset.norm===evstate.norm;
        b.style.background = active ? '#003478':'transparent';
        b.style.color = active ? '#fff':'var(--ink)';
      });
      cpRenderEvolution();
    });
  });

  function cpRenderAll(){
    cpRefreshSubFilters();
    cpRenderFilterSummary();
    cpRenderEvolution();
    cpRenderDailyCompare();
    cpRenderKpis();
    cpRenderTopMovers();
    cpRenderModelChart();
    cpRenderAgencyChart();
    cpRenderChannelChart();
    cpRenderHeatmap();
  }

  // Bindings
  document.getElementById('cp-monthA').addEventListener('change', e=>{ cpstate.monthA = e.target.value; cpRenderAll(); });
  document.getElementById('cp-monthB').addEventListener('change', e=>{ cpstate.monthB = e.target.value; cpRenderAll(); });
  document.getElementById('cp-marca').addEventListener('change', e=>{
    cpstate.marca = e.target.value;
    cpstate.agencia = ''; cpstate.modelo = '';
    cpRenderAll();
  });
  document.getElementById('cp-agencia').addEventListener('change', e=>{ cpstate.agencia = e.target.value; cpRenderAll(); });
  document.getElementById('cp-modelo').addEventListener('change', e=>{ cpstate.modelo = e.target.value; cpRenderAll(); });
  document.getElementById('cp-reset').addEventListener('click', ()=>{
    cpstate.agencia=''; cpstate.modelo='';
    document.getElementById('cp-agencia').value=''; document.getElementById('cp-modelo').value='';
    cpRenderAll();
  });

  cpRenderAll();

  // =========================================================
  //                  OTROS TAB (password gated)
  // =========================================================
  const OTROS_HASH = 'e3887ed7533583c89c72aa19a6bcc0f38c5370374af828009770eb85f142a30c';
  // SHA-256 de la contraseña. Cambiar al re-build si quieres otra.

  async function sha256(text){
    const buf = new TextEncoder().encode(text);
    const hash = await crypto.subtle.digest('SHA-256', buf);
    return Array.from(new Uint8Array(hash)).map(b=>b.toString(16).padStart(2,'0')).join('');
  }
  function otrosUnlocked(){ return localStorage.getItem('otros_unlocked')==='1'; }
  function otrosShowContent(){
    document.getElementById('otros-gate').style.display = 'none';
    document.getElementById('otros-content').style.display = 'block';
    initAnalysis();
    renderAnalysis();
  }
  function otrosShowGate(){
    document.getElementById('otros-gate').style.display = '';
    document.getElementById('otros-content').style.display = 'none';
    document.getElementById('otros-pw').value = '';
    document.getElementById('otros-pw-err').textContent = '';
    setTimeout(()=>{ const el=document.getElementById('otros-pw'); if(el) el.focus(); }, 50);
  }
  async function tryUnlock(){
    const input = document.getElementById('otros-pw').value;
    if(!input) return;
    const h = await sha256(input);
    if(h === OTROS_HASH){
      localStorage.setItem('otros_unlocked','1');
      otrosShowContent();
    } else {
      document.getElementById('otros-pw-err').textContent = 'Contraseña incorrecta';
      document.getElementById('otros-pw').value = '';
    }
  }
  document.getElementById('otros-pw-btn').addEventListener('click', tryUnlock);
  document.getElementById('otros-pw').addEventListener('keydown', e=>{ if(e.key==='Enter') tryUnlock(); });
  document.getElementById('otros-logout').addEventListener('click', ()=>{
    localStorage.removeItem('otros_unlocked');
    otrosShowGate();
  });
  // Hook into tab switch to refresh unlock state
  // Acceso libre: siempre mostrar contenido (sin gate de contraseña)
  document.querySelector('.tab-btn[data-tab="otros"]').addEventListener('click', ()=>{
    otrosShowContent();
  });
  // Asegurar que arranca desbloqueado
  localStorage.setItem('otros_unlocked','1');

  // =========================================================
  //              PESTAÑA CONVERSIÓN (gate compartido con Otros)
  // =========================================================
  function convShowGate(){
    document.getElementById('conv-gate').style.display = 'block';
    document.getElementById('conv-content').style.display = 'none';
  }
  function convShowContent(){
    document.getElementById('conv-gate').style.display = 'none';
    document.getElementById('conv-content').style.display = 'block';
    renderConversion();
  }
  async function convTryUnlock(){
    const pw = document.getElementById('conv-pw').value;
    const err = document.getElementById('conv-pw-err');
    err.textContent = '';
    const h = await sha256Hex(pw);
    if(h === OTROS_HASH){
      localStorage.setItem('otros_unlocked', '1');
      convShowContent();
    } else {
      err.textContent = 'Contraseña incorrecta';
    }
  }
  document.getElementById('conv-pw-btn').addEventListener('click', convTryUnlock);
  document.getElementById('conv-pw').addEventListener('keydown', e=>{ if(e.key==='Enter') convTryUnlock(); });
  document.getElementById('conv-logout').addEventListener('click', ()=>{
    localStorage.removeItem('otros_unlocked');
    convShowGate();
  });
  // Acceso libre: siempre mostrar contenido (sin gate de contraseña)
  document.querySelector('.tab-btn[data-tab="conv"]').addEventListener('click', ()=>{
    convShowContent();
  });

  // Estado de filtros de Conversión
  const convState = { mes:'', agencia:'', zona:'', modelo:'', canal:'' };
  function convFilterClientes(){
    const CONV = DATA.conversion_data?.FORD;
    if(!CONV || !CONV.clientes_flat) return [];
    return CONV.clientes_flat.filter(c => {
      if(convState.mes     && c.first_ym !== convState.mes)    return false;
      if(convState.agencia && c.agencia !== convState.agencia) return false;
      if(convState.zona    && c.zona    !== convState.zona)    return false;
      if(convState.modelo  && c.modelo  !== convState.modelo)  return false;
      if(convState.canal   && c.canal   !== convState.canal)   return false;
      return true;
    });
  }
  function convAggregate(clientes, by){
    // Definición B: 1 cliente único = 1 unidad de tráfico, sin importar cuántas veces vino
    const out = {};
    clientes.forEach(c => {
      const k = c[by] || 'Sin asignar';
      if(!out[k]) out[k] = {traffic:0, matched:0, ventas:0};
      out[k].traffic++;                              // 1 persona única
      if(c.cerro){
        out[k].matched++;                             // 1 persona que cerró
        out[k].ventas += (c.n_ventas || 1);           // pero puede haber comprado varios autos
      }
    });
    Object.values(out).forEach(d => {
      d.conv_pct = d.traffic > 0 ? +(100*d.matched/d.traffic).toFixed(1) : 0;
    });
    return out;
  }
  function convCalcCiclo(clientes){
    const ds = clientes.filter(c => c.ciclo_dias != null).map(c => c.ciclo_dias).sort((a,b)=>a-b);
    if(ds.length === 0) return {n:0, mediana:null, promedio:null, p75:null};
    const med = ds[Math.floor(ds.length/2)];
    const prom = ds.reduce((s,x)=>s+x,0) / ds.length;
    const p75 = ds[Math.floor(ds.length*0.75)];
    return {n:ds.length, mediana:med, promedio:+prom.toFixed(1), p75};
  }
  function convInitFilters(){
    const CONV = DATA.conversion_data?.FORD;
    if(!CONV || !CONV.clientes_flat) return;
    // Poblar modelo / canal dinámicamente
    const modelos = new Set(), canales = new Set();
    CONV.clientes_flat.forEach(c => {
      if(c.modelo) modelos.add(c.modelo);
      if(c.canal)  canales.add(c.canal);
    });
    const selMod = document.getElementById('conv-f-modelo');
    const selCan = document.getElementById('conv-f-canal');
    if(selMod && selMod.options.length === 1){
      [...modelos].sort().forEach(m => {
        const o = document.createElement('option'); o.value=m; o.textContent=m; selMod.appendChild(o);
      });
    }
    if(selCan && selCan.options.length === 1){
      [...canales].sort().forEach(c => {
        const o = document.createElement('option'); o.value=c; o.textContent=c; selCan.appendChild(o);
      });
    }
    ['mes','agencia','zona','modelo','canal'].forEach(k => {
      const el = document.getElementById('conv-f-'+k);
      if(!el || el.dataset._bound) return;
      el.dataset._bound = '1';
      el.addEventListener('change', e => {
        convState[k] = e.target.value;
        renderConversion();
      });
    });
    const resetBtn = document.getElementById('conv-f-reset');
    if(resetBtn && !resetBtn.dataset._bound){
      resetBtn.dataset._bound = '1';
      resetBtn.addEventListener('click', () => {
        Object.keys(convState).forEach(k => convState[k] = '');
        ['mes','agencia','zona','modelo','canal'].forEach(k => {
          const el = document.getElementById('conv-f-'+k);
          if(el) el.value = '';
        });
        renderConversion();
      });
    }
  }

  function renderConversion(){
    const CONV = DATA.conversion_data?.FORD;
    if(!CONV) return;
    convInitFilters();
    const clientes = convFilterClientes();
    // Definición B: personas únicas. Un cliente único = 1 unidad de tráfico.
    const n_traf  = clientes.length;
    const n_cerraron = clientes.filter(c => c.cerro).length;
    const n_ventas = clientes.filter(c => c.cerro).reduce((s,c) => s + (c.n_ventas || 1), 0);
    const conv = n_traf > 0 ? +(100*n_cerraron/n_traf).toFixed(1) : 0;
    const ciclo = convCalcCiclo(clientes);

    document.getElementById('conv-k-traf').textContent  = fmt(n_traf);
    document.getElementById('conv-k-cerr').textContent  = fmt(n_cerraron) + ' / ' + fmt(n_ventas);
    document.getElementById('conv-k-cerr-hint').textContent = `${n_cerraron} personas · ${n_ventas} vehículos facturados`;
    document.getElementById('conv-k-rate').textContent  = conv + '%';
    if(ciclo.mediana != null){
      document.getElementById('conv-k-ciclo').textContent = ciclo.mediana + 'd';
      document.getElementById('conv-k-ciclo-hint').textContent = `prom ${ciclo.promedio}d · p75 ${ciclo.p75}d · n=${ciclo.n}`;
    } else {
      document.getElementById('conv-k-ciclo').textContent = '—';
      document.getElementById('conv-k-ciclo-hint').textContent = 'Sin cierres en este filtro';
    }

    function pillColor(pct){
      if(pct >= 15) return 'green';
      if(pct >= 8) return 'yellow';
      if(pct >= 4) return 'orange';
      return 'red';
    }
    function visualBar(pct, maxPct){
      const w = maxPct>0 ? Math.max(2, Math.round(100*pct/maxPct)) : 0;
      const cls = pillColor(pct);
      const colors = {green:'#2e7d32', yellow:'#fbc02d', orange:'#ef6c00', red:'#c62828'};
      return `<div style="height:16px;background:#eef0f3;border-radius:4px;overflow:hidden;min-width:160px"><div style="height:100%;width:${w}%;background:${colors[cls]}"></div></div>`;
    }
    function renderTable(tbodySelector, data, labelHeader, sortByConv=true, minTraffic=0, topN=null){
      const allRows = Object.entries(data);
      // Total = TODA la data (no solo el slice mostrado) para que coincida con KPI hero
      const totAll = allRows.reduce((a,[,d])=>{
        a.t += d.traffic; a.m += (d.matched||0); a.v += (d.ventas||0); return a;
      }, {t:0,m:0,v:0});
      const totConv = totAll.t > 0 ? +(100*totAll.m/totAll.t).toFixed(1) : 0;
      // Slice de filas mostradas (filtro de display + top N)
      let rows = allRows.filter(([,d])=>d.traffic >= minTraffic);
      rows.sort((a,b)=> sortByConv ? (b[1].conv_pct - a[1].conv_pct) : ((b[1].matched||0) - (a[1].matched||0)));
      const slice = topN ? rows.slice(0, topN) : rows;
      const maxPct = Math.max(...slice.map(r=>r[1].conv_pct), 1);
      const tbody = document.querySelector(tbodySelector);
      const isRank = labelHeader === 'rank';
      tbody.innerHTML = slice.map(([k,d], i)=>{
        const cls = pillColor(d.conv_pct);
        const rankCol = isRank ? `<td class="num" style="font-weight:700;color:var(--muted)">${i+1}</td>` : '';
        return `<tr>
          ${rankCol}
          <td class="left"><strong>${k}</strong></td>
          <td class="num">${fmt(d.traffic)}</td>
          <td class="num" style="font-weight:700">${fmt(d.matched||0)}</td>
          <td class="num" style="color:var(--ford-2)">${fmt(d.ventas||0)}</td>
          <td class="num"><span class="status-pill ${cls}">${d.conv_pct.toFixed(1)}%</span></td>
          <td>${visualBar(d.conv_pct, maxPct)}</td>
        </tr>`;
      }).join('') + `<tr class="total">
        ${isRank ? '<td></td>' : ''}
        <td><strong>TOTAL</strong></td>
        <td class="num"><strong>${fmt(totAll.t)}</strong></td>
        <td class="num"><strong>${fmt(totAll.m)}</strong></td>
        <td class="num"><strong>${fmt(totAll.v)}</strong></td>
        <td class="num"><strong>${totConv.toFixed(1)}%</strong></td>
        <td></td>
      </tr>`;
    }

    // Recalcular breakdowns desde clientes filtrados
    const aggCanal   = convAggregate(clientes, 'canal');
    const aggModelo  = convAggregate(clientes, 'modelo');
    const aggAgencia = convAggregate(clientes, 'agencia');
    const aggAsesor  = convAggregate(clientes, 'asesor');
    // Filtrar asesores con <5 leads (ruido)
    const aggAsesorFilt = {};
    Object.entries(aggAsesor).forEach(([k,v]) => { if(v.traffic >= 5) aggAsesorFilt[k] = v; });

    // Sin minTraffic en canal/modelo/agencia (mostrar todos para que cuadre TOTAL).
    // Asesores sí filtramos a >=5 leads para evitar ruido individual.
    renderTable('#conv-tbl-canal tbody',   aggCanal,   'canal',   true);
    renderTable('#conv-tbl-modelo tbody',  aggModelo,  'modelo',  true);
    renderTable('#conv-tbl-agencia tbody', aggAgencia, 'agencia', true);
    renderTable('#conv-tbl-asesor tbody',  aggAsesorFilt, 'rank',  false, 5, 20);
    renderConvChartEvol();
    renderConvChartModelos();
  }

  // Gráfica de conversión por modelo mes a mes (líneas múltiples).
  // Cada modelo tiene un chip toggle independiente — el filtro global "Modelo"
  // se respeta también (si seleccionas un modelo arriba, solo se muestra ese).
  let convChartModelos = null;
  const CONV_MODELO_ORDER = ['TERRITORY','ESCAPE','EVEREST','EXPLORER','EXPEDITION','BRONCO','F-150','RANGER'];
  const CONV_MODELO_COLORS = {
    'TERRITORY':  '#003478', 'F-150':      '#c62828',
    'RANGER':     '#2e7d32', 'EVEREST':    '#a36307',
    'ESCAPE':     '#ef6c00', 'EXPLORER':   '#1565c0',
    'EXPEDITION': '#6a1b9a', 'BRONCO':     '#455a64',
  };
  // Estado: qué modelos están activos en el gráfico (toggle local al gráfico)
  const convChartModelosOn = {};
  CONV_MODELO_ORDER.forEach(m => convChartModelosOn[m] = true);

  function renderConvModelosChips(){
    const wrap = document.getElementById('conv-modelos-chips');
    if(!wrap) return;
    wrap.innerHTML = CONV_MODELO_ORDER.map(m => {
      const on = convChartModelosOn[m];
      const color = CONV_MODELO_COLORS[m];
      const bg = on ? color : '#fff';
      const fg = on ? '#fff' : color;
      const border = color;
      return `<button class="conv-model-chip" data-modelo="${m}" style="
        background:${bg};color:${fg};border:1.5px solid ${border};
        padding:4px 12px;border-radius:999px;font:inherit;font-size:11px;
        font-weight:600;cursor:pointer;letter-spacing:.3px;
        opacity:${on?'1':'0.5'};transition:all .15s">
        ${m}
      </button>`;
    }).join('') + `
      <button class="conv-model-chip-action" data-action="all" style="
        background:transparent;border:1px solid #d1d5db;padding:4px 12px;
        border-radius:999px;font:inherit;font-size:11px;color:var(--muted);
        cursor:pointer;margin-left:8px">Todos</button>
      <button class="conv-model-chip-action" data-action="none" style="
        background:transparent;border:1px solid #d1d5db;padding:4px 12px;
        border-radius:999px;font:inherit;font-size:11px;color:var(--muted);
        cursor:pointer">Ninguno</button>`;
    // Bindings
    wrap.querySelectorAll('.conv-model-chip').forEach(btn => {
      btn.addEventListener('click', () => {
        const m = btn.dataset.modelo;
        convChartModelosOn[m] = !convChartModelosOn[m];
        renderConvModelosChips();
        renderConvChartModelos();
      });
    });
    wrap.querySelectorAll('.conv-model-chip-action').forEach(btn => {
      btn.addEventListener('click', () => {
        const v = btn.dataset.action === 'all';
        CONV_MODELO_ORDER.forEach(m => convChartModelosOn[m] = v);
        renderConvModelosChips();
        renderConvChartModelos();
      });
    });
  }

  function renderConvChartModelos(){
    const CONV = DATA.conversion_data?.FORD;
    if(!CONV || !CONV.clientes_flat) return;
    const canvas = document.getElementById('conv-chart-modelos');
    if(!canvas) return;

    // Asegurar que los chips estén renderizados (primera vez)
    if(!document.querySelector('#conv-modelos-chips .conv-model-chip')){
      renderConvModelosChips();
    }

    // Filtros activos EXCEPTO mes y modelo (queremos ver todos los modelos activos)
    const filtered = CONV.clientes_flat.filter(c => {
      if(convState.agencia && c.agencia !== convState.agencia) return false;
      if(convState.zona    && c.zona    !== convState.zona)    return false;
      if(convState.canal   && c.canal   !== convState.canal)   return false;
      return true;
    });

    const meses  = ['2026-01','2026-02','2026-03','2026-04','2026-05'];
    const labels = ['Enero','Febrero','Marzo','Abril','Mayo'];
    const MODELO_ORDER = CONV_MODELO_ORDER;
    const COLORS = CONV_MODELO_COLORS;

    // Selección: si filtro global tiene modelo, usar solo ese; sino, los chips activos
    let modelosToShow;
    if(convState.modelo){
      modelosToShow = [convState.modelo];
    } else {
      modelosToShow = MODELO_ORDER.filter(m => convChartModelosOn[m]);
    }

    const datasets = modelosToShow.map(modelo => {
      const series = meses.map(ym => {
        const sub = filtered.filter(c => c.modelo === modelo && c.first_ym === ym);
        const tot = sub.length;
        const cerr = sub.filter(c => c.cerro).length;
        return {
          pct: tot > 0 ? Math.round(100*cerr/tot*10)/10 : null,
          tot, cerr
        };
      });
      const color = COLORS[modelo] || '#666';
      return {
        label: modelo,
        data: series.map(s => s.pct),
        _stats: series,
        borderColor: color,
        backgroundColor: color,
        pointBackgroundColor: color,
        pointBorderColor: '#fff',
        pointBorderWidth: 1,
        borderWidth: 2.5,
        pointRadius: 5,
        tension: 0.3,
        spanGaps: true,
        fill: false,
      };
    });

    if(convChartModelos){ convChartModelos.destroy(); }
    convChartModelos = new Chart(canvas, {
      type: 'line',
      data: { labels, datasets },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: 'nearest', intersect: false },
        plugins: {
          legend: {
            position: 'bottom',
            labels: { font:{size:11}, padding:10, usePointStyle:true, pointStyle:'circle' }
          },
          tooltip: {
            callbacks: {
              label: (ctx) => {
                const ds = ctx.dataset;
                const s = ds._stats[ctx.dataIndex];
                if(!s || s.tot === 0) return `${ds.label}: sin data`;
                return `${ds.label}: ${s.pct}% (${s.cerr}/${s.tot})`;
              }
            }
          },
          datalabels: {
            display: ctx => ctx.dataset.data[ctx.dataIndex] != null,
            anchor: 'end', align: 'top', offset: 5,
            color: ctx => ctx.dataset.borderColor,
            font: { size: 10, weight: '700' },
            formatter: v => v != null ? v + '%' : ''
          }
        },
        layout: { padding: { top: 24 } },
        scales: {
          y: {
            beginAtZero: true,
            ticks: { callback: v => v + '%', font:{size:11} },
            title: { display:true, text:'% Conversión', font:{size:11,weight:'600'} }
          },
          x: { ticks:{font:{size:11}}, grid:{display:false} }
        }
      }
    });
  }

  // Gráfica de evolución mensual de conversión (respeta todos los filtros excepto mes)
  let convChartEvol = null;
  function renderConvChartEvol(){
    const CONV = DATA.conversion_data?.FORD;
    if(!CONV || !CONV.clientes_flat) return;
    const canvas = document.getElementById('conv-chart-evol');
    if(!canvas) return;

    // Aplicar todos los filtros EXCEPTO mes (porque el gráfico ya separa por mes)
    const filtered = CONV.clientes_flat.filter(c => {
      if(convState.agencia && c.agencia !== convState.agencia) return false;
      if(convState.zona    && c.zona    !== convState.zona)    return false;
      if(convState.modelo  && c.modelo  !== convState.modelo)  return false;
      if(convState.canal   && c.canal   !== convState.canal)   return false;
      return true;
    });

    const meses  = ['2026-01','2026-02','2026-03','2026-04','2026-05'];
    const labels = ['Enero','Febrero','Marzo','Abril','Mayo'];
    const stats = meses.map(m => {
      const sub = filtered.filter(c => c.first_ym === m);
      const total = sub.length;
      const cerraron = sub.filter(c => c.cerro).length;
      const ventas = sub.filter(c => c.cerro).reduce((s,c) => s + (c.n_ventas || 1), 0);
      const pct = total > 0 ? Math.round(100*cerraron/total*10)/10 : null;
      return { total, cerraron, ventas, pct };
    });

    if(convChartEvol){ convChartEvol.destroy(); }
    convChartEvol = new Chart(canvas, {
      type: 'line',
      data: {
        labels,
        datasets: [{
          label: '% Conversión',
          data: stats.map(s => s.pct),
          borderColor: '#003478',
          backgroundColor: 'rgba(0,52,120,0.10)',
          borderWidth: 3,
          pointRadius: 6,
          pointBackgroundColor: '#003478',
          pointBorderColor: '#fff',
          pointBorderWidth: 2,
          tension: 0.3,
          fill: true,
          spanGaps: true,
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode:'index', intersect:false },
        plugins: {
          legend: { display:false },
          tooltip: {
            callbacks: {
              label: (ctx) => {
                const s = stats[ctx.dataIndex];
                if(s.total === 0) return 'Sin tráfico';
                return [
                  `Conversión: ${s.pct}%`,
                  `${s.cerraron} cerraron de ${s.total} personas`,
                  `${s.ventas} vehículos facturados`,
                ];
              }
            }
          },
          datalabels: {
            display: ctx => stats[ctx.dataIndex].pct != null,
            anchor: 'end', align: 'top', offset: 8,
            color: '#003478', font: { size: 13, weight: '700' },
            formatter: (v, ctx) => stats[ctx.dataIndex].pct != null ? stats[ctx.dataIndex].pct + '%' : ''
          }
        },
        scales: {
          y: {
            beginAtZero: true,
            ticks: { callback: v => v + '%', font:{size:11} },
            title: { display:true, text:'% Conversión', font:{size:11,weight:'600'} }
          },
          x: { ticks:{font:{size:11}}, grid:{display:false} }
        },
        layout: { padding: { top: 24 } }
      }
    });
  }

  // =========================================================
  //              PESTAÑA COMPETENCIA (importaciones ORGU vs QM)
  // =========================================================
  function compImpShowGate(){
    document.getElementById('comp-imp-gate').style.display='block';
    document.getElementById('comp-imp-content').style.display='none';
  }
  function compImpShowContent(){
    document.getElementById('comp-imp-gate').style.display='none';
    document.getElementById('comp-imp-content').style.display='block';
    renderCompImp();
  }
  async function compImpTryUnlock(){
    const pw = document.getElementById('comp-imp-pw').value;
    const err = document.getElementById('comp-imp-pw-err');
    err.textContent = '';
    const h = await sha256Hex(pw);
    if(h === OTROS_HASH){
      localStorage.setItem('otros_unlocked','1');
      compImpShowContent();
    } else { err.textContent = 'Contraseña incorrecta'; }
  }
  document.getElementById('comp-imp-pw-btn').addEventListener('click', compImpTryUnlock);
  document.getElementById('comp-imp-pw').addEventListener('keydown', e=>{ if(e.key==='Enter') compImpTryUnlock(); });
  document.getElementById('comp-imp-logout').addEventListener('click', ()=>{
    localStorage.removeItem('otros_unlocked'); compImpShowGate();
  });
  document.querySelector('.tab-btn[data-tab="comp-imp"]').addEventListener('click', ()=>{
    if(otrosUnlocked()) compImpShowContent(); else compImpShowGate();
  });

  // ─────────── TAB EMBUDO ───────────
  let _embudoInit = false;
  const EMBUDO_COLORS = ['#003478','#1565c0','#0f766e','#f57f17','#e65100','#2e7d32'];
  const embudoState = { meses: [] };  // meses seleccionados (multi)

  function embudoAgencia(){
    const E = DATA.embudo_data; if(!E) return null;
    return document.getElementById('embudo-agencia').value || E.default_agencia;
  }
  // Agrega (suma) los meses seleccionados en un solo embudo
  function embudoAggregate(){
    const E = DATA.embudo_data; if(!E) return null;
    const ag = embudoAgencia();
    const agData = E.agencias[ag] || {};
    const meses = embudoState.meses.filter(m=> agData[m]);
    if(meses.length===0) return null;
    // etapas: de cualquier mes
    const etapas = agData[meses[0]].etapas;
    const totales = {}; const por_modelo = {}; const por_asesor = {};
    etapas.forEach(e=> totales[e]=0);
    meses.forEach(mes=>{
      const c = agData[mes];
      etapas.forEach(e=> totales[e]+=(c.totales[e]||0));
      Object.entries(c.por_modelo).forEach(([mod,fila])=>{
        por_modelo[mod] = por_modelo[mod] || {};
        etapas.forEach(e=> por_modelo[mod][e]=(por_modelo[mod][e]||0)+(fila[e]||0));
      });
      Object.entries(c.por_asesor||{}).forEach(([ase,fila])=>{
        por_asesor[ase] = por_asesor[ase] || {};
        etapas.forEach(e=> por_asesor[ase][e]=(por_asesor[ase][e]||0)+(fila[e]||0));
      });
    });
    return { etapas, totales, por_modelo, por_asesor, meses };
  }
  function embudoInitFilters(){
    const E = DATA.embudo_data; if(!E) return;
    const selA = document.getElementById('embudo-agencia');
    const selMod = document.getElementById('embudo-modelo');
    if(selA.options.length===0){
      Object.keys(E.agencias).forEach(a=>{ const o=document.createElement('option'); o.value=a;o.textContent=a;selA.appendChild(o);});
      selA.value = E.default_agencia;
      selA.addEventListener('change', ()=>{ embudoResetMeses(); embudoRenderChips(); embudoFillModelos(); renderEmbudo(); });
    }
    embudoResetMeses();
    embudoRenderChips();
    embudoFillModelos();
    selMod.addEventListener('change', renderEmbudo);
  }
  function embudoMesesDisponibles(){
    const E = DATA.embudo_data; const ag = embudoAgencia();
    return (E.meses[ag]||[]).filter(m=> E.agencias[ag] && E.agencias[ag][m]);
  }
  function embudoResetMeses(){
    // por defecto: todos los meses seleccionados
    embudoState.meses = embudoMesesDisponibles().slice();
  }
  function embudoRenderChips(){
    const wrap = document.getElementById('embudo-meses-chips');
    const meses = embudoMesesDisponibles();
    wrap.innerHTML = meses.map(m=>{
      const on = embudoState.meses.includes(m);
      return `<button type="button" class="embudo-mes-chip" data-mes="${m}"
        style="padding:5px 12px;border-radius:16px;border:1.5px solid #0f766e;cursor:pointer;font-size:12px;font-weight:600;
        background:${on?'#0f766e':'#fff'};color:${on?'#fff':'#0f766e'}">${m}</button>`;
    }).join('') + `<button type="button" id="embudo-mes-todos" style="padding:5px 10px;border-radius:16px;border:1px dashed #94a3b8;background:#fff;color:#64748b;cursor:pointer;font-size:11px">Todos</button>`;
    wrap.querySelectorAll('.embudo-mes-chip').forEach(b=> b.addEventListener('click',()=>{
      const m=b.dataset.mes;
      if(embudoState.meses.includes(m)) embudoState.meses = embudoState.meses.filter(x=>x!==m);
      else embudoState.meses.push(m);
      if(embudoState.meses.length===0) embudoState.meses=[m]; // no dejar vacío
      embudoRenderChips(); embudoFillModelos(); renderEmbudo();
    }));
    const todos = document.getElementById('embudo-mes-todos');
    if(todos) todos.addEventListener('click',()=>{ embudoResetMeses(); embudoRenderChips(); embudoFillModelos(); renderEmbudo(); });
  }
  function embudoFillModelos(){
    const agg = embudoAggregate();
    const selMod = document.getElementById('embudo-modelo');
    const cur = selMod.value;
    const mods = agg ? Object.keys(agg.por_modelo) : [];
    selMod.innerHTML = '<option value="">Todos los modelos</option>' + mods.map(m=>`<option value="${m}">${m}</option>`).join('');
    if(mods.includes(cur)) selMod.value = cur;
  }
  function renderEmbudo(){
    const E = DATA.embudo_data;
    if(!E){ document.getElementById('embudo-source').textContent='Datos de embudo no disponibles'; return; }
    const c = embudoAggregate();
    if(!c) return;
    const ag = embudoAgencia();
    const modelo = document.getElementById('embudo-modelo').value;
    const mesesLbl = c.meses.length === embudoMesesDisponibles().length ? 'todos los meses' : c.meses.join(' + ');
    document.getElementById('embudo-source').textContent =
      `${ag} · ${mesesLbl} · ${modelo||'todos los modelos'}`;

    // Datos según filtro de modelo
    const etapas = c.etapas;
    let vals;
    if(modelo && c.por_modelo[modelo]) vals = etapas.map(e=> c.por_modelo[modelo][e]||0);
    else vals = etapas.map(e=> c.totales[e]||0);
    const top = vals[0] || 1;

    // Embudo visual (barras decrecientes con ancho proporcional)
    const funnelEl = document.getElementById('embudo-funnel');
    document.getElementById('embudo-sub-general').textContent =
      `${modelo||'Todos'} · conversión Cotización→Cierre ${vals[0]? (100*vals[vals.length-1]/vals[0]).toFixed(1):0}%`;
    funnelEl.innerHTML = etapas.map((e,i)=>{
      const v = vals[i];
      const w = Math.max(8, 100*v/top);
      const convTraf = vals[0] ? (100*v/vals[0]).toFixed(0) : null;  // % vs Tráfico
      return `<div style="margin:6px 0;display:flex;align-items:center;gap:10px">
        <div style="width:96px;text-align:right;font-size:12px;font-weight:600;color:#374151">${e}</div>
        <div style="flex:1;background:#f1f5f9;border-radius:6px;overflow:hidden">
          <div style="width:${w}%;background:${EMBUDO_COLORS[i]};color:#fff;padding:8px 12px;border-radius:6px;font-weight:700;font-size:13px;white-space:nowrap">${v}</div>
        </div>
        <div style="width:80px;font-size:11px;color:var(--muted)" title="% vs Cotización">${convTraf!=null?convTraf+'% cotiz.':''}</div>
      </div>`;
    }).join('');

    // Tabla por modelo × etapa (respeta filtros: meses agregados + modelo)
    const head = document.getElementById('embudo-tbl-head');
    head.innerHTML = '<th>Modelo</th>' + etapas.map(e=>`<th class="num">${e}</th>`).join('') + '<th class="num">% cierre</th>';
    const tbody = document.querySelector('#embudo-tbl tbody');
    let mods = Object.entries(c.por_modelo).sort((a,b)=> (b[1][etapas[0]]||0)-(a[1][etapas[0]]||0));
    // Filtro de modelo: si hay uno seleccionado, mostrar solo ese
    if(modelo) mods = mods.filter(([mod])=> mod===modelo);
    tbody.innerHTML = mods.map(([mod,fila])=>{
      const t = fila[etapas[0]]||0, ci = fila[etapas[etapas.length-1]]||0;
      const cierrePct = t? (100*ci/t).toFixed(0):0;
      return `<tr><td class="left"><strong>${mod}</strong></td>`+
        etapas.map(e=>`<td class="num">${fila[e]||''}</td>`).join('')+
        `<td class="num" style="font-weight:600">${cierrePct}%</td></tr>`;
    }).join('') || `<tr><td colspan="${etapas.length+2}" style="text-align:center;color:var(--muted);padding:14px">Sin datos para esta selección</td></tr>`;
    // TOTAL: si hay modelo filtrado, el total es ese modelo; si no, suma de todos
    const tf = document.querySelector('#embudo-tbl tfoot');
    let totRow = {};
    if(modelo && c.por_modelo[modelo]){
      etapas.forEach(e=> totRow[e]=c.por_modelo[modelo][e]||0);
    } else {
      etapas.forEach(e=> totRow[e]=c.totales[e]||0);
    }
    const tCierre = totRow[etapas[0]]? (100*totRow[etapas[etapas.length-1]]/totRow[etapas[0]]).toFixed(0):0;
    tf.innerHTML = `<tr class="total"><td><strong>TOTAL${modelo?' ('+modelo+')':''}</strong></td>`+
      etapas.map(e=>`<td class="num" style="font-weight:700">${totRow[e]||0}</td>`).join('')+
      `<td class="num" style="font-weight:700">${tCierre}%</td></tr>`;

    // Tabla por ASESOR × etapa (suma meses seleccionados)
    const aHead = document.getElementById('embudo-asesor-head');
    aHead.innerHTML = '<th>Asesor</th>' + etapas.map(e=>`<th class="num">${e}</th>`).join('') + '<th class="num">% cierre</th>';
    const aBody = document.querySelector('#embudo-asesor-tbl tbody');
    const ases = Object.entries(c.por_asesor||{}).sort((a,b)=> (b[1][etapas[etapas.length-1]]||0)-(a[1][etapas[etapas.length-1]]||0));
    aBody.innerHTML = ases.length ? ases.map(([ase,fila])=>{
      const t = fila[etapas[0]]||0, ci = fila[etapas[etapas.length-1]]||0;
      const cierrePct = t? (100*ci/t).toFixed(0):0;
      return `<tr><td class="left"><strong>${ase}</strong></td>`+
        etapas.map(e=>`<td class="num">${fila[e]||''}</td>`).join('')+
        `<td class="num" style="font-weight:600">${cierrePct}%</td></tr>`;
    }).join('') : `<tr><td colspan="${etapas.length+2}" style="text-align:center;color:var(--muted);padding:14px">Sin datos</td></tr>`;
    const aTot = {}; etapas.forEach(e=> aTot[e]=0);
    ases.forEach(([_,fila])=> etapas.forEach(e=> aTot[e]+=(fila[e]||0)));
    const aCierre = aTot[etapas[0]]? (100*aTot[etapas[etapas.length-1]]/aTot[etapas[0]]).toFixed(0):0;
    document.querySelector('#embudo-asesor-tbl tfoot').innerHTML =
      `<tr class="total"><td><strong>TOTAL</strong></td>`+
      etapas.map(e=>`<td class="num" style="font-weight:700">${aTot[e]||0}</td>`).join('')+
      `<td class="num" style="font-weight:700">${aCierre}%</td></tr>`;

    // ─── INSIGHTS AUTOMÁTICOS ───
    renderEmbudoInsights(c, modelo);
  }

  function renderEmbudoInsights(c, modeloFiltro){
    const el = document.getElementById('embudo-insights'); if(!el) return;
    const insights = [];
    const etapas = c.etapas;
    const E0 = etapas[0], EC = etapas[etapas.length-1], EP = etapas[1]; // Cotiz, Cierre, Presentación
    const fPct = v => (v||0).toFixed(0)+'%';

    // ── 1. Mejor asesor (eficiencia: cotiz→presentación + cierre) ──
    const ases = Object.entries(c.por_asesor||{}).filter(([_,f])=> f[E0]>=10);
    if(ases.length>=2){
      const conPres = ases.map(([n,f])=>({n, cotiz:f[E0], pres:f[EP], cierre:f[EC],
        presPct: f[E0]? 100*f[EP]/f[E0]:0, ciePct: f[E0]? 100*f[EC]/f[E0]:0}));
      const topPres = [...conPres].sort((a,b)=> b.presPct - a.presPct)[0];
      const topCie  = [...conPres].sort((a,b)=> b.ciePct - a.ciePct)[0];
      const avgPres = conPres.reduce((s,x)=>s+x.presPct,0)/conPres.length;
      if(topPres.presPct - avgPres > 10){
        insights.push({tipo:'good', titulo:'🏆 Asesor estrella: ' + topPres.n,
          html:`<strong>${topPres.n}</strong> lleva <strong>${fPct(topPres.presPct)}</strong> de sus cotizaciones a presentación (promedio del equipo: ${fPct(avgPres)}). Cierra <strong>${fPct(topPres.ciePct)}</strong> (${topPres.cierre} de ${topPres.cotiz}). <em>Candidato natural para entrenar al resto del equipo en el paso cotización→presentación.</em>`});
      }
      // Asesor con mucho volumen y poca conversión
      const peor = [...conPres].sort((a,b)=> a.ciePct - b.ciePct)[0];
      const mejor = [...conPres].sort((a,b)=> b.ciePct - a.ciePct)[0];
      if(peor.cotiz >= mejor.cotiz*0.8 && (mejor.ciePct - peor.ciePct) > 5){
        const gap = Math.round(peor.cotiz * (mejor.ciePct - peor.ciePct) / 100);
        insights.push({tipo:'warn', titulo:'⚠️ Volumen alto, conversión baja: ' + peor.n,
          html:`<strong>${peor.n}</strong> recibe ${peor.cotiz} cotizaciones (similar a ${mejor.n} con ${mejor.cotiz}) pero cierra solo <strong>${fPct(peor.ciePct)}</strong> vs <strong>${fPct(mejor.ciePct)}</strong> del top. Si igualara al promedio del equipo cerraría ~<strong>${gap} ventas más</strong>. Auditar calidad de seguimiento.`});
      }
    }

    // ── 2. Modelo con mejor / peor conversión ──
    const mods = Object.entries(c.por_modelo||{}).filter(([_,f])=> f[E0]>=10);
    if(mods.length>=2 && !modeloFiltro){
      const mejor = mods.map(([n,f])=>({n,cotiz:f[E0],cierre:f[EC],pct:f[E0]?100*f[EC]/f[E0]:0}))
                       .sort((a,b)=>b.pct-a.pct);
      const top = mejor[0], peor = mejor[mejor.length-1];
      if(top.pct - peor.pct > 8){
        insights.push({tipo:'good', titulo:'💎 Modelo más rentable de convertir: ' + top.n,
          html:`<strong>${top.n}</strong> tiene la mejor tasa de cierre: <strong>${fPct(top.pct)}</strong> (${top.cierre} de ${top.cotiz}). Si pudieras inyectar más prospectos a este modelo, cada uno tiene la mayor probabilidad de cerrar venta.`});
        const lost = Math.round(peor.cotiz * (top.pct - peor.pct) / 100);
        insights.push({tipo:'warn', titulo:'🚨 Modelo que sangra prospectos: ' + peor.n,
          html:`<strong>${peor.n}</strong> tiene la peor conversión: <strong>${fPct(peor.pct)}</strong> (${peor.cierre} de ${peor.cotiz}). Hay <strong>${peor.cotiz} cotizaciones que solo produjeron ${peor.cierre} ventas</strong>. Revisar: ¿calidad de prospecto, precio, inventario o mensaje?`});
      }
    }

    // ── 3. Cuello de botella global ──
    const caidas = [];
    for(let i=1;i<etapas.length;i++){
      const a = c.totales[etapas[i-1]]||0, b = c.totales[etapas[i]]||0;
      if(a>0) caidas.push({de:etapas[i-1], a:etapas[i], perdidas: a-b, pctPerdido: 100*(a-b)/a});
    }
    caidas.sort((x,y)=> y.perdidas - x.perdidas);
    if(caidas[0] && caidas[0].pctPerdido > 30){
      const cb = caidas[0];
      insights.push({tipo:'warn', titulo:`🔻 Cuello de botella: ${cb.de} → ${cb.a}`,
        html:`En esa transición se pierde el <strong>${fPct(cb.pctPerdido)}</strong> de los prospectos (${cb.perdidas} negocios desaparecen). Es la etapa con mayor fuga del embudo y donde una mejora pequeña en %, daría el mayor impacto en ventas.`});
    }

    // ── 4. Evolución mensual (solo si hay varios meses seleccionados) ──
    if(c.meses && c.meses.length>=2){
      const ag = embudoAgencia(); const E = DATA.embudo_data;
      const mesData = c.meses.map(m=>{
        const cm = E.agencias[ag][m]; const t = cm.totales[E0]||0;
        return {mes:m, cotiz:t, cierre:cm.totales[EC]||0, sol:cm.totales[etapas[2]||EC]||0,
                pct: t? 100*(cm.totales[EC]||0)/t : 0};
      });
      const first = mesData[0], last = mesData[mesData.length-1];
      const deltaConv = last.pct - first.pct;
      if(Math.abs(deltaConv) > 5){
        const tipo = deltaConv<0 ? 'warn' : 'good';
        const arrow = deltaConv<0 ? '⬇️ cae' : '⬆️ sube';
        insights.push({tipo, titulo:`📊 Tendencia: la conversión ${arrow} mes a mes`,
          html:`De <strong>${first.mes}</strong> a <strong>${last.mes}</strong> la conversión Cotización→Cierre pasó de <strong>${fPct(first.pct)}</strong> a <strong>${fPct(last.pct)}</strong> (${deltaConv>=0?'+':''}${deltaConv.toFixed(0)} pts). ` +
            mesData.map(m=>`${m.mes} ${fPct(m.pct)}`).join(' · ')});
      }
      // Si solicitudes de crédito caen fuerte
      const solFirst = mesData[0].sol, solLast = mesData[mesData.length-1].sol;
      if(solFirst >= 10 && solLast <= solFirst*0.4){
        insights.push({tipo:'warn', titulo:'💳 Las solicitudes de crédito se desplomaron',
          html:`Pasaron de <strong>${solFirst}</strong> (${mesData[0].mes}) a <strong>${solLast}</strong> (${mesData[mesData.length-1].mes}). El canal de financiamiento se está rompiendo y eso arrastra al cierre. Investigar: política bancaria, tasas, equipo de F&I.`});
      }
    }

    // ── 5. Oportunidad de margen (modelo top conversion + bajo volumen) ──
    if(!modeloFiltro){
      const mods2 = Object.entries(c.por_modelo||{}).map(([n,f])=>({n,cotiz:f[E0],cierre:f[EC],pct:f[E0]?100*f[EC]/f[E0]:0}));
      const subdesarrollados = mods2.filter(m=> m.pct >= 30 && m.cotiz < 40);
      subdesarrollados.forEach(m=>{
        insights.push({tipo:'info', titulo:`✨ Oportunidad: inyectar tráfico a ${m.n}`,
          html:`<strong>${m.n}</strong> cierra <strong>${fPct(m.pct)}</strong> (${m.cierre} de ${m.cotiz}) — alta conversión pero solo ${m.cotiz} prospectos. Si triplicas el flujo (vía pauta digital o seguimiento), podrías cerrar <strong>~${Math.round(m.cotiz*2*m.pct/100)} ventas adicionales</strong> en este periodo manteniendo la efectividad.`});
      });
    }

    el.innerHTML = insights.length===0 ?
      '<p style="color:var(--muted);text-align:center;padding:14px">Sin hallazgos relevantes para esta selección de filtros.</p>' :
      insights.map(ins => `<div class="insight-card ${ins.tipo}"><h4>${ins.titulo}</h4><p>${ins.html}</p></div>`).join('');
  }
  document.querySelector('.tab-btn[data-tab="embudo"]').addEventListener('click', ()=>{
    if(!_embudoInit){ embudoInitFilters(); _embudoInit=true; }
    renderEmbudo();
  });

  let compImpChart = null;
  function renderCompImp(){
    const C = DATA.competencia_data;
    if(!C){
      document.getElementById('comp-imp-source').textContent = 'Archivo no disponible';
      return;
    }
    document.getElementById('comp-imp-source').textContent = 'ORGU (AUTOSHARECORP) vs QM (Quito Motors) · fuente: ' + C.source_file;
    const t = C.totales;
    document.getElementById('comp-k-2025').textContent = fmt(t.tot_2025);
    document.getElementById('comp-k-2025-hint').textContent = `ORGU ${fmt(t.orgu_2025)} · QM ${fmt(t.qm_2025)}`;
    document.getElementById('comp-k-2026').textContent = fmt(t.tot_2026);
    document.getElementById('comp-k-2026-hint').textContent = `ORGU ${fmt(t.orgu_2026)} · QM ${fmt(t.qm_2026)}`;
    document.getElementById('comp-k-share25').textContent = t.orgu_share_2025 + '%';
    document.getElementById('comp-k-share26').textContent = t.orgu_share_2026 + '%';
    const delta = t.delta_share_total;
    const deltaStr = (delta>=0?'+':'') + delta + ' pts vs 2025';
    const deltaEl = document.getElementById('comp-k-delta');
    deltaEl.textContent = deltaStr;
    deltaEl.style.color = delta>=0 ? 'var(--pos)' : 'var(--neg)';
    const shareEl = document.getElementById('comp-k-share26');
    shareEl.className = 'val ' + (delta>=0?'pos':'neg');

    // TENDENCIA 3 AÑOS
    const yr3 = document.getElementById('comp-3yr');
    if(yr3){
      const years = [
        {y:'2024', o:t.orgu_2024, q:t.qm_2024, tot:t.tot_2024, sh:t.orgu_share_2024, note:'12 meses'},
        {y:'2025', o:t.orgu_2025, q:t.qm_2025, tot:t.tot_2025, sh:t.orgu_share_2025, note:'12 meses'},
        {y:'2026', o:t.orgu_2026, q:t.qm_2026, tot:t.tot_2026, sh:t.orgu_share_2026, note:'ene–may (parcial)'},
      ];
      yr3.innerHTML = years.map(yr=>{
        const lead = yr.sh>=50;
        const col = lead ? '#16a34a' : '#dc2626';
        return `<div class="card-big" style="border:1px solid ${lead?'#bbf7d0':'#fecaca'}">
          <div class="lbl">${yr.y} · ${yr.note}</div>
          <div class="val" style="color:${col}">${yr.sh}% <span style="font-size:13px;font-weight:600;color:var(--muted)">ORGU</span></div>
          <div class="hint">ORGU ${fmt(yr.o)} · QM ${fmt(yr.q)} · total ${fmt(yr.tot)} ${lead?'· ORGU lidera':'· QM lidera'}</div>
        </div>`;
      }).join('');
    }
    // CIF 2026
    const cifEl = document.getElementById('comp-cif');
    if(cifEl && (t.cif_orgu_2026 || t.cif_qm_2026)){
      const fUSD = n => 'USD ' + (n||0).toLocaleString('es-EC',{maximumFractionDigits:0});
      const totCif = (t.cif_orgu_2026||0)+(t.cif_qm_2026||0);
      const pctO = totCif? Math.round(100*t.cif_orgu_2026/totCif):0;
      cifEl.innerHTML = `<strong>💵 Inversión CIF en importación 2026:</strong> ORGU ${fUSD(t.cif_orgu_2026)} (${pctO}%) · QM ${fUSD(t.cif_qm_2026)} (${100-pctO}%). `+
        `<span style="color:#9333ea">El CIF es el valor aduanero (costo+seguro+flete) de los vehículos importados. Nota: se excluyeron 32 registros de mayo con cantidad/CIF mal capturados (=100.000).</span>`;
    }

    // VENTAS Y MARGEN ESTIMADO (con selector de año)
    const fUSD0 = n => 'USD ' + Math.round(n||0).toLocaleString('es-EC');
    function renderCompMargen(){
      const anios = C.margen_anios || {'2026': C.margen};
      const pmAnios = C.margen_modelo_anios || {'2026': C.margen_por_modelo};
      const selA = document.getElementById('comp-margen-anio');
      const yr = (selA && selA.value) || '2026';
      const mg = anios[yr]; const pm = pmAnios[yr] || [];
      if(!mg) return;
      const yrLabel = yr==='2026' ? '2026 (ene–may)' : yr;
      const cardsEl = document.getElementById('comp-margen-cards');
      if(cardsEl){
        const mk = (dist, color, bg, border) => {
          const d = mg[dist]; if(!d) return '';
          return `<div class="card-big" style="background:${bg};border:1px solid ${border}">
            <div class="lbl">${dist==='ORGU'?'🔵 ORGU (AUTOSHARECORP)':'🔴 QM (Quito Motors)'} · ${yrLabel}</div>
            <div class="val" style="color:${color}">${fUSD0(d.mg)}</div>
            <div class="hint">margen · ventas ${fUSD0(d.rev)} (${d.margen_pct}%) · ${d.u} u · ticket prom ${fUSD0(d.ticket_prom)}</div>
          </div>`;
        };
        cardsEl.innerHTML = mk('ORGU','#0369a1','linear-gradient(135deg,#e0f2fe,#f0f9ff)','#bae6fd')
                          + mk('QM','#be185d','linear-gradient(135deg,#fce7f3,#fdf2f8)','#fbcfe8');
      }
      const mTb = document.querySelector('#comp-margen-tbl tbody');
      const mFt = document.querySelector('#comp-margen-tbl tfoot');
      if(mTb){
        mTb.innerHTML = pm.map(x=>{
          return `<tr>
            <td class="left"><strong>${x.modelo}</strong></td>
            <td class="num">${x.margen_unit!=null?fUSD0(x.margen_unit):'<span style="color:#bbb">s/PBD</span>'}</td>
            <td class="num">${x.orgu_u||''}</td>
            <td class="num">${x.ventas_orgu?fUSD0(x.ventas_orgu):''}</td>
            <td class="num" style="color:var(--pos)">${x.margen_orgu?fUSD0(x.margen_orgu):''}</td>
            <td class="num">${x.qm_u||''}</td>
            <td class="num">${x.ventas_qm?fUSD0(x.ventas_qm):''}</td>
            <td class="num" style="color:var(--neg)">${x.margen_qm?fUSD0(x.margen_qm):''}</td>
            <td class="num" style="font-weight:700">${x.ventas_total?fUSD0(x.ventas_total):''}</td>
          </tr>`;
        }).join('');
        mFt.innerHTML = `<tr class="total">
          <td><strong>TOTAL ${yrLabel}</strong></td><td class="num">—</td>
          <td class="num">${mg.ORGU.u}</td><td class="num" style="font-weight:700">${fUSD0(mg.ORGU.rev)}</td><td class="num" style="font-weight:700">${fUSD0(mg.ORGU.mg)}</td>
          <td class="num">${mg.QM.u}</td><td class="num" style="font-weight:700">${fUSD0(mg.QM.rev)}</td><td class="num" style="font-weight:700">${fUSD0(mg.QM.mg)}</td>
          <td class="num" style="font-weight:700">${fUSD0(mg.ORGU.rev + mg.QM.rev)}</td>
        </tr>`;
      }
    }
    const selMA = document.getElementById('comp-margen-anio');
    if(selMA && !selMA.dataset.bound){ selMA.addEventListener('change', renderCompMargen); selMA.dataset.bound='1'; }
    renderCompMargen();

    // ORIGEN USA
    const usaTb = document.querySelector('#comp-usa-tbl tbody');
    if(usaTb && C.usa_share){
      usaTb.innerHTML = [2024,2025,2026].map(yr=>{
        const u = C.usa_share[yr]; if(!u) return '';
        const o = u.ORGU || {pct:0,usa:0}, q = u.QM || {pct:0,usa:0};
        const vent = (o.pct - q.pct).toFixed(0);
        return `<tr>
          <td><strong>${yr}${yr===2026?' (parcial)':''}</strong></td>
          <td class="num"><span class="status-pill ${o.pct>=30?'green':o.pct>=15?'yellow':'red'}">${o.pct}%</span></td>
          <td class="num">${o.usa}</td>
          <td class="num"><span class="status-pill ${q.pct>=30?'green':q.pct>=15?'yellow':'red'}">${q.pct}%</span></td>
          <td class="num">${q.usa}</td>
          <td class="num" style="font-weight:700;color:${(o.pct-q.pct)>=0?'var(--pos)':'var(--neg)'}">${(o.pct-q.pct)>=0?'+':''}${vent} pts</td>
        </tr>`;
      }).join('');
    }

    // SWING DE SHARE
    const swTb = document.querySelector('#comp-swing-tbl tbody');
    if(swTb && C.swing){
      swTb.innerHTML = C.swing.map(s=>{
        const dCol = s.delta>=0 ? 'var(--pos)' : 'var(--neg)';
        const arrow = s.delta>=15?'⬆️':s.delta<=-15?'⬇️':'→';
        return `<tr>
          <td class="left"><strong>${s.modelo}</strong></td>
          <td class="num">${s.share_2025}%</td>
          <td class="num">${s.share_2026}%</td>
          <td class="num" style="font-weight:700;color:${dCol}">${arrow} ${s.delta>=0?'+':''}${s.delta.toFixed(1)} pts</td>
          <td class="num" style="color:var(--muted)">${s.orgu_2025}/${s.qm_2025}</td>
          <td class="num" style="color:var(--muted)">${s.orgu_2026}/${s.qm_2026}</td>
        </tr>`;
      }).join('');
    }

    // TABLA
    const tbody = document.querySelector('#comp-tbl tbody');
    tbody.innerHTML = C.modelos.map(m=>{
      const share26 = m.orgu_share_2026;
      const shareCls = share26 == null ? 'gray'
                     : share26 >= 60 ? 'green'
                     : share26 >= 45 ? 'yellow'
                     : 'red';
      const deltaShare = m.delta_share;
      const deltaCell = deltaShare == null ? '<td class="num" style="color:var(--muted)">—</td>'
                      : `<td class="num" style="color:${deltaShare>=0?'var(--pos)':'var(--neg)'};font-weight:600">${deltaShare>=0?'+':''}${deltaShare.toFixed(1)} pts</td>`;
      return `<tr>
        <td class="left"><strong>${m.modelo}</strong></td>
        <td class="num">${m.orgu_2025||''}</td>
        <td class="num">${m.qm_2025||''}</td>
        <td class="num" style="font-weight:600">${m.tot_2025||''}</td>
        <td class="num">${m.orgu_2026||''}</td>
        <td class="num">${m.qm_2026||''}</td>
        <td class="num" style="font-weight:600">${m.tot_2026||''}</td>
        <td class="num" style="font-weight:700">${m.total}</td>
        <td class="num"><span class="status-pill ${shareCls}">${share26 != null ? share26+'%' : '—'}</span></td>
        ${deltaCell}
      </tr>`;
    }).join('') + `<tr class="total">
      <td><strong>TOTAL</strong></td>
      <td class="num">${fmt(t.orgu_2025)}</td><td class="num">${fmt(t.qm_2025)}</td><td class="num">${fmt(t.tot_2025)}</td>
      <td class="num">${fmt(t.orgu_2026)}</td><td class="num">${fmt(t.qm_2026)}</td><td class="num">${fmt(t.tot_2026)}</td>
      <td class="num">${fmt(t.total)}</td>
      <td class="num">${t.orgu_share_2026}%</td>
      <td class="num" style="color:${t.delta_share_total>=0?'var(--pos)':'var(--neg)'}">${t.delta_share_total>=0?'+':''}${t.delta_share_total} pts</td>
    </tr>`;

    // Selector de modelo y gráfica
    const sel = document.getElementById('comp-imp-modelo');
    if(sel.options.length === 0){
      C.modelos.forEach(m=>{
        const o = document.createElement('option');
        o.value = m.modelo; o.textContent = m.modelo;
        sel.appendChild(o);
      });
      sel.addEventListener('change', renderCompImpChart);
    }
    if(!sel.value) sel.value = C.modelos[0].modelo;
    const selAnio = document.getElementById('comp-imp-anio');
    if(selAnio && !selAnio.dataset.bound){
      selAnio.addEventListener('change', renderCompImpChart);
      selAnio.dataset.bound = '1';
    }
    renderCompImpChart();
  }

  function renderCompImpChart(){
    const C = DATA.competencia_data; if(!C) return;
    const modelo = document.getElementById('comp-imp-modelo').value;
    const m = C.modelos.find(x=>x.modelo===modelo);
    if(!m) return;
    const anioF = (document.getElementById('comp-imp-anio')||{}).value || '';
    const meses = anioF ? C.meses.filter(ym=>ym.startsWith(anioF)) : C.meses;
    const orgu = meses.map(ym=>m.mensual[ym]?.orgu || 0);
    const qm   = meses.map(ym=>m.mensual[ym]?.qm || 0);
    const labels = meses.map(ym=>{
      const [y,mo] = ym.split('-');
      const names = ['Ene','Feb','Mar','Abr','May','Jun','Jul','Ago','Sep','Oct','Nov','Dic'];
      return names[parseInt(mo)-1] + ' ' + y.slice(2);
    });
    const ctx = document.getElementById('comp-imp-chart');
    if(compImpChart){ compImpChart.destroy(); }
    compImpChart = new Chart(ctx, {
      type:'bar',
      data:{labels, datasets:[
        {label:'ORGU', data:orgu, backgroundColor:'rgba(0,52,120,0.85)', stack:'a'},
        {label:'QM',   data:qm,   backgroundColor:'rgba(198,40,40,0.75)', stack:'a'},
      ]},
      options:{
        responsive:true, maintainAspectRatio:false,
        interaction:{mode:'index', intersect:false},
        plugins:{
          legend:{position:'bottom', labels:{font:{size:11}}},
          tooltip:{callbacks:{
            footer:(items)=>{
              const total = items.reduce((s,i)=>s+i.parsed.y, 0);
              return total ? 'Total: '+total : '';
            }
          }},
          datalabels:{display:false}
        },
        scales:{
          x:{stacked:true, ticks:{font:{size:10}}},
          y:{stacked:true, beginAtZero:true, ticks:{font:{size:11}}}
        }
      }
    });
  }

  // =========================================================
  //              ANÁLISIS COMPLETO (Otros tab)
  // =========================================================
  const AN_MONTHS_2026 = ['enero_2026','febrero_2026','marzo_2026','abril_2026','mayo_2026'];
  const AN_MONTH_LBL = {'enero_2026':'Enero','febrero_2026':'Febrero','marzo_2026':'Marzo','abril_2026':'Abril','mayo_2026':'Mayo'};
  const anstate = { view:'ytd', modelo:'', agencia:'', canal:'marketing' };
  // Categorías de canal (Marketing ~80% vs Asesor Comercial ~20%)
  const AN_CH_CATS = (DATA.channel_categories) || {
    marketing: ['Showroom','Hubspot','Ferias y Eventos','Feria/Eventos','Ferias','Llamada In'],
    asesor:    ['Recompra','Referido por Cliente','Referidos por empleado','Gestión Externa','Prospección','Empleado','Talleres','Redes Sociales Propias','Catálogo público'],
    all:       []
  };
  function anCanalSet(){
    if(anstate.canal === 'marketing') return new Set(AN_CH_CATS.marketing);
    if(anstate.canal === 'asesor')    return new Set(AN_CH_CATS.asesor);
    return new Set([...AN_CH_CATS.marketing, ...AN_CH_CATS.asesor]);
  }
  function anCanalLabel(){
    return anstate.canal === 'marketing' ? 'Sólo marketing' :
           anstate.canal === 'asesor'    ? 'Sólo asesor' :
                                           'Todos los canales';
  }
  // Escala de meta según filtro de canal. matrix_meta guarda la meta marketing (80%).
  //   marketing → ×1.0     (meta marketing como está en el Excel = 80% del total)
  //   asesor    → ×0.25    (= 20% / 80% = el cuadro de arriba menos el de marketing)
  //   all       → ×1.25    (= meta total 100%: suma de marketing + asesor)
  const AN_META_SPLIT = (DATA.meta_split) || {marketing_pct:0.80, asesor_pct:0.20};
  const AN_CANAL_META_RATIO = {
    marketing: 1.0,
    asesor:    AN_META_SPLIT.asesor_pct / AN_META_SPLIT.marketing_pct,
    all:       1.0 / AN_META_SPLIT.marketing_pct,
  };
  function anScaleMeta(metaMkt){
    return metaMkt * (AN_CANAL_META_RATIO[anstate.canal] || 1.0);
  }
  // Para meses en curso, escala la meta proporcionalmente a los días transcurridos
  // (meta al día), para que el cumplimiento no se vea artificialmente bajo cuando
  // el mes aún no termina. Meses cerrados → factor 1.0.
  function anMonthDayFactor(fm){
    if(!fm || !fm.days_lab) return 1.0;
    if(fm.days_trans >= fm.days_lab) return 1.0;
    return fm.days_trans / fm.days_lab;
  }
  function anHasInProgressMonth(monthKeys){
    return monthKeys.some(mk=>{
      const fm = FORD_MONTHS[mk];
      return fm && fm.days_lab && fm.days_trans < fm.days_lab;
    });
  }
  let anInited = false;

  function initAnalysis(){
    if(anInited) return;
    anInited = true;
    // Populate model + agency selects from FORD data
    const ff = FORD_MONTHS['enero_2026'] || FORD_MONTHS[AN_MONTHS_2026[0]] || FORD;
    const modelos = ff?.model_order || [];
    const agencias = ff?.dealer_order || [];
    const elMod = document.getElementById('an-modelo');
    modelos.forEach(m=>{ const o=document.createElement('option'); o.value=m; o.textContent=m; elMod.appendChild(o); });
    const elAg = document.getElementById('an-agencia');
    agencias.forEach(d=>{ const o=document.createElement('option'); o.value=d; o.textContent=d; elAg.appendChild(o); });
    // Bind
    document.getElementById('an-view').addEventListener('change', e=>{ anstate.view = e.target.value; renderAnalysis(); });
    document.getElementById('an-modelo').addEventListener('change', e=>{ anstate.modelo = e.target.value; renderAnalysis(); });
    document.getElementById('an-agencia').addEventListener('change', e=>{ anstate.agencia = e.target.value; renderAnalysis(); });
    document.getElementById('an-canal').addEventListener('change', e=>{ anstate.canal = e.target.value; renderAnalysis(); });
    document.getElementById('an-reset').addEventListener('click', ()=>{
      anstate.view='ytd'; anstate.modelo=''; anstate.agencia=''; anstate.canal='marketing';
      document.getElementById('an-view').value='ytd';
      document.getElementById('an-modelo').value='';
      document.getElementById('an-agencia').value='';
      document.getElementById('an-canal').value='marketing';
      renderAnalysis();
    });
  }

  // helper: sumar curr, meta para un scope dado (lista de meses, modelos, agencias)
  // curr respeta el filtro de canal (marketing/asesor/todos) leyendo dealer_model_channel.
  // meta también respeta el filtro: matrix_meta guarda la meta marketing (80%);
  // la escalamos según la categoría activa (×1.0 / ×0.25 / ×1.25).
  // Para el mes en curso usamos meta-al-día (× days_trans/days_lab) para que el cumpl%
  // no se vea artificialmente bajo cuando todavía no terminan los días laborables.
  function anAgg(monthKeys, models, dealers){
    let curr=0, metaMkt=0;
    const canalSet = anCanalSet();
    monthKeys.forEach(mk=>{
      const fm = FORD_MONTHS[mk]; if(!fm) return;
      const dayFactor = anMonthDayFactor(fm);
      const mods = models && models.length ? models : (fm.model_order||[]);
      const deals = dealers && dealers.length ? dealers : (fm.dealer_order||[]);
      const dmc = fm.dealer_model_channel || {};
      mods.forEach(m=>{
        deals.forEach(d=>{
          const chMap = (dmc[d]||{})[m] || {};
          for(const k in chMap){
            if(canalSet.has(k)) curr += chMap[k] || 0;
          }
          metaMkt += ((fm.matrix_meta?.[m]?.[d]) || 0) * dayFactor;
        });
      });
    });
    const meta = Math.round(anScaleMeta(metaMkt));
    return {curr, meta};
  }

  function anScopeMonths(){
    return anstate.view === 'ytd' ? AN_MONTHS_2026 : [anstate.view];
  }
  function anScopeModels(){ return anstate.modelo ? [anstate.modelo] : null; }
  function anScopeDealers(){ return anstate.agencia ? [anstate.agencia] : null; }
  function anViewLabel(){ return anstate.view==='ytd' ? 'YTD 2026 (Ene-May)' : AN_MONTH_LBL[anstate.view]+' 2026'; }

  function metaBarHtml(real, meta, pct){
    const ratio = meta>0 ? Math.min(1.5, real/meta) : 0;
    const w = Math.max(2, Math.round(100*ratio/1.5));
    const metaPos = Math.round(100*1/1.5);
    const cls = pct==null?'red':pct>=100?'green':pct>=70?'yellow':'red';
    const pctStr = pct==null ? '—' : pct.toFixed(0)+'%';
    return `<div class="meta-bar">
      <div class="fill ${cls}" style="width:${w}%">${pct>=8?pctStr:''}</div>
      ${meta>0?`<div class="marker" style="left:${metaPos}%"></div>`:''}
    </div>`;
  }
  function pctColor(pct){ return pct>=100?'var(--pos)':pct>=70?'#f57f17':'var(--neg)'; }
  function fmtSigned(n){ return (n>=0?'+':'')+n; }

  function renderAnalysisFilterSummary(){
    const wrap = document.getElementById('an-filter-summary');
    const chips = [{k:'_', label:'Vista: '+anViewLabel(), locked:true},
                   {k:'__canal', label:'Canal: '+anCanalLabel(), locked:true}];
    if(anstate.modelo) chips.push({k:'modelo', label:'Modelo: '+anstate.modelo});
    if(anstate.agencia) chips.push({k:'agencia', label:'Agencia: '+anstate.agencia});
    wrap.innerHTML = '<span style="font-weight:600;color:var(--ink)">Filtros:</span> ' +
      chips.map(c=>`<span class="chip" ${c.locked?'style="opacity:.85"':''}>${c.label}${c.locked?'':`<button data-k="${c.k}" title="Quitar">×</button>`}</span>`).join('');
    wrap.querySelectorAll('button[data-k]').forEach(b=>b.addEventListener('click',()=>{
      anstate[b.dataset.k]='';
      document.getElementById('an-'+b.dataset.k).value='';
      renderAnalysis();
    }));
  }

  function renderAnHero(){
    const months = anScopeMonths();
    const {curr, meta} = anAgg(months, anScopeModels(), anScopeDealers());
    const pct = meta>0 ? 100*curr/meta : null;
    const gap = curr - meta;
    const k1 = document.getElementById('an-k1');
    k1.textContent = pct==null ? '—' : pct.toFixed(1)+'%';
    k1.className = 'val ' + (pct==null?'':pct>=100?'pos':pct>=70?'warn':'neg');
    document.getElementById('an-k1-lbl').textContent = 'Cumplimiento';
    const proRata = anHasInProgressMonth(months);
    document.getElementById('an-k1-hint').textContent = anViewLabel() + ' · ' + anCanalLabel() + (meta>0?` · ${curr}/${meta}`:'') + (proRata?' · meta al día':'');
    document.getElementById('an-k2').textContent = fmt(curr);
    document.getElementById('an-k2-hint').textContent = 'Tráfico Ford · ' + anCanalLabel() + (anstate.modelo?` · ${anstate.modelo}`:'') + (anstate.agencia?` · ${anstate.agencia}`:'');
    document.getElementById('an-k3').textContent = fmt(meta);
    const gapEl = document.getElementById('an-k3-hint');
    gapEl.textContent = meta>0 ? `gap ${fmtSigned(gap)}` : 'sin meta';
    gapEl.style.color = gap>=0 ? 'var(--pos)' : 'var(--neg)';
  }

  function renderAnPorModelo(){
    const months = anScopeMonths();
    const ff = FORD_MONTHS[months[months.length-1]] || FORD_MONTHS[AN_MONTHS_2026[0]];
    const modelos = ff?.model_order || [];
    // filter by anstate.modelo if set
    const inModels = anstate.modelo ? [anstate.modelo] : null;
    document.getElementById('an-mod-sub').textContent = anViewLabel() + (anstate.agencia?` · ${anstate.agencia}`:'') + (inModels?` · sólo ${anstate.modelo}`:'');
    const rows = modelos.filter(m => !inModels || m===inModels[0]).map(m=>{
      const {curr, meta} = anAgg(months, [m], anScopeDealers());
      const pct = meta>0 ? 100*curr/meta : null;
      return {m, curr, meta, pct, gap: curr-meta};
    }).filter(r => r.curr>0 || r.meta>0)
      .sort((a,b)=>{
        if(a.pct==null && b.pct==null) return b.curr-a.curr;
        if(a.pct==null) return 1;
        if(b.pct==null) return -1;
        return b.pct-a.pct;
      });
    const totReal = rows.reduce((s,r)=>s+r.curr,0);
    const totMeta = rows.reduce((s,r)=>s+r.meta,0);
    const totPct = totMeta>0 ? 100*totReal/totMeta : null;
    const tbody = document.querySelector('#an-tbl-modelo tbody');
    tbody.innerHTML = rows.map(r=>`<tr>
      <td><strong>${r.m}</strong></td>
      <td class="num">${fmt(r.curr)}</td>
      <td class="num">${fmt(r.meta)}</td>
      <td class="num" style="color:${pctColor(r.pct)};font-weight:700">${r.pct==null?'—':r.pct.toFixed(0)+'%'}</td>
      <td class="bar-cell">${metaBarHtml(r.curr, r.meta, r.pct)}</td>
      <td class="num" style="color:${r.gap>=0?'var(--pos)':'var(--neg)'};font-weight:700">${fmtSigned(r.gap)}</td>
    </tr>`).join('') + `<tr class="total">
      <td>TOTAL</td><td class="num">${fmt(totReal)}</td><td class="num">${fmt(totMeta)}</td>
      <td class="num" style="color:${pctColor(totPct)}">${totPct==null?'—':totPct.toFixed(1)+'%'}</td>
      <td></td>
      <td class="num" style="color:${totReal-totMeta>=0?'var(--pos)':'var(--neg)'}">${fmtSigned(totReal-totMeta)}</td>
    </tr>`;
  }

  function renderAnPorAgencia(){
    const months = anScopeMonths();
    const ff = FORD_MONTHS[months[months.length-1]] || FORD_MONTHS[AN_MONTHS_2026[0]];
    const dealers = ff?.dealer_order || [];
    const inDealers = anstate.agencia ? [anstate.agencia] : null;
    document.getElementById('an-ag-sub').textContent = anViewLabel() + (anstate.modelo?` · ${anstate.modelo}`:'') + (inDealers?` · sólo ${anstate.agencia}`:'');
    const rows = dealers.filter(d => !inDealers || d===inDealers[0]).map(d=>{
      const {curr, meta} = anAgg(months, anScopeModels(), [d]);
      const pct = meta>0 ? 100*curr/meta : null;
      return {d, curr, meta, pct, gap: curr-meta};
    }).filter(r => r.curr>0 || r.meta>0)
      .sort((a,b)=>{
        if(a.pct==null && b.pct==null) return b.curr-a.curr;
        if(a.pct==null) return 1;
        if(b.pct==null) return -1;
        return b.pct-a.pct;
      });
    const totReal = rows.reduce((s,r)=>s+r.curr,0);
    const totMeta = rows.reduce((s,r)=>s+r.meta,0);
    const totPct = totMeta>0 ? 100*totReal/totMeta : null;
    const tbody = document.querySelector('#an-tbl-agencia tbody');
    tbody.innerHTML = rows.map(r=>`<tr>
      <td><strong>${r.d}</strong></td>
      <td class="num">${fmt(r.curr)}</td>
      <td class="num">${fmt(r.meta)}</td>
      <td class="num" style="color:${pctColor(r.pct)};font-weight:700">${r.pct==null?'—':r.pct.toFixed(0)+'%'}</td>
      <td class="bar-cell">${metaBarHtml(r.curr, r.meta, r.pct)}</td>
      <td class="num" style="color:${r.gap>=0?'var(--pos)':'var(--neg)'};font-weight:700">${fmtSigned(r.gap)}</td>
    </tr>`).join('') + `<tr class="total">
      <td>TOTAL</td><td class="num">${fmt(totReal)}</td><td class="num">${fmt(totMeta)}</td>
      <td class="num" style="color:${pctColor(totPct)}">${totPct==null?'—':totPct.toFixed(1)+'%'}</td>
      <td></td>
      <td class="num" style="color:${totReal-totMeta>=0?'var(--pos)':'var(--neg)'}">${fmtSigned(totReal-totMeta)}</td>
    </tr>`;
  }

  function renderAnPorCanal(){
    const months = anScopeMonths();
    document.getElementById('an-ch-sub').textContent = anViewLabel() + ' · ' + anCanalLabel() + (anstate.modelo?` · ${anstate.modelo}`:'') + (anstate.agencia?` · ${anstate.agencia}`:'');
    // Sum channels across months × dealers × models in scope, restringido al set de canal activo
    const canalSet = anCanalSet();
    const ch = {};
    months.forEach(mk=>{
      const fm = FORD_MONTHS[mk]; if(!fm) return;
      const dmc = fm.dealer_model_channel || {};
      const deals = anstate.agencia ? [anstate.agencia] : (fm.dealer_order || []);
      const mods = anstate.modelo ? [anstate.modelo] : (fm.model_order || []);
      // include Otros if no agency filter
      const dealList = anstate.agencia ? deals : [...deals, 'Otros'];
      dealList.forEach(d=>{
        mods.forEach(m=>{
          const ms = (dmc[d]||{})[m] || {};
          Object.entries(ms).forEach(([c,v])=>{
            if(!canalSet.has(c)) return;
            ch[c] = (ch[c]||0) + (v||0);
          });
        });
      });
    });
    const entries = Object.entries(ch).filter(([,v])=>v>0).sort((a,b)=>b[1]-a[1]);
    const total = entries.reduce((s,[,v])=>s+v,0) || 1;
    const tbody = document.querySelector('#an-tbl-canal tbody');
    tbody.innerHTML = entries.map(([k,v])=>{
      const pct = 100*v/total;
      const w = Math.round(pct);
      return `<tr>
        <td><strong>${k}</strong></td>
        <td class="num">${fmt(v)}</td>
        <td class="num" style="font-weight:700">${pct.toFixed(1)}%</td>
        <td class="bar-cell"><div class="meta-bar"><div class="fill green" style="width:${Math.max(2,w)}%">${pct>=8?pct.toFixed(0)+'%':''}</div></div></td>
      </tr>`;
    }).join('') + `<tr class="total"><td>TOTAL</td><td class="num">${fmt(total)}</td><td class="num">100%</td><td></td></tr>`;
  }

  function renderAnHeatmap(){
    const months = anScopeMonths();
    const ff = FORD_MONTHS[months[months.length-1]] || FORD_MONTHS[AN_MONTHS_2026[0]];
    document.getElementById('an-heat-sub').textContent = anViewLabel() + ' · ' + anCanalLabel();
    const modelos = anstate.modelo ? [anstate.modelo] : (ff?.model_order||[]);
    const dealers = anstate.agencia ? [anstate.agencia] : (ff?.dealer_order||[]);
    const canalSet = anCanalSet();
    document.getElementById('an-heat-head').innerHTML =
      `<tr><th class="left">Modelo</th>${dealers.map(d=>`<th>${d}</th>`).join('')}<th>Total</th></tr>`;
    const tbody = document.querySelector('#an-heatmap tbody');
    tbody.innerHTML = modelos.map(m=>{
      let rowReal=0, rowMeta=0;
      const cells = dealers.map(d=>{
        let real=0, metaMkt=0;
        months.forEach(mk=>{
          const fm = FORD_MONTHS[mk]; if(!fm) return;
          const dayFactor = anMonthDayFactor(fm);
          const chMap = (fm.dealer_model_channel?.[d]||{})[m] || {};
          for(const k in chMap){ if(canalSet.has(k)) real += chMap[k]||0; }
          metaMkt += ((fm.matrix_meta?.[m]?.[d])||0) * dayFactor;
        });
        const meta = Math.round(anScaleMeta(metaMkt));
        rowReal+=real; rowMeta+=meta;
        if(meta===0 && real===0) return `<td class="cell dash" title="Sin tráfico ni meta">—</td>`;
        if(meta===0 && real>0) return `<td class="cell grey" title="${real} reg, sin meta"><div class="cell-with-count"><span>N/A</span><span class="ct">${real} reg</span></div></td>`;
        const pct = 100*real/meta;
        const cls = pct>=100?'green':pct>=70?'yellow':'red';
        return `<td class="cell ${cls}" title="${m} en ${d}: ${real}/${meta} (${pct.toFixed(0)}%)"><div class="cell-with-count"><span>${pct.toFixed(0)}%</span><span class="ct">${real}/${meta}</span></div></td>`;
      }).join('');
      let totCell;
      if(rowMeta===0){ totCell = rowReal===0?`<td class="cell dash">—</td>`:`<td class="cell grey">N/A<br><span class="ct">${rowReal}</span></td>`; }
      else {
        const pct = 100*rowReal/rowMeta;
        const cls = pct>=100?'green':pct>=70?'yellow':'red';
        totCell = `<td class="cell ${cls}" style="font-weight:700"><div class="cell-with-count"><span>${pct.toFixed(0)}%</span><span class="ct">${rowReal}/${rowMeta}</span></div></td>`;
      }
      return `<tr><td class="left">${m}</td>${cells}${totCell}</tr>`;
    }).join('');
  }

  function renderAnPorMes(){
    document.getElementById('an-evo-sub').textContent = (anstate.modelo||'Todos los modelos') + ' · ' + (anstate.agencia||'Todas las agencias');
    let prevReal = null;
    const rows = AN_MONTHS_2026.map(mk=>{
      const {curr, meta} = anAgg([mk], anScopeModels(), anScopeDealers());
      const pct = meta>0 ? 100*curr/meta : null;
      const delta = prevReal==null ? null : curr - prevReal;
      prevReal = curr;
      return {mk, label:AN_MONTH_LBL[mk], curr, meta, pct, delta};
    });
    const totReal = rows.reduce((s,r)=>s+r.curr,0);
    const totMeta = rows.reduce((s,r)=>s+r.meta,0);
    const totPct = totMeta>0 ? 100*totReal/totMeta : null;
    const tbody = document.querySelector('#an-tbl-mes tbody');
    tbody.innerHTML = rows.map(r=>`<tr>
      <td><strong>${r.label}</strong></td>
      <td class="num">${fmt(r.curr)}</td>
      <td class="num">${fmt(r.meta)}</td>
      <td class="num" style="color:${pctColor(r.pct)};font-weight:700">${r.pct==null?'—':r.pct.toFixed(0)+'%'}</td>
      <td class="bar-cell">${metaBarHtml(r.curr, r.meta, r.pct)}</td>
      <td class="num" style="color:${r.delta==null?'var(--muted)':r.delta>=0?'var(--pos)':'var(--neg)'};font-weight:700">${r.delta==null?'—':fmtSigned(r.delta)}</td>
    </tr>`).join('') + `<tr class="total">
      <td>TOTAL YTD</td><td class="num">${fmt(totReal)}</td><td class="num">${fmt(totMeta)}</td>
      <td class="num" style="color:${pctColor(totPct)}">${totPct==null?'—':totPct.toFixed(1)+'%'}</td>
      <td></td><td></td>
    </tr>`;
  }

  // Cruce tráfico × inventario × reservas — pestaña Otros.
  // Vista 1: heatmap mes × modelo (todos los modelos Ford en una tabla compacta).
  // Vista 2: tabla detalle con el modelo filtrado (o Ford total si no hay filtro).
  // Solo considera meses 2026 (oct-dic 2025 no tienen metas y distorsionan la lectura).
  function renderAnCruce(){
    if(!DATA.inventario || !DATA.inventario.monthly_cross) return;
    const mc = DATA.inventario.monthly_cross['FORD'];
    if(!mc) return;
    const breakdown = DATA.ford_meta_breakdown || {};

    // Solo meses 2026
    const monthKeys = (DATA.months_config || [])
      .map(c => c.key)
      .filter(k => k.endsWith('_2026'));
    const monthLabels = monthKeys.map(k => {
      const c = (DATA.months_config || []).find(x => x.key === k);
      return c ? c.label.replace(' 2026','') : k;
    });

    // Calcula la fila por modelo (o Ford total) para un mes, con filtro opcional por agencia.
    // Cuando hay agenciaOpt: tráfico/meta usan matrix_cnt/matrix_meta por agencia;
    //   ventas/reservas usan por_agencia; disp e arribos se mantienen a nivel modelo
    //   total (no se atribuyen a agencia históricamente).
    function calcRow(mk, modeloOpt, agenciaOpt){
      const cr = mc[mk]; if(!cr) return null;
      const fm = FORD_MONTHS[mk]; if(!fm) return null;
      let trafico, meta;
      if(modeloOpt && agenciaOpt){
        trafico = (fm.matrix_cnt?.[modeloOpt]?.[agenciaOpt]) || 0;
        meta    = (fm.matrix_meta?.[modeloOpt]?.[agenciaOpt]) || 0;
      } else if(modeloOpt){
        trafico = (fm.models?.[modeloOpt]?.curr) || 0;
        meta    = (fm.models?.[modeloOpt]?.meta) || 0;
      } else if(agenciaOpt){
        trafico = (fm.dealers?.[agenciaOpt]?.curr) || 0;
        meta    = (fm.dealers?.[agenciaOpt]?.meta) || 0;
      } else {
        trafico = fm.total_curr || 0;
        meta    = fm.meta_total || 0;
      }
      const cumpl = meta > 0 ? Math.round(100*trafico/meta) : null;
      const src = modeloOpt ? (cr.por_modelo?.[modeloOpt] || {}) : cr;
      const mb  = breakdown[mk] || {};

      // Calcular ventas / reservas / arribos según filtros
      let ventas, reserv_som, reserv_eom, arribos, disp_som, disp_eom;
      if(agenciaOpt){
        // Filtrar por agencia: ventas + reservas vienen de por_agencia; disp queda total modelo
        if(modeloOpt){
          const ag = src.por_agencia?.[agenciaOpt] || {};
          ventas = ag.ventas || 0;
          reserv_som = ag.reserv_som ?? null;
          reserv_eom = ag.reserv_eom ?? null;
        } else {
          // Sumar agencia a través de todos los modelos
          ventas = 0; reserv_som = 0; reserv_eom = 0;
          let r_som_has = false, r_eom_has = false;
          Object.values(cr.por_modelo || {}).forEach(srcM => {
            const ag = srcM.por_agencia?.[agenciaOpt] || {};
            ventas += ag.ventas || 0;
            if(ag.reserv_eom != null){ reserv_eom += ag.reserv_eom; r_eom_has = true; }
            if(ag.reserv_som != null){ reserv_som += ag.reserv_som; r_som_has = true; }
          });
          if(!r_som_has) reserv_som = null;
          if(!r_eom_has) reserv_eom = null;
        }
        // Disp y arribos NO se desglosan por agencia (los VINs disponibles no
        // están atribuidos a una agencia hasta que se reserven/facturen).
        arribos  = src.arribos ?? null;
        disp_som = src.disp_som;
        disp_eom = src.disp_eom;
      } else {
        ventas = src.ventas || 0;
        arribos = src.arribos || 0;
        disp_som = src.disp_som;
        disp_eom = src.disp_eom;
        reserv_som = src.reserv_som;
        reserv_eom = src.reserv_eom;
      }

      // Cobertura efectiva: respeta filtro modelo Y agencia
      let utilTot = 0, metaVentasTot = 0;
      const _calc = (m, srcM, metaV_ag) => {
        const reservas = (agenciaOpt
          ? (srcM.por_agencia?.[agenciaOpt]?.reserv_som ?? 0)
          : (srcM.reserv_som || 0));
        // disp + arribos: cuando filtra por agencia, usamos disp/arribos total modelo
        // como mejor aproximación disponible (no podemos asignar VINs por agencia).
        const inv      = (srcM.disp_som || 0) + (srcM.arribos || 0);
        const metaV    = agenciaOpt ? (metaV_ag || 0) : ((mb[m]?.meta_ventas) || 0);
        const util     = metaV > 0 ? Math.min(reservas, inv, metaV) : 0;
        return {util, metaV};
      };
      if(modeloOpt){
        const metaV_ag = agenciaOpt ? ((mb[modeloOpt]?.por_agencia||{})[agenciaOpt]?.meta_ventas || 0) : 0;
        const x = _calc(modeloOpt, src, metaV_ag);
        utilTot = x.util; metaVentasTot = x.metaV;
      } else if(cr.por_modelo){
        Object.entries(cr.por_modelo).forEach(([m, srcM]) => {
          const metaV_ag = agenciaOpt ? ((mb[m]?.por_agencia||{})[agenciaOpt]?.meta_ventas || 0) : 0;
          const x = _calc(m, srcM, metaV_ag);
          utilTot += x.util; metaVentasTot += x.metaV;
        });
      }
      const coberturaPct = metaVentasTot > 0 ? Math.round(100*utilTot/metaVentasTot) : null;
      return {
        mk, lbl: cr.mes_label, is_current: cr.is_current,
        trafico, meta, cumpl,
        ventas, arribos, disp_som, disp_eom, reserv_som, reserv_eom,
        metaVentas: metaVentasTot,
        reservasUtiles: utilTot,
        coberturaPct,
        agencia_filtered: !!agenciaOpt,
      };
    }

    // Indicador principal = % cumplimiento de TRÁFICO (lo que el equipo de marketing mide).
    // El diagnóstico (color) considera además el contexto: ventas, stock, reservas.
    //
    // Casos que detecta:
    //  ✅ Tráfico cumple Y ventas también                → "ritmo OK"
    //  ⚠️ Tráfico cumple PERO sobre-stock y ventas bajas → "trajo gente pero no vende"
    //  ✅ Tráfico bajo PERO reservas pre-mes con stock   → "bajo justificado"
    //  📦 Tráfico bajo porque no había stock              → "sin inventario"
    //  🟥 Tráfico bajo + sobre-stock crónico              → "sobre-stock, no necesita más tráfico"
    //  📉 Tráfico bajo sin explicación operativa          → "caída real"
    function diagnose(r, prevR){
      if(!r) return {cls:'gray', emoji:'·', cumpl:null, sub:'sin datos', detail:'Sin datos'};
      if(r.is_current) return {cls:'gray', emoji:'⏳', cumpl:null, sub:'en curso', detail:'Mes incompleto'};
      // Sin meta de tráfico — pero pudo haber actividad real
      if(!r.meta || r.meta === 0){
        if(r.ventas > 0 || r.trafico > 0){
          // Hubo actividad real, reflejarlo aunque no haya meta para evaluar cumplimiento
          return {cls: r.ventas > 0 ? 'green' : 'yellow',
                  emoji: r.ventas > 0 ? '✅' : '⚪',
                  cumpl:null,
                  altNum: r.ventas > 0 ? r.ventas : r.trafico,
                  altUnit: r.ventas > 0 ? 'vts' : 'tráf',
                  sub: r.ventas > 0 ? `${r.ventas} ventas` : `${r.trafico} tráfico`,
                  detail:`Sin meta cargada · Tráfico: ${r.trafico} · Ventas: ${r.ventas}`};
        }
        return {cls:'gray', emoji:'—', cumpl:null, sub:'sin meta', detail:'No hay meta cargada y no hubo actividad'};
      }
      const cumplT = r.cumpl;  // % cumplimiento de tráfico
      const trafEnMeta = cumplT >= 85;
      // Cumpl de ventas (puede ser null si no hay meta de ventas)
      const cumplV = r.metaVentas > 0 ? Math.round(100 * r.ventas / r.metaVentas) : null;
      const stockSom = r.disp_som ?? 0;
      const stockEom = r.disp_eom ?? 0;
      // Sobre-stock: stock al cierre > 2× meta_ventas Y ventas bajas
      const sobreStock = r.metaVentas > 0 && stockEom > r.metaVentas * 2 && cumplV !== null && cumplV < 50;
      // Sin stock: stock inicio < 30% de meta_ventas
      const sinStock = r.metaVentas > 0 && stockSom < r.metaVentas * 0.3;
      // Reservas que ayudan: reservas con stock cubren ≥60% de la meta_ventas
      const reservasAlivian = r.coberturaPct !== null && r.coberturaPct >= 60;

      // Tráfico cumple meta
      if(trafEnMeta){
        if(sobreStock){
          return {cls:'orange', emoji:'⚠️', cumpl:cumplT, sub:'trajo gente, no vende',
                  detail:`Tráfico ${cumplT}% pero solo ${r.ventas} ventas con ${stockEom} en stock — problema comercial, no de marketing`};
        }
        return {cls:'green', emoji:'✅', cumpl:cumplT, sub:'ritmo OK',
                detail:`Tráfico ${r.trafico}/${r.meta} (${cumplT}%) y ventas ${r.ventas}/${r.metaVentas||'—'}`};
      }
      // Tráfico bajo — investigar por qué
      if(sobreStock){
        return {cls:'red', emoji:'🟥', cumpl:cumplT, sub:'sobre-stock crónico',
                detail:`Stock cierre ${stockEom} (meta vtas ${r.metaVentas}) con solo ${r.ventas} ventas — el producto no rota, marketing no resolverá esto`};
      }
      if(reservasAlivian){
        return {cls:'green', emoji:'✅', cumpl:cumplT, sub:'con reservas',
                detail:`Tráfico bajo (${cumplT}%) está justificado: ${r.reservasUtiles} reservas con stock cubren ${r.coberturaPct}% de la meta de ventas`};
      }
      if(sinStock){
        return {cls:'red', emoji:'📦', cumpl:cumplT, sub:'sin stock',
                detail:`Solo ${stockSom} disp al inicio del mes — no había con qué generar interés`};
      }
      if(cumplT >= 60){
        return {cls:'yellow', emoji:'⚠️', cumpl:cumplT, sub:'parcial',
                detail:`Tráfico ${r.trafico}/${r.meta} (${cumplT}%) — bajo objetivo pero recuperable`};
      }
      return {cls:'red', emoji:'📉', cumpl:cumplT, sub:'caída real',
              detail:`Tráfico ${r.trafico}/${r.meta} (${cumplT}%) sin explicación operativa`};
    }

    // ====================== HEATMAP MES × MODELO ======================
    const modelOrder = ['TERRITORY','ESCAPE','EVEREST','EXPLORER','EXPEDITION','BRONCO','F-150','RANGER'];
    const heatHead = document.querySelector('#an-tbl-cruce-heat thead');
    const heatBody = document.querySelector('#an-tbl-cruce-heat tbody');
    heatHead.innerHTML = `<tr><th style="background:var(--ford-2);min-width:110px">Modelo</th>${monthLabels.map(l => `<th style="background:var(--ford-2);min-width:90px">${l}</th>`).join('')}</tr>`;

    function cellHtml(r, prevR){
      if(!r) return `<td style="background:#f9fafb;color:#d1d5db;text-align:center;border:2px solid #fff">·</td>`;
      const diag = diagnose(r, prevR);
      const BG = {green:'#c8e6c9', yellow:'#fff59d', orange:'#ffcc80', red:'#ffcdd2', gray:'#eceff1'};
      const FG = {green:'#1b5e20', yellow:'#7a5601', orange:'#bf5300', red:'#b71c1c', gray:'#546e7a'};
      const bg = BG[diag.cls] || '#fff';
      const fg = FG[diag.cls] || '#666';
      // Tooltip compacto, solo lo esencial
      const cumplV = (r.metaVentas > 0) ? Math.round(100*r.ventas/r.metaVentas) : null;
      const tip = `${r.lbl}\nTráfico: ${r.trafico} / ${r.meta || '—'} (${r.cumpl ?? '—'}%)\nVentas: ${r.ventas} / ${r.metaVentas || '—'} (${cumplV != null ? cumplV+'%' : '—'})\nStock inicio → cierre: ${r.disp_som ?? '—'} → ${r.disp_eom ?? '—'}\nReservas activas inicio: ${r.reserv_som ?? '—'}\n→ ${diag.detail}`;
      // bigNum: si hay cumpl tráfico, mostrar %; si no, mostrar volumen absoluto cuando hubo actividad
      const bigNum = diag.cumpl != null ? diag.cumpl + '%'
                   : diag.altNum != null ? diag.altNum
                   : '—';
      const bigUnit = (diag.cumpl == null && diag.altUnit) ? `<span style="font-size:11px;font-weight:600;opacity:.7;margin-left:2px">${diag.altUnit}</span>` : '';
      return `<td title="${tip.replace(/"/g,'&quot;')}" style="background:${bg};color:${fg};text-align:center;padding:10px 6px;border:2px solid #fff;min-width:90px">
        <div style="font-size:18px;line-height:1;margin-bottom:3px">${diag.emoji}</div>
        <div style="font-size:17px;font-weight:800;line-height:1">${bigNum}${bigUnit}</div>
        <div style="font-size:10px;font-weight:500;letter-spacing:.3px;margin-top:3px;opacity:.8">${diag.sub}</div>
      </td>`;
    }

    // Filtro de agencia: si está activo, todas las filas se calculan con ese filtro.
    const filtroAgencia = anstate.agencia || null;
    // Por cada modelo, calcular fila para cada mes
    const rowsByModel = {};
    modelOrder.forEach(modelo => {
      rowsByModel[modelo] = monthKeys.map(mk => calcRow(mk, modelo, filtroAgencia));
    });
    const totalRows = monthKeys.map(mk => calcRow(mk, null, filtroAgencia));

    heatBody.innerHTML = modelOrder.map(modelo => {
      const rs = rowsByModel[modelo];
      const cells = rs.map((r, i) => cellHtml(r, i>0 ? rs[i-1] : null)).join('');
      return `<tr>
        <td class="left"><strong>${modelo}</strong></td>
        ${cells}
      </tr>`;
    }).join('') + `<tr class="total">
      <td><strong>TOTAL FORD</strong></td>
      ${totalRows.map((r,i) => cellHtml(r, i>0 ? totalRows[i-1] : null)).join('')}
    </tr>`;

    // ====================== TABLA DETALLE ======================
    const filtroModelo = anstate.modelo || null;
    const detailScope = [
      filtroModelo ? `Modelo: ${filtroModelo}` : 'Todos los modelos Ford',
      filtroAgencia ? `Agencia: ${filtroAgencia}` : null,
    ].filter(Boolean).join(' · ');
    document.getElementById('an-cruce-detail-title').textContent = 'Detalle por mes — ' + detailScope;
    const detailRows = monthKeys.map(mk => calcRow(mk, filtroModelo, filtroAgencia)).filter(Boolean);
    const tbody = document.querySelector('#an-tbl-cruce tbody');
    tbody.innerHTML = detailRows.map((r,i) => {
      const diag = diagnose(r, i>0 ? detailRows[i-1] : null);
      const cumplT = r.cumpl;
      const cumplStr = cumplT == null ? '—' : cumplT + '%';
      const cumplCls = cumplT == null ? 'color:var(--muted)'
                     : cumplT >= 100 ? 'color:var(--pos);font-weight:700'
                     : cumplT >= 85  ? 'color:#f57f17;font-weight:700'
                     : 'color:var(--neg);font-weight:700';
      const trafStr = r.meta > 0 ? `${r.trafico} / ${r.meta}` : `${r.trafico}`;
      const ventasStr = r.metaVentas > 0
        ? `${r.ventas} / ${r.metaVentas} (${Math.round(100*r.ventas/r.metaVentas)}%)`
        : `${r.ventas}`;
      return `<tr>
        <td class="left"><strong>${r.lbl}</strong>${r.is_current?' <span style="font-size:10px;color:var(--muted);font-weight:500">en curso</span>':''}</td>
        <td class="num">${trafStr}</td>
        <td class="num" style="${cumplCls}">${cumplStr}</td>
        <td class="num">${ventasStr}</td>
        <td class="num">${r.disp_som ?? '—'}</td>
        <td class="num">${r.disp_eom ?? '—'}</td>
        <td class="num">${r.reserv_som ?? '—'}</td>
        <td><span class="status-pill ${diag.cls}" title="${(diag.detail||'').replace(/"/g,'&quot;')}">${diag.emoji} ${diag.sub}</span></td>
      </tr>`;
    }).join('');
  }

  function renderAnInsights(){
    const insights = [];
    const months = anScopeMonths();
    const isYtd = anstate.view==='ytd';
    const scope = (anstate.modelo?`modelo ${anstate.modelo}`:'todos los modelos') + ' · ' + (anstate.agencia?`agencia ${anstate.agencia}`:'todas las agencias');

    // Total
    const {curr, meta} = anAgg(months, anScopeModels(), anScopeDealers());
    const pct = meta>0?100*curr/meta:null;
    insights.push({type: pct==null?'warn': pct>=100?'good':pct>=70?'warn':'bad', title:'📊 Cumplimiento general',
      html: `Bajo el scope <strong>${scope}</strong> (${anViewLabel()}), tráfico real es <span class="data">${curr}</span> contra meta <span class="data">${meta}</span> → cumplimiento <span class="data">${pct==null?'N/A':pct.toFixed(1)+'%'}</span>${meta>0?`, gap <span class="data">${fmtSigned(curr-meta)}</span>`:''}.`});

    // Best/worst model
    const ff = FORD_MONTHS[AN_MONTHS_2026[0]] || FORD;
    if(!anstate.modelo){
      const perModel = (ff?.model_order||[]).map(m=>{
        const {curr:c,meta:me} = anAgg(months, [m], anScopeDealers());
        return {m,c,me,p: me>0?100*c/me:null};
      }).filter(r=>r.c>0||r.me>0);
      const withMeta = perModel.filter(r=>r.p!=null);
      if(withMeta.length){
        const best = [...withMeta].sort((a,b)=>b.p-a.p)[0];
        const worst = [...withMeta].sort((a,b)=>a.p-b.p)[0];
        insights.push({type: best.p>=100?'good':'warn', title:'🚗 Mejor modelo vs meta',
          html:`<strong>${best.m}</strong> lidera con <span class="data">${best.p.toFixed(0)}%</span> (${best.c}/${best.me}).`});
        insights.push({type:'bad', title:'🚗 Peor modelo vs meta',
          html:`<strong>${worst.m}</strong> tiene el mayor gap con <span class="data">${worst.p.toFixed(0)}%</span> (${worst.c}/${worst.me}), faltan <span class="data">${worst.me-worst.c}</span> registros.`});
      }
    }

    // Best/worst agency
    if(!anstate.agencia){
      const perAg = (ff?.dealer_order||[]).map(d=>{
        const {curr:c,meta:me} = anAgg(months, anScopeModels(), [d]);
        return {d,c,me,p: me>0?100*c/me:null};
      }).filter(r=>r.c>0||r.me>0);
      const withMeta = perAg.filter(r=>r.p!=null);
      if(withMeta.length){
        const best = [...withMeta].sort((a,b)=>b.p-a.p)[0];
        const worst = [...withMeta].sort((a,b)=>a.p-b.p)[0];
        insights.push({type: best.p>=100?'good':'warn', title:'🏢 Mejor agencia vs meta',
          html:`<strong>${best.d}</strong> lidera con <span class="data">${best.p.toFixed(0)}%</span> (${best.c}/${best.me}).`});
        insights.push({type:'bad', title:'🏢 Peor agencia vs meta',
          html:`<strong>${worst.d}</strong> tiene el mayor gap con <span class="data">${worst.p.toFixed(0)}%</span> (${worst.c}/${worst.me}), faltan <span class="data">${worst.me-worst.c}</span> registros.`});
      }
    }

    // Best/worst month (only in YTD view)
    if(isYtd){
      const perMes = AN_MONTHS_2026.map(mk=>{
        const {curr:c,meta:me} = anAgg([mk], anScopeModels(), anScopeDealers());
        return {mk,label:AN_MONTH_LBL[mk],c,me,p: me>0?100*c/me:null};
      });
      const withMeta = perMes.filter(r=>r.p!=null);
      if(withMeta.length){
        const best = [...withMeta].sort((a,b)=>b.p-a.p)[0];
        const worst = [...withMeta].sort((a,b)=>a.p-b.p)[0];
        insights.push({type:'warn', title:'📅 Mejor y peor mes',
          html:`<strong>${best.label}</strong> con <span class="data">${best.p.toFixed(0)}%</span> · <strong>${worst.label}</strong> con <span class="data">${worst.p.toFixed(0)}%</span>. Spread: <span class="data">${(best.p-worst.p).toFixed(0)} puntos</span>.`});
      }
    }

    // Top canal (filtrado por categoría activa: marketing/asesor/todos)
    const ch = {};
    const insCanalSet = anCanalSet();
    months.forEach(mk=>{
      const fm = FORD_MONTHS[mk]; if(!fm) return;
      const dmc = fm.dealer_model_channel || {};
      const deals = anstate.agencia ? [anstate.agencia] : (fm.dealer_order || []);
      const mods = anstate.modelo ? [anstate.modelo] : (fm.model_order || []);
      const dealList = anstate.agencia ? deals : [...deals, 'Otros'];
      dealList.forEach(d=>{
        mods.forEach(m=>{
          const ms = (dmc[d]||{})[m] || {};
          Object.entries(ms).forEach(([c,v])=>{
            if(!insCanalSet.has(c)) return;
            ch[c] = (ch[c]||0) + (v||0);
          });
        });
      });
    });
    const chEntries = Object.entries(ch).filter(([,v])=>v>0).sort((a,b)=>b[1]-a[1]);
    if(chEntries.length){
      const total = chEntries.reduce((s,[,v])=>s+v,0);
      const [topC,topV] = chEntries[0];
      insights.push({type:'warn', title:'📡 Canal dominante',
        html:`<strong>${topC}</strong> concentra <span class="data">${(100*topV/total).toFixed(0)}%</span> del tráfico (${topV} de ${total}). ${chEntries.length>1?`Le sigue ${chEntries[1][0]} con ${(100*chEntries[1][1]/total).toFixed(0)}%.`:''}`});
    }

    document.getElementById('an-insights').innerHTML = insights.map(ins=>`
      <div class="insight-card ${ins.type}">
        <h4>${ins.title}</h4>
        <p>${ins.html}</p>
      </div>`).join('');
  }

  function renderAnalysis(){
    renderAnalysisFilterSummary();
    renderAnHero();
    renderAnPorModelo();
    renderAnPorAgencia();
    renderAnPorCanal();
    renderAnHeatmap();
    renderAnPorMes();
    renderAnCruce();
    renderAnInsights();
  }

  // =========================================================
  //              MÓDULO INVENTARIO
  // =========================================================
  const INV = DATA.inventario || null;
  const INV_AGENCIES = ['CJA','Orellana','La Y','Tumbaco','Manta','Machala','Portoviejo'];
  const invstate = { marca: 'FORD', mes: DATA.default_month_key || 'mayo_2026', versionFilter: '', cobView: 'modelo' };
  let invInited = false;

  function initInventario(){
    if(invInited || !INV) return;
    invInited = true;
    document.getElementById('inv-marca').addEventListener('change', e=>{
      invstate.marca = e.target.value;
      renderInventario();
    });
    // Toggle Modelo / Versión para tabla de cobertura
    document.querySelectorAll('.inv-cob-toggle-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        const view = btn.dataset.view;
        if(view === invstate.cobView) return;
        invstate.cobView = view;
        document.querySelectorAll('.inv-cob-toggle-btn').forEach(b => {
          const on = (b.dataset.view === view);
          b.classList.toggle('active', on);
          b.setAttribute('aria-selected', on ? 'true' : 'false');
        });
        document.getElementById('inv-cob-title-suffix').textContent = view === 'version' ? 'por versión' : 'por modelo';
        document.getElementById('inv-cob-col-row').textContent = view === 'version' ? 'Versión' : 'Modelo';
        renderInvCobertura();
      });
    });
  }

  // Tráfico del mes seleccionado, sumando TODOS los canales (marketing + asesor).
  // dealer_model_channel ya tiene los 15 canales del BD.
  function invTrafficMes(modelo){
    let monthData;
    if(invstate.marca === 'FORD'){
      monthData = FORD_MONTHS[invstate.mes];
    } else {
      monthData = (DATA.brands_months?.[invstate.mes]||{})[invstate.marca];
    }
    if(!monthData) return 0;
    let total = 0;
    const dmc = monthData.dealer_model_channel || {};
    Object.values(dmc).forEach(modelMap => {
      const chMap = modelMap[modelo] || {};
      Object.values(chMap).forEach(v => { total += v || 0; });
    });
    return total;
  }
  // Months of Supply (MOS) basado en velocidad de VENTAS (no tráfico) — más realista
  // para industria automotriz donde no se vende diariamente.
  //   MOS = disponible / ventas_promedio_mensual_últimos_6m_cerrados
  function invMOSFromSales(invModel){
    if(!invModel) return null;
    const v = invModel.ventas_avg_mensual || 0;
    if(v <= 0) return null;
    return (invModel.disp_total || 0) / v;
  }

  // Umbrales en MESES. Sobre-stock es también problema (capital atorado, depreciación)
  // por lo que se marca con rojo, no azul.
  function invCoverageClass(mos){
    if(mos == null) return {emoji:'—',  cls:'',       label:'sin ventas'};
    if(mos < 1)     return {emoji:'🟥', cls:'red',    label:'déficit'};
    if(mos < 2)     return {emoji:'🟡', cls:'yellow', label:'ajustado'};
    if(mos <= 4)    return {emoji:'🟢', cls:'green',  label:'sano'};
    return {emoji:'🟥', cls:'red', label:'sobre-stock'};
  }

  function renderInvHero(){
    if(!INV) return;
    const bd = INV.brands?.[invstate.marca];
    if(!bd){ return; }
    let disp=0, res=0, cola=0, pipe=0, colaSinVin=0;
    Object.values(bd.modelos).forEach(m=>{
      disp += m.disp_total; res += m.res_total; cola += m.cola_total;
      pipe += m.pipeline_usa + m.pipeline_nac; colaSinVin += m.cola_sin_vin;
    });
    document.getElementById('inv-k-disp').textContent = fmt(disp);
    document.getElementById('inv-k-disp-hint').textContent = `Stock listo · snapshot ${INV.snapshot_date}`;
    document.getElementById('inv-k-res').textContent = fmt(res);
    document.getElementById('inv-k-cola').textContent = fmt(cola);
    document.getElementById('inv-k-cola-hint').textContent = `${colaSinVin} sin VIN asignado (esperando llegada)`;
    document.getElementById('inv-k-pipe').textContent = fmt(pipe);
  }

  function renderInvCobertura(){
    if(!INV) return;
    const bd = INV.brands?.[invstate.marca];
    if(!bd){ document.querySelector('#inv-tbl-cob tbody').innerHTML = '<tr><td colspan="10">Sin datos de inventario para esta marca.</td></tr>'; return; }
    const mesLbl = (MONTHS_CONFIG.find(c=>c.key===invstate.mes)?.label) || invstate.mes;
    const isVersion = invstate.cobView === 'version';
    document.getElementById('inv-cob-sub').innerHTML =
      `MOS = disponible / ventas mensuales (promedio últ 3 meses cerrados) · ⚠️ junto a Ventas/mes = ritmo limitado por falta de stock (hay reservas sin VIN) · `
      + (isVersion
          ? `Tráfico no disponible por versión (el BD solo registra marca + modelo). · `
          : `Tráfico = todos los canales de <strong>${mesLbl}</strong> · `)
      + `🟥 déficit (&lt;1 mes) · 🟡 ajustado (1-2) · 🟢 sano (2-4) · 🟥 sobre-stock (&gt;4 meses)`;

    // Helpers
    function fmtMos(m){
      if(m == null) return '—';
      if(m > 99) return '99+';
      return m.toFixed(1);
    }
    function camCell(transito, pipeUsa, pipeNac, total){
      const tip = `${transito} en tránsito (ya inventario) · ${pipeUsa} pedidos USA · ${pipeNac} nacionalización`;
      return `<td class="num" style="color:var(--muted)" title="${tip}">${fmt(total)}</td>`;
    }
    function buildRow(label, d, opts){
      const inAgency = Object.values(d.disp_agencias||{}).reduce((s,v)=>s+v,0);
      const ventasMes = d.ventas_avg_mensual || 0;
      const mos = invMOSFromSales(d);
      const status = invCoverageClass(mos);
      const pipeUsa = d.pipeline_usa || 0;
      const pipeNac = d.pipeline_nac || 0;
      const transito = d.disp_transito || 0;
      const enCamino = transito + pipeUsa + pipeNac;
      const trafficMes = opts.showTraffic ? invTrafficMes(opts.modeloForTraffic || label) : null;
      return { label, d, inAgency, transito, dispTotal: d.disp_total,
        resTotal: d.res_total, cola: d.cola_total, pipeUsa, pipeNac, enCamino,
        ventasMes, trafficMes, mos, status };
    }
    function rowHtml(r, opts){
      const rowClass = opts.rowClass || '';
      const labelHtml = opts.labelHtml || `<strong>${r.label}</strong>`;
      const trafCell = opts.showTraffic
        ? `<td class="num">${fmt(r.trafficMes)}</td>`
        : `<td class="num" style="color:#c9ccd6" title="No hay atribución de tráfico por versión — el BD registra solo marca y modelo">—</td>`;
      return `<tr class="${rowClass}">
        <td class="left">${labelHtml}</td>
        <td class="num">${fmt(r.inAgency)}</td>
        ${camCell(r.transito, r.pipeUsa, r.pipeNac, r.enCamino)}
        <td class="num" style="font-weight:700">${fmt(r.dispTotal)}</td>
        <td class="num">${fmt(r.resTotal)}</td>
        <td class="num">${fmt(r.cola)}</td>
        <td class="num">${r.ventasMes>0?r.ventasMes.toFixed(1):'—'}${r.d.venta_limitada_por_stock?' <span title="Hay reservas sin VIN — el ritmo real de demanda es mayor que las ventas observadas porque hubo falta de stock" style="color:#ef6c00">⚠️</span>':''}</td>
        ${trafCell}
        <td class="num" style="font-weight:700">${fmtMos(r.mos)}</td>
        <td class="num"><span class="status-pill ${r.status.cls}">${r.status.emoji} ${r.status.label}</span></td>
      </tr>`;
    }
    function statusOrder(s){
      return s.cls==='red' && s.label==='déficit' ? 0
           : s.cls==='yellow' ? 1
           : s.cls==='green' ? 2
           : s.cls==='red' && s.label==='sobre-stock' ? 3
           : 4;
    }

    let bodyHtml = '';
    let tot = {inAgency:0,transito:0,dispTotal:0,resTotal:0,cola:0,pipeUsa:0,pipeNac:0,enCamino:0,trafficMes:0,ventasMes:0};

    if(!isVersion){
      // ============ VISTA POR MODELO (default) ============
      const rows = Object.entries(bd.modelos)
        .map(([m, d]) => buildRow(m, d, {showTraffic:true, modeloForTraffic:m}))
        .sort((a,b) => statusOrder(a.status) - statusOrder(b.status) || b.cola - a.cola);
      rows.forEach(r => {
        tot.inAgency += r.inAgency; tot.transito += r.transito; tot.dispTotal += r.dispTotal;
        tot.resTotal += r.resTotal; tot.cola += r.cola;
        tot.pipeUsa += r.pipeUsa; tot.pipeNac += r.pipeNac; tot.enCamino += r.enCamino;
        tot.trafficMes += r.trafficMes; tot.ventasMes += r.ventasMes;
      });
      bodyHtml = rows.map(r => rowHtml(r, {showTraffic:true})).join('');
    } else {
      // ============ VISTA POR VERSIÓN ============
      // Agrupar versiones por modelo; ordenar modelos por mayor demanda total
      // (cola + ventas), y dentro de cada grupo ordenar versiones por estado/cola.
      const modelos = Object.entries(bd.modelos).map(([m, d]) => {
        const versiones = Object.entries(d.versiones || {})
          .map(([ver, vd]) => buildRow(ver, vd, {showTraffic:false}))
          .sort((a,b) => statusOrder(a.status) - statusOrder(b.status)
                       || b.cola - a.cola || b.dispTotal - a.dispTotal);
        return {m, d, versiones, demand: (d.cola_total||0) + (d.ventas_3m||0)};
      }).sort((a,b) => b.demand - a.demand);

      modelos.forEach(({m, d, versiones}) => {
        if(versiones.length === 0) return;
        // Subtotal por modelo (a partir del nivel modelo, NO la suma de versiones —
        // así el lector ve la realidad oficial del modelo aunque la suma debería
        // coincidir).
        const modeloRow = buildRow(m, d, {showTraffic:true, modeloForTraffic:m});
        tot.inAgency += modeloRow.inAgency; tot.transito += modeloRow.transito;
        tot.dispTotal += modeloRow.dispTotal; tot.resTotal += modeloRow.resTotal;
        tot.cola += modeloRow.cola;
        tot.pipeUsa += modeloRow.pipeUsa; tot.pipeNac += modeloRow.pipeNac;
        tot.enCamino += modeloRow.enCamino; tot.trafficMes += modeloRow.trafficMes;
        tot.ventasMes += modeloRow.ventasMes;
        // Cabecera del grupo: nombre modelo + totales pequeños
        bodyHtml += `<tr class="version-group-head"><td colspan="10">📦 ${m} — ${versiones.length} versión${versiones.length===1?'':'es'} · disp ${fmt(modeloRow.dispTotal)} · cola ${fmt(modeloRow.cola)} · vtas/mes ${modeloRow.ventasMes>0?modeloRow.ventasMes.toFixed(1):'—'}</td></tr>`;
        versiones.forEach(vr => {
          bodyHtml += rowHtml(vr, {showTraffic:false, rowClass:'version-row'});
        });
      });
    }

    // Fila TOTAL
    const totMos = tot.ventasMes>0 ? tot.dispTotal/tot.ventasMes : null;
    const totStatus = invCoverageClass(totMos);
    const totTrafCell = isVersion
      ? `<td class="num" style="color:#c9ccd6">—</td>`
      : `<td class="num">${fmt(tot.trafficMes)}</td>`;
    bodyHtml += `<tr class="total">
        <td class="left"><strong>TOTAL</strong></td>
        <td class="num">${fmt(tot.inAgency)}</td>
        ${camCell(tot.transito, tot.pipeUsa, tot.pipeNac, tot.enCamino)}
        <td class="num">${fmt(tot.dispTotal)}</td>
        <td class="num">${fmt(tot.resTotal)}</td>
        <td class="num">${fmt(tot.cola)}</td>
        <td class="num">${tot.ventasMes.toFixed(1)}</td>
        ${totTrafCell}
        <td class="num">${fmtMos(totMos)}</td>
        <td class="num"><span class="status-pill ${totStatus.cls}">${totStatus.emoji} ${totStatus.label}</span></td>
      </tr>`;

    document.querySelector('#inv-tbl-cob tbody').innerHTML = bodyHtml;
  }

  // Cards de versiones: una card por cada modelo con reservas en cola (independiente de
  // cuántas versiones tenga). Cada card muestra el total + barras horizontales por versión.
  function renderInvVersiones(){
    if(!INV) return;
    const wrap = document.getElementById('inv-version-cards');
    const bd = INV.brands?.[invstate.marca];
    if(!bd){ wrap.innerHTML = '<div class="vc-empty">Sin datos para esta marca.</div>'; return; }

    // Todos los modelos con al menos 1 reserva en cola
    const all = Object.entries(bd.modelos)
      .filter(([m, d]) => d.cola_total > 0)
      .sort((a,b) => b[1].cola_total - a[1].cola_total);

    if(all.length === 0){
      wrap.innerHTML = '<div class="vc-empty">No hay reservas en cola para esta marca.</div>';
      return;
    }

    wrap.innerHTML = all.map(([modelo, d])=>{
      let vers = Object.entries(d.cola_versions||{}).filter(([,v])=>v>0).sort((a,b)=>b[1]-a[1]);
      // Fallback: si no hay versiones desglosadas, usar el modelo como única "versión"
      if(vers.length === 0) vers = [[modelo, d.cola_total]];
      const total = d.cola_total;
      const max = vers[0][1];
      const rows = vers.map(([ver, count])=>{
        const pct = total>0 ? Math.round(100*count/total) : 0;
        const w = Math.round(100*count/max);
        return `
          <div class="vc-row">
            <div class="label">${ver}</div>
            <div class="count">${count}</div>
            <div class="pct">${pct}%</div>
            <div class="vc-bar"><div class="fill" style="width:${w}%"></div></div>
          </div>`;
      }).join('');
      return `
        <div class="version-card">
          <div class="vc-head">
            <div class="name">${modelo}</div>
            <div><span class="total-lbl">Total cola</span><span class="total">${total}</span></div>
          </div>
          ${rows}
        </div>`;
    }).join('');
  }

  // Matriz reservas en cola: filas = agencias, columnas = modelos
  function renderInvColaPorAgencia(){
    if(!INV) return;
    const bd = INV.brands?.[invstate.marca];
    const head = document.querySelector('#inv-tbl-cola-agencia thead');
    const tbody = document.querySelector('#inv-tbl-cola-agencia tbody');
    if(!bd){
      head.innerHTML = ''; tbody.innerHTML = '<tr><td>Sin datos.</td></tr>';
      return;
    }
    const brandKey = invstate.marca === 'FORD' ? 'FORD' :
                     invstate.marca === 'DONGFENG_ORGU' ? 'DONGFENG' :
                     invstate.marca === 'CHERY_ORGU' ? 'CHERY' :
                     invstate.marca === 'MAZDA_ORGU' ? 'MAZDA' : 'RAM';
    const cola = (INV.cola_detail||[]).filter(c => c.marca === brandKey);
    if(cola.length === 0){
      head.innerHTML = '';
      tbody.innerHTML = '<tr><td style="text-align:center;color:var(--muted);padding:14px">Sin reservas en cola para esta marca.</td></tr>';
      return;
    }

    // Modelos visibles: solo los que tienen al menos 1 reserva, ordenados por cola desc
    const modelTot = {};
    cola.forEach(c => { modelTot[c.modelo] = (modelTot[c.modelo]||0) + 1; });
    const modelos = Object.keys(modelTot).sort((a,b) => modelTot[b] - modelTot[a]);
    // Agencias visibles: las del panel + cualquier otra que aparezca en cola
    const agencySet = new Set();
    cola.forEach(c => agencySet.add(c.agencia));
    const agencies = INV_AGENCIES.filter(a => agencySet.has(a))
      .concat([...agencySet].filter(a => !INV_AGENCIES.includes(a)).sort());

    // Construir matriz
    const mtx = {};
    agencies.forEach(a => { mtx[a] = {}; modelos.forEach(m => { mtx[a][m] = 0; }); });
    cola.forEach(c => {
      if(mtx[c.agencia] && mtx[c.agencia][c.modelo] !== undefined){
        mtx[c.agencia][c.modelo]++;
      }
    });

    // Calcular totales por agencia, por modelo, gran total
    const rowTot = {}; let grand = 0;
    agencies.forEach(a => {
      rowTot[a] = modelos.reduce((s,m) => s + mtx[a][m], 0);
      grand += rowTot[a];
    });

    // Ordenar agencias por total desc (más reservas arriba)
    agencies.sort((a,b) => rowTot[b] - rowTot[a]);

    // Filas = modelos · columnas = agencias
    head.innerHTML = `<tr><th>Modelo</th>${agencies.map(a => `<th class="num">${a}</th>`).join('')}<th class="num">Total</th></tr>`;
    tbody.innerHTML = modelos.map(m => {
      const cells = agencies.map(a => {
        const v = mtx[a][m];
        return v === 0
          ? `<td class="num" style="color:#d1d5db">·</td>`
          : `<td class="num" style="font-weight:600">${v}</td>`;
      }).join('');
      return `<tr>
        <td class="left"><strong>${m}</strong></td>
        ${cells}
        <td class="num" style="font-weight:700;background:#f3f5fa">${modelTot[m]}</td>
      </tr>`;
    }).join('') + `<tr class="total">
      <td><strong>TOTAL</strong></td>
      ${agencies.map(a => `<td class="num">${rowTot[a]}</td>`).join('')}
      <td class="num"><strong>${grand}</strong></td>
    </tr>`;
  }

  // Tiempo de espera del cliente (reserva → factura).
  // Ventana expanding: ancla fija en 1 Mayo 2025, crece mes a mes (12m → 24m → 36m...).
  function renderInvWaitTimes(){
    if(!INV) return;
    const wt = INV.wait_times?.[invstate.marca];
    const win = INV.wait_times?.['_window'];
    // Actualizar etiqueta de periodo en el header
    if(win){
      const startFmt = win.start_date.split('-').reverse().join('/');
      const periodEl = document.getElementById('inv-wait-period');
      if(periodEl) periodEl.textContent = `Días desde reserva hasta facturación · desde ${startFmt} (${win.months} meses acumulados)`;
    }
    if(!wt){
      ['inv-wait-median','inv-wait-mean','inv-wait-p75','inv-wait-n'].forEach(id=>{
        document.getElementById(id).textContent = '—';
      });
      document.querySelector('#inv-tbl-wait tbody').innerHTML = '<tr><td colspan="8">Sin datos.</td></tr>';
      return;
    }
    // KPIs hero — todo en meses (1 mes = 30 días)
    const g = wt.global_window;
    // Convierte días → meses con 1 decimal y suffix "m"
    const fmtM = (days)=>{
      if(days == null) return '—';
      const m = days / 30;
      return m.toFixed(1) + 'm';
    };
    document.getElementById('inv-wait-median').textContent = fmtM(g.mediana);
    document.getElementById('inv-wait-mean').textContent   = fmtM(g.promedio);
    document.getElementById('inv-wait-p75').textContent    = fmtM(g.p75);
    document.getElementById('inv-wait-n').textContent      = (g.n != null ? g.n.toLocaleString('es-EC') : '—');

    // Tabla por modelo, ordenada por mediana descendente (peor arriba)
    const rows = Object.entries(wt.por_modelo)
      .filter(([m,s])=>s.n>0)
      .sort((a,b)=>(b[1].mediana||0)-(a[1].mediana||0));

    if(rows.length === 0){
      document.querySelector('#inv-tbl-wait tbody').innerHTML = '<tr><td colspan="8" style="text-align:center;color:var(--muted)">Sin facturas en la ventana de análisis.</td></tr>';
      return;
    }

    // Color de la mediana, umbrales en meses: <1m verde, 1-2m amarillo, 2-3m naranja, >3m rojo
    function medColor(d){
      if(d == null) return '';
      const m = d/30;
      if(m < 1) return 'green';
      if(m < 2) return 'yellow';
      if(m < 3) return 'orange';
      return 'red';
    }
    // Barra de distribución apilada (5 buckets en meses: <1, 1-2, 2-3, 3-6, >6)
    function distBar(buckets, total){
      if(!total) return '';
      const segs = [
        {k:'m0_1',   c:'#2e7d32', lbl:'<1m'},
        {k:'m1_2',   c:'#7cb342', lbl:'1-2m'},
        {k:'m2_3',   c:'#fbc02d', lbl:'2-3m'},
        {k:'m3_6',   c:'#ef6c00', lbl:'3-6m'},
        {k:'m6_plus',c:'#c62828', lbl:'>6m'},
      ];
      return `<div style="display:flex;height:16px;border-radius:4px;overflow:hidden;background:#eef0f3;min-width:160px" title="${segs.map(s=>`${s.lbl}: ${buckets[s.k]||0}`).join(' · ')}">${
        segs.map(s=>{
          const v = buckets[s.k]||0;
          const w = 100*v/total;
          return w>0 ? `<div style="background:${s.c};width:${w}%" title="${s.lbl}: ${v}"></div>` : '';
        }).join('')
      }</div>`;
    }

    // F→E (factura → entrega): tiempo logístico corto, se mantiene en DÍAS
    const fmtDays = (v)=> v == null ? '—' : Math.round(v) + 'd';
    const entByModel = wt.entrega_por_modelo || {};
    document.querySelector('#inv-tbl-wait tbody').innerHTML = rows.map(([m,s])=>{
      const cls = medColor(s.mediana);
      const ent = entByModel[m];
      const entCell = (ent && ent.n>0)
        ? `<td class="num" title="N=${ent.n} · prom=${fmtDays(ent.promedio)}">${fmtDays(ent.mediana)}</td>`
        : `<td class="num" style="color:var(--muted)">—</td>`;
      return `<tr>
        <td class="left"><strong>${m}</strong></td>
        <td class="num">${s.n}</td>
        <td class="num"><span class="status-pill ${cls}">${fmtM(s.mediana)}</span></td>
        <td class="num">${fmtM(s.promedio)}</td>
        <td class="num">${fmtM(s.p75)}</td>
        <td class="num" style="color:var(--muted)">${fmtM(s.max)}</td>
        ${entCell}
        <td>${distBar(s.buckets, s.n)}</td>
      </tr>`;
    }).join('');
  }

  function renderInvMatrix(){
    if(!INV) return;
    const bd = INV.brands?.[invstate.marca];
    if(!bd) return;
    const modelos = Object.keys(bd.modelos);
    // Recoger todas las agencias que aparecen en disp_agencias o res_agencias
    const agSet = new Set();
    modelos.forEach(m=>{
      Object.keys(bd.modelos[m].disp_agencias).forEach(a=>agSet.add(a));
    });
    const ags = INV_AGENCIES.filter(a=>agSet.has(a));
    // Si la marca no es Ford, mostrar solo las relevantes
    const head = document.querySelector('#inv-tbl-matrix thead');
    head.innerHTML = `<tr><th class="left">Modelo</th>${ags.map(a=>`<th>${a}</th>`).join('')}<th>Tránsito</th><th>Total disp.</th></tr>`;
    const tbody = document.querySelector('#inv-tbl-matrix tbody');
    let totalsAg = {}, totalTr=0, totalDisp=0;
    ags.forEach(a=>totalsAg[a]=0);
    tbody.innerHTML = modelos.map(m=>{
      const d = bd.modelos[m];
      let rowTotal = d.disp_total;
      totalTr += d.disp_transito; totalDisp += d.disp_total;
      const cells = ags.map(a=>{
        const v = d.disp_agencias[a] || 0;
        totalsAg[a] += v;
        return `<td class="num" style="${v>0?'font-weight:600':'color:var(--muted)'}">${v||'·'}</td>`;
      }).join('');
      return `<tr>
        <td class="left"><strong>${m}</strong></td>
        ${cells}
        <td class="num" style="color:var(--muted)">${d.disp_transito||'·'}</td>
        <td class="num" style="font-weight:700">${rowTotal}</td>
      </tr>`;
    }).join('') + `<tr class="total">
      <td><strong>TOTAL</strong></td>
      ${ags.map(a=>`<td class="num">${totalsAg[a]}</td>`).join('')}
      <td class="num">${totalTr}</td>
      <td class="num">${totalDisp}</td>
    </tr>`;
  }

  function renderInvAging(){
    if(!INV) return;
    const bd = INV.brands?.[invstate.marca];
    if(!bd) return;
    let a30=0, a60=0, a90=0, aOld=0, sinVin=0, colaTot=0;
    Object.values(bd.modelos).forEach(m=>{
      a30 += m.cola_aging['0_30']||0;
      a60 += m.cola_aging['31_60']||0;
      a90 += m.cola_aging['61_90']||0;
      aOld+= m.cola_aging['90_plus']||0;
      sinVin += m.cola_sin_vin;
      colaTot += m.cola_total;
    });
    document.getElementById('inv-aging-30').textContent = fmt(a30);
    document.getElementById('inv-aging-60').textContent = fmt(a60);
    document.getElementById('inv-aging-90').textContent = fmt(a90);
    document.getElementById('inv-aging-old').textContent = fmt(aOld);
    document.getElementById('inv-aging-sinvin').textContent = `${sinVin} / ${colaTot}`;

    // Top reservas más antiguas para esta marca
    const brandKey = invstate.marca === 'FORD' ? 'FORD' :
                     invstate.marca === 'DONGFENG_ORGU' ? 'DONGFENG' :
                     invstate.marca === 'CHERY_ORGU' ? 'CHERY' :
                     invstate.marca === 'MAZDA_ORGU' ? 'MAZDA' : 'RAM';
    const cola = (INV.cola_detail||[]).filter(c=>c.marca === brandKey && c.aging_days != null)
      .sort((a,b)=>b.aging_days - a.aging_days).slice(0,12);
    const tbody = document.querySelector('#inv-tbl-aging tbody');
    if(cola.length === 0){
      tbody.innerHTML = '<tr><td colspan="9">Sin reservas con fecha registrada para esta marca.</td></tr>';
      return;
    }
    tbody.innerHTML = cola.map(c=>{
      const agingCls = c.aging_days>90?'red':c.aging_days>60?'yellow':c.aging_days>30?'orange':'';
      return `<tr>
        <td class="left"><strong>${c.modelo}</strong></td>
        <td class="left">${c.agencia||'—'}</td>
        <td class="left" style="font-size:12px">${c.cliente||'—'}</td>
        <td class="left" style="font-size:12px">${c.asesor||'—'}</td>
        <td class="num" style="font-size:12px">${c.fecha||'—'}</td>
        <td class="num"><span class="status-pill ${agingCls}">${c.aging_days}</span></td>
        <td class="num">${c.valor==null?'—':'$'+fmt(c.valor)}</td>
        <td class="num" style="font-size:11px;color:var(--muted)">${c.modalidad||'—'}</td>
        <td class="num">${c.sin_vin?'⏳':'✓'}</td>
      </tr>`;
    }).join('');
  }

  function renderInvInsights(){
    if(!INV) return;
    const bd = INV.brands?.[invstate.marca]; if(!bd) return;
    const insights = [];
    // 1. Modelos en déficit (basado en ventas mensuales)
    const deficits = Object.entries(bd.modelos).map(([m,d])=>{
      const mos = invMOSFromSales(d);
      return {m,d,mos};
    }).filter(x => x.mos !== null && x.mos < 1 && x.d.ventas_avg_mensual > 0).sort((a,b)=>a.mos - b.mos);
    if(deficits.length){
      const list = deficits.slice(0,4).map(x => `<strong>${x.m}</strong> (${x.d.disp_total} disp, ${x.d.ventas_avg_mensual}/mes, ${x.mos.toFixed(1)} meses)`).join(', ');
      insights.push({type:'critical', title:'🟥 Modelos en déficit (riesgo de pérdida de venta)',
        html:`Stock por debajo de 1 mes al ritmo de ventas: ${list}. ${deficits.length>4?` +${deficits.length-4} más.`:''}`});
    }
    // 2. Demanda represada (cola sin VIN)
    const represadas = Object.entries(bd.modelos).map(([m,d])=>({m, cola: d.cola_sin_vin, disp: d.disp_total}))
      .filter(x => x.cola > 0).sort((a,b)=>b.cola - a.cola);
    if(represadas.length){
      const list = represadas.slice(0,4).map(x => `<strong>${x.m}</strong> (${x.cola} reservas vs ${x.disp} disp)`).join(', ');
      const totSinVin = represadas.reduce((s,x)=>s+x.cola,0);
      insights.push({type:'warn', title:'⏳ Demanda represada (reservas sin stock asignado)',
        html:`<span class="data">${totSinVin}</span> clientes ya reservaron pero esperan que llegue su unidad: ${list}.`});
    }
    // 3. Sobre-stock — MOS > 4 meses (capital atorado, depreciación)
    const sobre = Object.entries(bd.modelos).map(([m,d])=>{
      const mos = invMOSFromSales(d);
      return {m,d,mos: mos===null && d.disp_total>0 ? Infinity : mos};
    }).filter(x => x.mos !== null && x.mos > 4).sort((a,b)=>b.mos - a.mos);
    if(sobre.length){
      const list = sobre.slice(0,4).map(x => `<strong>${x.m}</strong> (${x.d.disp_total} disp, ${x.mos===Infinity?'sin ventas':x.mos.toFixed(1)+' meses'})`).join(', ');
      insights.push({type:'critical', title:'🟥 Sobre-stock — capital atorado / riesgo de depreciación',
        html:`Inventario por encima de 4 meses de venta: ${list}. Considerar campaña de liquidación, descuento o redistribución entre agencias.`});
    }
    // 4. Aging crítico
    let aOld=0;
    Object.values(bd.modelos).forEach(m => aOld += m.cola_aging['90_plus']||0);
    if(aOld > 0){
      insights.push({type:'warn', title:'⚠️ Reservas viejas (>90 días)',
        html:`<span class="data">${aOld}</span> reservas llevan más de 90 días sin cerrar. Riesgo alto de cancelación — auditar con asesor responsable.`});
    }
    // 5. Pipeline alivia déficit?
    const alivioModelos = deficits.filter(x => (x.d.pipeline_nac + x.d.pipeline_usa) > 0);
    if(alivioModelos.length){
      const list = alivioModelos.map(x=>`<strong>${x.m}</strong> (+${x.d.pipeline_nac+x.d.pipeline_usa} en camino)`).join(', ');
      insights.push({type:'good', title:'🚚 Pipeline en camino para déficits',
        html:`Próximas llegadas alivian: ${list}.`});
    }

    document.getElementById('inv-insights').innerHTML = insights.length===0 ?
      '<p style="color:var(--muted)">Sin insights para esta combinación.</p>' :
      insights.map(ins => `<div class="insight-card ${ins.type}"><h4>${ins.title}</h4><p>${ins.html}</p></div>`).join('');
  }

  function renderInventario(){
    if(!INV){
      document.getElementById('inv-sub').textContent = 'Archivo de inventario no disponible';
      return;
    }
    renderInvHero();
    renderInvCobertura();
    renderInvColaPorAgencia();
    renderInvVersiones();
    renderInvWaitTimes();
    renderInvMatrix();
    renderInvAging();
    renderInvInsights();
  }

  // Hook tab switch
  document.querySelector('.tab-btn[data-tab="inv"]').addEventListener('click', ()=>{
    initInventario();
    renderInventario();
  });

  // ─────────── TAB INVERSIÓN XIY ───────────
  let _xiyRendered = false;
  const xiyFilters = {mes:'', modelo:'', agencia:'', campaign:''};

  function xiyClassifyFunnel(campName){
    const n = (campName || '').toUpperCase();
    if (/AYF |BRANDING|LANZAMIENTO|INCREMENTO SEGUIDORES|RENOVATION|INTERACCI(O|Ó)N/.test(n)) return 'Awareness';
    if (/POSICIONAMIENTO|UTILIDADES|BLINDADOS|OPEN HOUSE|RACE WEEKEND|POWERDAYS|POWER DAYS/.test(n)) return 'Consideración';
    return 'Performance'; // default: LEADS, RENTING y genéricos
  }

  function xiyNormalizeModelo(modelo){
    // Mapea modelos finos Xiy a las claves del panel
    const m = (modelo || '').toUpperCase();
    if (m.includes('RANGER')) return 'RANGER';
    if (m.includes('F-150') || m.includes('F150')) return 'F-150';
    if (m.includes('EVEREST')) return 'EVEREST';
    if (m.includes('TERRITORY')) return 'TERRITORY';
    if (m.includes('ESCAPE')) return 'ESCAPE';
    if (m.includes('EXPLORER')) return 'EXPLORER';
    if (m.includes('EXPEDITION')) return 'EXPEDITION';
    if (m.includes('BRONCO')) return 'BRONCO';
    return null; // No es modelo Ford atribuible
  }

  function xiyFilterLines(){
    const flat = (DATA.xiy_meta && DATA.xiy_meta.source) ? (DATA._xiy_flat_cache || null) : null;
    let lines = DATA.xiy_lines_flat || [];
    if(!lines.length && DATA.xiy_meta && DATA.xiy_meta._lines_flat){
      lines = DATA.xiy_meta._lines_flat;
    }
    // Fallback: leer de data_xiy.json via DATA.xiy_flat si existe
    if(!lines.length){
      // Iterar campaigns como fallback
      lines = (DATA.xiy && DATA.xiy._lines_flat) || [];
    }
    return lines.filter(L => {
      if(xiyFilters.mes      && L.month     !== xiyFilters.mes)      return false;
      if(xiyFilters.agencia  && !xiyMatchAgencia(L, xiyFilters.agencia)) return false;
      if(xiyFilters.campaign && L.campaign  !== xiyFilters.campaign) return false;
      if(xiyFilters.modelo){
        const norm = xiyNormalizeModelo(L.modelo) || 'No atribuido';
        if(norm !== xiyFilters.modelo) return false;
      }
      return true;
    });
  }

  function xiyMatchAgencia(line, ag){
    // Replica la lógica del extractor: si audience tiene la agencia
    const a = (line.audience || '').toUpperCase();
    if(ag === 'Tumbaco')    return /TUMBACO/.test(a) || (/SIERRA/.test(a) && !/LA Y/.test(a));
    if(ag === 'La Y')       return /LA Y/.test(a) || /SIERRA/.test(a);
    if(ag === 'CJA')        return /CJA|CUENCA/.test(a);
    if(ag === 'Orellana')   return /ORELLANA/.test(a);
    if(ag === 'Manta')      return /MANTA/.test(a) || /MANABI|MANAB(Í|I)/.test(a) || /COSTA/.test(a);
    if(ag === 'Machala')    return /MACHALA/.test(a) || /COSTA/.test(a);
    if(ag === 'Portoviejo') return /PORTOVIEJO/.test(a) || /MANABI|MANAB(Í|I)/.test(a) || /COSTA/.test(a);
    return true;
  }

  function xiyAggregate(lines){
    // Re-construye totals_modelo, months, totals_agencia, totals_medio,
    // objective_totals, modelo_objective desde una lista filtrada de líneas.
    const out = {
      total_general: 0,
      total_atribuible_modelo: 0,
      total_non_modelo: 0,
      total_multi_nacional: 0,
      months: {},
      totals_mes: {},
      totals_mes_non_modelo: {},
      totals_modelo: {},
      non_modelo: {},
      totals_agencia: {},
      totals_medio: {},
      medio_objective: {},
      objective_totals: {},
      modelo_objective: {},
      months_order: [],
      panel_models: ['RANGER','F-150','EVEREST','TERRITORY','ESCAPE','EXPLORER','EXPEDITION','BRONCO'],
      panel_agencias: ['Tumbaco','La Y','CJA','Orellana','Manta','Machala','Portoviejo'],
    };
    const monthsSeen = new Set();
    lines.forEach(L => {
      const mes = L.month;
      const amt = +L.amount || 0;
      const conv = +L.conversiones_esperadas || 0;
      const camp = L.campaign || '';
      const objCat = xiyClassifyFunnel(camp);
      const modCanonical = xiyNormalizeModelo(L.modelo);
      monthsSeen.add(mes);

      out.total_general += amt;
      out.totals_mes[mes] = (out.totals_mes[mes]||0) + amt;

      // objective totals
      out.objective_totals[objCat] = out.objective_totals[objCat] || {amount:0, n_lines:0};
      out.objective_totals[objCat].amount += amt;
      out.objective_totals[objCat].n_lines += 1;

      if(modCanonical){
        out.total_atribuible_modelo += amt;
        out.months[mes] = out.months[mes] || {};
        out.months[mes][modCanonical] = out.months[mes][modCanonical] || {amount:0, convers:0, n_lines:0};
        out.months[mes][modCanonical].amount += amt;
        out.months[mes][modCanonical].convers += conv;
        out.months[mes][modCanonical].n_lines += 1;
        out.totals_modelo[modCanonical] = out.totals_modelo[modCanonical] || {amount:0, convers:0, n_lines:0};
        out.totals_modelo[modCanonical].amount += amt;
        out.totals_modelo[modCanonical].convers += conv;
        out.totals_modelo[modCanonical].n_lines += 1;
        out.modelo_objective[modCanonical] = out.modelo_objective[modCanonical] || {};
        out.modelo_objective[modCanonical][objCat] = (out.modelo_objective[modCanonical][objCat]||0) + amt;
      } else {
        out.total_non_modelo += amt;
        const label = L.modelo || 'Sin modelo';
        out.non_modelo[label] = out.non_modelo[label] || {amount:0, convers:0, n_lines:0};
        out.non_modelo[label].amount += amt;
        out.non_modelo[label].convers += conv;
        out.non_modelo[label].n_lines += 1;
        out.totals_mes_non_modelo[mes] = (out.totals_mes_non_modelo[mes]||0) + amt;
      }

      // Agencia (replicar map_audience_to_agencias)
      const ags = xiyAudienceToAgencias(L.audience);
      if(ags && ags.length){
        const share = amt / ags.length;
        ags.forEach(ag => {
          out.totals_agencia[ag] = out.totals_agencia[ag] || {amount:0, n_lines:0};
          out.totals_agencia[ag].amount += share;
          out.totals_agencia[ag].n_lines += 1;
        });
      } else {
        out.total_multi_nacional += amt;
      }

      // Medio
      let medio = (L.media || 'Sin medio').trim();
      const mu = medio.toUpperCase();
      if(['TIK TOK','TIKTOK','TIK-TOK'].includes(mu)) medio = 'TikTok';
      else if(mu === 'META') medio = 'Meta';
      else if(mu === 'GOOGLE') medio = 'Google';
      out.totals_medio[medio] = out.totals_medio[medio] || {amount:0, n_lines:0};
      out.totals_medio[medio].amount += amt;
      out.totals_medio[medio].n_lines += 1;
      out.medio_objective[medio] = out.medio_objective[medio] || {};
      out.medio_objective[medio][objCat] = (out.medio_objective[medio][objCat]||0) + amt;
    });
    const ORDER = ['Enero','Febrero','Marzo','Abril','Mayo'];
    out.months_order = ORDER.filter(m => monthsSeen.has(m));
    return out;
  }

  // Recalcula tráfico/ventas marketing por modelo/agencia desde clientes_flat
  // aplicando los filtros activos. Si no hay filtros, devuelve los breakdowns
  // pre-calculados (por_modelo_mkt / por_agencia_mkt).
  const XIY_MKT_CHANNELS = new Set(['Showroom','Hubspot','Ferias y Eventos',
    'Feria/Eventos','Ferias','Llamada In','Mailing']);

  function xiyTrafficBreakdowns(){
    const FORD = (DATA.conversion_data && DATA.conversion_data.FORD) || {};
    const noFilters = !xiyFilters.modelo && !xiyFilters.agencia;
    if(noFilters){
      return {
        por_modelo:  FORD.por_modelo_mkt  || FORD.por_modelo  || {},
        por_agencia: FORD.por_agencia_mkt || FORD.por_agencia || {},
      };
    }
    // Recalcular desde clientes_flat aplicando filtros
    const flat = FORD.clientes_flat || [];
    const por_modelo = {};
    const por_agencia = {};
    flat.forEach(c => {
      if(!XIY_MKT_CHANNELS.has(c.canal)) return;
      // Aplicar filtros de modelo / agencia
      if(xiyFilters.modelo && (c.modelo||'').toUpperCase() !== xiyFilters.modelo) return;
      if(xiyFilters.agencia && c.agencia !== xiyFilters.agencia) return;
      const mod = (c.modelo||'Sin modelo').toUpperCase();
      const ag  = c.agencia || 'Sin agencia';
      por_modelo[mod]  = por_modelo[mod]  || {traffic:0, matched:0};
      por_agencia[ag]  = por_agencia[ag]  || {traffic:0, matched:0};
      por_modelo[mod].traffic++;
      por_agencia[ag].traffic++;
      if(c.cerro){
        por_modelo[mod].matched++;
        por_agencia[ag].matched++;
      }
    });
    // calcular conv_pct
    for(const k in por_modelo){
      const d = por_modelo[k];
      d.conv_pct = d.traffic>0 ? +(100*d.matched/d.traffic).toFixed(1) : 0;
    }
    for(const k in por_agencia){
      const d = por_agencia[k];
      d.conv_pct = d.traffic>0 ? +(100*d.matched/d.traffic).toFixed(1) : 0;
    }
    return { por_modelo, por_agencia };
  }

  function xiyAudienceToAgencias(audience){
    if(!audience) return null;
    const a = audience.toUpperCase();
    const direct = [];
    if (/TUMBACO/.test(a))   direct.push('Tumbaco');
    if (/LA Y/.test(a))      direct.push('La Y');
    if (/CJA|CUENCA/.test(a))direct.push('CJA');
    if (/ORELLANA/.test(a))  direct.push('Orellana');
    if (/MANTA/.test(a))     direct.push('Manta');
    if (/MACHALA/.test(a))   direct.push('Machala');
    if (/PORTOVIEJO/.test(a))direct.push('Portoviejo');
    if(direct.length) return direct;
    if (/SIERRA/.test(a))    return ['Tumbaco','La Y'];
    if (/MANABI|MANAB[ÍI]/.test(a)) return ['Manta','Portoviejo'];
    if (/COSTA/.test(a))     return ['Machala','Manta','Portoviejo'];
    return null;
  }

  // ─────────── GRÁFICO EVOLUCIÓN MENSUAL CPV/CAC/CONV ───────────
  let _xiyEvoChart = null;
  // Estado: modelos seleccionados (vacío array = "Todos" agregado)
  const xiyEvoState = { selectedModels: ['__ALL__'] };

  function xiyComputeMonthlyMetrics(modelosSelected){
    // Devuelve {meses, cpv, cac, conv, inv, traf, vent} con respeto a filtros
    // generales del tab (mes/agencia/campaña) y los modelos seleccionados aquí.
    const MONTHS = ['Enero','Febrero','Marzo','Abril','Mayo'];
    const YM_MAP = {'Enero':'2026-01','Febrero':'2026-02','Marzo':'2026-03','Abril':'2026-04','Mayo':'2026-05'};
    const YM_REV = Object.fromEntries(Object.entries(YM_MAP).map(([k,v])=>[v,k]));
    const wantAll = modelosSelected.includes('__ALL__') || modelosSelected.length === 0;

    // 1) Inversión por mes - desde lines_flat filtrado
    const flatLines = (DATA.xiy && DATA.xiy._lines_flat) || [];
    const invByMonth = Object.fromEntries(MONTHS.map(m => [m, 0]));
    flatLines.forEach(L => {
      // Aplicar filtros generales del tab
      if(xiyFilters.mes      && L.month     !== xiyFilters.mes)      return;
      if(xiyFilters.campaign && L.campaign  !== xiyFilters.campaign) return;
      if(xiyFilters.agencia){
        const ags = xiyAudienceToAgencias(L.audience);
        if(!ags || !ags.includes(xiyFilters.agencia)) return;
      }
      // Filtro de modelo (chips locales + filtro general)
      const norm = xiyNormalizeModelo(L.modelo);
      // Si filtro general activo y este modelo no coincide → fuera
      if(xiyFilters.modelo && norm !== xiyFilters.modelo) return;
      // Si selección de chips local NO incluye este modelo → fuera
      if(!wantAll && !modelosSelected.includes(norm || '__NONE__')) return;
      // Si modelo es null y no se quiere "Sin atribuir", también va
      // (lo dejamos pasar si wantAll para no perder inversión multi-modelo)
      if(!norm && !wantAll) return;
      invByMonth[L.month] = (invByMonth[L.month] || 0) + (+L.amount || 0);
    });

    // 2) Tráfico y ventas por mes desde clientes_flat
    const flat = (DATA.conversion_data && DATA.conversion_data.FORD && DATA.conversion_data.FORD.clientes_flat) || [];
    const trafByMonth = Object.fromEntries(MONTHS.map(m => [m, 0]));
    const ventByMonth = Object.fromEntries(MONTHS.map(m => [m, 0]));
    flat.forEach(c => {
      if(!XIY_MKT_CHANNELS.has(c.canal)) return;
      // Filtro modelo
      const modUpper = (c.modelo||'').toUpperCase();
      if(xiyFilters.modelo && modUpper !== xiyFilters.modelo) return;
      if(!wantAll && !modelosSelected.includes(modUpper || '__NONE__')) return;
      // Filtro agencia
      if(xiyFilters.agencia && c.agencia !== xiyFilters.agencia) return;
      // Filtro mes (filtra el mes del first toque)
      const mesName = YM_REV[c.first_ym];
      if(!mesName) return;
      if(xiyFilters.mes && mesName !== xiyFilters.mes) return;
      trafByMonth[mesName]++;
      if(c.cerro) ventByMonth[mesName]++;
    });

    // 3) Calcular CPV, CAC, Conv por mes; solo meses con datos
    const result = { meses: [], cpv: [], cac: [], conv: [], inv: [], traf: [], vent: [] };
    MONTHS.forEach(m => {
      const inv = invByMonth[m] || 0;
      const traf = trafByMonth[m] || 0;
      const vent = ventByMonth[m] || 0;
      if(inv === 0 && traf === 0 && vent === 0) return;
      result.meses.push(m);
      result.cpv.push(traf>0 ? +(inv/traf).toFixed(2) : null);
      result.cac.push(vent>0 ? +(inv/vent).toFixed(2) : null);
      result.conv.push(traf>0 ? +(100*vent/traf).toFixed(1) : null);
      result.inv.push(inv);
      result.traf.push(traf);
      result.vent.push(vent);
    });
    return result;
  }

  function renderXiyEvolutionChips(){
    const PANEL_MODELS = ['RANGER','F-150','EVEREST','TERRITORY','ESCAPE','EXPLORER'];
    const chipsEl = document.getElementById('xiy-evo-chips');
    if(!chipsEl) return;
    const isAll = xiyEvoState.selectedModels.includes('__ALL__') || xiyEvoState.selectedModels.length === 0;
    const items = [
      {key:'__ALL__', label:'Todos (agregado)', color:'#003478'},
      ...PANEL_MODELS.map(m => ({key:m, label:m, color:MODEL_COLOR(m)})),
    ];
    chipsEl.innerHTML = items.map(it => {
      const active = it.key === '__ALL__' ? isAll : xiyEvoState.selectedModels.includes(it.key);
      const bg = active ? it.color : '#fff';
      const fg = active ? '#fff' : it.color;
      const border = it.color;
      return `<button type="button" class="xiy-evo-chip" data-key="${it.key}"
        style="padding:6px 14px;border-radius:18px;border:1.5px solid ${border};background:${bg};color:${fg};font-weight:600;cursor:pointer;font-size:12.5px;transition:all .15s">
        ${it.label}
      </button>`;
    }).join('');
    chipsEl.querySelectorAll('button').forEach(btn => {
      btn.addEventListener('click', () => {
        const k = btn.dataset.key;
        if(k === '__ALL__'){
          xiyEvoState.selectedModels = ['__ALL__'];
        } else {
          // Quitar __ALL__ y togglear el modelo
          xiyEvoState.selectedModels = xiyEvoState.selectedModels.filter(x => x !== '__ALL__');
          if(xiyEvoState.selectedModels.includes(k)){
            xiyEvoState.selectedModels = xiyEvoState.selectedModels.filter(x => x !== k);
          } else {
            xiyEvoState.selectedModels.push(k);
          }
          if(xiyEvoState.selectedModels.length === 0) xiyEvoState.selectedModels = ['__ALL__'];
        }
        renderXiyEvolutionChips();
        renderXiyEvolution();
      });
    });
  }

  // Paleta de colores por modelo (consistente con otros tabs)
  function MODEL_COLOR(modelo){
    const COLORS = {
      'RANGER':'#e11d48',     // rojo
      'F-150':'#0369a1',      // azul
      'EVEREST':'#16a34a',    // verde
      'TERRITORY':'#a16207',  // dorado
      'ESCAPE':'#7c3aed',     // morado
      'EXPLORER':'#0891b2',   // turquesa
      'EXPEDITION':'#be185d', // magenta
      'BRONCO':'#475569',     // gris
    };
    return COLORS[modelo] || '#64748b';
  }

  function renderXiyEvolution(){
    const canvas = document.getElementById('xiy-evo-chart');
    if(!canvas || !window.Chart) return;
    // Asegurar chips renderizados
    renderXiyEvolutionChips();
    // Toggles
    const showTraf = document.getElementById('xiy-evo-show-traf')?.checked !== false;
    const showVent = document.getElementById('xiy-evo-show-vent')?.checked !== false;
    const showCac  = document.getElementById('xiy-evo-show-cac')?.checked === true;
    const showConv = document.getElementById('xiy-evo-show-conv')?.checked !== false;

    const data = xiyComputeMonthlyMetrics(xiyEvoState.selectedModels);
    const fUSD2_local = (n) => 'USD ' + (n||0).toLocaleString('es-EC',{minimumFractionDigits:2,maximumFractionDigits:2});

    const datasets = [];
    if(showTraf) datasets.push({
      label:'Tráfico (visitas mkt)', data:data.traf, borderColor:'#0369a1', backgroundColor:'#0369a133',
      tension:0.3, yAxisID:'yCount', borderWidth:2.5, pointRadius:4, pointBackgroundColor:'#0369a1',
      spanGaps:true,
      datalabels:{ align:'top', anchor:'end', color:'#0369a1', font:{weight:'700',size:11},
        formatter:(v)=> v==null?'':v.toLocaleString('es-EC') }
    });
    if(showVent) datasets.push({
      label:'Ventas atribuidas', data:data.vent, borderColor:'#f59e0b', backgroundColor:'#f59e0b33',
      tension:0.3, yAxisID:'yCount', borderWidth:2.5, pointRadius:4, pointBackgroundColor:'#f59e0b',
      spanGaps:true,
      datalabels:{ align:'bottom', anchor:'start', color:'#f59e0b', font:{weight:'700',size:11},
        formatter:(v)=> v==null?'':v.toLocaleString('es-EC') }
    });
    if(showCac) datasets.push({
      label:'CAC (USD)', data:data.cac, borderColor:'#be185d', backgroundColor:'#be185d33',
      tension:0.3, yAxisID:'yUSD', borderWidth:2.5, pointRadius:4, pointBackgroundColor:'#be185d', borderDash:[6,3],
      spanGaps:true,
      datalabels:{ align:'bottom', anchor:'start', color:'#be185d', font:{weight:'600',size:10},
        formatter:(v)=> v==null?'':'$'+v.toFixed(0) }
    });
    if(showConv) datasets.push({
      label:'Conversión (%)', data:data.conv, borderColor:'#16a34a', backgroundColor:'#16a34a33',
      tension:0.3, yAxisID:'yPct', borderWidth:2.5, pointRadius:5, pointBackgroundColor:'#16a34a',
      spanGaps:true,
      datalabels:{ align:'top', anchor:'end', color:'#16a34a', font:{weight:'700',size:11},
        formatter:(v)=> v==null?'':v.toFixed(1)+'%' }
    });

    if(_xiyEvoChart){ _xiyEvoChart.destroy(); _xiyEvoChart = null; }
    _xiyEvoChart = new Chart(canvas, {
      type:'line',
      data:{ labels:data.meses, datasets },
      options:{
        responsive:true, maintainAspectRatio:false,
        interaction:{ mode:'index', intersect:false },
        plugins:{
          legend:{ position:'top', labels:{ usePointStyle:true, padding:14 } },
          tooltip:{
            callbacks:{
              afterBody:(ctxs)=>{
                const i = ctxs[0]?.dataIndex;
                if(i==null) return [];
                return [
                  `Inversión: ${fUSD2_local(data.inv[i])}`,
                  `Tráfico mkt: ${data.traf[i]}`,
                  `Ventas atrib.: ${data.vent[i]}`,
                ];
              }
            }
          },
          datalabels:{ display:true },
        },
        scales:{
          yCount:{ position:'left', title:{ display:true, text:'Cantidad (visitas / ventas)' },
                   beginAtZero:true, ticks:{ precision:0, callback:(v)=> v.toLocaleString('es-EC') } },
          yUSD:{ position:'right', title:{ display:showCac, text:'CAC (USD)' },
                 beginAtZero:true, display:showCac,
                 grid:{ drawOnChartArea:false }, ticks:{ callback:(v)=> '$'+v.toLocaleString('es-EC') } },
          yPct:{ position:'right', title:{ display:true, text:'Conversión (%)' }, beginAtZero:true,
                 grid:{ drawOnChartArea:false }, ticks:{ callback:(v)=> v+'%' },
                 offset:showCac }, // si CAC visible, ofrecer offset para no encimar ejes
          x:{ title:{ display:false } }
        }
      }
    });

    // Summary text
    const sumEl = document.getElementById('xiy-evo-summary');
    if(sumEl && data.meses.length){
      const lastIdx = data.meses.length - 1;
      const labels = xiyEvoState.selectedModels.includes('__ALL__')
        ? 'Todos los modelos'
        : xiyEvoState.selectedModels.join(' + ');
      sumEl.textContent = `${labels} · ${data.meses[0]}–${data.meses[lastIdx]} · ${data.traf.reduce((a,b)=>a+b,0)} visitas mkt · ${data.vent.reduce((a,b)=>a+b,0)} ventas atrib. · ${fUSD2_local(data.inv.reduce((a,b)=>a+b,0))} invertidos`;
    }
  }

  function xiyInitFilters(){
    // Listeners para los toggles de métricas del gráfico de evolución
    ['xiy-evo-show-traf','xiy-evo-show-vent','xiy-evo-show-cac','xiy-evo-show-conv'].forEach(id => {
      const el = document.getElementById(id);
      if(el && !el.dataset.bound){
        el.addEventListener('change', renderXiyEvolution);
        el.dataset.bound = '1';
      }
    });

    // Necesito tener lines_flat disponible. Lo cargamos desde DATA.xiy._lines_flat
    // (lo agrego en aggregate.py). Si no está, los filtros quedan inactivos.
    if(!DATA.xiy || !DATA.xiy._lines_flat){
      const fc = document.getElementById('xiy-f-clear');
      if(fc) fc.parentElement.style.display = 'none';
      return;
    }
    const lines = DATA.xiy._lines_flat;
    DATA.xiy_lines_flat = lines;
    // Opciones únicas
    const meses = [...new Set(lines.map(l => l.month))];
    const ORDER = ['Enero','Febrero','Marzo','Abril','Mayo'];
    meses.sort((a,b)=> ORDER.indexOf(a) - ORDER.indexOf(b));
    const modelos = [...new Set(lines.map(l => xiyNormalizeModelo(l.modelo)).filter(Boolean))].sort();
    const agencias = ['Tumbaco','La Y','CJA','Orellana','Manta','Machala','Portoviejo'];
    const campaigns = [...new Set(lines.map(l => l.campaign))].sort();

    const fillSelect = (id, options, label) => {
      const el = document.getElementById(id);
      if(!el) return;
      el.innerHTML = `<option value="">Todos los ${label}</option>` +
        options.map(o => `<option value="${o}">${o}</option>`).join('');
      el.addEventListener('change', e => {
        const key = id.replace('xiy-f-','');
        xiyFilters[key] = e.target.value;
        renderXiy();
      });
    };
    fillSelect('xiy-f-mes', meses, 'meses');
    fillSelect('xiy-f-modelo', modelos, 'modelos');
    fillSelect('xiy-f-agencia', agencias, 'agencias');

    const clear = document.getElementById('xiy-f-clear');
    if(clear){
      clear.addEventListener('click', () => {
        Object.keys(xiyFilters).forEach(k => xiyFilters[k] = '');
        ['xiy-f-mes','xiy-f-modelo','xiy-f-agencia'].forEach(id => {
          const e = document.getElementById(id); if(e) e.value = '';
        });
        renderXiy();
      });
    }
  }
  let _xiyFiltersInit = false;

  function renderXiy(){
    if(!_xiyFiltersInit){ xiyInitFilters(); _xiyFiltersInit = true; }
    // Si tenemos lines_flat, agregamos dinámicamente con filtros aplicados;
    // si no, usamos los agregados pre-calculados de DATA.xiy
    let XIY;
    if(DATA.xiy && DATA.xiy._lines_flat){
      const filtered = (DATA.xiy._lines_flat).filter(L => {
        if(xiyFilters.mes      && L.month     !== xiyFilters.mes)      return false;
        if(xiyFilters.campaign && L.campaign  !== xiyFilters.campaign) return false;
        if(xiyFilters.modelo){
          const norm = xiyNormalizeModelo(L.modelo);
          if(norm !== xiyFilters.modelo) return false;
        }
        if(xiyFilters.agencia){
          const ags = xiyAudienceToAgencias(L.audience);
          if(!ags || !ags.includes(xiyFilters.agencia)) return false;
        }
        return true;
      });
      XIY = xiyAggregate(filtered);
      // Summary
      const sumEl = document.getElementById('xiy-f-summary');
      if(sumEl){
        const active = Object.entries(xiyFilters).filter(([_,v])=>v).map(([k,v])=>`${k}=${v}`).join(' · ');
        const fUSD = (n) => 'USD ' + (n||0).toLocaleString('es-EC',{maximumFractionDigits:0});
        sumEl.textContent = active
          ? `Filtros: ${active}  →  ${filtered.length} líneas · ${fUSD(XIY.total_general)}`
          : `Sin filtros · ${filtered.length} líneas · ${fUSD(XIY.total_general)}`;
      }
    } else {
      XIY = DATA.xiy || {};
    }
    const tblMmTbody  = document.querySelector('#xiy-tbl-modelo-mes tbody');
    const tblMmHead   = document.getElementById('xiy-tbl-modelo-mes-head');
    const tblMmFoot   = document.querySelector('#xiy-tbl-modelo-mes tfoot');
    const tblRoasTb   = document.querySelector('#xiy-tbl-roas tbody');
    const tblRoasFt   = document.querySelector('#xiy-tbl-roas tfoot');
    const tblNonTb    = document.querySelector('#xiy-tbl-nonmodelo tbody');
    const tblNonFt    = document.querySelector('#xiy-tbl-nonmodelo tfoot');

    if(!XIY){
      document.getElementById('xiy-k-total').textContent = '—';
      document.getElementById('xiy-k-top').textContent = '—';
      document.getElementById('xiy-k-cpv').textContent = '—';
      document.getElementById('xiy-k-cac').textContent = '—';
      tblMmTbody.innerHTML = '<tr><td colspan="99" style="text-align:center;color:var(--muted);padding:20px">No hay datos de Xiy en data.json. Corre <code>python3 xiy_extractor.py && python3 aggregate.py</code>.</td></tr>';
      return;
    }

    const fUSD = (n) => 'USD ' + (n||0).toLocaleString('es-EC',{minimumFractionDigits:0,maximumFractionDigits:0});
    const fUSD2 = (n) => 'USD ' + (n||0).toLocaleString('es-EC',{minimumFractionDigits:2,maximumFractionDigits:2});
    const fInt = (n) => (n||0).toLocaleString('es-EC');
    const fPct = (n) => (n==null||!isFinite(n)) ? '—' : (n.toFixed(1)+'%');

    // HERO 1: Inversión total
    const total = XIY.total_general || 0;
    document.getElementById('xiy-k-total').textContent = fUSD(total);
    const monthsOrder = XIY.months_order || [];
    const periodoLbl = monthsOrder.length ? `${monthsOrder[0]}-${monthsOrder[monthsOrder.length-1]} 2026` : '2026';
    document.getElementById('xiy-k-total-hint').textContent = `USD con IVA · ${periodoLbl}`;
    document.getElementById('xiy-k-total-lbl').textContent = `Inversión total (${periodoLbl})`;

    // HERO 2: Modelo top
    const totalsModelo = XIY.totals_modelo || {};
    const modeloEntries = Object.entries(totalsModelo).sort((a,b)=> b[1].amount - a[1].amount);
    if(modeloEntries.length){
      const [topMod, topD] = modeloEntries[0];
      const pctTop = total>0 ? (100*topD.amount/total) : 0;
      document.getElementById('xiy-k-top').textContent = topMod;
      document.getElementById('xiy-k-top-hint').textContent = `${fUSD(topD.amount)} · ${pctTop.toFixed(1)}% del total`;
    } else {
      document.getElementById('xiy-k-top').textContent = '—';
    }

    // HERO 3 y 4: CPV y CAC (calculados desde tráfico/ventas filtrado a marketing)
    const _heroTraf = xiyTrafficBreakdowns();
    let heroTraffic = 0, heroMatched = 0;
    for(const k in _heroTraf.por_modelo){
      heroTraffic += _heroTraf.por_modelo[k].traffic || 0;
      heroMatched += _heroTraf.por_modelo[k].matched || 0;
    }
    const cpvGlobal = heroTraffic>0 ? (total/heroTraffic) : null;
    const cacGlobal = heroMatched>0 ? (total/heroMatched) : null;
    document.getElementById('xiy-k-cpv').textContent = cpvGlobal!=null ? fUSD2(cpvGlobal) : '—';
    document.getElementById('xiy-k-cpv-hint').textContent =
      `${fUSD(total)} ÷ ${heroTraffic.toLocaleString('es-EC')} visitas mkt`;
    document.getElementById('xiy-k-cac').textContent = cacGlobal!=null ? fUSD2(cacGlobal) : '—';
    document.getElementById('xiy-k-cac-hint').textContent =
      `${fUSD(total)} ÷ ${heroMatched.toLocaleString('es-EC')} ventas atribuidas`;

    // ─── TABLA 1: matriz modelo × mes ───
    // Construir cabecera dinámicamente
    const PANEL_MODELS = ['RANGER','F-150','EVEREST','TERRITORY','ESCAPE','EXPLORER','EXPEDITION','BRONCO'];
    // Solo mostrar filas que tienen al menos algo de inversión
    const modelosActivos = PANEL_MODELS.filter(m => (totalsModelo[m]?.amount || 0) > 0);

    // Reset cabecera y construirla
    tblMmHead.innerHTML = '<th>Modelo</th>' +
      monthsOrder.map(m => `<th class="num">${m}</th>`).join('') +
      '<th class="num">Total</th>';

    // Filas
    let trsMm = '';
    const totalPorMes = {};
    monthsOrder.forEach(m => totalPorMes[m] = 0);
    let totalAtrib = 0;
    modelosActivos.forEach(mod => {
      let totalRow = 0;
      const cells = monthsOrder.map(mes => {
        const v = (XIY.months[mes] && XIY.months[mes][mod]) ? XIY.months[mes][mod].amount : 0;
        totalRow += v; totalPorMes[mes] += v;
        return `<td class="num">${v>0 ? fUSD(v) : '<span style="color:#bbb">—</span>'}</td>`;
      }).join('');
      totalAtrib += totalRow;
      trsMm += `<tr><td><strong>${mod}</strong></td>${cells}<td class="num"><strong>${fUSD(totalRow)}</strong></td></tr>`;
    });
    tblMmTbody.innerHTML = trsMm || '<tr><td colspan="99" style="text-align:center;color:var(--muted);padding:14px">Sin inversión atribuible a modelos.</td></tr>';

    // Footer: total atribuible + distribución por funnel
    const objTot = XIY.objective_totals || {};
    const perfA = objTot['Performance']?.amount || 0;
    const awareA = objTot['Awareness']?.amount || 0;
    const consA  = (objTot['Consideración']?.amount || 0) + (objTot['Activación']?.amount || 0) + (objTot['Otros']?.amount || 0);
    const totFun = perfA + awareA + consA;
    const pPerf = totFun>0 ? (100*perfA/totFun) : 0;
    const pAware = totFun>0 ? (100*awareA/totFun) : 0;
    const pCons = totFun>0 ? (100*consA/totFun) : 0;
    const ncols = monthsOrder.length + 2; // Modelo + meses + Total
    tblMmFoot.innerHTML =
      '<tr style="background:#f3f4f6;font-weight:700">' +
        '<td>TOTAL atribuible</td>' +
        monthsOrder.map(m => `<td class="num">${fUSD(totalPorMes[m])}</td>`).join('') +
        `<td class="num">${fUSD(totalAtrib)}</td>` +
      '</tr>' +
      `<tr style="background:#fafbfc;font-size:12px;color:var(--muted)">` +
        `<td colspan="${ncols}" style="padding:8px 10px">` +
          `<strong>Distribución por etapa del funnel:</strong> ` +
          `<span style="margin-left:14px;color:#0369a1">🎯 Performance ${pPerf.toFixed(1)}% (${fUSD(perfA)})</span> · ` +
          `<span style="margin-left:8px;color:#a16207">📢 Awareness ${pAware.toFixed(1)}% (${fUSD(awareA)})</span> · ` +
          `<span style="margin-left:8px;color:#6d28d9">🤔 Consideración ${pCons.toFixed(1)}% (${fUSD(consA)})</span>` +
        '</td>' +
      '</tr>';

    // ─── TABLA 2: cruce ROAS con tráfico y ventas ───
    // Tráfico filtrado a canales marketing + filtros del tab aplicados
    const _trafBreak = xiyTrafficBreakdowns();
    const porModeloPanel = _trafBreak.por_modelo;
    let trsRoas = '';
    let sumInv=0, sumTraf=0, sumVent=0;
    modelosActivos.forEach(mod => {
      const inv = totalsModelo[mod]?.amount || 0;
      const pm = porModeloPanel[mod] || {};
      const traf = pm.traffic || 0;
      const vent = pm.matched || 0;
      const convPct = pm.conv_pct;
      const cpl = traf>0 ? (inv/traf) : null;
      const cac = vent>0 ? (inv/vent) : null;
      sumInv += inv; sumTraf += traf; sumVent += vent;
      trsRoas += `<tr>
        <td><strong>${mod}</strong></td>
        <td class="num">${fUSD(inv)}</td>
        <td class="num">${fInt(traf)}</td>
        <td class="num">${fInt(vent)}</td>
        <td class="num">${convPct!=null ? convPct.toFixed(1)+'%' : '—'}</td>
        <td class="num">${cpl!=null ? fUSD2(cpl) : '<span style="color:#bbb">sin tráfico</span>'}</td>
        <td class="num">${cac!=null ? fUSD2(cac) : '<span style="color:#bbb">sin ventas</span>'}</td>
      </tr>`;
    });
    tblRoasTb.innerHTML = trsRoas || '<tr><td colspan="7" style="text-align:center;color:var(--muted);padding:14px">Sin datos para cruzar.</td></tr>';

    const cplTot = sumTraf>0 ? (sumInv/sumTraf) : null;
    const cacTot = sumVent>0 ? (sumInv/sumVent) : null;
    const convTot = sumTraf>0 ? (100*sumVent/sumTraf) : null;
    tblRoasFt.innerHTML = `<tr style="background:#f3f4f6;font-weight:700">
      <td>TOTAL</td>
      <td class="num">${fUSD(sumInv)}</td>
      <td class="num">${fInt(sumTraf)}</td>
      <td class="num">${fInt(sumVent)}</td>
      <td class="num">${convTot!=null ? convTot.toFixed(1)+'%' : '—'}</td>
      <td class="num">${cplTot!=null ? fUSD2(cplTot) : '—'}</td>
      <td class="num">${cacTot!=null ? fUSD2(cacTot) : '—'}</td>
    </tr>`;

    // ─── GRÁFICO: Evolución mensual CPV / CAC / Conversión ───
    renderXiyEvolution();

    // ─── TABLA 2B: Performance vs Awareness por modelo ───
    const objTotals = XIY.objective_totals || {};
    const modeloObj = XIY.modelo_objective || {};
    const OBJ_ORDER = ['Performance','Awareness','Consideración'];

    // (Cards removidas; los % por funnel se muestran ahora en el footer de
    // la tabla matriz modelo × mes.)

    // Tabla por modelo
    const tblPaTb = document.querySelector('#xiy-tbl-perfaware-modelo tbody');
    const tblPaFt = document.querySelector('#xiy-tbl-perfaware-modelo tfoot');
    let trsPa = '';
    const totsPa = {Performance:0, Awareness:0, 'Consideración':0};
    // incluir modelos + Multi/no-modelo
    const todasFilas = [...modelosActivos];
    // agregar la fila "Sin atribuir a modelo" si existe
    const moNonModelo = {};
    OBJ_ORDER.forEach(o => moNonModelo[o] = 0);
    Object.entries(XIY.non_modelo || {}).forEach(([label, d]) => {
      // non_modelo no tiene objective_breakdown, así que agrupamos en awareness por default
      // mejor mostrar todo Awareness/Marca de campañas no-modelo
      moNonModelo['Awareness'] = (moNonModelo['Awareness']||0) + (d.amount||0);
    });

    todasFilas.forEach(mod => {
      const breakdown = modeloObj[mod] || {};
      const row = OBJ_ORDER.map(o => breakdown[o] || 0);
      const tot = row.reduce((a,b)=>a+b, 0);
      OBJ_ORDER.forEach((o,i) => totsPa[o] += row[i]);
      const pctPerf = tot>0 ? (100*row[0]/tot) : 0;
      trsPa += `<tr>
        <td><strong>${mod}</strong></td>
        ${row.map(v => `<td class="num">${v>0 ? fUSD(v) : '<span style="color:#bbb">—</span>'}</td>`).join('')}
        <td class="num"><strong>${fUSD(tot)}</strong></td>
        <td class="num">${pctPerf.toFixed(0)}%</td>
      </tr>`;
    });

    tblPaTb.innerHTML = trsPa || '<tr><td colspan="7" style="text-align:center;color:var(--muted);padding:14px">Sin datos.</td></tr>';
    const totPa = OBJ_ORDER.reduce((s,o)=>s+totsPa[o], 0);
    const pctPerfTot = totPa>0 ? (100*totsPa['Performance']/totPa) : 0;
    tblPaFt.innerHTML = `<tr style="background:#f3f4f6;font-weight:700">
      <td>TOTAL atribuible a modelo</td>
      ${OBJ_ORDER.map(o => `<td class="num">${fUSD(totsPa[o])}</td>`).join('')}
      <td class="num">${fUSD(totPa)}</td>
      <td class="num">${pctPerfTot.toFixed(0)}%</td>
    </tr>`;

    // ─── TABLA 3: por Agencia (con cruce de tráfico/ventas) ───
    const tblAgTb = document.querySelector('#xiy-tbl-agencia tbody');
    const tblAgFt = document.querySelector('#xiy-tbl-agencia tfoot');
    const totalsAgencia = XIY.totals_agencia || {};
    // Tráfico filtrado a canales marketing + filtros del tab aplicados
    const porAgenciaPanel = _trafBreak.por_agencia;
    const PANEL_AGS = XIY.panel_agencias || ['Tumbaco','La Y','CJA','Orellana','Manta','Machala','Portoviejo'];
    const agentriesOrdered = PANEL_AGS
      .map(ag => [ag, totalsAgencia[ag] || {amount:0, n_lines:0}])
      .filter(([ag, d]) => d.amount > 0)
      .sort((a,b) => b[1].amount - a[1].amount);
    let trsAg = '';
    let sumInvAg=0, sumTrafAg=0, sumVentAg=0;
    agentriesOrdered.forEach(([ag, d]) => {
      const inv = d.amount;
      const pa = porAgenciaPanel[ag] || {};
      const traf = pa.traffic || 0;
      const vent = pa.matched || 0;
      const cpl = traf>0 ? (inv/traf) : null;
      const cac = vent>0 ? (inv/vent) : null;
      const pct = total>0 ? (100*inv/total) : 0;
      sumInvAg += inv; sumTrafAg += traf; sumVentAg += vent;
      trsAg += `<tr>
        <td><strong>${ag}</strong></td>
        <td class="num">${fUSD(inv)}</td>
        <td class="num">${pct.toFixed(1)}%</td>
        <td class="num">${fInt(traf)}</td>
        <td class="num">${fInt(vent)}</td>
        <td class="num">${cpl!=null ? fUSD2(cpl) : '<span style="color:#bbb">—</span>'}</td>
        <td class="num">${cac!=null ? fUSD2(cac) : '<span style="color:#bbb">—</span>'}</td>
      </tr>`;
    });
    tblAgTb.innerHTML = trsAg || '<tr><td colspan="7" style="text-align:center;color:var(--muted);padding:14px">Sin atribución por agencia.</td></tr>';
    const cplTotAg = sumTrafAg>0 ? (sumInvAg/sumTrafAg) : null;
    const cacTotAg = sumVentAg>0 ? (sumInvAg/sumVentAg) : null;
    tblAgFt.innerHTML = `<tr style="background:#f3f4f6;font-weight:700">
      <td>TOTAL atribuido a agencia</td>
      <td class="num">${fUSD(sumInvAg)}</td>
      <td class="num">${total>0?(100*sumInvAg/total).toFixed(1)+'%':'—'}</td>
      <td class="num">${fInt(sumTrafAg)}</td>
      <td class="num">${fInt(sumVentAg)}</td>
      <td class="num">${cplTotAg!=null ? fUSD2(cplTotAg) : '—'}</td>
      <td class="num">${cacTotAg!=null ? fUSD2(cacTotAg) : '—'}</td>
    </tr>`;
    // Multi/Nacional disclaimer
    const multiNac = XIY.total_multi_nacional || 0;
    const elMN = document.getElementById('xiy-multi-nacional');
    if(elMN) elMN.textContent = fUSD(multiNac);

    // ─── TABLA 4: por Medio ───
    const tblMedTb = document.querySelector('#xiy-tbl-medio tbody');
    const tblMedFt = document.querySelector('#xiy-tbl-medio tfoot');
    const totalsMedio = XIY.totals_medio || {};
    const medioObj = XIY.medio_objective || {};
    const medioEntries = Object.entries(totalsMedio).sort((a,b)=> b[1].amount - a[1].amount);
    let trsMed = '';
    let totMed = 0;
    medioEntries.forEach(([med, d]) => {
      const inv = d.amount;
      const pct = total>0 ? (100*inv/total) : 0;
      totMed += inv;
      // distribución por objetivo
      const objs = medioObj[med] || {};
      const objsStr = Object.entries(objs)
        .sort((a,b)=> b[1] - a[1])
        .map(([o,v]) => `<span style="white-space:nowrap;margin-right:8px"><strong>${o}</strong>: ${fUSD(v)}</span>`)
        .join('');
      trsMed += `<tr>
        <td><strong>${med}</strong></td>
        <td class="num">${fUSD(inv)}</td>
        <td class="num">${pct.toFixed(1)}%</td>
        <td class="num">${d.n_lines||0}</td>
        <td style="font-size:13px">${objsStr || '—'}</td>
      </tr>`;
    });
    tblMedTb.innerHTML = trsMed || '<tr><td colspan="5" style="text-align:center;color:var(--muted);padding:14px">Sin datos de medio.</td></tr>';
    tblMedFt.innerHTML = `<tr style="background:#f3f4f6;font-weight:700">
      <td>TOTAL</td>
      <td class="num">${fUSD(totMed)}</td>
      <td class="num">${total>0?'100.0%':'—'}</td>
      <td class="num">—</td>
      <td></td>
    </tr>`;

    // ─── TABLA 5: NO atribuible ───
    const nonModelo = XIY.non_modelo || {};
    const nonEntries = Object.entries(nonModelo).sort((a,b)=> b[1].amount - a[1].amount);
    const totNon = XIY.total_non_modelo || 0;
    let trsNon = '';
    nonEntries.forEach(([label, d]) => {
      const pct = total>0 ? (100*d.amount/total) : 0;
      trsNon += `<tr>
        <td>${label}</td>
        <td class="num">${fUSD(d.amount)}</td>
        <td class="num">${d.n_lines||0}</td>
        <td class="num">${pct.toFixed(1)}%</td>
      </tr>`;
    });
    tblNonTb.innerHTML = trsNon || '<tr><td colspan="4" style="text-align:center;color:var(--muted);padding:14px">Toda la inversión es atribuible a un modelo Ford.</td></tr>';

    const totNonPct = total>0 ? (100*totNon/total) : 0;
    tblNonFt.innerHTML = `<tr style="background:#f3f4f6;font-weight:700">
      <td>TOTAL NO atribuible</td>
      <td class="num">${fUSD(totNon)}</td>
      <td class="num">—</td>
      <td class="num">${totNonPct.toFixed(1)}%</td>
    </tr>`;

    // Footer con timestamp si disponible
    const meta = DATA.xiy_meta;
    if(meta && meta.fetched_at){
      document.getElementById('xiy-footer').innerHTML =
        `Fuente: <a href="${meta.source||'#'}" target="_blank">Xiy.today (sheet consolidado)</a> · ` +
        `${meta.n_campaigns||0} campañas · ${meta.n_lines||0} líneas · ` +
        `extraído ${meta.fetched_at}. Tráfico y ventas: BD interna ORGU cruzada con DATOS (FACTURADO).`;
    }

    _xiyRendered = true;
  }

  document.querySelector('.tab-btn[data-tab="xiy"]').addEventListener('click', ()=>{
    renderXiy();
  });

  // (vestige) ESCAPE-only function — kept for backward compat, not called
  function renderEscapeAnalysis(){
    // Sólo meses 2026 con metas reales
    const months = ['enero_2026','febrero_2026','marzo_2026','abril_2026','mayo_2026'];
    const monthLabels = {'enero_2026':'Enero','febrero_2026':'Febrero','marzo_2026':'Marzo','abril_2026':'Abril','mayo_2026':'Mayo'};

    // YTD totals
    let ytdReal=0, ytdMeta=0;
    months.forEach(k=>{
      const fm = FORD_MONTHS[k]; if(!fm) return;
      const e = fm.models?.['ESCAPE']; if(!e) return;
      ytdReal += e.curr || 0;
      ytdMeta += e.meta || 0;
    });
    const ytdPct = ytdMeta>0 ? (100*ytdReal/ytdMeta) : null;
    document.getElementById('esc-ytd-real').textContent = fmt(ytdReal);
    document.getElementById('esc-ytd-meta').textContent = fmt(ytdMeta);
    const pctEl = document.getElementById('esc-ytd-pct');
    pctEl.textContent = ytdPct==null ? '—' : ytdPct.toFixed(1)+'%';
    pctEl.className = 'val ' + (ytdPct==null?'':ytdPct>=100?'pos':ytdPct>=70?'warn':'neg');
    document.getElementById('esc-ytd-hint').textContent = 'Ene-May 2026 · '+ytdReal+'/'+ytdMeta;
    document.getElementById('esc-ytd-gap').textContent = ytdMeta>0 ? `gap ${ytdReal-ytdMeta}` : 'sin meta';

    // Monthly table
    const rowsHtml = months.map(k=>{
      const fm = FORD_MONTHS[k]; if(!fm) return '';
      const e = fm.models?.['ESCAPE']; if(!e) return '';
      const curr = e.curr, meta = e.meta;
      const pct = meta>0 ? 100*curr/meta : null;
      const gap = curr - meta;
      const ratio = meta>0 ? Math.min(1.5, curr/meta) : 0;
      const w = Math.max(2, Math.round(100*ratio/1.5));
      const metaPos = Math.round(100*1/1.5); // marker at 100% (which is 66% of bar 0-150%)
      const cls = pct==null?'red':pct>=100?'green':pct>=70?'yellow':'red';
      const pctStr = pct==null ? '—' : pct.toFixed(0)+'%';
      return `<tr>
        <td><strong>${monthLabels[k]}</strong></td>
        <td class="num">${fmt(curr)}</td>
        <td class="num">${fmt(meta)}</td>
        <td class="num" style="color:${pct>=100?'var(--pos)':pct>=70?'#f57f17':'var(--neg)'};font-weight:700">${pctStr}</td>
        <td class="bar-cell">
          <div class="meta-bar">
            <div class="fill ${cls}" style="width:${w}%">${pct>=8?pctStr:''}</div>
            ${meta>0?`<div class="marker" style="left:${metaPos}%"></div>`:''}
          </div>
        </td>
        <td class="num" style="color:${gap>=0?'var(--pos)':'var(--neg)'};font-weight:700">${gap>=0?'+':''}${gap}</td>
      </tr>`;
    }).join('');
    document.querySelector('#esc-monthly tbody').innerHTML = rowsHtml +
      `<tr class="total"><td>TOTAL YTD</td><td class="num">${fmt(ytdReal)}</td><td class="num">${fmt(ytdMeta)}</td>
       <td class="num">${ytdPct==null?'—':ytdPct.toFixed(1)+'%'}</td><td></td>
       <td class="num" style="color:${ytdReal>=ytdMeta?'var(--pos)':'var(--neg)'}">${ytdReal-ytdMeta>=0?'+':''}${ytdReal-ytdMeta}</td></tr>`;

    // Por agencia acumulado
    const dealers = ['CJA','Orellana','La Y','Tumbaco','Manta','Machala','Portoviejo'];
    const agg = {};
    dealers.forEach(d => agg[d] = {real:0, meta:0});
    months.forEach(k=>{
      const fm = FORD_MONTHS[k]; if(!fm) return;
      dealers.forEach(d=>{
        agg[d].real += (fm.matrix_cnt?.['ESCAPE']?.[d]) || 0;
        agg[d].meta += (fm.matrix_meta?.['ESCAPE']?.[d]) || 0;
      });
    });
    const agencyRows = dealers.map(d=>({d, real:agg[d].real, meta:agg[d].meta,
      pct: agg[d].meta>0 ? 100*agg[d].real/agg[d].meta : null}))
      .sort((a,b)=>b.real-a.real);
    const agencyHtml = agencyRows.map(r=>{
      const pctStr = r.pct==null ? '—' : r.pct.toFixed(0)+'%';
      const cls = r.pct==null?'red':r.pct>=100?'green':r.pct>=70?'yellow':'red';
      const ratio = r.meta>0 ? Math.min(1.5, r.real/r.meta) : 0;
      const w = Math.max(2, Math.round(100*ratio/1.5));
      const metaPos = Math.round(100*1/1.5);
      return `<tr>
        <td><strong>${r.d}</strong></td>
        <td class="num">${fmt(r.real)}</td>
        <td class="num">${fmt(r.meta)}</td>
        <td class="num" style="color:${r.pct>=100?'var(--pos)':r.pct>=70?'#f57f17':'var(--neg)'};font-weight:700">${pctStr}</td>
        <td class="bar-cell">
          <div class="meta-bar">
            <div class="fill ${cls}" style="width:${w}%">${r.pct>=8?pctStr:''}</div>
            ${r.meta>0?`<div class="marker" style="left:${metaPos}%"></div>`:''}
          </div>
        </td>
      </tr>`;
    }).join('');
    document.querySelector('#esc-agency tbody').innerHTML = agencyHtml +
      `<tr class="total"><td>TOTAL</td><td class="num">${fmt(ytdReal)}</td><td class="num">${fmt(ytdMeta)}</td>
       <td class="num">${ytdPct==null?'—':ytdPct.toFixed(0)+'%'}</td><td></td></tr>`;

    // Insights (dinámicos)
    const insights = [];
    // 1) Best/worst mes
    const monthsPct = months.map(k=>{
      const e = FORD_MONTHS[k]?.models?.['ESCAPE'];
      return {k, label:monthLabels[k], curr:e?.curr||0, meta:e?.meta||0, pct: e?.meta>0?100*e.curr/e.meta:null};
    }).filter(x=>x.pct!=null);
    const bestMonth = [...monthsPct].sort((a,b)=>b.pct-a.pct)[0];
    const worstMonth = [...monthsPct].sort((a,b)=>a.pct-b.pct)[0];
    if(bestMonth && worstMonth){
      insights.push({type:bestMonth.pct>=100?'good':'warn', title:'📈 Mejor y peor mes', html:
        `<strong>${bestMonth.label}</strong> fue el mes más cerca de meta con <span class="data">${bestMonth.pct.toFixed(0)}%</span> (${bestMonth.curr}/${bestMonth.meta}).
        <strong>${worstMonth.label}</strong> el peor con <span class="data">${worstMonth.pct.toFixed(0)}%</span> (${worstMonth.curr}/${worstMonth.meta}).
        Spread de <span class="data">${(bestMonth.pct-worstMonth.pct).toFixed(0)} puntos porcentuales</span>.`});
    }
    // 2) Meta progression
    const metaProgression = months.map(k=>FORD_MONTHS[k]?.models?.['ESCAPE']?.meta || 0);
    const metaGrowth = metaProgression[metaProgression.length-1] && metaProgression[0]
      ? (100*(metaProgression[metaProgression.length-1]-metaProgression[0])/metaProgression[0]) : 0;
    insights.push({type:'warn', title:'📊 Evolución de meta', html:
      `Meta mensual ESCAPE pasó de <span class="data">${metaProgression[0]}</span> (Ene) a <span class="data">${metaProgression[metaProgression.length-1]}</span> (May).
      Crecimiento de <span class="data">${metaGrowth>0?'+':''}${metaGrowth.toFixed(0)}%</span> mientras el tráfico real promedio se mantuvo en <span class="data">${(ytdReal/months.length).toFixed(0)} reg/mes</span>.`});
    // 3) Top agencia
    const topAg = agencyRows.filter(r=>r.pct!=null)[0];
    const worstAg = [...agencyRows].filter(r=>r.pct!=null && r.real>0).sort((a,b)=>a.pct-b.pct)[0];
    if(topAg && worstAg){
      insights.push({type:'warn', title:'🏢 Concentración geográfica', html:
        `<strong>${topAg.d}</strong> lidera con <span class="data">${topAg.real}</span> reg (${topAg.pct.toFixed(0)}% de su meta).
        <strong>${worstAg.d}</strong> en el extremo opuesto con apenas <span class="data">${worstAg.real}</span> reg (${worstAg.pct.toFixed(0)}%).
        Las 3 mejores agencias concentran <span class="data">${(100*agencyRows.slice(0,3).reduce((s,r)=>s+r.real,0)/ytdReal).toFixed(0)}%</span> del tráfico total.`});
    }
    // 4) Gap acumulado
    insights.push({type:ytdPct>=70?'warn':'bad', title:'⚠️ Brecha acumulada', html:
      `El acumulado YTD tiene un gap de <span class="data">${ytdReal-ytdMeta}</span> registros (${ytdPct?ytdPct.toFixed(0):'—'}% cumplimiento).
      Para cerrar el año con 100% se requerirían <span class="data">${Math.ceil((ytdMeta-ytdReal)/(12-5))}</span> reg/mes adicionales sobre el ritmo histórico
      (asumiendo metas iguales en próximos meses).`});
    // 5) Ritmo May vs meta
    const mayMd = FORD_MONTHS['mayo_2026']?.models?.['ESCAPE'];
    if(mayMd && mayMd.meta>0){
      const dt = FORD_MONTHS['mayo_2026'].days_trans;
      const dl = FORD_MONTHS['mayo_2026'].days_lab;
      const proj = Math.round((mayMd.curr/dt) * dl);
      const projPct = 100*proj/mayMd.meta;
      insights.push({type:projPct>=70?'warn':'bad', title:'🔮 Proyección Mayo', html:
        `Al día ${dt} de ${dl}, ESCAPE va en <span class="data">${mayMd.curr}</span> reg. Proyección lineal al cierre: <span class="data">${proj}</span> reg vs meta <span class="data">${mayMd.meta}</span> (<span class="data">${projPct.toFixed(0)}% cumpl. proy.</span>).
        Ritmo actual: <span class="data">${(mayMd.curr/dt).toFixed(2)} reg/día lab.</span>; meta diaria implícita: <span class="data">${(mayMd.meta/dl).toFixed(2)} reg/día lab.</span>`});
    }

    document.getElementById('esc-insights').innerHTML = insights.map(ins=>`
      <div class="insight-card ${ins.type}">
        <h4>${ins.title}</h4>
        <p>${ins.html}</p>
      </div>`).join('');
  }
})();
</script>
</body>
</html>
"""

HTML = HTML.replace("__DATA_JSON__", safe_data)
(BASE / "index.html").write_text(HTML, encoding="utf-8")
print("Wrote", BASE/"index.html", "-", len(HTML), "chars")
