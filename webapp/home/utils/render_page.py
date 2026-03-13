from __future__ import annotations

from typing import Any, Iterable, Optional

from flask import render_template

from webapp.home.utils.load_and_save import load_eml
from webapp.home.forms import init_form_md5
from webapp.home.check_metadata import init_evaluation, format_tooltip
from webapp.home.views import set_current_page, get_help, get_helps


def render_page(
    template: str,
    *,
    filename: str,
    form: Any,
    tooltip_section: str,
    current_page_key: str,
    help_keys: Iterable[str],
    eml_node: Optional[Any] = None,
    title: Optional[str] = None,
    tooltip: Optional[str] = None,
    init_md5: bool = True,
    do_evaluation: bool = True,
    **ctx: Any,
):
    """
    Render a standard ezEML page with the common boilerplate:
      - load EML (unless provided)
      - init form md5 (optional)
      - initialize evaluation + tooltip (optional)
      - set current page
      - gather help content
      - render template with common context fields

    Parameters
    ----------
    template:
        Jinja template filename (e.g., "abstract.html").
    filename:
        Active document/package filename.
    form:
        WTForms form instance.
    tooltip_section:
        Section name used by format_tooltip (e.g., "abstract", "keyword").
    current_page_key:
        String used by set_current_page (e.g., "abstract", "keyword").
    help_keys:
        Keys passed to get_helps/get_help. If you pass multiple keys, get_helps is used.
        If you pass a single key, get_help is used.
    eml_node:
        If you already loaded EML upstream, pass it to avoid re-loading.
    title:
        Optional page title to pass to the template.
    tooltip:
        Optional tooltip; if not provided and do_evaluation is True, one will be computed.
    init_md5:
        Whether to call init_form_md5(form).
    do_evaluation:
        Whether to call init_evaluation and compute tooltip.
    **ctx:
        Extra template variables forwarded to render_template().

    Returns
    -------
    The result of flask.render_template().
    """
    # Load EML if caller didn't provide it
    if eml_node is None:
        eml_node = load_eml(filename=filename)

    # Initialize form md5 hash (used by is_dirty_form)
    if init_md5:
        init_form_md5(form)

    # Status badge tooltip
    if do_evaluation and tooltip is None:
        init_evaluation(eml_node, filename)
        tooltip = format_tooltip(None, section=tooltip_section)

    # Navigation state
    set_current_page(current_page_key)

    # Help
    help_keys_list = list(help_keys)
    if len(help_keys_list) == 1:
        help_content = [get_help(help_keys_list[0])]
    else:
        help_content = get_helps(help_keys_list)

    # Common context passed to templates
    common_ctx = dict(
        filename=filename,
        form=form,
        help=help_content,
        tooltip=tooltip,
    )
    if title is not None:
        common_ctx["title"] = title

    # Merge in caller-provided context; caller wins on conflicts
    common_ctx.update(ctx)

    return render_template(template, **common_ctx)
