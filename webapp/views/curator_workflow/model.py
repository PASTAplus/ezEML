
from webapp import db

# Database models

class WorkflowPackage(db.Model):
    __bind_key__ = 'curator_workflow'
    __tablename__ = 'packages'
    package_id = db.Column(db.Integer, primary_key=True)
    owner_login = db.Column(db.Text, unique=False, nullable=False)  # the ezEML ID for the owner
    package_name = db.Column(db.Text, unique=False, nullable=False)

    __table_args__ = (db.UniqueConstraint('owner_login', 'package_name', name='_package_uc'),)

class Workflow(db.Model):
    __bind_key__ = 'curator_workflow'
    __tablename__ = 'workflows'
    id = db.Column(db.Integer, primary_key=True)
    package_id = db.Column(db.Integer, db.ForeignKey('packages.package_id'), nullable=False)
    workflow_type = db.Column(
        db.Text,
        db.CheckConstraint(
            "workflow_type IN ('STAGING','PRODUCTION')"
        ),
        nullable=False
    )
    entered_pid = db.Column(db.Text)
    pid_status = db.Column(
        db.Text,
        db.CheckConstraint(
            "pid_status IN ("
            "'',"
            "'PID_ASSIGNED',"
            "'PID_ENTERED_IN_EML'"
            ")"
        ),
        nullable=False
    )
    eval_status = db.Column(
        db.Text,
        db.CheckConstraint(
            "eval_status IN ("
            "'',"
            "'EVAL_IN_PROGRESS',"
            "'ERROR_REPORT',"
            "'EVAL_REPORT'"
            ")"
        ),
        nullable=False
    )
    upload_status = db.Column(
        db.Text,
        db.CheckConstraint(
            "upload_status IN ("
            "'',"
            "'UPLOAD_IN_PROGRESS',"
            "'UPLOAD_ERROR',"
            "'UPLOAD_COMPLETED'"
            ")"
        ),
        nullable=False
    )
    assigned_pid = db.Column(db.Text)
    pid_entered_in_eml = db.Column(db.Text)
    eval_transaction_id = db.Column(db.Text)
    report = db.Column(db.Text)
    has_errors = db.Column(db.Boolean)
    ready_to_upload = db.Column(db.Boolean)
    create_transaction_id = db.Column(db.Text)
    landing_page_link = db.Column(db.Text)


