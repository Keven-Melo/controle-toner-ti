from flask import Flask, render_template_string, redirect
import sqlite3

app = Flask(__name__)

DADOS_INICIAIS = [
    ("2IO9", "Almoxarifado", "-", 1, 0),
    ("2IA6", "Aquiraz", "-", 1, 0),
    ("2IO8", "Aracati", "-", 1, 0),
    ("IYA8", "Doc. Ambiental", "-", 0, 1),
    ("2GS1", "MTR", "-", 0, 1),
    ("2IP4", "Operacional", "-", 1, 0),
    ("2IP7", "Solda", "-", 1, 0),
    ("2IP3", "Comercial", "-", 1, 0),
    ("2IP8", "Compras", "-", 1, 0),
    ("2IP9", "Diretoria", "-", 1, 0),
    ("2IP5", "Licitação", "-", 1, 0),
    ("2IQ1", "Manutenção", "-", 1, 0),
    ("2IP2", "QSMS", "-", 1, 0),
    ("2MS6", "Setor Pessoal", "-", 1, 0),
    ("-", "Braslimp", "LaserJet", 1, 0),
    ("2IO7", "-", "Color CMYK", 0, 0),
    ("9I55", "GP (New Printer)", "CMYK", 0, 0),
    ("MQW5", "Pecém", "-", 3, 0),
]

def init_db():
    conn = sqlite3.connect("banco.db")
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS estoque (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo TEXT,
            setor TEXT,
            modelo TEXT,
            quantidade INTEGER,
            aguardando INTEGER DEFAULT 0
        )
    """)

    cursor.execute("SELECT COUNT(*) FROM estoque")
    if cursor.fetchone()[0] == 0:
        cursor.executemany("""
            INSERT INTO estoque (codigo, setor, modelo, quantidade, aguardando)
            VALUES (?, ?, ?, ?, ?)
        """, DADOS_INICIAIS)
        conn.commit()

    conn.close()

init_db()

def calcular_status(qtd, aguardando):
    if qtd >= 1:
        return "OK"
    if qtd == 0 and aguardando == 1:
        return "Aguardando Selbetti"
    return "PROBLEMA"

HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Controle de Toner Backup</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
</head>
<body class="bg-light">

<div class="container mt-4">

<h2 class="mb-4">🖨 Controle de Toner Backup - Estoque TI</h2>

<div class="card">
<div class="card-body">
<table class="table table-striped table-hover">
<thead class="table-dark">
<tr>
<th>Código</th>
<th>Unidade</th>
<th>Modelo</th>
<th>Estoque</th>
<th>Status</th>
<th>Ações</th>
</tr>
</thead>
<tbody>
{% for item in dados %}
<tr>
<td>{{item.codigo}}</td>
<td>{{item.setor}}</td>
<td>{{item.modelo}}</td>
<td><strong>{{item.quantidade}}</strong></td>
<td>
{% if item.status == "OK" %}
<span class="badge bg-success">🟢 OK</span>
{% elif item.status == "Aguardando Selbetti" %}
<span class="badge bg-warning text-dark">🟡 Aguardando</span>
{% else %}
<span class="badge bg-danger">🔴 PROBLEMA</span>
{% endif %}
</td>
<td>
<a href="/mais/{{item.id}}" class="btn btn-sm btn-success">+</a>
<a href="/menos/{{item.id}}" class="btn btn-sm btn-danger">-</a>
<a href="/solicitar/{{item.id}}" class="btn btn-sm btn-warning">Solicitar</a>
<a href="/recebido/{{item.id}}" class="btn btn-sm btn-primary">Recebido</a>
</td>
</tr>
{% endfor %}
</tbody>
</table>
</div>
</div>

</div>
</body>
</html>
"""

@app.route("/")
def index():
    conn = sqlite3.connect("banco.db")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM estoque")
    rows = cursor.fetchall()
    conn.close()

    dados = []
    for r in rows:
        status = calcular_status(r[4], r[5])
        dados.append({
            "id": r[0],
            "codigo": r[1],
            "setor": r[2],
            "modelo": r[3],
            "quantidade": r[4],
            "status": status
        })

    return render_template_string(HTML, dados=dados)

@app.route("/mais/<int:id>")
def mais(id):
    conn = sqlite3.connect("banco.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE estoque SET quantidade = quantidade + 1 WHERE id=?", (id,))
    cursor.execute("UPDATE estoque SET aguardando = 0 WHERE id=?", (id,))
    conn.commit()
    conn.close()
    return redirect("/")

@app.route("/menos/<int:id>")
def menos(id):
    conn = sqlite3.connect("banco.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE estoque SET quantidade = quantidade - 1 WHERE id=?", (id,))
    conn.commit()
    conn.close()
    return redirect("/")

@app.route("/solicitar/<int:id>")
def solicitar(id):
    conn = sqlite3.connect("banco.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE estoque SET aguardando = 1 WHERE id=?", (id,))
    conn.commit()
    conn.close()
    return redirect("/")

@app.route("/recebido/<int:id>")
def recebido(id):
    conn = sqlite3.connect("banco.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE estoque SET quantidade = 1, aguardando = 0 WHERE id=?", (id,))
    conn.commit()
    conn.close()
    return redirect("/")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)