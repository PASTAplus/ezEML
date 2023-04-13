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
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr
import smtplib
import ssl

import daiquiri

from webapp.config import Config


logger = daiquiri.getLogger(__name__)


def send_mail(subject, msg, to, to_name=None):
    """
    Returns True if email is sent successfully, otherwise a string containing the error message is returned.
    So, the return value should be tested by the caller as follows:
        if send_mail(subject, msg, to) is True:
    to avoid a false positive when there is an error message, which will be truthy.
    """
    message = MIMEMultipart("alternative")
    message["Subject"] = subject
    # The from identity needs to be known to the relay server
    message["From"] = formataddr((Config.FROM_NAME, Config.FROM))
    if to and to_name:
        message["To"] = formataddr((to_name, to))
    else:
        message["To"] = formataddr((Config.TO_NAME, Config.TO))

    part = MIMEText(msg, "plain")
    message.attach(part)

    try:
        with smtplib.SMTP(Config.RELAY_HOST, Config.RELAY_TLS_PORT) as server:
            server.starttls()
            server.login(Config.RELAY_USER, Config.RELAY_PASSWORD)
            # TODO - TEMP - Temporarily comment out to avoid sending emails
            server.sendmail(Config.FROM, to, message.as_string())

        log_msg = f"Sending email to: {to}"
        logger.info(log_msg)
        logger.info(f"Email message: {message.as_string()}")
        return True
    except smtplib.SMTPException as e:
        logger.error(e)
        if e.smtp_error:
            return e.smtp_error.decode()
        else:
            return 'Email failed to send'
    except Exception as e:
        logger.error(e)
        return 'Email failed to send'
