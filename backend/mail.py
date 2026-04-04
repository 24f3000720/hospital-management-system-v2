from datetime import datetime
from email.message import EmailMessage
import mimetypes
from pathlib import Path
import os
import re
import smtplib

from flask import current_app


def _slugify(value):
    slug = re.sub(r'[^a-zA-Z0-9]+', '-', value.strip().lower()).strip('-')
    return slug or 'message'


def ensure_runtime_dir(relative_path):
    runtime_dir = Path(current_app.root_path) / relative_path
    runtime_dir.mkdir(parents=True, exist_ok=True)
    return runtime_dir


def send_mail_message(subject, recipients, html_body, text_body='', category='general', attachment_path=None):
    sender = current_app.config.get('MAIL_SENDER', 'no-reply@localhospital.app')

    smtp_host = os.getenv('SMTP_HOST')
    smtp_port = int(os.getenv('SMTP_PORT', '587'))
    smtp_username = os.getenv('SMTP_USERNAME')
    smtp_password = os.getenv('SMTP_PASSWORD')
    smtp_use_tls = os.getenv('SMTP_USE_TLS', 'true').lower() in ('1', 'true', 'yes')

    if smtp_host:
        message = EmailMessage()
        message['Subject'] = subject
        message['From'] = sender
        message['To'] = ', '.join(recipients)
        message.set_content(text_body or subject)
        message.add_alternative(html_body, subtype='html')

        if attachment_path:
            attachment_file = Path(attachment_path)
            if attachment_file.exists():
                mime_type, _ = mimetypes.guess_type(str(attachment_file))
                maintype, subtype = (mime_type or 'application/octet-stream').split('/', 1)
                message.add_attachment(
                    attachment_file.read_bytes(),
                    maintype=maintype,
                    subtype=subtype,
                    filename=attachment_file.name
                )

        with smtplib.SMTP(smtp_host, smtp_port) as server:
            if smtp_use_tls:
                server.starttls()
            if smtp_username and smtp_password:
                server.login(smtp_username, smtp_password)
            server.send_message(message)

        return {
            'delivery': 'smtp',
            'recipients': recipients,
            'subject': subject,
        }

    outbox_dir = ensure_runtime_dir(current_app.config.get('MAIL_OUTBOX_DIR', 'instance/outbox'))
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    base_name = f'{timestamp}_{_slugify(category)}_{_slugify(subject)}'

    html_path = outbox_dir / f'{base_name}.html'
    meta_path = outbox_dir / f'{base_name}.txt'

    html_path.write_text(html_body, encoding='utf-8')
    meta_lines = [
        f'Subject: {subject}',
        f'From: {sender}',
        f'To: {", ".join(recipients)}',
        f'Category: {category}',
    ]

    if text_body:
        meta_lines.extend(['', text_body])

    if attachment_path:
        meta_lines.extend(['', f'Attachment: {attachment_path}'])

    meta_path.write_text('\n'.join(meta_lines), encoding='utf-8')

    return {
        'delivery': 'outbox',
        'html_path': str(html_path),
        'meta_path': str(meta_path),
        'recipients': recipients,
        'subject': subject,
    }
