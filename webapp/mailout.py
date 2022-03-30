#!/usr/bin/env python
# -*- coding: utf-8 -*-

""":Mod: mailout

:Synopsis:

:Author:
    servilla

:Created:
    5/24/18
"""
import smtplib

import daiquiri
import unicodedata
from webapp.config import Config


logger = daiquiri.getLogger("mailout: " + __name__)


def normalize_text(text):
    normalized = unicodedata.normalize('NFKD', text)
    normalized = "".join([c for c in normalized if not unicodedata.combining(c)])
    return normalized


def send_mail(subject, msg, to, sender_name=None, sender_email=None):
    success = False

    # Convert subject and msg to byte array
    body = (
        # FIXME - smtplib, as we're currently using it, fails if the body of the message contains
        #  accented characters. For now, we will convert to unaccented characters.
        ("Subject: " + normalize_text(subject) + "\n").encode()
        + ("To: " + ",".join(to) + "\n").encode()
        + ("From: " + Config.HOVER_MAIL + "\n\n").encode()
        # FIXME - smtplib, as we're currently using it, fails if the body of the message contains
        #  accented characters. For now, we will convert to unaccented characters.
        + (normalize_text(msg) + "\n").encode()
    )

    smtpObj = smtplib.SMTP_SSL("mail.hover.com", 465)
    logger.warn("Created smtpObj")
    try:
        smtpObj.ehlo()
        smtpObj.login(Config.HOVER_MAIL, Config.HOVER_PASSWORD)
        smtpObj.sendmail(from_addr=Config.HOVER_MAIL, to_addrs=to, msg=body)
        success = True
        log_msg = f"Sending email to: {to}"
        if sender_name and sender_email:
            log_msg += f"  Sender: {sender_name} - {sender_email}"
        logger.warn(log_msg)
        logger.warn(f"Email body: {body}")
    except Exception as e:
        response = "Sending email failed - " + str(e)
        logger.error(response)
    finally:
        smtpObj.quit()
    return success


def main():
    return 0


if __name__ == "__main__":
    main()
