from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import (
    current_user, login_required
)
from markupsafe import escape

from webapp.home.utils.hidden_buttons import non_saving_hidden_buttons_decorator
from webapp.pages import *
from webapp.home.home_utils import log_error, log_info
from webapp.home.views import get_helps, set_current_page, get_back_url
from webapp.views.collaborations.db_session import db_session

from webapp.views.curator_workflow.forms import CuratorWorkflowForm

from webapp.views.curator_workflow.handle_requests import (
    PastaEnvironment,
    check_existence,
    create_reservation,
    delete_reservation,
    evaluate_data_package,
    upload_data_package,
    get_error_report,
    get_evaluate_report,
    portal_url_for_environment,
    url_for_environment
)
from webapp.views.curator_workflow.workflows import (
    update_workflow,
    WorkflowValues,
    get_workflow,
    get_workflow_values,
    get_eval_in_progress_workflows,
    get_upload_in_progress_workflows,
    remove_workflow
)

workflow_bp = Blueprint('workflow', __name__, template_folder='templates')


@workflow_bp.route('/curator_workflow/<filename>', methods=['GET', 'POST'])
@login_required
@non_saving_hidden_buttons_decorator
def curator_workflow(filename=None):
    """
    Handle the Curator Workflow page.

    This page is available only to admins and data_curators.
    """
    import webapp.auth.user_data as user_data
    from webapp.home.utils.load_and_save import load_eml
    from webapp.home.utils.create_nodes import create_title, create_data_package_id, create_pubinfo

    def log_preamble():
        return f'Curator workflow:  - curator={current_user._cname}, package={filename} - '

    def check_revision_of_value(form, pasta_environment: PastaEnvironment):
        retval = None
        revision_of = form.revision_of.data

        if not revision_of:
            flash('Enter a value for "Revision of"')
        else:
            # Check format of revision_of
            substrings = revision_of.split('.')
            if len(substrings) == 2:
                revision_of += '.0'
                substrings = revision_of.split('.')
            if len(substrings) != 3:
                flash('Invalid value for "Revision of"', 'error')
            else:
                scope, identifier, revision = revision_of.split('.')
                if scope.lower() != 'edi':
                    flash('Scope must be "edi"', 'error')
                elif not identifier.isdigit():
                    flash('Identifier must be numeric', 'error')
                elif not revision.isdigit():
                    flash('Revision must be numeric', 'error')
                else:
                    new_revision = str(int(revision) + 1)
                    retval = f'{scope}.{identifier}.{new_revision}'
                    status, text = check_existence(pasta_environment, scope, identifier, new_revision)
                    if 200 <= status < 300:
                        flash(f'Revision {retval} already exists. Try again.')
                        retval = None
        return retval

    def pasta_environment_from_workflow_type(workflow_type):
        if workflow_type == 'STAGING':
            return PastaEnvironment.STAGING
        else:
            return PastaEnvironment.PRODUCTION

    def handle_reserve_pid(workflow_type, workflow_form):
        if workflow_form.new_or_revision.data == 'New':
            remove_workflow(workflow_type, owner_login, package_name=filename)
            scope = 'edi'  # We always use edi scope
            status, identifier = create_reservation(pasta_environment_from_workflow_type(workflow_type), scope)
            if 200 <= status < 300:
                reserve_package_id = f'{scope}.{identifier}.1'
                log_info(f'{log_preamble()} {workflow_type.lower()}_reserve - created reservation {reserve_package_id}')
                update_workflow(workflow_type, owner_login, package_name=filename,
                                revision_of='', pid_status='PID_ASSIGNED', eval_status='', upload_status='',
                                assigned_pid=reserve_package_id)
            else:
                log_error(f'{log_preamble()} {workflow_type.lower()}_reserve returns status {status}')
        else:
            new_revision = check_revision_of_value(workflow_form, pasta_environment_from_workflow_type(workflow_type))
            if new_revision is not None:
                remove_workflow(workflow_type, owner_login, package_name=filename)
                log_info(f'{log_preamble()} creating revision {new_revision}')
                update_workflow(workflow_type, owner_login, package_name=filename, revision_of=workflow_form.revision_of.data,
                                pid_status='PID_ASSIGNED', eval_status='', upload_status='',
                                assigned_pid=new_revision)

    def handle_apply_pid(workflow_type, workflow_values):
        current_document = user_data.get_active_document()
        if current_document:
            data_package_id = workflow_values.assigned_pid
            create_data_package_id(data_package_id, filename)
            log_info(f'{log_preamble()}applied PID to EML - {data_package_id}')
            update_workflow(workflow_type, owner_login, package_name=filename,
                            pid_status='PID_ENTERED_IN_EML', eval_status='', upload_status='',
                            pid_entered_in_eml=data_package_id)

    def handle_evaluate(workflow_type):
        status, eval_transaction_id = evaluate_data_package(pasta_environment_from_workflow_type(workflow_type))
        if 200 <= status < 300:
            update_workflow(workflow_type, owner_login, package_name=filename, eval_status='EVAL_IN_PROGRESS',
                            upload_status='',
                            eval_transaction_id=eval_transaction_id, report='', ready_to_upload=False,
                            create_transaction_id='', landing_page_link='')
        else:
            log_error(f'{log_preamble()} handle_evaluate({workflow_type}) returns status {status}')

    def handle_report(workflow_type):
        workflow_values = get_workflow_values(workflow_type, owner_login, filename)
        if workflow_values.eval_status == 'ERROR_REPORT':
            return redirect(url_for('workflow.display_text', text=workflow_values.report))

    def handle_upload(workflow_type, revision_of: str=None):
        status, create_transaction_id = upload_data_package(pasta_environment_from_workflow_type(workflow_type), revision_of)
        if 200 <= status < 300:
            update_workflow(workflow_type, owner_login, package_name=filename, upload_status='UPLOAD_IN_PROGRESS',
                            create_transaction_id=create_transaction_id, report='')
        else:
            log_error(f'{log_preamble()} handle_upload({workflow_type}) returns status {status}')

    # Load the EML so the badges are rendered correctly
    eml_node = load_eml(filename=filename)

    if not current_user.is_admin() and not current_user.is_data_curator():
        flash('You are not authorized to access the Curator Workflow page', 'error')
        return redirect(url_for(PAGE_INDEX))

    owner_login = user_data.get_active_document_owner_login()

    staging_values = get_workflow_values('STAGING', owner_login, filename)
    production_values = get_workflow_values('PRODUCTION', owner_login, filename)

    staging_form = CuratorWorkflowForm()
    production_form = CuratorWorkflowForm()

    # Process POST
    if request.method == 'POST':

        if "staging_reserve" in request.form:
            handle_reserve_pid('STAGING', staging_form)

        if "staging_apply_pid" in request.form:
            handle_apply_pid('STAGING', staging_values)

        if "staging_evaluate" in request.form:
            handle_evaluate('STAGING')

        if "staging_report" in request.form:
            handle_report('STAGING')

        if "staging_upload" in request.form:
            handle_upload('STAGING', staging_values.revision_of)

        if "production_reserve" in request.form:
            handle_reserve_pid('PRODUCTION', production_form)

        if "production_apply_pid" in request.form:
            handle_apply_pid('PRODUCTION', production_values)

        if "production_evaluate" in request.form:
            handle_evaluate('PRODUCTION')

        if "production_report" in request.form:
            handle_report('PRODUCTION')

        if "production_upload" in request.form:
            handle_upload('PRODUCTION', production_values.revision_of)

    help = get_helps(['manage_data_usage'])
    set_current_page('curator_workflow')

    staging_values = get_workflow_values('STAGING', owner_login, filename)
    production_values = get_workflow_values('PRODUCTION', owner_login, filename)

    staging_form.revision_of.data = staging_values.revision_of
    staging_form.new_or_revision.data = 'Revision' if staging_values.revision_of else "New"
    production_form.revision_of.data = production_values.revision_of
    production_form.new_or_revision.data = 'Revision' if production_values.revision_of else "New"

    return render_template('curator_workflow.html', is_admin=current_user.is_admin(),
                           staging_values=staging_values._asdict(),
                           production_values=production_values._asdict(),
                           staging_form=staging_form, production_form=production_form, help=help)


# The following is intended to be invoked from a cron job to check for evals that were in progress and have now completed.
@workflow_bp.route('/check_eval_completions', methods=['GET', 'POST'])
def check_eval_completions():

    def has_errors(report:str=None):
        if not report:
            return True
        root = etree.fromstring(report.encode('utf-8'))
        ns = {'qr': 'eml://ecoinformatics.org/qualityReport'}
        errors = root.xpath("//qr:qualityCheck[qr:status='error']", namespaces=ns)
        if errors:
            return True
        else:
            return False

    try:
        with db_session(None) as session:
            in_progress = get_eval_in_progress_workflows()
            for workflow in in_progress:
                status, report = get_error_report(PastaEnvironment[workflow.workflow_type], workflow.eval_transaction_id)
                if status in (200, 400):
                    # There's an error report.
                    workflow.eval_status = 'ERROR_REPORT'
                    workflow.report = report
                    workflow.ready_to_upload = False
                elif status == 404:
                    # No error report was found. Now check for eval report.
                    status, report = get_evaluate_report(PastaEnvironment[workflow.workflow_type], workflow.eval_transaction_id)
                    if status == 200:
                        workflow.eval_status = 'EVAL_REPORT'
                        workflow.report = report
                        workflow.ready_to_upload = not has_errors(report)

            in_progress = get_upload_in_progress_workflows()
            for workflow in in_progress:
                status, text = get_error_report(PastaEnvironment[workflow.workflow_type], workflow.create_transaction_id)
                if 200 <= status < 300 and text:
                    workflow.upload_status = 'UPLOAD_ERROR'
                    workflow.landing_page_link = text
                    break
                scope, identifier, revision = workflow.assigned_pid.split('.')
                status, report = check_existence(PastaEnvironment[workflow.workflow_type], scope, identifier, revision)
                if 200 <= status < 300:
                    workflow.upload_status = 'UPLOAD_COMPLETED'
                    workflow.landing_page_link = f'{portal_url_for_environment(PastaEnvironment[workflow.workflow_type])}/nis/mapbrowse?scope={scope}&identifier={identifier}&revision={revision}'

            return ''
    except Exception as e:
        pass


from lxml import etree
from markupsafe import Markup
def format_eval_report(xml_data):
    output = '<hr>'
    def format_quality_check_item(qc, item_type):
        output = f"<b>{ item_type }</b><br>"
        for elem in qc:
            # Check if the element's tag is in the specified list
            if elem.tag.split('}')[-1] in ('name', 'description', 'expected', 'found', 'explanation'):
                # Format the tag (capitalize) and make it italic, as well as the colon
                tag = elem.tag.split('}')[-1].capitalize()
                output += f"<i style='color: grey;'>{tag}:</i>&nbsp;&nbsp;{elem.text.strip() if elem.text else 'N/A'}<br>"
        output += '<hr>'
        return output

    # Parse XML
    root = etree.fromstring(xml_data.encode('utf-8'))

    # Define namespace
    ns = {'qr': 'eml://ecoinformatics.org/qualityReport'}

    package_id_element = root.find('qr:packageId', ns)
    package_id = package_id_element.text if package_id_element is not None else None

    # Find qualityCheck elements where the <status> subelement has value 'error' or 'warn'
    errors = root.xpath("//qr:qualityCheck[qr:status='error']", namespaces=ns)
    warnings = root.xpath("//qr:qualityCheck[qr:status='warn']", namespaces=ns)

    if errors:
        for error in errors:
            output += format_quality_check_item(error, 'Error')
    else:
        output += 'No errors were reported.<hr>'
    if warnings:
        for warning in warnings:
            output += format_quality_check_item(warning, 'Warning')
    else:
        output += 'No warnings were reported.<hr>'

    return Markup(output), package_id


@workflow_bp.route('/display_eval_result/<workflow_type>', methods=['GET', 'POST'])
@login_required
@non_saving_hidden_buttons_decorator
def display_eval_result(workflow_type:str):
    import webapp.auth.user_data as user_data
    owner_login = user_data.get_active_document_owner_login()

    current_document = user_data.get_active_document()

    if workflow_type == 'staging':
        workflow_values = get_workflow_values('STAGING', owner_login, current_document)
    else:
        workflow_values = get_workflow_values('PRODUCTION', owner_login, current_document)

    heading = 'Quality Report'
    package_id = ''
    if workflow_values.eval_status == 'EVAL_IN_PROGRESS':
        text = 'The evaluation is still in progress. Please check back later.'
    else:
        if workflow_values.eval_status == 'ERROR_REPORT':
            text = workflow_values.report
            heading = 'Error Report'
        elif workflow_values.eval_status == 'EVAL_REPORT':
            text, package_id = format_eval_report(workflow_values.report)
        else:
            text = 'Unknown workflow evaluation status'

    output = f'''
    <html>
        <body lang=EN-US style='word-wrap:break-word;font-family:arial,sans-serif;font-size: 12pt;margin-top: 50px;margin-left: 100px;margin-right: 200px;'>
            <b>ezEML Package Name:</b> { current_document }
            <p>'''
    if package_id:
        output += f'<b>Data Package ID:</b> {package_id}<p>'
    output += f'''
            <h2>{ heading }</h2>
            <p>
            {escape(text)}
        </body>
    </html>
    '''
    return output
