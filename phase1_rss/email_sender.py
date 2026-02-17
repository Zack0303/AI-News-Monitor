from __future__ import annotations

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any


def render_digest_html(items: list[dict[str, Any]], generated_at: str) -> str:
    rows = []
    for idx, item in enumerate(items, start=1):
        rows.append(
            (
                f"<h3>{idx}. {item.get('title', 'Untitled')}</h3>"
                f"<p><b>Score:</b> {item.get('total_score', 0)}</p>"
                f"<p><b>Category:</b> {item.get('category', 'general')}</p>"
                f"<p>{item.get('summary_cn', 'No summary')}</p>"
                f"<p><a href=\"{item.get('link', '#')}\">{item.get('link', '#')}</a></p>"
                "<hr/>"
            )
        )
    content = "\n".join(rows) if rows else "<p>No relevant items today.</p>"
    return (
        "<html><body>"
        "<h2>AI News Monitor - Daily Digest</h2>"
        f"<p>Generated at: {generated_at}</p>"
        f"{content}"
        "</body></html>"
    )


def send_digest_email(
    *,
    smtp_host: str,
    smtp_port: int,
    smtp_user: str,
    smtp_password: str,
    mail_from: str,
    mail_to: str,
    subject: str,
    html_body: str,
) -> None:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = mail_from
    msg["To"] = mail_to
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as server:
        server.starttls()
        server.login(smtp_user, smtp_password)
        server.sendmail(mail_from, [mail_to], msg.as_string())
