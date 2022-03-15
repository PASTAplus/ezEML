from wtforms import (
    StringField, SelectField, RadioField, HiddenField
)

from wtforms.validators import (
    InputRequired, Optional, Regexp
)

from wtforms.widgets import TextArea

from webapp.home.custom_validators import (
    valid_min_length
)

from webapp.home.intellectual_rights import (
    INTELLECTUAL_RIGHTS_CC0, INTELLECTUAL_RIGHTS_CC_BY
)

from webapp.home.forms import EDIForm
from webapp.home.views import get_keywords


class AbstractForm(EDIForm):
    abstract = StringField('Abstract (Recommended)', widget=TextArea(),
                           validators=[Optional()])
    md5 = HiddenField('')


class IntellectualRightsForm(EDIForm):
    intellectual_rights_radio = RadioField('Intellectual Rights',
                                           choices=[("CC0", INTELLECTUAL_RIGHTS_CC0),
                                                    ("CCBY", INTELLECTUAL_RIGHTS_CC_BY),
                                                    ("Other", "Other (Enter text below)")
                                                    ],
                                           # default="CC0",
                                           validators=[InputRequired()])
    intellectual_rights = StringField('', widget=TextArea(), validators=[])
    md5 = HiddenField('')


class KeywordSelectForm(EDIForm):
    pass


class KeywordForm(EDIForm):
    keyword = StringField('Keyword *', validators=[])

    lter_keyword_select = SelectField('', choices=[], validators=[])

    keyword_type = SelectField('Keyword Type (Optional)',
                               choices=[("", ""),
                                        ("place", "place"),
                                        ("stratum", "stratum"),
                                        ("taxonomic", "taxonomic"),
                                        ("temporal", "temporal"),
                                        ("theme", "theme")])
    md5 = HiddenField('')

    def init_keywords(self):
        lter_keywords = get_keywords('LTER')
        keyword_choices = [("", "")]
        for keyword in lter_keywords:
            keyword_choices.append((keyword, keyword))
        self.lter_keyword_select.choices = keyword_choices


class PubDateForm(EDIForm):
    pubdate = StringField('Publication Date',
                          validators=[Optional(), Regexp(r'^(\d\d\d\d)-(01|02|03|04|05|06|07|08|09|10|11|12)-(0[1-9]|[1-2]\d|30|31)|(\d\d\d\d)$', message='Invalid date format')])
    md5 = HiddenField('')


class PublicationInfoForm(EDIForm):
    pubplace = StringField('Publication Place (Optional)', validators=[])
    pubdate = StringField('Publication Date (Optional)', validators=[])
    md5 = HiddenField('')


class TitleForm(EDIForm):
    title = StringField('Title *', validators=[InputRequired(message='Title is required')])
    md5 = HiddenField('')


class DataPackageIDForm(EDIForm):
    data_package_id = StringField('Data Package ID *', validators=[])
    md5 = HiddenField('')
