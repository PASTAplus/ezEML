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


def send_mail(subject, msg, to):
    success = False

    # Convert subject and msg to byte array
    body = (
        ("Subject: " + subject + "\n").encode()
        + ("To: " + ",".join(to) + "\n").encode()
        + ("From: " + Config.HOVER_MAIL + "\n\n").encode()
        + (msg + "\n").encode()
    )

    smtpObj = smtplib.SMTP("mail.hover.com", 587)
    try:
        smtpObj.ehlo()
        smtpObj.starttls()
        smtpObj.login(Config.HOVER_MAIL, Config.HOVER_PASSWORD)
        smtpObj.sendmail(from_addr=Config.HOVER_MAIL, to_addrs=to, msg=body)
        success = True
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
