from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    send_file,
    jsonify,
    session,
)
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func, extract

import datetime
from datetime import timedelta

import os
import csv
import io

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from babel.numbers import format_currency
from matplotlib.figure import Figure
from io import BytesIO

from extensions import db, mail
from emails import send_report

from dateutil.relativedelta import relativedelta
from matplotlib.ticker import MaxNLocator

import numpy as np

app = Flask(__name__)

current_date = datetime.date.today()
recipients = os.getenv("REPORT_RECIPIENTS", "acftrein@gmail.com").split(",")


def gerar_png_grafico(meses_labels, totais, considerados, titulo):
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.plot(meses_labels, totais, marker="o", color="blue", label="Faturamento")
    ax.plot(meses_labels, considerados, marker="s", color="green", label="NFS-e")
    ax.set_ylim(0, max(max(totais), max(considerados)) * 1.1)
    ax.set_title(titulo)
    # ax.set_ylabel("R$")
    ax.legend()
    ax.yaxis.set_major_locator(MaxNLocator(nbins=8))
    ax.grid(True, which="major", linestyle="--", linewidth=0.5, alpha=0.7)
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()

    buf = BytesIO()
    plt.savefig(buf, format="png")
    buf.seek(0)
    plt.close()
    return send_file(buf, mimetype="image/png")


@app.route("/grafico_12meses")
def grafico_12_meses():
    meses, totais, considerados = obter_totais_por_periodo(12)
    # print("DEBUG (12_meses):", meses, totais, considerados)
    return gerar_png_grafico(meses, totais, considerados, "Últimos 12 meses")


@app.route("/grafico_ano")
def grafico_ano_corrente():
    hoje = datetime.date.today()
    ano_atual = hoje.year
    mes_atual = hoje.month - 1  # EXCLUI o mês atual

    if mes_atual == 0:
        return gerar_png_grafico([], [], [], "Ano corrente")  # Nenhum mês fechado ainda

    meses = []
    totais = []
    totais_considerados = []

    for i in range(1, mes_atual + 1):
        ref = datetime.date(ano_atual, i, 1)
        inicio = ref
        fim = ref + relativedelta(months=1)

        registros = Payment.query.filter(
            Payment.data >= inicio, Payment.data < fim
        ).all()

        total = sum(r.valor for r in registros)
        total_considerado = sum(r.valor for r in registros if r.considerar)

        meses.append(f"{ref.month:02d}/{ref.year}")
        totais.append(round(total, 2))
        totais_considerados.append(round(total_considerado, 2))

    return gerar_png_grafico(meses, totais, totais_considerados, "Ano corrente")


@app.route("/grafico_3meses")
def grafico_3_meses():
    meses, totais, considerados = obter_totais_por_periodo(3)
    # print("DEBUG (3_meses):", meses, totais, considerados)
    return gerar_png_grafico(meses, totais, considerados, "Últimos 3 meses")


@app.route("/grafico_atual")
def grafico_atual():
    hoje = date.today()
    inicio = hoje.replace(day=1)
    fim = inicio + relativedelta(months=1)

    registros = Payment.query.filter(Payment.data >= inicio, Payment.data < fim).all()
    total = sum(r.valor for r in registros)
    total_considerado = sum(r.valor for r in registros if r.considerar)

    labels = [f"{inicio.month:02d}/{inicio.year}"]
    valores = [round(total, 2), round(total_considerado, 2)]

    # Cria gráfico em barras agrupadas
    fig, ax = plt.subplots(figsize=(4, 4))
    categories = ["Faturamento", "NFS-e"]
    x = np.arange(len(categories))
    width = 0.9

    ax.bar(x, valores, width, color=["blue", "green"])
    ax.set_xticks(x)
    ax.set_xticklabels(categories, rotation=45, ha="right")
    # ax.set_ylabel("R$")
    ax.set_title(f"Atual ({labels[0]})")
    ax.grid(axis="y", linestyle="--", alpha=0.6)
    plt.tight_layout()

    buf = BytesIO()
    fig.savefig(buf, format="png")
    buf.seek(0)
    plt.close(fig)
    return send_file(buf, mimetype="image/png")


def obter_totais_por_periodo(periodo):
    # hoje = datetime.date.today().replace(day=1)
    hoje = datetime.date.today().replace(day=1) - relativedelta(months=1)
    meses = []
    totais = []
    totais_considerados = []

    for i in range(periodo - 1, -1, -1):
        ref = hoje - relativedelta(months=i)
        inicio = ref
        fim = ref + relativedelta(months=1)

        registros = Payment.query.filter(
            Payment.data >= inicio, Payment.data < fim
        ).all()

        total = sum(r.valor for r in registros)
        total_considerado = sum(r.valor for r in registros if r.considerar)

        meses.append(f"{ref.month:02d}/{ref.year}")
        totais.append(round(total, 2))
        totais_considerados.append(round(total_considerado, 2))

    return meses, totais, totais_considerados


@app.route("/grafico/<int:meses>")
def grafico_periodo(meses):
    meses_labels, totais, considerados = obter_totais_por_periodo(meses)
    print("DEBUG:", meses_labels, totais, considerados)

    fig, ax = plt.subplots(figsize=(6, 4))

    ax.plot(meses_labels, totais, marker="o", color="gray", label="Total bruto")
    ax.plot(meses_labels, considerados, marker="s", color="green", label="Considerados")

    ax.set_ylim(0, max(max(totais), max(considerados)) * 1.1)
    ax.set_title(f"Faturamento últimos {meses} meses")
    # ax.set_ylabel("R$")
    ax.yaxis.set_major_locator(MaxNLocator(nbins=10))
    ax.legend()
    ax.grid(True, which="major", linestyle="--", linewidth=0.5, alpha=0.7)

    plt.xticks(rotation=45, ha="right")

    plt.tight_layout()

    buf = BytesIO()
    plt.savefig(buf, format="png")
    buf.seek(0)
    plt.close()
    return send_file(buf, mimetype="image/png")


def obter_totais_ultimos_3_meses():
    hoje = datetime.date.today()
    meses = []
    totais = []
    totais_considerados = []

    for i in range(2, -1, -1):  # últimos 3 meses: mais antigo → atual
        mes_ano = hoje - timedelta(days=i * 30)
        ano = mes_ano.year
        mes = mes_ano.month

        total = (
            db.session.query(func.sum(Payment.valor))
            .filter(extract("year", Payment.data) == ano)
            .filter(extract("month", Payment.data) == mes)
            .scalar()
            or 0
        )

        total_considerado = (
            db.session.query(func.sum(Payment.valor))
            .filter(extract("year", Payment.data) == ano)
            .filter(extract("month", Payment.data) == mes)
            .filter(Payment.considerar == True)
            .scalar()
            or 0
        )

        meses.append(f"{mes:02d}/{ano}")
        totais.append(round(total, 2))
        totais_considerados.append(round(total_considerado, 2))

    return meses, totais, totais_considerados


@app.route("/grafico-recentes")
def grafico_recente():
    meses, totais, totais_considerados = obter_totais_ultimos_3_meses()

    fig, ax = plt.subplots(figsize=(6, 4))

    # Tons de verde para as barras
    tons_verde = ["#66bb6a", "#43a047", "#2e7d32"]
    ax.bar(meses, totais, color=tons_verde)

    # Linha para os valores considerados
    ax.plot(
        meses,
        totais_considerados,
        color="#f21c1c",
        marker="o",
        linestyle="-",
        linewidth=2,
        label="Considerados",
    )

    # Rótulos para os pontos da linha
    for i, val in enumerate(totais_considerados):
        ax.text(
            i,
            val + 0.5,
            f"R$ {val:,.2f}",
            ha="center",
            va="bottom",
            fontsize=8,
            color="#f21c1c",
        )

    # Rótulos para barras
    for i, v in enumerate(totais):
        ax.text(i, v + 0.5, f"R$ {v:,.2f}", ha="center", fontsize=8)

    ax.set_ylabel("R$ Faturado")
    ax.set_title("Faturamento últimos 3 meses")
    ax.legend()

    plt.tight_layout()
    img = BytesIO()
    plt.savefig(img, format="png")
    img.seek(0)
    plt.close()
    return send_file(img, mimetype="image/png")


@app.template_filter("format_currency")
def format_currency_filter(value):
    return format_currency(value, "BRL", locale="pt_BR")


# app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'mudar_isso')
# app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
# SECRET_KEY=4f3c7d9f2b87c8432e1c6a23a88f1a65
app.config["SECRET_KEY"] = "4f3c7d9f2b87c8432e1c6a23a88f1a65"

# app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///database.db"
# app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:////home/atrein/apmontanari/instance/database.db'

# Caminho local
local_db = "sqlite:///database.db"

# Caminho do servidor (PythonAnywhere)
server_db = "sqlite:////home/atrein/apmontanari/instance/database.db"

# Detecta se está rodando local ou na web
if "PYTHONANYWHERE_DOMAIN" in os.environ:
    app.config["SQLALCHEMY_DATABASE_URI"] = server_db
else:
    app.config["SQLALCHEMY_DATABASE_URI"] = local_db

app.config["MAIL_SERVER"] = "smtp.gmail.com"
app.config["MAIL_PORT"] = 587
app.config["MAIL_USE_TLS"] = True
app.config["MAIL_USERNAME"] = "acftrein@gmail.com"  # troque pelo seu
app.config["MAIL_PASSWORD"] = "uhzi hnky zxts ofxf"  # senha do app ou normal
app.config["MAIL_DEFAULT_SENDER"] = "acftrein@gmail.com"  # mesmo remetente

db.init_app(app)
mail.init_app(app)


class Payment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    cpf = db.Column(db.String(11), nullable=False)
    valor = db.Column(db.Float, nullable=False)
    data = db.Column(db.Date, nullable=False)
    considerar = db.Column(db.Boolean, default=True)  # NOVO


from datetime import date, timedelta
from dateutil.relativedelta import relativedelta


@app.route("/", methods=["GET", "POST"])
def index():
    # Lista de nomes únicos para autocomplete
    nomes = [row[0] for row in db.session.query(Payment.nome).distinct().all()]

    # Gera lista dos últimos 12 meses no formato "YYYY-MM"
    hoje = datetime.date.today().replace(day=1)
    competencias_disponiveis = [
        (hoje - relativedelta(months=i)).strftime("%Y-%m") for i in range(13, -1, -1)
    ]

    # Define competência padrão (mês atual)
    if (
        "competencia" not in session
        or session["competencia"] not in competencias_disponiveis
    ):
        session["competencia"] = competencias_disponiveis[-1]

    if request.method == "POST" and "competencia" in request.form:
        if request.form["competencia"] in competencias_disponiveis:
            session["competencia"] = request.form["competencia"]
        return redirect(url_for("index"))

    competencia = session["competencia"]
    ano, mes = map(int, competencia.split("-"))
    inicio = date(ano, mes, 1)
    fim = inicio + relativedelta(months=1)

    registros = Payment.query.filter(Payment.data >= inicio, Payment.data < fim).all()
    total = sum(r.valor for r in registros)
    total_marked = sum(r.valor for r in registros if r.considerar)

    return render_template(
        "index.html",
        registros=registros,
        current_date=datetime.date.today().isoformat(),
        competencia=competencia,
        nomes=nomes,
        total=total,
        total_marked=total_marked,
        mes_atual=datetime.date.today().month,
        competencias=competencias_disponiveis,  # usado no dropdown
    )


@app.route("/registrar", methods=["POST"])
def registrar():
    nome = request.form["nome"]
    nome = request.form["nome"].strip().upper()
    cpf = request.form["cpf"].strip()
    valor_str = (
        request.form["valor"]
        .replace("R$", "")
        .replace(".", "")
        .replace(",", ".")
        .strip()
    )
    valor = float(valor_str)
    data_str = request.form["data"]
    # data = datetime.strptime(data_str, "%Y-%m-%d").date()
    data = datetime.datetime.strptime(data_str, "%Y-%m-%d").date()
    novo = Payment(nome=nome, cpf=cpf, valor=valor, data=data)
    db.session.add(novo)
    db.session.commit()
    flash("Lançamento registrado!")
    return redirect(url_for("index"))


@app.route("/report")
def report():
    competencia = session.get("competencia", datetime.date.today().strftime("%Y-%m"))
    ano, mes = map(int, competencia.split("-"))
    inicio = datetime.date(ano, mes, 1)
    fim = datetime.date(ano + int(mes / 12), (mes % 12) + 1, 1)

    pags = Payment.query.filter(Payment.data >= inicio, Payment.data < fim).all()

    csv_buf = io.StringIO()
    writer = csv.writer(csv_buf, delimiter=";")
    writer.writerow(["nome", "cpf", "valor", "data", "considerar"])
    for p in pags:
        writer.writerow(
            [
                p.nome,
                p.cpf,
                f"{p.valor:.2f}",
                p.data.strftime("%Y-%m-%d"),
                "Sim" if p.considerar else "Não",
            ]
        )
    csv_data = csv_buf.getvalue()

    send_report(pags, csv_data)
    flash("Relatório enviado com sucesso!")
    return redirect(url_for("index"))


@app.route("/atualizar", methods=["POST"])
def atualizar():
    # print(request.form)

    competencia = session.get("competencia", datetime.date.today().strftime("%Y-%m"))
    ano, mes = map(int, competencia.split("-"))
    inicio = datetime.date(ano, mes, 1)
    fim = datetime.date(ano + int(mes / 12), (mes % 12) + 1, 1)

    registros = Payment.query.filter(Payment.data >= inicio, Payment.data < fim).all()

    for r in registros:
        marcado = f"considerar_{r.id}" in request.form
        r.considerar = marcado
    db.session.commit()
    flash("Registro(s) atualizado(s)!")
    return redirect(url_for("index"))


@app.route("/excluir/<int:id>", methods=["POST"])
def excluir(id):
    registro = Payment.query.get_or_404(id)
    db.session.delete(registro)
    db.session.commit()
    flash(f"Registro do cliente {registro.nome} excluído com sucesso.")
    return redirect(url_for("index"))


@app.route("/get-cpf")
def get_cpf():
    nome = request.args.get("nome")
    if not nome:
        return jsonify({"cpf": ""})

    registro = Payment.query.filter_by(nome=nome).order_by(Payment.data.desc()).first()
    if registro:
        return jsonify({"cpf": registro.cpf})
    return jsonify({"cpf": ""})


@app.route("/cpf-por-nome")
def cpf_por_nome():
    nome = request.args.get("nome")
    registro = Payment.query.filter_by(nome=nome).first()
    return jsonify({"cpf": registro.cpf if registro else ""})


if __name__ == "__main__":
    with app.app_context():  # ⬅️ Isso cria o contexto necessário
        db.create_all()
        print("Caminho real do banco:", os.path.abspath("database.db"))
    app.run(debug=True, host="0.0.0.0")
