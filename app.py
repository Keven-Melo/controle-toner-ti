"""
Controle de Toner — TI
Dependências: flask flask-login werkzeug psycopg2-binary
pip install flask flask-login werkzeug psycopg2-binary
"""

import os
import psycopg2
import psycopg2.extras
from datetime import datetime
from functools import wraps

from flask import (Flask, render_template_string, redirect, url_for,
                   request, flash, get_flashed_messages)
from flask_login import (LoginManager, UserMixin, login_user,
                         logout_user, login_required, current_user)
from werkzeug.security import generate_password_hash, check_password_hash

# ─────────────────────────────────────────────
#  App & Login setup
# ─────────────────────────────────────────────
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "TROQUE-ESTA-CHAVE-POR-ALGO-SEGURO-EM-PRODUCAO")

login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message = "Por favor, faça login para continuar."

# ─────────────────────────────────────────────
#  Dados iniciais
# ─────────────────────────────────────────────
DADOS_INICIAIS = [
    ("2IO9", "Almoxarifado",     "-",          1, 0, 72),
    ("2IA6", "Aquiraz",          "-",          1, 0, 45),
    ("2IO8", "Aracati",          "-",          1, 0, 15),
    ("IYA8", "Doc. Ambiental",   "-",          0, 1, 8),
    ("2GS1", "MTR",              "-",          0, 1, 5),
    ("2IP4", "Operacional",      "-",          1, 0, 88),
    ("2IP7", "Solda",            "-",          1, 0, 60),
    ("2IP3", "Comercial",        "-",          1, 0, 33),
    ("2IP8", "Compras",          "-",          1, 0, 91),
    ("2IP9", "Diretoria",        "-",          1, 0, 19),
    ("2IP5", "Licitação",        "-",          1, 0, 54),
    ("2IQ1", "Manutenção",       "-",          1, 0, 12),
    ("2IP2", "QSMS",             "-",          1, 0, 77),
    ("2MS6", "Setor Pessoal",    "-",          1, 0, 40),
    ("-",    "Braslimp",         "LaserJet",   1, 0, 25),
    ("2IO7", "-",                "Color CMYK", 0, 0, 3),
    ("9I55", "GP (New Printer)", "CMYK",       0, 0, 68),
    ("MQW5", "Pecém",            "-",          3, 0, 82),
]

USUARIOS_INICIAIS = [
    ("admin", generate_password_hash("admin123"), "Administrador", 1),
    ("ti",    generate_password_hash("ti2024"),   "Equipe TI",     0),
]

# ─────────────────────────────────────────────
#  Banco de dados — PostgreSQL
# ─────────────────────────────────────────────
DATABASE_URL = os.environ.get("DATABASE_URL")

def get_db():
    conn = psycopg2.connect(DATABASE_URL)
    return conn

def fetchall(cursor):
    """Retorna lista de dicts a partir de um cursor já executado."""
    cols = [d[0] for d in cursor.description]
    return [dict(zip(cols, row)) for row in cursor.fetchall()]

def fetchone(cursor):
    """Retorna um dict ou None a partir de um cursor já executado."""
    row = cursor.fetchone()
    if row is None:
        return None
    cols = [d[0] for d in cursor.description]
    return dict(zip(cols, row))

def init_db():
    conn = get_db()
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS estoque (
            id         SERIAL PRIMARY KEY,
            codigo     TEXT,
            setor      TEXT,
            modelo     TEXT,
            quantidade INTEGER,
            aguardando INTEGER DEFAULT 0,
            observacao TEXT    DEFAULT '',
            tinta_pct  INTEGER DEFAULT NULL
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS historico (
            id         SERIAL PRIMARY KEY,
            estoque_id INTEGER,
            usuario    TEXT,
            acao       TEXT,
            detalhe    TEXT,
            criado_em  TEXT
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id       SERIAL PRIMARY KEY,
            username TEXT UNIQUE,
            password TEXT,
            nome     TEXT,
            is_admin INTEGER DEFAULT 0
        )
    """)

    # Popula estoque se vazio
    c.execute("SELECT COUNT(*) FROM estoque")
    if c.fetchone()[0] == 0:
        for row in DADOS_INICIAIS:
            c.execute(
                "INSERT INTO estoque (codigo,setor,modelo,quantidade,aguardando,tinta_pct) VALUES (%s,%s,%s,%s,%s,%s)",
                row
            )

    # Popula usuários se vazio
    c.execute("SELECT COUNT(*) FROM usuarios")
    if c.fetchone()[0] == 0:
        for row in USUARIOS_INICIAIS:
            c.execute(
                "INSERT INTO usuarios (username,password,nome,is_admin) VALUES (%s,%s,%s,%s)",
                row
            )

    conn.commit()
    conn.close()

init_db()

# ─────────────────────────────────────────────
#  User model
# ─────────────────────────────────────────────
class User(UserMixin):
    def __init__(self, row):
        self.id       = row["id"]
        self.username = row["username"]
        self.nome     = row["nome"]
        self.is_admin = bool(row["is_admin"])

@login_manager.user_loader
def load_user(user_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM usuarios WHERE id=%s", (user_id,))
    row = fetchone(c)
    conn.close()
    return User(row) if row else None

# ─────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────
def calcular_status(qtd, aguardando):
    if qtd >= 1:        return "OK"
    if aguardando == 1: return "Aguardando Selbetti"
    return "PROBLEMA"

def registrar(estoque_id, acao, detalhe=""):
    conn = get_db()
    c = conn.cursor()
    nome = current_user.nome if current_user.is_authenticated else "Sistema"
    c.execute(
        "INSERT INTO historico (estoque_id,usuario,acao,detalhe,criado_em) VALUES (%s,%s,%s,%s,%s)",
        (estoque_id, nome, acao, detalhe,
         datetime.now().strftime("%d/%m/%Y %H:%M"))
    )
    conn.commit()
    conn.close()

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash("Acesso restrito a administradores.", "error")
            return redirect(url_for("index"))
        return f(*args, **kwargs)
    return decorated

# ══════════════════════════════════════════════
#  CSS global
# ══════════════════════════════════════════════
CSS = """
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
:root{
    /* Braslimp green palette */
    --sb-bg:#14381f;--sb-bg2:#1a4526;--sb-border:rgba(255,255,255,.08);
    --sb-text:rgba(255,255,255,.9);--sb-muted:rgba(255,255,255,.45);
    --sb-active:rgba(255,255,255,.1);--sb-hover:rgba(255,255,255,.07);
    --sb-accent:#4ade80;

    --bg:#f5f7f5;--surface:#fff;--border:#e3e8e3;--border2:#cdd5cd;
    --text:#111c11;--muted:#5a6b5a;--light:#93a893;
    --primary:#166534;--primary-hover:#14532d;
    --primary-bg:#f0fdf4;--primary-bd:#86efac;

    --ok:#16a34a;--ok-bg:#f0fdf4;--ok-bd:#bbf7d0;
    --warn:#b45309;--warn-bg:#fffbeb;--warn-bd:#fde68a;
    --danger:#dc2626;--danger-bg:#fef2f2;--danger-bd:#fecaca;

    --mono:'JetBrains Mono',monospace;--sans:'Inter',sans-serif;
    --r:8px;--sh:0 1px 3px rgba(0,0,0,.07),0 1px 2px rgba(0,0,0,.04);
    --sh-md:0 4px 16px rgba(0,0,0,.1);
}
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
body{font-family:var(--sans);background:var(--bg);color:var(--text);font-size:14px;line-height:1.5;-webkit-font-smoothing:antialiased}
a{color:inherit;text-decoration:none}

/* ── Shell ── */
.shell{display:flex;min-height:100vh}
.sidebar{width:230px;background:var(--sb-bg);display:flex;flex-direction:column;flex-shrink:0;position:fixed;top:0;left:0;bottom:0}
.sb-logo{padding:22px 20px 18px;border-bottom:1px solid var(--sb-border);display:flex;align-items:center;gap:12px}
.sb-logo .icon{width:34px;height:34px;border-radius:8px;overflow:hidden;flex-shrink:0;display:flex;align-items:center;justify-content:center;background:#fff}
.sb-logo .icon img{width:34px;height:34px;object-fit:contain}
.sb-logo .brand{font-weight:700;font-size:14px;line-height:1.25;color:var(--sb-text)}
.sb-logo .brand span{font-weight:400;color:var(--sb-muted);font-size:11px;display:block;margin-top:1px}
.nav-section{padding:16px 12px 8px}
.nav-label{font-size:10px;font-weight:600;letter-spacing:.1em;text-transform:uppercase;color:var(--sb-muted);padding:0 10px;margin-bottom:6px}
.nav-item{display:flex;align-items:center;gap:9px;padding:8px 10px;border-radius:6px;font-size:13px;font-weight:500;color:var(--sb-muted);transition:all .12s;cursor:pointer}
.nav-item:hover{background:var(--sb-hover);color:var(--sb-text)}
.nav-item.active{background:var(--sb-active);color:var(--sb-text);font-weight:600}
.nav-item.active .nav-icon{color:var(--sb-accent)}
.nav-icon{font-size:15px;width:18px;text-align:center}
.sb-divider{height:1px;background:var(--sb-border);margin:8px 12px}
.sb-footer{margin-top:auto;padding:16px 12px;border-top:1px solid var(--sb-border)}
.user-chip{display:flex;align-items:center;gap:9px;padding:6px 8px}
.user-av{width:30px;height:30px;background:var(--sb-accent);border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:12px;font-weight:700;color:var(--sb-bg);flex-shrink:0}
.user-name{font-size:12px;font-weight:600;color:var(--sb-text)}
.user-role{font-size:10px;color:var(--sb-muted)}
.logout-lnk{margin-top:6px;display:block;font-size:12px;color:var(--sb-muted);padding:5px 8px;border-radius:5px;transition:all .12s}
.logout-lnk:hover{color:#fca5a5;background:rgba(220,38,38,.15)}

/* ── Main ── */
.main{margin-left:230px;flex:1;display:flex;flex-direction:column;min-height:100vh}
.topbar{height:56px;background:var(--surface);border-bottom:1px solid var(--border);display:flex;align-items:center;padding:0 28px;gap:12px;position:sticky;top:0;z-index:10}
.topbar-title{font-size:15px;font-weight:600;flex:1;color:var(--text)}
.topbar-sub{font-size:12px;color:var(--muted)}
.content{padding:28px;flex:1}

/* ── Card ── */
.card{background:var(--surface);border:1px solid var(--border);border-radius:var(--r);box-shadow:var(--sh)}
.card-header{display:flex;align-items:center;justify-content:space-between;padding:14px 20px;border-bottom:1px solid var(--border)}
.card-title{font-size:13px;font-weight:600}
.card-sub{font-size:12px;color:var(--muted);margin-top:1px}

/* ── Stats ── */
.stats-row{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-bottom:20px}
.stat{background:var(--surface);border:1px solid var(--border);border-radius:var(--r);padding:16px 18px;box-shadow:var(--sh)}
.stat-label{font-size:11px;font-weight:600;color:var(--muted);text-transform:uppercase;letter-spacing:.06em;margin-bottom:6px}
.stat-number{font-family:var(--mono);font-size:28px;font-weight:700;line-height:1}
.stat-number.c-ok{color:var(--ok)}.stat-number.c-warn{color:var(--warn)}.stat-number.c-danger{color:var(--danger)}.stat-number.c-primary{color:var(--primary)}
.stat-hint{font-size:11px;color:var(--muted);margin-top:4px}

/* ── Alert ── */
.alert{display:flex;align-items:center;gap:10px;padding:10px 14px;border-radius:var(--r);font-size:13px;margin-bottom:16px;border-left:3px solid}
.alert-danger{background:var(--danger-bg);border-color:var(--danger);color:var(--danger)}

/* ── Table ── */
.table-wrap{overflow-x:auto}
table{width:100%;border-collapse:collapse}
thead th{font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:.07em;color:var(--muted);padding:10px 16px;text-align:left;background:var(--bg);border-bottom:1px solid var(--border);white-space:nowrap}
tbody td{padding:11px 16px;border-bottom:1px solid var(--border);vertical-align:middle;font-size:13px}
tbody tr:last-child td{border-bottom:none}
tbody tr:hover td{background:#f9fbf9}

/* ── Badges ── */
.badge{display:inline-flex;align-items:center;gap:4px;padding:3px 9px;border-radius:20px;font-size:11px;font-weight:600;white-space:nowrap;border:1px solid}
.badge-ok{background:var(--ok-bg);color:var(--ok);border-color:var(--ok-bd)}
.badge-warn{background:var(--warn-bg);color:var(--warn);border-color:var(--warn-bd)}
.badge-danger{background:var(--danger-bg);color:var(--danger);border-color:var(--danger-bd)}
.badge-primary{background:var(--primary-bg);color:var(--primary);border-color:var(--primary-bd)}

/* ── Qty ── */
.qty{font-family:var(--mono);font-weight:700;font-size:15px}
.qty-0{color:var(--danger)}.qty-1{color:var(--warn)}.qty-ok{color:var(--ok)}

/* ── Code ── */
.code{font-family:var(--mono);font-size:12px;background:var(--bg);border:1px solid var(--border);padding:2px 7px;border-radius:4px;color:var(--muted)}

/* ── Buttons ── */
.btn{display:inline-flex;align-items:center;gap:5px;padding:6px 12px;border-radius:6px;font-size:12px;font-weight:600;cursor:pointer;border:1px solid transparent;font-family:var(--sans);transition:all .12s;text-decoration:none}
.btn-primary{background:var(--primary);color:#fff;border-color:var(--primary)}.btn-primary:hover{background:var(--primary-hover)}
.btn-ghost{background:transparent;color:var(--muted);border-color:var(--border)}.btn-ghost:hover{color:var(--text);border-color:var(--border2)}
.btn-danger-ghost{background:transparent;color:var(--danger);border-color:var(--danger-bd)}.btn-danger-ghost:hover{background:var(--danger-bg)}
.action-row{display:flex;gap:4px;align-items:center;flex-wrap:wrap}
.act{padding:4px 8px;border-radius:5px;font-size:11px;font-weight:600;cursor:pointer;border:1px solid transparent;font-family:var(--sans);transition:all .1s;text-decoration:none;display:inline-block;white-space:nowrap}
.act-plus{background:var(--ok-bg);color:var(--ok);border-color:var(--ok-bd)}
.act-minus{background:var(--danger-bg);color:var(--danger);border-color:var(--danger-bd)}
.act-req{background:var(--warn-bg);color:var(--warn);border-color:var(--warn-bd)}
.act-recv{background:var(--primary-bg);color:var(--primary);border-color:var(--primary-bd)}
.act-edit{background:var(--bg);color:var(--muted);border-color:var(--border)}
.act:hover{filter:brightness(.93)}

/* ── Obs ── */
.obs-text{font-size:12px;color:var(--muted);font-style:italic;max-width:180px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;display:block}
.obs-empty{color:var(--light)}

/* ── Forms ── */
.form-group{margin-bottom:16px}
label{display:block;font-size:12px;font-weight:600;color:var(--muted);margin-bottom:5px;text-transform:uppercase;letter-spacing:.05em}
input[type=text],input[type=password],textarea,select{width:100%;padding:8px 11px;border:1px solid var(--border);border-radius:6px;font-size:13px;font-family:var(--sans);color:var(--text);background:var(--surface);transition:border .12s;outline:none}
input:focus,textarea:focus,select:focus{border-color:var(--primary);box-shadow:0 0 0 3px rgba(22,101,52,.12)}
textarea{resize:vertical;min-height:60px}

/* ── Login ── */
.login-wrap{min-height:100vh;display:flex;align-items:center;justify-content:center;background:var(--sb-bg)}
.login-card{background:var(--surface);border:1px solid var(--border);border-radius:12px;box-shadow:var(--sh-md);padding:36px 40px;width:340px}
.login-logo{display:flex;align-items:center;gap:10px;margin-bottom:28px}
.login-logo .icon{width:42px;height:42px;background:#fff;border-radius:9px;border:1px solid var(--border);overflow:hidden;display:flex;align-items:center;justify-content:center}
.login-logo .icon img{width:38px;height:38px;object-fit:contain}
.login-logo .label{font-weight:700;font-size:14px;line-height:1.2;color:var(--text)}
.login-logo .label span{font-weight:400;color:var(--muted);font-size:11px;display:block}
.flash-msg{padding:8px 12px;border-radius:6px;font-size:12px;margin-bottom:14px}
.flash-error{background:var(--danger-bg);color:var(--danger);border:1px solid var(--danger-bd)}
.flash-success{background:var(--ok-bg);color:var(--ok);border:1px solid var(--ok-bd)}

/* ── Modal ── */
.modal-backdrop{display:none;position:fixed;inset:0;background:rgba(0,0,0,.35);z-index:100;align-items:center;justify-content:center}
.modal-backdrop.open{display:flex}
.modal{background:var(--surface);border:1px solid var(--border);border-radius:10px;box-shadow:var(--sh-md);padding:24px 28px;width:400px;max-width:96vw}
.modal-title{font-size:14px;font-weight:700;margin-bottom:16px}
.modal-actions{display:flex;gap:8px;justify-content:flex-end;margin-top:16px}

/* ── History ── */
.h-item{display:flex;align-items:flex-start;gap:12px;padding:11px 20px;border-bottom:1px solid var(--border)}
.h-item:last-child{border-bottom:none}
.h-dot{width:8px;height:8px;border-radius:50%;flex-shrink:0;margin-top:5px}
.h-dot-plus{background:var(--ok)}.h-dot-minus{background:var(--danger)}
.h-dot-req{background:var(--warn)}.h-dot-recv{background:var(--primary)}
.h-dot-obs{background:var(--muted)}.h-dot-other{background:var(--light)}
.h-acao{font-size:13px;font-weight:500}
.h-meta{font-size:11px;color:var(--muted);margin-top:1px}

/* ── Misc ── */
.section-gap{margin-top:28px}
@media(max-width:768px){.sidebar{display:none}.main{margin-left:0}.stats-row{grid-template-columns:repeat(2,1fr)}}
</style>
"""

# ── Shared layout renderer ────────────────────────────────────────────────────
LAYOUT = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{{ page_title }} — TI Toner</title>
{{ css }}
</head>
<body>
<div class="shell">
  <aside class="sidebar">
    <div class="sb-logo">
      <div class="icon"><img src="https://media.licdn.com/dms/image/v2/D4D0BAQG0smJnZAhyhw/company-logo_200_200/company-logo_200_200/0/1689000003837/braslimpoficial_logo?e=2147483647&v=beta&t=7Pq4Tq4bXr0Z1cr4VpMETmGUD4mXZed6_xccVMK7pr8" alt="Braslimp"></div>
      <div class="brand">Braslimp<span>Controle de Toners</span></div>
    </div>
    <nav class="nav-section">
      <div class="nav-label">Menu</div>
      <a href="{{ url_for('index') }}"     class="nav-item {% if active=='inventario' %}active{% endif %}"><span class="nav-icon">📦</span> Inventário</a>
      <a href="{{ url_for('historico') }}" class="nav-item {% if active=='historico' %}active{% endif %}"><span class="nav-icon">📋</span> Histórico</a>
      <a href="{{ url_for('dashboard') }}" class="nav-item {% if active=='dashboard' %}active{% endif %}"><span class="nav-icon">📊</span> Dashboard</a>
      {% if current_user.is_admin %}
      <div class="nav-label" style="margin-top:12px">Admin</div>
      <a href="{{ url_for('usuarios') }}"  class="nav-item {% if active=='usuarios' %}active{% endif %}"><span class="nav-icon">👥</span> Usuários</a>
      {% endif %}
    </nav>
    <div class="sb-footer">
      <div class="user-chip">
        <div class="user-av">{{ current_user.nome[0] }}</div>
        <div>
          <div class="user-name">{{ current_user.nome }}</div>
          <div class="user-role">{{ 'Admin' if current_user.is_admin else 'Equipe' }}</div>
        </div>
      </div>
      <a href="{{ url_for('logout') }}" class="logout-lnk">Sair</a>
    </div>
  </aside>
  <div class="main">
    <div class="topbar">
      <div class="topbar-title">{{ page_title }}</div>
      <div class="topbar-sub">{{ page_sub }}</div>
    </div>
    <div class="content">{{ body }}</div>
  </div>
</div>
</body></html>"""

def render_page(title, sub, active, body):
    from markupsafe import Markup
    return render_template_string(
        LAYOUT,
        page_title=title, page_sub=sub, active=active,
        body=Markup(body), css=Markup(CSS),
        url_for=url_for, current_user=current_user,
    )

# ══════════════════════════════════════════════
#  Routes
# ══════════════════════════════════════════════

# ── Login ─────────────────────────────────────
LOGIN_HTML = """<!DOCTYPE html>
<html lang="pt-BR">
<head><meta charset="UTF-8"><title>Login — TI Toner</title>{{ css }}</head>
<body>
<div class="login-wrap">
  <div class="login-card">
    <div class="login-logo">
      <div class="icon"><img src="https://media.licdn.com/dms/image/v2/D4D0BAQG0smJnZAhyhw/company-logo_200_200/company-logo_200_200/0/1689000003837/braslimpoficial_logo?e=2147483647&v=beta&t=7Pq4Tq4bXr0Z1cr4VpMETmGUD4mXZed6_xccVMK7pr8" alt="Braslimp"></div>
      <div class="label">Braslimp<span>Controle de Toners · TI</span></div>
    </div>
    {% for cat,msg in msgs %}
    <div class="flash-msg flash-{{ cat }}">{{ msg }}</div>
    {% endfor %}
    <form method="POST">
      <div class="form-group">
        <label>Usuário</label>
        <input type="text" name="username" autofocus required placeholder="seu.usuario">
      </div>
      <div class="form-group">
        <label>Senha</label>
        <input type="password" name="password" required placeholder="••••••••">
      </div>
      <button type="submit" class="btn btn-primary" style="width:100%;justify-content:center;padding:9px;margin-top:4px">Entrar</button>
    </form>
  </div>
</div>
</body></html>"""

@app.route("/login", methods=["GET","POST"])
def login():
    from markupsafe import Markup
    if current_user.is_authenticated:
        return redirect(url_for("index"))
    if request.method == "POST":
        u = request.form.get("username","").strip()
        p = request.form.get("password","")
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT * FROM usuarios WHERE username=%s", (u,))
        row = fetchone(c)
        conn.close()
        if row and check_password_hash(row["password"], p):
            login_user(User(row))
            return redirect(url_for("index"))
        flash("Usuário ou senha incorretos.", "error")
    msgs = get_flashed_messages(with_categories=True)
    return render_template_string(LOGIN_HTML, css=Markup(CSS), msgs=msgs)

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))

# ── Inventário ────────────────────────────────
@app.route("/")
@login_required
def index():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM estoque ORDER BY setor")
    rows = fetchall(c)
    c.execute("SELECT COALESCE(SUM(quantidade),0) FROM estoque")
    total = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM estoque WHERE quantidade=0")
    zerados = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM estoque WHERE aguardando=1")
    aguardando = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM estoque WHERE quantidade>=1")
    ok_count = c.fetchone()[0]
    conn.close()

    dados, alerta = [], False
    for r in rows:
        st = calcular_status(r["quantidade"], r["aguardando"])
        if r["quantidade"] == 0 and r["aguardando"] == 0:
            alerta = True
        dados.append({**r, "status": st})

    zerados_count = sum(1 for d in dados if d["quantidade"]==0 and d["aguardando"]==0)
    stats = {"total": total, "zerados": zerados, "aguardando": aguardando, "ok": ok_count}

    body = render_template_string(INV_BODY,
        dados=dados, alerta=alerta, stats=stats,
        zerados_count=zerados_count, url_for=url_for,
        obs_map={d["id"]: d["observacao"] for d in dados},
        tinta_map={d["id"]: d["tinta_pct"] for d in dados})
    return render_page("Inventário", "Controle de toners em estoque", "inventario", body)

INV_BODY = """
{% if alerta %}
<div class="alert alert-danger">
  ⚠ <strong>Atenção:</strong> {{ zerados_count }} toner(s) com estoque zerado sem pedido em aberto.
</div>
{% endif %}
<div class="stats-row">
  <div class="stat"><div class="stat-label">Total em Estoque</div><div class="stat-number c-primary">{{ stats.total }}</div><div class="stat-hint">unidades</div></div>
  <div class="stat"><div class="stat-label">Setores OK</div><div class="stat-number c-ok">{{ stats.ok }}</div><div class="stat-hint">estoque normal</div></div>
  <div class="stat"><div class="stat-label">Aguardando</div><div class="stat-number c-warn">{{ stats.aguardando }}</div><div class="stat-hint">pedidos em trânsito</div></div>
  <div class="stat"><div class="stat-label">Zerados</div><div class="stat-number c-danger">{{ stats.zerados }}</div><div class="stat-hint">ação necessária</div></div>
</div>
<div class="card">
  <div class="card-header">
    <div><div class="card-title">Inventário de Toners</div><div class="card-sub">{{ dados|length }} itens cadastrados</div></div>
  </div>
  <div class="table-wrap">
  <table>
    <thead>
      <tr><th>Código</th><th>Setor / Unidade</th><th>Modelo</th><th>Qtd</th><th>Status</th><th>Nível de Tinta</th><th>Observação</th><th>Ações</th></tr>
    </thead>
    <tbody>
    {% for item in dados %}
    <tr>
      <td><span class="code">{{ item.codigo }}</span></td>
      <td><strong>{{ item.setor }}</strong></td>
      <td style="color:var(--muted)">{{ item.modelo }}</td>
      <td><span class="qty {% if item.quantidade==0 %}qty-0{% elif item.quantidade==1 %}qty-1{% else %}qty-ok{% endif %}">{{ item.quantidade }}</span></td>
      <td>
        {% if item.status=="OK" %}<span class="badge badge-ok">● OK</span>
        {% elif item.status=="Aguardando Selbetti" %}<span class="badge badge-warn">● Aguardando</span>
        {% else %}<span class="badge badge-danger">● Problema</span>{% endif %}
      </td>
      <td>
        {% if item.tinta_pct is not none %}
          <div style="display:flex;align-items:center;gap:7px;min-width:90px">
            <div style="flex:1;height:4px;background:var(--border);border-radius:2px;overflow:hidden">
              <div style="height:100%;border-radius:2px;width:{{ item.tinta_pct }}%;background:{% if item.tinta_pct <= 20 %}var(--danger){% elif item.tinta_pct <= 50 %}var(--warn){% else %}var(--ok){% endif %}"></div>
            </div>
            <span style="font-family:var(--mono);font-size:11px;font-weight:700;color:{% if item.tinta_pct <= 20 %}var(--danger){% elif item.tinta_pct <= 50 %}var(--warn){% else %}var(--ok){% endif %};white-space:nowrap;min-width:32px;text-align:right">{{ item.tinta_pct }}%</span>
            {% if item.tinta_pct <= 20 %}<span title="Crítico" style="font-size:11px;line-height:1">⚠</span>{% endif %}
          </div>
        {% else %}
          <span style="font-size:12px;color:var(--light)">—</span>
        {% endif %}
      </td>
      <td><span class="obs-text {% if not item.observacao %}obs-empty{% endif %}" title="{{ item.observacao or '' }}">{{ item.observacao if item.observacao else '—' }}</span></td>
      <td>
        <div class="action-row">
          <a href="{{ url_for('mais',    id=item.id) }}" class="act act-plus">+ Add</a>
          <a href="{{ url_for('menos',   id=item.id) }}" class="act act-minus">− Rem</a>
          <a href="{{ url_for('solicitar',id=item.id)}}" class="act act-req">Solicitar</a>
          <a href="{{ url_for('recebido', id=item.id)}}" class="act act-recv">Recebido</a>
          <a href="#" class="act act-edit" onclick="openObs({{ item.id }});return false">Obs</a>
          <a href="#" class="act act-edit" onclick="openTinta({{ item.id }});return false">🖨 Tinta</a>
        </div>
      </td>
    </tr>
    {% endfor %}
    </tbody>
  </table>
  </div>
</div>
<!-- Modal observação -->
<div class="modal-backdrop" id="obs-modal">
  <div class="modal" onclick="event.stopPropagation()">
    <div class="modal-title">✏ Editar Observação</div>
    <form id="obs-form" method="POST">
      <div class="form-group">
        <label>Observação</label>
        <textarea name="observacao" id="obs-input"
          placeholder="Ex: toner reservado, compatível com modelo X..."
          style="width:100%;min-height:80px;padding:8px 11px;border:1px solid #e3e8e3;border-radius:6px;font-size:13px;font-family:inherit;resize:vertical;outline:none;box-sizing:border-box"></textarea>
      </div>
      <div class="modal-actions">
        <button type="button" class="btn btn-ghost" onclick="closeObs()">Cancelar</button>
        <button type="submit" class="btn btn-primary">Salvar</button>
      </div>
    </form>
  </div>
</div>

<script>
var obsData = {{ obs_map | tojson }};
var tintaData = {{ tinta_map | tojson }};

function openObs(id) {
  document.getElementById('obs-form').action = '/observacao/' + id;
  document.getElementById('obs-input').value = obsData[id] || '';
  document.getElementById('obs-modal').classList.add('open');
  setTimeout(function(){ document.getElementById('obs-input').focus(); }, 50);
}
function closeObs() {
  document.getElementById('obs-modal').classList.remove('open');
}
document.getElementById('obs-modal').addEventListener('click', function(e) {
  if (e.target === this) closeObs();
});

function openTinta(id) {
  document.getElementById('tinta-form').action = '/tinta/' + id;
  var val = tintaData[id];
  document.getElementById('tinta-input').value = (val !== null && val !== undefined) ? val : '';
  updateTintaPreview();
  document.getElementById('tinta-modal').classList.add('open');
  setTimeout(function(){ document.getElementById('tinta-input').focus(); }, 50);
}
function closeTinta() {
  document.getElementById('tinta-modal').classList.remove('open');
}
function updateTintaPreview() {
  var val = parseInt(document.getElementById('tinta-input').value) || 0;
  val = Math.max(0, Math.min(100, val));
  var bar = document.getElementById('tinta-preview-bar');
  var label = document.getElementById('tinta-preview-label');
  var color = val <= 20 ? 'var(--danger)' : val <= 50 ? 'var(--warn)' : 'var(--ok)';
  bar.style.width = val + '%';
  bar.style.background = color;
  label.textContent = val + '%';
  label.style.color = color;
}
document.getElementById('tinta-modal').addEventListener('click', function(e) {
  if (e.target === this) closeTinta();
});
document.addEventListener('keydown', function(e) {
  if (e.key === 'Escape') { closeObs(); closeTinta(); }
});
</script>

<!-- Modal tinta -->
<div class="modal-backdrop" id="tinta-modal">
  <div class="modal" onclick="event.stopPropagation()">
    <div class="modal-title">🖨 Nível de Tinta</div>
    <form id="tinta-form" method="POST">
      <div class="form-group">
        <label>Percentual estimado (%)</label>
        <input type="number" name="tinta_pct" id="tinta-input"
          min="0" max="100" placeholder="Ex: 75"
          oninput="updateTintaPreview()"
          style="width:100%;padding:8px 11px;border:1px solid #e3e8e3;border-radius:6px;font-size:13px;font-family:inherit;outline:none">
      </div>
      <div style="margin-bottom:16px">
        <div style="height:10px;background:var(--border);border-radius:5px;overflow:hidden;margin-bottom:6px">
          <div id="tinta-preview-bar" style="height:100%;border-radius:5px;width:0%;background:var(--ok);transition:width .2s,background .2s"></div>
        </div>
        <div style="display:flex;justify-content:space-between;font-size:11px;color:var(--muted)">
          <span>0%</span>
          <span id="tinta-preview-label" style="font-weight:700;font-family:var(--mono)">—</span>
          <span>100%</span>
        </div>
      </div>
      <div style="font-size:11px;color:var(--muted);margin-bottom:16px;padding:8px 10px;background:var(--bg);border-radius:6px;border:1px solid var(--border)">
        🟢 Acima de 50% · 🟡 Entre 20–50% · 🔴 Abaixo de 20% (alerta crítico)
      </div>
      <div class="modal-actions">
        <button type="button" class="btn btn-ghost" onclick="closeTinta()">Cancelar</button>
        <button type="submit" class="btn btn-primary">Salvar</button>
      </div>
    </form>
  </div>
</div>
"""

# ── Ações ─────────────────────────────────────
@app.route("/mais/<int:id>")
@login_required
def mais(id):
    conn = get_db(); c = conn.cursor()
    c.execute("SELECT setor FROM estoque WHERE id=%s", (id,))
    row = fetchone(c)
    c.execute("UPDATE estoque SET quantidade=quantidade+1, aguardando=0 WHERE id=%s", (id,))
    conn.commit(); conn.close()
    registrar(id, "Adição", f"+1 unidade — {row['setor']}")
    return redirect(url_for("index"))

@app.route("/menos/<int:id>")
@login_required
def menos(id):
    conn = get_db(); c = conn.cursor()
    c.execute("SELECT setor,quantidade FROM estoque WHERE id=%s", (id,))
    row = fetchone(c)
    if row["quantidade"] > 0:
        c.execute("UPDATE estoque SET quantidade=quantidade-1 WHERE id=%s", (id,))
        conn.commit()
        registrar(id, "Retirada", f"-1 unidade — {row['setor']}")
    conn.close()
    return redirect(url_for("index"))

@app.route("/solicitar/<int:id>")
@login_required
def solicitar(id):
    conn = get_db(); c = conn.cursor()
    c.execute("SELECT setor FROM estoque WHERE id=%s", (id,))
    row = fetchone(c)
    c.execute("UPDATE estoque SET aguardando=1 WHERE id=%s", (id,))
    conn.commit(); conn.close()
    registrar(id, "Solicitação", f"Pedido enviado à Selbetti — {row['setor']}")
    return redirect("https://selbetti.com.br/")

@app.route("/recebido/<int:id>")
@login_required
def recebido(id):
    conn = get_db(); c = conn.cursor()
    c.execute("SELECT setor FROM estoque WHERE id=%s", (id,))
    row = fetchone(c)
    c.execute("UPDATE estoque SET quantidade=quantidade+1, aguardando=0 WHERE id=%s", (id,))
    conn.commit(); conn.close()
    registrar(id, "Recebimento", f"Toner recebido +1 — {row['setor']}")
    return redirect(url_for("index"))

@app.route("/observacao/<int:id>", methods=["POST"])
@login_required
def observacao(id):
    obs = request.form.get("observacao","").strip()
    conn = get_db(); c = conn.cursor()
    c.execute("SELECT setor FROM estoque WHERE id=%s", (id,))
    row = fetchone(c)
    c.execute("UPDATE estoque SET observacao=%s WHERE id=%s", (obs, id))
    conn.commit(); conn.close()
    registrar(id, "Observação", f"Obs atualizada — {row['setor']}: \"{obs}\"")
    return redirect(url_for("index"))

@app.route("/tinta/<int:id>", methods=["POST"])
@login_required
def tinta(id):
    try:
        pct = int(request.form.get("tinta_pct", 100))
        pct = max(0, min(100, pct))
    except ValueError:
        pct = None
    conn = get_db(); c = conn.cursor()
    c.execute("SELECT setor FROM estoque WHERE id=%s", (id,))
    row = fetchone(c)
    c.execute("UPDATE estoque SET tinta_pct=%s WHERE id=%s", (pct, id))
    conn.commit(); conn.close()
    registrar(id, "Nível de Tinta", f"Tinta atualizada para {pct}% — {row['setor']}")
    return redirect(url_for("index"))

# ── Histórico ─────────────────────────────────
HIST_BODY = """
<div class="card">
  <div class="card-header">
    <div><div class="card-title">Histórico de Movimentações</div><div class="card-sub">{{ registros|length }} registros recentes</div></div>
    {% if current_user.is_admin %}
    <a href="{{ url_for('limpar_historico') }}" onclick="return confirm('Limpar todo o histórico?')" class="btn btn-danger-ghost">Limpar tudo</a>
    {% endif %}
  </div>
  {% if not registros %}
    <p style="padding:24px 20px;color:var(--muted);font-size:13px">Nenhum registro ainda.</p>
  {% endif %}
  {% for r in registros %}
  <div class="h-item">
    <div class="h-dot
      {% if 'Adição' in r.acao or 'Recebimento' in r.acao %}h-dot-plus
      {% elif 'Retirada' in r.acao %}h-dot-minus
      {% elif 'Solicitação' in r.acao %}h-dot-req
      {% elif 'Observação' in r.acao %}h-dot-obs
      {% else %}h-dot-other{% endif %}"></div>
    <div style="flex:1"><div class="h-acao">{{ r.acao }}</div><div class="h-meta">{{ r.detalhe }}</div></div>
    <div style="text-align:right;flex-shrink:0">
      <div style="font-size:12px;font-weight:600;color:var(--muted)">{{ r.usuario }}</div>
      <div style="font-size:11px;color:var(--light)">{{ r.criado_em }}</div>
    </div>
  </div>
  {% endfor %}
</div>
"""

@app.route("/historico")
@login_required
def historico():
    conn = get_db(); c = conn.cursor()
    c.execute("SELECT * FROM historico ORDER BY id DESC LIMIT 200")
    rows = fetchall(c)
    conn.close()
    body = render_template_string(HIST_BODY, registros=rows,
        url_for=url_for, current_user=current_user)
    return render_page("Histórico", "Últimas movimentações registradas", "historico", body)

@app.route("/historico/limpar")
@login_required
@admin_required
def limpar_historico():
    conn = get_db(); c = conn.cursor()
    c.execute("DELETE FROM historico")
    conn.commit(); conn.close()
    return redirect(url_for("historico"))

# ── Dashboard ─────────────────────────────────
DASH_BODY = """
<style>
.kpi-row{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-bottom:20px}
.kpi{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:18px 20px;box-shadow:var(--sh)}
.kpi-label{font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.08em;color:var(--muted);margin-bottom:6px}
.kpi-val{font-family:var(--mono);font-size:36px;font-weight:700;line-height:1}
.kpi-val.kv-green{color:var(--ok)}.kpi-val.kv-warn{color:var(--warn)}.kpi-val.kv-red{color:var(--danger)}.kpi-val.kv-blue{color:var(--primary)}
.kpi-sub{font-size:11px;color:var(--muted);margin-top:5px}
.panel{background:var(--surface);border:1px solid var(--border);border-radius:10px;box-shadow:var(--sh)}
.panel-title{font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.08em;color:var(--muted);padding:14px 18px 0}
.panel-body{padding:10px 18px 16px}
.attn-item{display:flex;align-items:center;gap:10px;padding:8px 0;border-bottom:1px solid var(--border)}
.attn-item:last-child{border-bottom:none}
.attn-dot{width:7px;height:7px;border-radius:50%;flex-shrink:0}
.attn-setor{font-size:13px;font-weight:500;flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.mini-badge{font-size:10px;font-weight:700;padding:2px 7px;border-radius:4px;border:1px solid;white-space:nowrap;flex-shrink:0}
.tbar-row{display:flex;align-items:center;gap:10px;padding:6px 0;border-bottom:1px solid var(--border)}
.tbar-row:last-child{border-bottom:none}
.tbar-setor{font-size:12px;width:120px;flex-shrink:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;color:var(--text)}
.tbar-track{flex:1;height:6px;background:var(--border);border-radius:3px;overflow:hidden}
.tbar-fill{height:100%;border-radius:3px;transition:width .5s ease}
.tbar-val{font-family:var(--mono);font-size:11px;font-weight:700;width:34px;text-align:right;flex-shrink:0}
@media(max-width:900px){.kpi-row{grid-template-columns:repeat(2,1fr)}}
</style>

<div class="kpi-row">
  <div class="kpi"><div class="kpi-label">Total em Estoque</div><div class="kpi-val kv-blue">{{ total }}</div><div class="kpi-sub">{{ total_itens }} setores monitorados</div></div>
  <div class="kpi"><div class="kpi-label">Setores OK</div><div class="kpi-val kv-green">{{ ok_count }}</div><div class="kpi-sub">{{ pct_ok }}% em dia</div></div>
  <div class="kpi"><div class="kpi-label">Aguardando</div><div class="kpi-val kv-warn">{{ aguardando }}</div><div class="kpi-sub">pedidos em trânsito</div></div>
  <div class="kpi"><div class="kpi-label">Zerados</div><div class="kpi-val kv-red">{{ zerados }}</div><div class="kpi-sub">requerem ação</div></div>
</div>

<div style="display:grid;grid-template-columns:220px 1fr;gap:16px;margin-bottom:20px">
  <div class="panel" style="display:flex;flex-direction:column;align-items:center;justify-content:center;padding:28px 20px;gap:8px;text-align:center">
    <div style="font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.08em;color:var(--muted)">Saúde Geral</div>
    <div style="font-family:var(--mono);font-size:52px;font-weight:700;line-height:1;color:{% if pct_ok >= 80 %}var(--ok){% elif pct_ok >= 50 %}var(--warn){% else %}var(--danger){% endif %}">{{ pct_ok }}%</div>
    <div style="font-size:12px;color:var(--muted)">{% if pct_ok >= 80 %}Tudo certo{% elif pct_ok >= 50 %}Atenção necessária{% else %}Estado crítico{% endif %}</div>
    <div style="width:100%;height:6px;background:var(--border);border-radius:3px;overflow:hidden;margin-top:4px">
      <div style="height:100%;border-radius:3px;width:{{ pct_ok }}%;background:{% if pct_ok >= 80 %}var(--ok){% elif pct_ok >= 50 %}var(--warn){% else %}var(--danger){% endif %}"></div>
    </div>
  </div>
  <div class="panel">
    <div class="panel-title">Requer Atenção</div>
    <div class="panel-body">
      {% set attn_z = detalhes | selectattr('quantidade', 'equalto', 0) | list %}
      {% set attn_l = detalhes | selectattr('quantidade', 'equalto', 1) | list %}
      {% if not attn_z and not attn_l and not alertas_tinta and not avisos_tinta %}
        <div style="display:flex;align-items:center;gap:8px;padding:16px 0;color:var(--muted);font-size:13px">
          <span style="color:var(--ok);font-size:16px">✓</span> Nenhum problema encontrado
        </div>
      {% endif %}
      {% for d in attn_z %}
      <div class="attn-item">
        <span class="attn-dot" style="background:var(--danger)"></span>
        <span class="attn-setor">{{ d.setor }}</span>
        <span class="mini-badge" style="background:var(--danger-bg);color:var(--danger);border-color:var(--danger-bd)">Zerado</span>
      </div>
      {% endfor %}
      {% for d in alertas_tinta %}
      <div class="attn-item">
        <span class="attn-dot" style="background:var(--danger)"></span>
        <span class="attn-setor">{{ d.setor }}</span>
        <span class="mini-badge" style="background:var(--danger-bg);color:var(--danger);border-color:var(--danger-bd)">Tinta {{ d.tinta_pct }}%</span>
      </div>
      {% endfor %}
      {% for d in attn_l %}
      <div class="attn-item">
        <span class="attn-dot" style="background:var(--warn)"></span>
        <span class="attn-setor">{{ d.setor }}</span>
        <span class="mini-badge" style="background:var(--warn-bg);color:var(--warn);border-color:var(--warn-bd)">1 unidade</span>
      </div>
      {% endfor %}
      {% for d in avisos_tinta %}
      <div class="attn-item">
        <span class="attn-dot" style="background:var(--warn)"></span>
        <span class="attn-setor">{{ d.setor }}</span>
        <span class="mini-badge" style="background:var(--warn-bg);color:var(--warn);border-color:var(--warn-bd)">Tinta {{ d.tinta_pct }}%</span>
      </div>
      {% endfor %}
    </div>
  </div>
</div>

{% set com_tinta = detalhes | selectattr('tinta_pct') | list %}
{% if com_tinta %}
<div class="panel">
  <div class="panel-title">Nível de Tinta por Setor</div>
  <div class="panel-body">
    {% for d in com_tinta | sort(attribute='tinta_pct') %}
    <div class="tbar-row">
      <div class="tbar-setor" title="{{ d.setor }}">{{ d.setor }}</div>
      <div class="tbar-track">
        <div class="tbar-fill" style="width:{{ d.tinta_pct }}%;background:{% if d.tinta_pct<=20 %}var(--danger){% elif d.tinta_pct<=50 %}var(--warn){% else %}var(--ok){% endif %}"></div>
      </div>
      <div class="tbar-val" style="color:{% if d.tinta_pct<=20 %}var(--danger){% elif d.tinta_pct<=50 %}var(--warn){% else %}var(--ok){% endif %}">{{ d.tinta_pct }}%</div>
    </div>
    {% endfor %}
  </div>
</div>
{% endif %}
"""

@app.route("/dashboard")
@login_required
def dashboard():
    conn = get_db(); c = conn.cursor()
    c.execute("SELECT COALESCE(SUM(quantidade),0) FROM estoque")
    total = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM estoque WHERE quantidade=0 AND aguardando=0")
    zerados = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM estoque WHERE aguardando=1")
    aguardando = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM estoque WHERE quantidade>=1")
    ok_count = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM estoque")
    total_itens = c.fetchone()[0]
    c.execute("SELECT id,setor,quantidade,tinta_pct FROM estoque ORDER BY quantidade ASC, setor ASC")
    detalhes = fetchall(c)
    conn.close()
    pct_ok       = round(ok_count  / total_itens * 100) if total_itens else 0
    pct_problema = round(zerados   / total_itens * 100) if total_itens else 0
    alertas_tinta = [d for d in detalhes if d["tinta_pct"] is not None and d["tinta_pct"] <= 20]
    avisos_tinta  = [d for d in detalhes if d["tinta_pct"] is not None and 20 < d["tinta_pct"] <= 50]
    body = render_template_string(DASH_BODY,
        total=total, zerados=zerados, aguardando=aguardando, ok_count=ok_count,
        total_itens=total_itens, detalhes=detalhes, pct_ok=pct_ok, pct_problema=pct_problema,
        alertas_tinta=alertas_tinta, avisos_tinta=avisos_tinta)
    return render_page("Dashboard", "Visão geral do estoque", "dashboard", body)

# ── Usuários (admin) ──────────────────────────
USR_BODY = """
<div class="card">
  <div class="card-header">
    <div class="card-title">Gerenciar Usuários</div>
    <button class="btn btn-primary" onclick="document.getElementById('novo-modal').classList.add('open')">+ Novo usuário</button>
  </div>
  <div class="table-wrap">
  <table>
    <thead><tr><th>Usuário</th><th>Nome</th><th>Perfil</th><th></th></tr></thead>
    <tbody>
    {% for u in usuarios %}
    <tr>
      <td><span class="code">{{ u.username }}</span></td>
      <td>{{ u.nome }}</td>
      <td>{% if u.is_admin %}<span class="badge badge-primary">Admin</span>{% else %}<span class="badge">Equipe</span>{% endif %}</td>
      <td style="text-align:right">
        {% if u.id != current_user.id %}
        <a href="{{ url_for('excluir_usuario',id=u.id) }}"
           onclick="return confirm('Excluir {{ u.username }}?')" class="act act-minus">Excluir</a>
        {% endif %}
      </td>
    </tr>
    {% endfor %}
    </tbody>
  </table>
  </div>
</div>
<div class="modal-backdrop" id="novo-modal">
  <div class="modal">
    <div class="modal-title">Novo Usuário</div>
    <form method="POST" action="{{ url_for('criar_usuario') }}">
      <div class="form-group"><label>Usuário (login)</label><input type="text" name="username" required placeholder="nome.sobrenome"></div>
      <div class="form-group"><label>Nome completo</label><input type="text" name="nome" required placeholder="João Silva"></div>
      <div class="form-group"><label>Senha</label><input type="password" name="password" required placeholder="mínimo 6 caracteres"></div>
      <div class="form-group"><label>Perfil</label>
        <select name="is_admin"><option value="0">Equipe</option><option value="1">Administrador</option></select>
      </div>
      <div class="modal-actions">
        <button type="button" class="btn btn-ghost" onclick="document.getElementById('novo-modal').classList.remove('open')">Cancelar</button>
        <button type="submit" class="btn btn-primary">Criar</button>
      </div>
    </form>
  </div>
</div>
<script>document.getElementById('novo-modal').addEventListener('click',function(e){if(e.target===this)this.classList.remove('open')})</script>
"""

@app.route("/usuarios")
@login_required
@admin_required
def usuarios():
    conn = get_db(); c = conn.cursor()
    c.execute("SELECT * FROM usuarios ORDER BY nome")
    rows = fetchall(c)
    conn.close()
    body = render_template_string(USR_BODY, usuarios=rows,
        url_for=url_for, current_user=current_user)
    return render_page("Usuários", "Gerenciamento de acesso", "usuarios", body)

@app.route("/usuarios/criar", methods=["POST"])
@login_required
@admin_required
def criar_usuario():
    username = request.form.get("username","").strip()
    nome     = request.form.get("nome","").strip()
    password = request.form.get("password","")
    is_admin = int(request.form.get("is_admin", 0))
    if len(password) < 6:
        return redirect(url_for("usuarios"))
    try:
        conn = get_db(); c = conn.cursor()
        c.execute(
            "INSERT INTO usuarios (username,password,nome,is_admin) VALUES (%s,%s,%s,%s)",
            (username, generate_password_hash(password), nome, is_admin)
        )
        conn.commit(); conn.close()
    except Exception:
        pass
    return redirect(url_for("usuarios"))

@app.route("/usuarios/excluir/<int:id>")
@login_required
@admin_required
def excluir_usuario(id):
    conn = get_db(); c = conn.cursor()
    c.execute("DELETE FROM usuarios WHERE id=%s", (id,))
    conn.commit(); conn.close()
    return redirect(url_for("usuarios"))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)