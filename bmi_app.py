import http.server
import json
import sqlite3
import os
import urllib.parse
from datetime import datetime
from http import HTTPStatus

DB_PATH = os.path.join(os.path.dirname(__file__), "bmi_data.db")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            weight REAL NOT NULL,
            height REAL NOT NULL,
            bmi REAL NOT NULL,
            category TEXT NOT NULL,
            recorded_at TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    """)
    conn.commit()
    conn.close()

def calculate_bmi(weight, height):
    bmi = round(weight / (height ** 2), 1)
    if bmi < 18.5:
        category = "Underweight"
    elif bmi < 25.0:
        category = "Normal"
    elif bmi < 30.0:
        category = "Overweight"
    else:
        category = "Obese"
    return bmi, category

def get_or_create_user(name):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id FROM users WHERE name=?", (name,))
    row = c.fetchone()
    if row:
        user_id = row[0]
    else:
        now = datetime.now().isoformat()
        c.execute("INSERT INTO users (name, created_at) VALUES (?,?)", (name, now))
        conn.commit()
        user_id = c.lastrowid
    conn.close()
    return user_id

def save_record(user_id, weight, height, bmi, category):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    c.execute("""
        INSERT INTO records (user_id, weight, height, bmi, category, recorded_at)
        VALUES (?,?,?,?,?,?)
    """, (user_id, weight, height, bmi, category, now))
    conn.commit()
    conn.close()

def get_user_history(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        SELECT weight, height, bmi, category, recorded_at
        FROM records WHERE user_id=?
        ORDER BY recorded_at DESC LIMIT 30
    """, (user_id,))
    rows = c.fetchall()
    conn.close()
    return [{"weight": r[0], "height": r[1], "bmi": r[2], "category": r[3], "date": r[4]} for r in rows]

def get_all_users():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT name FROM users ORDER BY name")
    rows = c.fetchall()
    conn.close()
    return [r[0] for r in rows]

HTML_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>BMI Calculator</title>
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600&family=DM+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

  :root {
    --bg: #0f1117;
    --surface: #181c27;
    --card: #1e2333;
    --border: #2a304a;
    --text: #e8eaf0;
    --muted: #7a80a0;
    --accent: #6c8fff;
    --accent-glow: rgba(108,143,255,0.18);
    --green: #4ade80;
    --yellow: #facc15;
    --orange: #fb923c;
    --red: #f87171;
    --radius: 14px;
    --shadow: 0 4px 32px rgba(0,0,0,0.4);
  }

  body {
    font-family: 'DM Sans', sans-serif;
    background: var(--bg);
    color: var(--text);
    min-height: 100vh;
    display: flex;
    flex-direction: column;
    align-items: center;
  }

  header {
    width: 100%;
    padding: 28px 40px;
    display: flex;
    align-items: center;
    gap: 14px;
    border-bottom: 1px solid var(--border);
    background: var(--surface);
  }

  .logo-mark {
    width: 38px; height: 38px;
    background: var(--accent);
    border-radius: 10px;
    display: flex; align-items: center; justify-content: center;
    font-family: 'DM Mono', monospace;
    font-size: 13px;
    font-weight: 500;
    color: #fff;
    letter-spacing: -0.5px;
    box-shadow: 0 0 18px var(--accent-glow);
  }

  header h1 {
    font-size: 17px;
    font-weight: 600;
    letter-spacing: -0.3px;
  }

  header span {
    font-size: 13px;
    color: var(--muted);
    font-weight: 400;
    margin-left: 4px;
  }

  .tab-bar {
    display: flex;
    gap: 4px;
    margin-left: auto;
    background: var(--card);
    padding: 4px;
    border-radius: 10px;
    border: 1px solid var(--border);
  }

  .tab {
    padding: 6px 18px;
    border-radius: 7px;
    font-size: 13px;
    font-weight: 500;
    cursor: pointer;
    transition: all .2s;
    color: var(--muted);
    border: none;
    background: transparent;
  }

  .tab.active {
    background: var(--accent);
    color: #fff;
    box-shadow: 0 2px 10px rgba(108,143,255,.35);
  }

  .main {
    width: 100%;
    max-width: 980px;
    padding: 40px 24px;
  }

  .view { display: none; }
  .view.active { display: block; }

  .grid-2 {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 24px;
  }

  @media(max-width: 700px) {
    .grid-2 { grid-template-columns: 1fr; }
    header { padding: 18px 20px; flex-wrap: wrap; }
    .tab-bar { width: 100%; justify-content: center; }
  }

  .card {
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 28px;
    box-shadow: var(--shadow);
  }

  .card-title {
    font-size: 13px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 1px;
    color: var(--muted);
    margin-bottom: 22px;
  }

  .field { margin-bottom: 18px; }

  label {
    display: block;
    font-size: 13px;
    font-weight: 500;
    color: var(--muted);
    margin-bottom: 7px;
  }

  input[type=text], input[type=number], select {
    width: 100%;
    background: var(--surface);
    border: 1.5px solid var(--border);
    border-radius: 9px;
    padding: 11px 14px;
    color: var(--text);
    font-family: 'DM Sans', sans-serif;
    font-size: 15px;
    outline: none;
    transition: border-color .2s, box-shadow .2s;
  }

  input:focus, select:focus {
    border-color: var(--accent);
    box-shadow: 0 0 0 3px var(--accent-glow);
  }

  select option { background: var(--card); }

  .unit-row {
    display: flex;
    gap: 10px;
    align-items: flex-end;
  }

  .unit-row input { flex: 1; }

  .unit-badge {
    font-family: 'DM Mono', monospace;
    font-size: 12px;
    color: var(--muted);
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 7px;
    padding: 11px 12px;
    white-space: nowrap;
  }

  .btn {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    background: var(--accent);
    color: #fff;
    border: none;
    border-radius: 9px;
    padding: 12px 24px;
    font-family: 'DM Sans', sans-serif;
    font-size: 14px;
    font-weight: 600;
    cursor: pointer;
    transition: opacity .2s, transform .1s, box-shadow .2s;
    box-shadow: 0 2px 14px rgba(108,143,255,.3);
    width: 100%;
    justify-content: center;
    margin-top: 6px;
  }

  .btn:hover { opacity: 0.9; transform: translateY(-1px); box-shadow: 0 4px 20px rgba(108,143,255,.45); }
  .btn:active { transform: translateY(0); }

  .btn-ghost {
    background: transparent;
    border: 1.5px solid var(--border);
    color: var(--muted);
    box-shadow: none;
  }

  .btn-ghost:hover { border-color: var(--accent); color: var(--text); }

  .result-panel {
    display: none;
    flex-direction: column;
    gap: 20px;
  }

  .result-panel.show { display: flex; }

  .bmi-display {
    text-align: center;
    padding: 32px 0 24px;
    position: relative;
  }

  .bmi-number {
    font-size: 72px;
    font-weight: 300;
    letter-spacing: -4px;
    line-height: 1;
    font-family: 'DM Mono', monospace;
  }

  .bmi-label {
    font-size: 13px;
    font-weight: 500;
    letter-spacing: 2px;
    text-transform: uppercase;
    margin-top: 6px;
  }

  .bmi-category-badge {
    display: inline-block;
    margin-top: 14px;
    padding: 5px 16px;
    border-radius: 100px;
    font-size: 13px;
    font-weight: 600;
    letter-spacing: 0.5px;
  }

  .cat-Underweight { color: #93c5fd; background: rgba(147,197,253,.12); }
  .cat-Normal { color: var(--green); background: rgba(74,222,128,.12); }
  .cat-Overweight { color: var(--yellow); background: rgba(250,204,21,.12); }
  .cat-Obese { color: var(--red); background: rgba(248,113,113,.12); }
  .color-Underweight { color: #93c5fd; }
  .color-Normal { color: var(--green); }
  .color-Overweight { color: var(--yellow); }
  .color-Obese { color: var(--red); }

  .scale-bar {
    width: 100%;
    height: 8px;
    border-radius: 100px;
    background: linear-gradient(to right, #93c5fd 0%, #93c5fd 25%, #4ade80 25%, #4ade80 55%, #facc15 55%, #facc15 75%, #f87171 75%, #f87171 100%);
    position: relative;
    margin: 8px 0 14px;
  }

  .scale-marker {
    position: absolute;
    top: -4px;
    width: 16px;
    height: 16px;
    background: #fff;
    border-radius: 50%;
    transform: translateX(-50%);
    box-shadow: 0 0 0 3px var(--accent), 0 2px 8px rgba(0,0,0,.5);
    transition: left .6s cubic-bezier(.34,1.56,.64,1);
  }

  .scale-labels {
    display: flex;
    justify-content: space-between;
    font-size: 11px;
    color: var(--muted);
    font-family: 'DM Mono', monospace;
  }

  .stats-row {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 12px;
  }

  .stat-cell {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 14px 16px;
  }

  .stat-cell .label {
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.8px;
    color: var(--muted);
    margin-bottom: 4px;
  }

  .stat-cell .value {
    font-size: 18px;
    font-weight: 600;
    font-family: 'DM Mono', monospace;
  }

  .history-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 13.5px;
  }

  .history-table th {
    text-align: left;
    padding: 8px 12px;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.8px;
    color: var(--muted);
    border-bottom: 1px solid var(--border);
  }

  .history-table td {
    padding: 10px 12px;
    border-bottom: 1px solid rgba(42,48,74,.5);
    vertical-align: middle;
  }

  .history-table tr:last-child td { border-bottom: none; }

  .dot {
    display: inline-block;
    width: 8px; height: 8px;
    border-radius: 50%;
    margin-right: 6px;
    vertical-align: middle;
  }

  .dot-Underweight { background: #93c5fd; }
  .dot-Normal { background: var(--green); }
  .dot-Overweight { background: var(--yellow); }
  .dot-Obese { background: var(--red); }

  .empty-state {
    text-align: center;
    padding: 48px 24px;
    color: var(--muted);
    font-size: 14px;
  }

  .empty-icon { font-size: 36px; margin-bottom: 12px; }

  .chart-wrap {
    width: 100%;
    height: 200px;
    position: relative;
    margin-top: 8px;
  }

  canvas#trendChart {
    width: 100% !important;
    height: 100% !important;
  }

  .toast {
    position: fixed;
    bottom: 32px;
    left: 50%;
    transform: translateX(-50%) translateY(80px);
    background: var(--green);
    color: #000;
    font-weight: 600;
    font-size: 13px;
    padding: 10px 22px;
    border-radius: 100px;
    box-shadow: 0 4px 24px rgba(74,222,128,.4);
    transition: transform .3s cubic-bezier(.34,1.56,.64,1);
    z-index: 999;
    pointer-events: none;
  }

  .toast.show { transform: translateX(-50%) translateY(0); }

  .section-label {
    font-size: 22px;
    font-weight: 600;
    letter-spacing: -0.5px;
    margin-bottom: 6px;
  }

  .section-sub {
    font-size: 14px;
    color: var(--muted);
    margin-bottom: 28px;
  }

  .user-chip-row {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin-bottom: 20px;
  }

  .user-chip {
    padding: 5px 14px;
    border-radius: 100px;
    background: var(--surface);
    border: 1.5px solid var(--border);
    font-size: 13px;
    cursor: pointer;
    transition: all .2s;
    color: var(--muted);
  }

  .user-chip:hover, .user-chip.active {
    border-color: var(--accent);
    color: var(--text);
    background: var(--accent-glow);
  }

  .ideal-range {
    font-size: 13px;
    color: var(--muted);
    margin-top: 4px;
    text-align: center;
  }

  .ideal-range span { color: var(--green); font-family: 'DM Mono', monospace; font-weight: 500; }

  hr.divider {
    border: none;
    border-top: 1px solid var(--border);
    margin: 20px 0;
  }
</style>
</head>
<body>

<header>
  <div class="logo-mark">BMI</div>
  <div>
    <h1>Body Mass Index <span>Calculator</span></h1>
  </div>
  <div class="tab-bar">
    <button class="tab active" onclick="switchTab('calculator')">Calculate</button>
    <button class="tab" onclick="switchTab('history')">History</button>
    <button class="tab" onclick="switchTab('trends')">Trends</button>
  </div>
</header>

<div class="main">

  <div id="view-calculator" class="view active">
    <p class="section-label">Calculate BMI</p>
    <p class="section-sub">Enter your details to get your Body Mass Index score and health classification.</p>
    <div class="grid-2">
      <div class="card">
        <div class="card-title">Your Details</div>
        <div class="field">
          <label>Full Name</label>
          <input type="text" id="inp-name" placeholder="e.g. Alex Johnson" autocomplete="off">
        </div>
        <div class="field">
          <label>Weight</label>
          <div class="unit-row">
            <input type="number" id="inp-weight" placeholder="70" min="1" max="500" step="0.1">
            <div class="unit-badge">kg</div>
          </div>
        </div>
        <div class="field">
          <label>Height</label>
          <div class="unit-row">
            <input type="number" id="inp-height" placeholder="1.75" min="0.5" max="3" step="0.01">
            <div class="unit-badge">m</div>
          </div>
        </div>
        <div id="error-msg" style="color:var(--red);font-size:13px;margin-bottom:10px;display:none;"></div>
        <button class="btn" onclick="doCalculate()">
          <svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M9 3H5a2 2 0 00-2 2v4m6-6h10a2 2 0 012 2v4M9 3v18m0 0h10a2 2 0 002-2V9M9 21H5a2 2 0 01-2-2V9m0 0h18"/></svg>
          Calculate BMI
        </button>
      </div>

      <div class="card" id="result-card">
        <div class="card-title">Your Result</div>
        <div class="result-panel" id="result-panel">
          <div class="bmi-display">
            <div class="bmi-number" id="res-number">--</div>
            <div class="bmi-label" style="color:var(--muted)">Body Mass Index</div>
            <div class="bmi-category-badge" id="res-badge">—</div>
            <div class="ideal-range" id="res-ideal"></div>
          </div>
          <div>
            <div class="scale-bar">
              <div class="scale-marker" id="scale-marker" style="left:0%"></div>
            </div>
            <div class="scale-labels">
              <span>Underweight</span>
              <span>Normal</span>
              <span>Overweight</span>
              <span>Obese</span>
            </div>
          </div>
          <div class="stats-row">
            <div class="stat-cell">
              <div class="label">Weight</div>
              <div class="value" id="res-weight">—</div>
            </div>
            <div class="stat-cell">
              <div class="label">Height</div>
              <div class="value" id="res-height">—</div>
            </div>
          </div>
          <button class="btn btn-ghost" onclick="resetForm()">Clear & Recalculate</button>
        </div>
        <div id="result-empty" class="empty-state">
          <div class="empty-icon">⚖️</div>
          <div>Fill in your details and hit<br><strong>Calculate BMI</strong></div>
        </div>
      </div>
    </div>

    <div style="margin-top:28px;" class="card">
      <div class="card-title">BMI Classification Guide</div>
      <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:14px;">
        <div style="text-align:center;">
          <div style="font-size:22px;font-weight:600;color:#93c5fd;font-family:'DM Mono',monospace;">&lt; 18.5</div>
          <div style="font-size:12px;color:var(--muted);margin-top:4px;text-transform:uppercase;letter-spacing:.8px;">Underweight</div>
        </div>
        <div style="text-align:center;">
          <div style="font-size:22px;font-weight:600;color:var(--green);font-family:'DM Mono',monospace;">18.5–24.9</div>
          <div style="font-size:12px;color:var(--muted);margin-top:4px;text-transform:uppercase;letter-spacing:.8px;">Normal</div>
        </div>
        <div style="text-align:center;">
          <div style="font-size:22px;font-weight:600;color:var(--yellow);font-family:'DM Mono',monospace;">25–29.9</div>
          <div style="font-size:12px;color:var(--muted);margin-top:4px;text-transform:uppercase;letter-spacing:.8px;">Overweight</div>
        </div>
        <div style="text-align:center;">
          <div style="font-size:22px;font-weight:600;color:var(--red);font-family:'DM Mono',monospace;">&ge; 30</div>
          <div style="font-size:12px;color:var(--muted);margin-top:4px;text-transform:uppercase;letter-spacing:.8px;">Obese</div>
        </div>
      </div>
    </div>
  </div>

  <div id="view-history" class="view">
    <p class="section-label">History</p>
    <p class="section-sub">Browse past BMI records for each user.</p>
    <div id="history-users" class="user-chip-row"></div>
    <div class="card" id="history-card">
      <div id="history-content" class="empty-state">
        <div class="empty-icon">📋</div>
        <div>Select a user above to view their history.</div>
      </div>
    </div>
  </div>

  <div id="view-trends" class="view">
    <p class="section-label">Trends</p>
    <p class="section-sub">Visualise BMI changes over time.</p>
    <div id="trends-users" class="user-chip-row"></div>
    <div class="card">
      <div class="card-title">BMI Over Time</div>
      <div class="chart-wrap">
        <canvas id="trendChart"></canvas>
      </div>
      <div id="trend-stats" style="margin-top:20px;display:none;">
        <hr class="divider">
        <div class="stats-row" style="grid-template-columns:repeat(4,1fr);">
          <div class="stat-cell"><div class="label">Entries</div><div class="value" id="ts-count">—</div></div>
          <div class="stat-cell"><div class="label">Latest</div><div class="value" id="ts-latest">—</div></div>
          <div class="stat-cell"><div class="label">Lowest</div><div class="value" id="ts-min">—</div></div>
          <div class="stat-cell"><div class="label">Highest</div><div class="value" id="ts-max">—</div></div>
        </div>
      </div>
    </div>
  </div>

</div>

<div class="toast" id="toast">Saved ✓</div>

<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<script>
let trendChart = null;

function switchTab(name) {
  document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.getElementById('view-' + name).classList.add('active');
  event.target.classList.add('active');
  if (name === 'history') loadUsers('history');
  if (name === 'trends') loadUsers('trends');
}

function showToast(msg) {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.classList.add('show');
  setTimeout(() => t.classList.remove('show'), 2400);
}

function showError(msg) {
  const el = document.getElementById('error-msg');
  el.textContent = msg;
  el.style.display = msg ? 'block' : 'none';
}

function bmiToPercent(bmi) {
  const min = 10, max = 40;
  return Math.min(100, Math.max(0, ((bmi - min) / (max - min)) * 100));
}

function idealWeight(height) {
  const lo = (18.5 * height * height).toFixed(1);
  const hi = (24.9 * height * height).toFixed(1);
  return { lo, hi };
}

async function doCalculate() {
  showError('');
  const name = document.getElementById('inp-name').value.trim();
  const weight = parseFloat(document.getElementById('inp-weight').value);
  const height = parseFloat(document.getElementById('inp-height').value);
  if (!name) return showError('Please enter your name.');
  if (!weight || weight <= 0 || weight > 500) return showError('Enter a valid weight (1–500 kg).');
  if (!height || height < 0.5 || height > 3) return showError('Enter a valid height (0.5–3.0 m).');

  const res = await fetch('/api/calculate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, weight, height })
  });
  const data = await res.json();
  if (!data.ok) return showError(data.error || 'Something went wrong.');

  const { bmi, category } = data;
  document.getElementById('res-number').textContent = bmi;
  document.getElementById('res-number').className = 'bmi-number color-' + category;
  const badge = document.getElementById('res-badge');
  badge.textContent = category;
  badge.className = 'bmi-category-badge cat-' + category;
  document.getElementById('res-weight').textContent = weight + ' kg';
  document.getElementById('res-height').textContent = height + ' m';
  const iw = idealWeight(height);
  document.getElementById('res-ideal').innerHTML = 'Ideal weight for your height: <span>' + iw.lo + '–' + iw.hi + ' kg</span>';
  document.getElementById('result-empty').style.display = 'none';
  document.getElementById('result-panel').classList.add('show');
  setTimeout(() => {
    document.getElementById('scale-marker').style.left = bmiToPercent(bmi) + '%';
  }, 80);
  showToast('Record saved ✓');
}

function resetForm() {
  document.getElementById('inp-name').value = '';
  document.getElementById('inp-weight').value = '';
  document.getElementById('inp-height').value = '';
  document.getElementById('result-panel').classList.remove('show');
  document.getElementById('result-empty').style.display = '';
  document.getElementById('scale-marker').style.left = '0%';
  showError('');
}

async function loadUsers(view) {
  const res = await fetch('/api/users');
  const data = await res.json();
  const container = document.getElementById(view + '-users');
  container.innerHTML = '';
  if (!data.users || data.users.length === 0) {
    container.innerHTML = '<div style="color:var(--muted);font-size:13px;">No users yet. Calculate a BMI first.</div>';
    return;
  }
  data.users.forEach(u => {
    const chip = document.createElement('button');
    chip.className = 'user-chip';
    chip.textContent = u;
    chip.onclick = () => {
      container.querySelectorAll('.user-chip').forEach(c => c.classList.remove('active'));
      chip.classList.add('active');
      if (view === 'history') loadHistory(u);
      else loadTrend(u);
    };
    container.appendChild(chip);
  });
}

async function loadHistory(name) {
  const res = await fetch('/api/history?name=' + encodeURIComponent(name));
  const data = await res.json();
  const card = document.getElementById('history-content');
  if (!data.records || data.records.length === 0) {
    card.innerHTML = '<div class="empty-state"><div class="empty-icon">📋</div><div>No records found.</div></div>';
    return;
  }
  let html = '<table class="history-table"><thead><tr><th>Date</th><th>BMI</th><th>Category</th><th>Weight</th><th>Height</th></tr></thead><tbody>';
  data.records.forEach(r => {
    html += `<tr>
      <td style="color:var(--muted);font-family:'DM Mono',monospace;font-size:12px;">${r.date}</td>
      <td><span class="color-${r.category}" style="font-family:'DM Mono',monospace;font-weight:600;">${r.bmi}</span></td>
      <td><span class="dot dot-${r.category}"></span>${r.category}</td>
      <td>${r.weight} kg</td>
      <td>${r.height} m</td>
    </tr>`;
  });
  html += '</tbody></table>';
  card.innerHTML = html;
}

async function loadTrend(name) {
  const res = await fetch('/api/history?name=' + encodeURIComponent(name));
  const data = await res.json();
  if (!data.records || data.records.length === 0) return;
  const records = [...data.records].reverse();
  const labels = records.map(r => r.date.split(' ')[0]);
  const bmis = records.map(r => r.bmi);

  const cats = records.map(r => r.category);
  const colorMap = { Underweight: '#93c5fd', Normal: '#4ade80', Overweight: '#facc15', Obese: '#f87171' };
  const pointColors = cats.map(c => colorMap[c]);

  const ctx = document.getElementById('trendChart').getContext('2d');
  if (trendChart) trendChart.destroy();

  trendChart = new Chart(ctx, {
    type: 'line',
    data: {
      labels,
      datasets: [{
        data: bmis,
        borderColor: '#6c8fff',
        backgroundColor: 'rgba(108,143,255,0.08)',
        pointBackgroundColor: pointColors,
        pointBorderColor: '#1e2333',
        pointBorderWidth: 2,
        pointRadius: 6,
        tension: 0.35,
        fill: true,
        borderWidth: 2.5
      }]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false }, tooltip: {
        callbacks: {
          label: (ctx) => ' BMI: ' + ctx.parsed.y
        },
        backgroundColor: '#1e2333',
        borderColor: '#2a304a',
        borderWidth: 1,
        titleColor: '#e8eaf0',
        bodyColor: '#7a80a0'
      }},
      scales: {
        x: { grid: { color: 'rgba(42,48,74,0.5)' }, ticks: { color: '#7a80a0', font: { family: 'DM Mono', size: 11 } } },
        y: {
          grid: { color: 'rgba(42,48,74,0.5)' },
          ticks: { color: '#7a80a0', font: { family: 'DM Mono', size: 11 } },
          min: Math.max(10, Math.min(...bmis) - 3),
          max: Math.max(...bmis) + 3
        }
      }
    }
  });

  document.getElementById('ts-count').textContent = bmis.length;
  document.getElementById('ts-latest').textContent = bmis[bmis.length - 1];
  document.getElementById('ts-min').textContent = Math.min(...bmis);
  document.getElementById('ts-max').textContent = Math.max(...bmis);
  document.getElementById('trend-stats').style.display = '';
}
</script>
</body>
</html>
"""

class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def send_json(self, data, status=200):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        qs = urllib.parse.parse_qs(parsed.query)

        if path == "/" or path == "/index.html":
            body = HTML_PAGE.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif path == "/api/users":
            users = get_all_users()
            self.send_json({"users": users})
        elif path == "/api/history":
            name = qs.get("name", [None])[0]
            if not name:
                return self.send_json({"error": "name required"}, 400)
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("SELECT id FROM users WHERE name=?", (name,))
            row = c.fetchone()
            conn.close()
            if not row:
                return self.send_json({"records": []})
            records = get_user_history(row[0])
            self.send_json({"records": records})
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path == "/api/calculate":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            try:
                payload = json.loads(body)
                name = str(payload.get("name", "")).strip()
                weight = float(payload.get("weight", 0))
                height = float(payload.get("height", 0))
                if not name:
                    raise ValueError("name required")
                if weight <= 0 or height <= 0:
                    raise ValueError("invalid values")
                bmi, category = calculate_bmi(weight, height)
                user_id = get_or_create_user(name)
                save_record(user_id, weight, height, bmi, category)
                self.send_json({"ok": True, "bmi": bmi, "category": category})
            except Exception as e:
                self.send_json({"ok": False, "error": str(e)}, 400)
        else:
            self.send_response(404)
            self.end_headers()

if __name__ == "__main__":
    init_db()
    PORT = 8080
    server = http.server.HTTPServer(("", PORT), Handler)
    print(f"\n  BMI Calculator running at → http://localhost:{PORT}\n")
    print("  Press Ctrl+C to stop.\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  Server stopped.")
