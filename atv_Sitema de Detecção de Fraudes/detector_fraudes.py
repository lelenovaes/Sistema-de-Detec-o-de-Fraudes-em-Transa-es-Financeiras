import re
import json
from collections import defaultdict
from datetime import datetime

ARQUIVO_LOG = "logs_transacoes.txt"

# Extrai o valor de um campo específico da linha do log 
# Exemplo: ID:12345|TIPO:PIX|VALOR:R$ 500,00

def parse_campo(linha, campo): 
    match = re.search(rf'{campo}:([^|]+)', linha)
    return match.group(1).strip() if match else ""

# Converte um valor monetário em formato texto para float
def extrair_valor(valor_str):
    try:
        return float(valor_str.replace("R$", "").replace(".", "").replace(",", ".").strip())
    except:
        return 0.0

# Transforma uma linha do arquivo em um dicionário.

def analisar_transacao(linha):
    if linha.startswith("#") or not linha.strip():
        return None
    dt_match = re.match(r'\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]', linha)
    if not dt_match:
        return None
    data_hora = datetime.strptime(dt_match.group(1), "%Y-%m-%d %H:%M:%S")

    # Cria o dicionário da transação
    t = {
        "id":           parse_campo(linha, "ID"),
        "tipo":         parse_campo(linha, "TIPO"),
        "origem_nome":  parse_campo(linha, "ORIGEM_NOME"),
        "origem_doc":   parse_campo(linha, "ORIGEM_DOC"),
        "destino_nome": parse_campo(linha, "DESTINO_NOME"),
        "destino_doc":  parse_campo(linha, "DESTINO_DOC"),
        "valor_str":    parse_campo(linha, "VALOR"),
        "banco_origem": parse_campo(linha, "BANCO_ORIGEM"),
        "banco_destino":parse_campo(linha, "BANCO_DESTINO"),
        "dispositivo":  parse_campo(linha, "DISPOSITIVO"),
        "localizacao":  parse_campo(linha, "LOCALIZACAO"),
        "descricao":    parse_campo(linha, "DESCRICAO"),
        "status":       parse_campo(linha, "STATUS"),
        "hora":         data_hora.hour,
        "data_hora":    dt_match.group(1),
    }
    t["valor"] = extrair_valor(t["valor_str"])
    return t

# calcula quantos pontos de fraude uma transação recebe.
def pontuar(t, todas):
    pontos = 0
    motivos = []

    # 1. Campos obrigatórios vazios (25 pts)

    campos_vazios = []
    if not t["origem_doc"]:  campos_vazios.append("CPF/CNPJ de origem")
    if not t["destino_doc"]: campos_vazios.append("CPF/CNPJ de destino")
    if not t["localizacao"]: campos_vazios.append("localização")
    if not t["descricao"]:   campos_vazios.append("descrição")
    if campos_vazios:
        pontos += 25
        motivos.append(("Dados incompletos", f"Campos ausentes: {', '.join(campos_vazios)}"))

    # 2. Horário suspeito 00h–04h (20 pts)

    if 0 <= t["hora"] < 4:
        pontos += 20
        motivos.append(("Horário suspeito", f"Transação às {t['hora']:02d}h (madrugada)"))

    # 3. Valor muito alto > R$50k (35 pts) ou > R$20k (15 pts)

    if t["valor"] > 50000:
        pontos += 35
        motivos.append(("Valor atípico elevado", f"R$ {t['valor']:,.2f} — acima de R$ 50.000"))
    elif t["valor"] > 20000:
        pontos += 15
        motivos.append(("Valor alto", f"R$ {t['valor']:,.2f} — acima de R$ 20.000"))

    # 4. Destinatário offshore / ECOMMERCE GLOBAL (45 pts)

    palavras_suspeitas = ["OFFSHORE", "ECOMMERCE GLOBAL"]
    for p in palavras_suspeitas:
        if p in t["destino_nome"].upper():
            pontos += 45
            motivos.append(("Destinatário offshore", f"Destino: '{t['destino_nome']}' — entidade de alto risco"))
            break

    # 5. Banco destino 380 sem ser offshore declarado (15 pts)

    if t["banco_destino"] == "380":
        for p in palavras_suspeitas:
            if p in t["destino_nome"].upper():
                break
        else:
            pontos += 15
            motivos.append(("Banco de risco", "Banco destino 380 — vinculado a operações suspeitas"))

    # 6. Status FALHA (20 pts)

    if t["status"] == "FALHA":
        pontos += 20
        motivos.append(("Transação com falha", "Status FALHA — possível tentativa de fraude bloqueada"))

    # 7. Tentativas repetidas mesmo doc+destino em ≤5 min (25 pts)

    dt_atual = datetime.strptime(t["data_hora"], "%Y-%m-%d %H:%M:%S")
    repeticoes = 0
    for outra in todas:
        if outra["id"] == t["id"]:
            continue
        if (outra["origem_doc"] == t["origem_doc"] and
                outra["destino_doc"] == t["destino_doc"] and
                t["origem_doc"]):
            dt_outra = datetime.strptime(outra["data_hora"], "%Y-%m-%d %H:%M:%S")
            if abs((dt_atual - dt_outra).total_seconds()) <= 300:
                repeticoes += 1
    if repeticoes > 0:
        pontos += 25
        motivos.append(("Tentativas repetidas", f"{repeticoes} transação(ões) idêntica(s) em ≤5 minutos (possível teste de cartão)"))

    # 8. Descrição incompatível com tipo SAQUE (20 pts)

    desc = t["descricao"].lower()
    if t["tipo"] == "SAQUE" and any(p in desc for p in ["compra", "pagamento", "farmacia", "supermercado"]):
        pontos += 20
        motivos.append(("Descrição inconsistente com tipo", f"SAQUE descrito como '{t['descricao']}'"))

# LIMITE, MESMO QUE TENHA 140 PONTOS = 100%
    pct = min(pontos, 100)
    if pct <= 30:   nivel = "BAIXO"
    elif pct <= 60: nivel = "MÉDIO"
    else:           nivel = "ALTO"

    return pct, nivel, motivos

# ── Leitura do arquivo log──────────────────────────────────────────────────────────────────
with open(ARQUIVO_LOG, encoding="utf-8") as f:
    linhas = f.readlines()

# criação da lista de transações

transacoes = [t for t in (analisar_transacao(l) for l in linhas) if t]

# Calcula risco de cada transação

for t in transacoes:
    pct, nivel, motivos = pontuar(t, transacoes)
    t["risco_pct"] = pct
    t["nivel"] = nivel
    t["motivos"] = motivos

# filtra possíveis fraudes (mantem so médias e altas)

fraudes = [t for t in transacoes if t["nivel"] in ("MÉDIO", "ALTO")]

# Conta quantas vezes cada motivo apareceu.

contagem_tipos = defaultdict(int)
for t in fraudes:
    for (categoria, _) in t["motivos"]:
        contagem_tipos[categoria] += 1

labels = list(contagem_tipos.keys())
valores_pizza = list(contagem_tipos.values())

# ── monta a tabela HTML ─────────────────────────────────────────────────────────────────────
linhas_tabela = ""
for t in sorted(fraudes, key=lambda x: x["risco_pct"], reverse=True):
    motivos_html = "<br>".join(f"• <b>{c}</b>: {d}" for c, d in t["motivos"])
    badge = f'<span class="badge {"alto" if t["nivel"] == "ALTO" else "medio"}">{t["nivel"]}</span>'
    linhas_tabela += f"""
    <tr>
        <td>{t['id']}</td>
        <td>{t['data_hora']}</td>
        <td>{t['tipo'].replace('_',' ')}</td>
        <td>{t['origem_nome']}</td>
        <td>{t['destino_nome']}</td>
        <td>R$ {t['valor']:,.2f}</td>
        <td><b>{t['risco_pct']}%</b></td>
        <td>{badge}</td>
        <td class="motivos">{motivos_html}</td>
    </tr>"""

total = len(transacoes)
n_fraudes = len(fraudes)
n_alto = sum(1 for t in fraudes if t["nivel"] == "ALTO")
n_medio = sum(1 for t in fraudes if t["nivel"] == "MÉDIO")

html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Detecção de Fraudes — Transações Financeiras</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: 'Segoe UI', sans-serif; background: #0f1117; color: #e2e8f0; min-height: 100vh; }}
  header {{ background: linear-gradient(135deg, #1a1f2e, #16213e); padding: 2rem 2.5rem; border-bottom: 3px solid #e53e3e; }}
  header h1 {{ font-size: 1.9rem; color: #fff; letter-spacing: -0.5px; }}
  header p {{ color: #a0aec0; margin-top: 0.4rem; font-size: 0.88rem; }}
  .stats {{ display: flex; gap: 1rem; padding: 1.5rem 2.5rem; flex-wrap: wrap; }}
  .card {{ background: #1a1f2e; border-radius: 10px; padding: 1.2rem 1.8rem; flex: 1; min-width: 140px; border-left: 4px solid; }}
  .card.total {{ border-color: #4a90d9; }} .card.fraude {{ border-color: #e53e3e; }}
  .card.alto {{ border-color: #fc4444; }} .card.medio {{ border-color: #f6ad55; }}
  .card .num {{ font-size: 2.2rem; font-weight: bold; line-height: 1; }}
  .card .label {{ color: #a0aec0; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 1px; margin-top: 0.3rem; }}
  .chart-section {{ background: #1a1f2e; margin: 0 2.5rem 1.5rem; border-radius: 12px; padding: 2rem; display: flex; flex-direction: column; align-items: center; }}
  .chart-section h2 {{ margin-bottom: 1.5rem; font-size: 1.1rem; color: #e2e8f0; align-self: flex-start; }}
  #pizza {{ max-height: 360px; max-width: 600px; }}
  .table-section {{ margin: 0 2.5rem 3rem; }}
  .table-section h2 {{ margin-bottom: 1rem; font-size: 1.1rem; }}
  .filter-bar {{ margin-bottom: 0.8rem; display: flex; gap: 0.8rem; flex-wrap: wrap; }}
  input[type=text] {{ background: #1a1f2e; border: 1px solid #2d3748; color: #e2e8f0; padding: 0.5rem 1rem; border-radius: 6px; flex: 1; min-width: 200px; outline: none; }}
  select {{ background: #1a1f2e; border: 1px solid #2d3748; color: #e2e8f0; padding: 0.5rem 1rem; border-radius: 6px; outline: none; cursor: pointer; }}
  .table-wrapper {{ overflow-x: auto; border-radius: 10px; border: 1px solid #2d3748; }}
  table {{ width: 100%; border-collapse: collapse; background: #1a1f2e; font-size: 0.82rem; }}
  th {{ background: #0d1320; padding: 0.75rem 0.8rem; text-align: left; color: #718096; text-transform: uppercase; font-size: 0.7rem; letter-spacing: 1px; }}
  td {{ padding: 0.7rem 0.8rem; border-bottom: 1px solid #1e2a3a; vertical-align: top; }}
  tr:last-child td {{ border-bottom: none; }}
  tr:hover td {{ background: #1e2a3a; }}
  .badge {{ padding: 0.2rem 0.65rem; border-radius: 20px; font-size: 0.72rem; font-weight: bold; white-space: nowrap; }}
  .badge.alto {{ background: #63171b; color: #fc8181; border: 1px solid #fc8181; }}
  .badge.medio {{ background: #5c340a; color: #f6ad55; border: 1px solid #f6ad55; }}
  .motivos {{ font-size: 0.77rem; color: #a0aec0; line-height: 1.7; max-width: 350px; }}
  .motivos b {{ color: #76e4f7; }}
</style>
</head>
<body>
<header>
  <h1>🔍 Sistema de Detecção de Fraudes Financeiras</h1>
  <p>Análise de {total} transações — Período: 01/04/2026 a 25/05/2026 | Fraudes detectadas (risco ≥ 31%): <strong style="color:#fc8181">{n_fraudes}</strong></p>
</header>

<div class="stats">
  <div class="card total"><div class="num">{total}</div><div class="label">Transações analisadas</div></div>
  <div class="card fraude"><div class="num">{n_fraudes}</div><div class="label">Fraudes detectadas</div></div>
  <div class="card alto"><div class="num">{n_alto}</div><div class="label">Risco Alto (&gt;60%)</div></div>
  <div class="card medio"><div class="num">{n_medio}</div><div class="label">Risco Médio (31–60%)</div></div>
</div>

<div class="chart-section">
  <h2>Tipos de Fraude Detectados</h2>
  <canvas id="pizza"></canvas>
</div>

<div class="table-section">
  <h2>Operações Fraudulentas</h2>
  <div class="filter-bar">
    <input type="text" id="filtro" onkeyup="filtrar()" placeholder="Buscar por ID, nome, tipo...">
    <select id="filtroNivel" onchange="filtrar()">
      <option value="">Todos os níveis</option>
      <option value="ALTO">ALTO</option>
      <option value="MÉDIO">MÉDIO</option>
    </select>
  </div>
  <div class="table-wrapper">
    <table id="tb">
      <thead>
        <tr>
          <th>ID</th><th>Data / Hora</th><th>Tipo</th><th>Origem</th><th>Destino</th>
          <th>Valor</th><th>Risco</th><th>Nível</th><th>Motivos</th>
        </tr>
      </thead>
      <tbody>{linhas_tabela}</tbody>
    </table>
  </div>
</div>

<script>
new Chart(document.getElementById('pizza').getContext('2d'), {{
  type: 'pie',
  data: {{
    labels: {json.dumps(labels, ensure_ascii=False)},
    datasets: [{{
      data: {json.dumps(valores_pizza)},
      backgroundColor: ['#e53e3e','#f6ad55','#4a90d9','#68d391','#b794f4','#76e4f7','#fc8181','#fbb6ce','#9ae6b4'],
      borderColor: '#0f1117',
      borderWidth: 3
    }}]
  }},
  options: {{
    plugins: {{
      legend: {{ labels: {{ color: '#e2e8f0', padding: 14, font: {{ size: 13 }} }} }},
      tooltip: {{ callbacks: {{ label: c => ` ${{c.label}}: ${{c.raw}} ocorrências` }} }}
    }}
  }}
}});

function filtrar() {{
  const txt = document.getElementById('filtro').value.toLowerCase();
  const nv  = document.getElementById('filtroNivel').value;
  document.querySelectorAll('#tb tbody tr').forEach(tr => {{
    const ok = tr.textContent.toLowerCase().includes(txt) &&
               (!nv || tr.querySelector('.badge').textContent.trim() === nv);
    tr.style.display = ok ? '' : 'none';
  }});
}}
</script>
</body>
</html>"""

# Salva o relatório

with open("relatorio_fraudes.html", "w", encoding="utf-8") as f:
    f.write(html)

print(f"Total: {total} | Fraudes: {n_fraudes} | ALTO: {n_alto} | MÉDIO: {n_medio}")
print("Tipos:", dict(contagem_tipos))
