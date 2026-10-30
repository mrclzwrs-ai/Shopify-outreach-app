def send_real_email(smtp_server, smtp_port, sender_email, sender_password, sender_name, recipient_email, subject, body_text):
    # Verwijder eventuele per ongeluk getypte spaties
    clean_email = sender_email.strip()
    clean_password = sender_password.replace(" ", "").strip()
    port = int(smtp_port)

    msg = MIMEMultipart()
    msg['From'] = f"{sender_name} <{clean_email}>"
    msg['To'] = recipient_email
    msg['Subject'] = subject
    msg.attach(MIMEText(body_text, 'plain', 'utf-8'))
    
    try:
        if port == 465:
            # Directe SSL-verbinding voor Google Workspace / Gmail
            server = smtplib.SMTP_SSL(smtp_server, port, timeout=20)
        else:
            # Standaard TLS-verbinding
            server = smtplib.SMTP(smtp_server, port, timeout=20)
            server.starttls()
            
        server.login(clean_email, clean_password)
        server.send_message(msg)
        server.quit()
        return True, "Verzonden"
    except Exception as ex:
        return False, str(ex)
)
b
