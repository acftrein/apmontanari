def send_report(payments, csv_data):
    from flask_mail import Message
    from extensions import mail
    from flask import session
    from datetime import datetime
    import os

    # Obtem a competência (ex: "2025-06") da sessão
    competencia = session.get('competencia', datetime.today().strftime('%Y-%m'))
    ano, mes = competencia.split('-')
    mes_nome = datetime.strptime(mes, "%m").strftime("%B").capitalize()

    # Lista de destinatários
    recipients = os.getenv('REPORT_RECIPIENTS', 'acftrein@gmail.com').split(',')
    print("DESTINATÁRIOS:", recipients)

    if not recipients or recipients == ['']:
        raise ValueError("Nenhum destinatário definido em REPORT_RECIPIENTS.")

    # Monta e-mail
    msg = Message(
        subject=f"Relatório de Pagamentos – {mes_nome}/{ano}",
        recipients=recipients,
        body=f"Segue o relatório de {len(payments)} pagamentos do mês de {mes_nome}/{ano}."
    )

    msg.attach(
        f"relatorio_{mes_nome}_{ano}.csv",
        "text/csv",
        csv_data.encode('utf-8')
    )

    mail.send(msg)
