from typing import NamedTuple
from webapp.views.curator_workflow.model import (
    WorkflowPackage, Workflow
)
from webapp.views.collaborations.db_session import db_session

class WorkflowValues(NamedTuple):
    revision_of: str
    pid_status: str
    eval_status: str
    upload_status: str
    assigned_pid: str
    pid_entered_in_eml: str
    eval_transaction_id: str
    report: str
    ready_to_upload: bool
    create_transaction_id: str
    landing_page_link: str


def create_package(owner_login: str, package_name: str, session=None):
    package = WorkflowPackage(
        owner_login=owner_login,
        package_name=package_name)
    session.add(package)
    session.flush()
    return package

def get_package(owner_login: str, package_name: str, session=None):
    with db_session(session) as session:
        package = WorkflowPackage.query.filter_by(owner_login=owner_login, package_name=package_name).first()
        if not package:
            package = create_package(owner_login, package_name, session)
        return package

def create_workflow(workflow_type: str, owner_login: str, package_name: str, session=None):
    with db_session(session) as session:
        package = get_package(owner_login, package_name, session)
        workflow = Workflow(
            package_id=package.package_id,
            workflow_type=workflow_type,
            pid_status='',
            eval_status='',
            upload_status=''
        )
        session.add(workflow)
        session.flush()
        return workflow

def get_workflow(workflow_type: str, owner_login:str, package_name:str, create_if_not_found:bool=True, session=None):
    with db_session(session) as session:
        package = get_package(owner_login, package_name, session)
        workflow = Workflow.query.filter_by(workflow_type=workflow_type, package_id=package.package_id).first()
        if not workflow and create_if_not_found:
            workflow = create_workflow(workflow_type, owner_login, package_name, session)
        return workflow


def remove_workflow(workflow_type:str, owner_login:str, package_name:str, session=None):
    # If staging or production workflows exist, they are removed.
    with db_session(session) as session:
        if workflow_type == 'STAGING':
            staging = get_workflow('STAGING', owner_login, package_name, create_if_not_found=False, session=session)
            if staging:
                session.delete(staging)
        elif workflow_type == 'PRODUCTION':
            production = get_workflow('PRODUCTION', owner_login, package_name, create_if_not_found=False, session=session)
            if production:
                session.delete(production)

def remove_workflows(owner_login:str, package_name:str, session=None):
    # If staging or production workflows exist, they are removed.
    with db_session(session) as session:
        staging = get_workflow('STAGING', owner_login, package_name, create_if_not_found=False, session=session)
        if staging:
            session.delete(staging)
        production = get_workflow('PRODUCTION', owner_login, package_name, create_if_not_found=False, session=session)
        if production:
            session.delete(production)


def update_workflow(workflow_type:str, owner_login:str, package_name:str, revision_of:str=None,
                    pid_status:str=None, eval_status:str=None, upload_status:str=None,
                    assigned_pid:str=None, pid_entered_in_eml:str=None,
                    eval_transaction_id:str=None, report:str=None, ready_to_upload:bool=None,
                    create_transaction_id:str=None, landing_page_link:str=None,
                    session=None):
    with db_session(session) as session:
        workflow = get_workflow(workflow_type, owner_login, package_name, session)
        if revision_of is not None:
            workflow.revision_of = revision_of
        if pid_status is not None:
            workflow.pid_status = pid_status
        if eval_status is not None:
            workflow.eval_status = eval_status
        if upload_status is not None:
            workflow.upload_status = upload_status
        if assigned_pid:
            workflow.assigned_pid = assigned_pid
        if pid_entered_in_eml:
            workflow.pid_entered_in_eml = pid_entered_in_eml
        if eval_transaction_id is not None:
            workflow.eval_transaction_id = eval_transaction_id
        if report is not None:
            workflow.report = report
        if ready_to_upload is not None:
            workflow.ready_to_upload = ready_to_upload
        if create_transaction_id is not None:
            workflow.create_transaction_id = create_transaction_id
        if landing_page_link is not None:
            workflow.landing_page_link = landing_page_link


def get_workflow_values(workflow_type:str, owner_login:str, package_name:str, session=None):
    with db_session(session) as session:
        workflow_values = WorkflowValues('', '', '', '', '', '', '', '', False, '', '')
        workflow = get_workflow(workflow_type, owner_login, package_name, create_if_not_found=False, session=session)
        if workflow:
            workflow_values = WorkflowValues(
                workflow.revision_of if workflow.revision_of else '',
                workflow.pid_status if workflow.pid_status else '',
                workflow.eval_status if workflow.eval_status else '',
                workflow.upload_status if workflow.upload_status else '',
                workflow.assigned_pid if workflow.assigned_pid else '',
                workflow.pid_entered_in_eml if workflow.pid_entered_in_eml else '',
                workflow.eval_transaction_id if workflow.eval_transaction_id else '',
                workflow.report if workflow.report else '',
                workflow.ready_to_upload if workflow.ready_to_upload else False,
                workflow.create_transaction_id if workflow.create_transaction_id else '',
                workflow.landing_page_link if workflow.landing_page_link else '')
        return workflow_values


def get_eval_in_progress_workflows():
    in_progress = []
    with db_session(None) as session:
        for workflow_type in ('STAGING', 'PRODUCTION'):
            workflows = Workflow.query.filter_by(workflow_type=workflow_type).all()
            for workflow in workflows:
                if workflow.eval_status == 'EVAL_IN_PROGRESS':
                    in_progress.append(workflow)
    return in_progress


def get_upload_in_progress_workflows():
    in_progress = []
    with db_session(None) as session:
        for workflow_type in ('STAGING', 'PRODUCTION'):
            workflows = Workflow.query.filter_by(workflow_type=workflow_type).all()
            for workflow in workflows:
                if workflow.upload_status == 'UPLOAD_IN_PROGRESS':
                    in_progress.append(workflow)
    return in_progress
