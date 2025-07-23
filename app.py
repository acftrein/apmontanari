from flask import Flask, session, render_template, request, redirect, url_for, flash
from flask import jsonify
from extensions import db, mail
from datetime import datetime
import csv, io, os
from emails import send_report

recipients = os.getenv("REPORT_RECIPIENTS", "acftrein@gmail.com").split(",")

app = Flask(__name__)

from babel.numbers import format_currency
from datetime import date

current_date = date.today().isoformat()


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
    nomes = [n[0] for n in db.session.query(Payment.nome).distinct().all()]

    if "competencia" not in session:
        session["competencia"] = date.today().strftime("%Y-%m")

    if request.method == "POST" and "competencia" in request.form:
        session["competencia"] = request.form["competencia"]
        return redirect(url_for("index"))

    competencia = session["competencia"]
    ano, mes = map(int, competencia.split("-"))
    inicio = date(ano, mes, 1)
    fim = date(ano + int(mes / 12), (mes % 12) + 1, 1)

    registros = Payment.query.filter(Payment.data >= inicio, Payment.data < fim).all()

    return render_template(
        "index.html",
        registros=registros,
        current_date=date.today().isoformat(),
        competencia=competencia,
        nomes=nomes,
    )


@app.route("/registrar", methods=["POST"])
def registrar():
    nome = request.form["nome"]
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
    data = datetime.strptime(data_str, "%Y-%m-%d").date()
    novo = Payment(nome=nome, cpf=cpf, valor=valor, data=data)
    db.session.add(novo)
    db.session.commit()
    flash("Lançamento registrado!")
    return redirect(url_for("index"))


@app.route("/report")
def report():
    competencia = session.get("competencia", date.today().strftime("%Y-%m"))
    ano, mes = map(int, competencia.split("-"))
    inicio = date(ano, mes, 1)
    fim = date(ano + int(mes / 12), (mes % 12) + 1, 1)

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

    competencia = session.get("competencia", date.today().strftime("%Y-%m"))
    ano, mes = map(int, competencia.split("-"))
    inicio = date(ano, mes, 1)
    fim = date(ano + int(mes / 12), (mes % 12) + 1, 1)

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
