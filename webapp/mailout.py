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

from webapp.config import Config


logger = daiquiri.getLogger("mailout: " + __name__)


def send_mail(subject, msg, to, sender_name=None, sender_email=None):
    success = False

    # Convert subject and msg to byte array
    body = (
        ("Subject: " + subject + "\n").encode()
        + ("To: " + ",".join(to) + "\n").encode()
        + ("From: " + Config.HOVER_MAIL + "\n\n").encode()
        + (msg + "\n").encode()
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
