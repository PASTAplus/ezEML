from lxml import etree
import os
from webapp.config import Config

from metapype.eml import names

standard_units = []
deprecated_standard_units = []
all_units = []


def _process_element(e, l, deprecated_only=False):
    tag = e.tag[e.tag.find("}") + 1:]  # Remove any prepended namespace
    if tag == 'unit':
        name = e.attrib.get('name', None)
        if deprecated_only:
            if 'deprecatedInFavorOf' in e.attrib:
                deprecated = e.attrib.get('deprecatedInFavorOf')
                l.append((name, deprecated))
        else:
            if 'deprecatedInFavorOf' not in e.attrib:
                l.append(name)
    else:
        for _ in e:
            if _.tag is not etree.Comment:
                _process_element(_, l, deprecated_only)


def from_xml(xml, deprecated_only=False):
    l = []
    _process_element(etree.fromstring(xml.encode("utf-8")), l, deprecated_only)
    return l


def init_standard_units():
    global standard_units, deprecated_standard_units, all_units
    with open(os.path.join(Config.BASE_DIR, 'webapp/static/eml-unitDictionary.xml'), 'r') as f:
        xml = f.read()
        standard_units = sorted(from_xml(xml), key=lambda x: x.lower())
        deprecated_standard_units = dict(from_xml(xml, deprecated_only=True))
        all_units = sorted(standard_units + list(deprecated_standard_units.keys()), key=lambda x: x.lower())


def has_deprecated_units(eml_node):
    has_deprecated_units = False
    unknown_units = set()
    standard_unit_nodes = []
    eml_node.find_all_descendants(names.STANDARDUNIT, standard_unit_nodes)
    for standard_unit_node in standard_unit_nodes:
        unit = standard_unit_node.content
        if unit in deprecated_standard_units:
            has_deprecated_units = True
        elif unit not in all_units:
            unknown_units.add(unit)
    return has_deprecated_units, unknown_units


if __name__ == "__main__":
    init_standard_units()
    foo = standard_units[0]
    ijk = 123