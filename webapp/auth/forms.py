  #!/usr/bin/env python
# -*- coding: utf-8 -*-

""":Mod: forms.py

:Synopsis:

:Author:
    servilla
    costa

:Created:
    3/6/18
"""

from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField, \
    SelectField
from wtforms.validators import DataRequired, Email, EqualTo, Length


class LoginForm(FlaskForm):
    domain_choices = [('edi', 'EDI'), ('lter', 'LTER')]
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    domain = SelectField('Domain', choices=domain_choices)
    submit = SubmitField('Sign In')


class CreateLdapUser(FlaskForm):
    uid = StringField('User ID', validators=[DataRequired()])
    gn = StringField('Given name', validators=[DataRequired()])
    sn = StringField('Surname', validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired(), Email(), 
                    EqualTo('confirm_email', message='Emails must match')])
    confirm_email = StringField('Confirm Email', 
                                validators=[DataRequired(), Email()])


class ResetPasswordInit(FlaskForm):
    uid = StringField('User ID', validators=[DataRequired()])


class ResetLdapPassword(FlaskForm):
    password = PasswordField('Password', validators=[DataRequired(), 
                EqualTo('confirm_password', message='Passwords must match'),
        Length(min=8, message='Password must have a minimum of 8 characters')])
    confirm_password = PasswordField('Confirm Password', 
                                validators=[DataRequired(),
        Length(min=8, message='Password must have a minimum of 8 characters')])


class ChangeLdapPassword(FlaskForm):
    uid = StringField('User ID', validators=[DataRequired()])
    password = PasswordField('Old Password', validators=[DataRequired()])
    new_password = PasswordField('New Password', validators=[DataRequired(), 
            EqualTo('confirm_new_password', message='Passwords must match'),
        Length(min=8, message='Password must have a minimum of 8 characters')])
    confirm_new_password = PasswordField('Confirm New Password', 
                                validators=[DataRequired(),
        Length(min=8, message='Password must have a minimum of 8 characters')])


class ModifyLdapUserInit(FlaskForm):
    uid = StringField('User ID', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])


class ModifyLdapUser(FlaskForm):
    password = PasswordField('Password', validators=[DataRequired()])
    gn = StringField('Given name', validators=[DataRequired()])
    sn = StringField('Surname', validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired(), Email(), 
                    EqualTo('confirm_email', message='Emails must match')])
    confirm_email = StringField('Confirm Email', 
                                validators=[DataRequired(), Email()])


class DeleteLdapUser(FlaskForm):
    uid = StringField('User ID', validators=[DataRequired()])