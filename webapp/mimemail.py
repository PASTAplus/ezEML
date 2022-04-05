#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
:Mod: mimemail

:Synopsis:
    Provide MIME Multipart email support (see: https://realpython.com/python-send-email/)

:Author:
    servilla

:Created:
    4/3/22
"""
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import daiquiri

from webapp.config import Config


logger = daiquiri.getLogger(__name__)


def send_mail(subject, msg, to, sender_name=None, sender_email=None) -> bool:

    message = MIMEMultipart("alternative")
    message["Subject"] = subject
    message["From"] = Config.HOVER_MAIL
    message["To"] = Config.HOVER_MAIL

    part = MIMEText(msg, "plain")
    message.attach(part)

    context = ssl.create_default_context()
    try:
        with smtplib.SMTP_SSL("mail.hover.com", 465, context=context) as server:
            server.login(Config.HOVER_MAIL, Config.HOVER_PASSWORD)
            server.sendmail(
                Config.HOVER_MAIL, Config.HOVER_MAIL, message.as_string()
            )
        log_msg = f"Sending email to: {to}"
        if sender_name and sender_email:
            log_msg += f"  Sender: {sender_name} - {sender_email}"
        logger.info(log_msg)
        logger.info(f"Email message: {message.as_string()}")
        return True
    except Exception as e:
        logger.error(e)
        return False
