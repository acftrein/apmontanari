from flask import Flask, render_template, request, redirect, url_for, flash, send_file, jsonify, session
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func, extract

import datetime
import os
import csv
import io

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from babel.numbers import format_currency
from matplotlib.figure import Figure
from io import BytesIO

from extensions import db, mail
from emails import send_report

app = Flask(__name__)

current_date = datetime.date.today()
recipients = os.getenv("REPORT_RECIPIENTS", "acftrein@gmail.com").split(",")

def obter_totais_ultimos_3_meses():
    hoje = datetime.date.today()
    meses = []
    totais = []

    for i in range(2, -1, -1):  # últimos 3 meses: mais antigo → atual
        mes_ano = hoje - datetime.timedelta(days=i*30)
        ano = mes_ano.year
        mes = mes_ano.month

        total = db.session.query(func.sum(Payment.valor))\
            .filter(extract('year', Payment.data) == ano)\
            .filter(extract('month', Payment.data) == mes)\
            .scalar() or 0

        meses.append(f'{mes:02d}/{ano}')
        totais.append(round(total, 2))

    return meses, totais

@app.route("/grafico-recentes")
def grafico_recente():
    meses, totais = obter_totais_ultimos_3_meses()

    fig, ax = plt.subplots(figsize=(6, 4))
    ax.bar(meses, totais, color=["#2185d0", "#f2711c", "#21ba45"])  # azul, laranja, verde
    ax.set_ylabel("R$ Faturado")
    ax.set_title("Faturamento últimos 3 meses")

    for i, v in enumerate(totais):
        ax.text(i, v + 0.1, f"R$ {v:,.2f}", ha='center', fontsize=8)

    plt.tight_layout()
    img = BytesIO()
    plt.savefig(img, format='png')
    img.seek(0)
    plt.close()
    return send_file(img, mimetype='image/png')

@app.template_filter("format_currency")
def format_currency_filter(value):
    return format_currency(value, "BRL", locale="pt_BR")


# app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'mudar_isso')
# app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
# SECRET_KEY=4f3c7d9f2b87c8432e1c6a23a88f1a65
app.config["SECRET_KEY"] = "4f3c7d9f2b87c8432e1c6a23a88f1a65"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///database.db"
# app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:////home/atrein/apmontanari/instance/database.db'

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


@app.route("/", methods=["GET", "POST"])
def index():

    # Pega nomes únicos para autocomplete
    #nomes = [n[0] for n in db.session.query(Payment.nome).distinct().all()]
    nomes = [row[0] for row in db.session.query(Payment.nome).distinct().all()]

    if "competencia" not in session:
        session["competencia"] = datetime.date.today().strftime("%Y-%m")

    if request.method == "POST" and "competencia" in request.form:
        session["competencia"] = request.form["competencia"]
        return redirect(url_for("index"))

    competencia = session["competencia"]
    ano, mes = map(int, competencia.split("-"))
    inicio = datetime.date(ano, mes, 1)
    fim = datetime.date(ano + int(mes / 12), (mes % 12) + 1, 1)

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
    flash("Marcações atualizadas!")
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
