"""
Helper functions for accessing taxonomic authorities.

There is a class for each supported taxonomic authority, implementing the TaxonomySource interface.
"""

import csv
import json
from lxml import etree
from lxml.etree import fromstring
import requests

from enum import Enum, auto

from webapp.home.exceptions import *
import webapp.views.coverage.coverage as coverage

class TaxonomySourceEnum(Enum):
    ITIS = auto()
    NCBI = auto()
    WORMS = auto()


class TaxonomySource:

    def __init__(self, source):
        self.source = source
        self._timeout = 5

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, name):
        self._name = name

    def prune_hierarchy(self, hierarchy):
        pruned = []
        for rank_name, taxon_name, taxon_id, link, provider in hierarchy:
            if rank_name.capitalize() not in (
                    'Varietas', 'Subspecies', 'Species', 'Subgenus', 'Genus', 'Subfamily', 'Family', 'Superfamily',
                    'Infraorder', 'Suborder', 'Order', 'Superorder', 'Infraclass', 'Subclass', 'Class',
                    'Superclass', 'Infraphylum', 'Subphylum', 'Subdivision', 'Subphylum (Subdivision)',
                    'Phylum', 'Division', 'Phylum (Division)', 'Superphylum', 'Infrakingdom', 'Subkingdom',
                    'Kingdom', 'Domain', 'Superdomain'):
                continue
            pruned.append((rank_name.capitalize(), taxon_name, taxon_id, link, provider))
        return pruned

    def get_common_name_by_id(self, taxon_id):
        pass

    def fill_common_names(self, hierarchy):
        filled = []
        if hierarchy:
            for rank_name, taxon_name, taxon_id, link, provider in hierarchy:
                common_names = self.get_common_names_by_id(taxon_id)
                filled.append((rank_name, taxon_name, common_names, taxon_id, link, provider))
        return filled


class ITISTaxonomy(TaxonomySource):
    """
    The ITIS taxonomy authority's implementation of the TaxonomySource interface.
    """

    def __init__(self):
        super().__init__(TaxonomySourceEnum.ITIS)

    def search_by_sciname(self, name):
        r = requests.get(f'http://www.itis.gov/ITISWebService/jsonservice/searchByScientificName?srchKey={name}',
                         timeout=self._timeout)
        return json.loads(r.text)

    def search_by_combined_name(self, name):
        d = self.search_by_sciname(name)
        for rec in d['scientificNames']:
            if rec and rec.get('combinedName') == name:
                return rec
        return None

    def get_hierarchy_up_from_tsn(self, tsn):
        r = requests.get(f'http://www.itis.gov/ITISWebService/jsonservice/getHierarchyUpFromTSN?tsn={tsn}',
                         timeout=self._timeout)
        return json.loads(r.text)

    def fill_hierarchy(self, name, levels=None):
        hierarchy = []
        rec = self.search_by_combined_name(name)
        if rec:
            tsn = rec['tsn']
            while tsn:
                parent = self.get_hierarchy_up_from_tsn(tsn)
                if parent:
                    rankName = parent['rankName']
                    taxonName = parent['taxonName']
                    parent_tsn = parent['parentTsn']
                    link = f'https://itis.gov/servlet/SingleRpt/SingleRpt?search_topic=TSN&search_value={tsn}'
                    provider = 'ITIS'
                    hierarchy.append((rankName, taxonName, tsn, link, provider))
                    tsn = parent_tsn
                    if levels and len(hierarchy) >= levels:
                        break
                else:
                    break
        return self.prune_hierarchy(hierarchy)

    def get_common_names_by_id(self, tsn):
        r = requests.get(f'http://www.itis.gov/ITISWebService/jsonservice/getCommonNamesFromTSN?tsn={tsn}',
                         timeout=self._timeout)
        d = json.loads(r.text)
        common_names = []
        for rec in d['commonNames']:
            if rec and rec.get('language') == 'English':
                common_names.append(rec.get('commonName'))
        return common_names


class WORMSTaxonomy(TaxonomySource):
    """
    The WORMS taxonomy authority's implementation of the TaxonomySource interface.
    """

    def __init__(self):
        super().__init__(TaxonomySourceEnum.WORMS)

    def get_aphia_id_by_name(self, name):
        r = requests.get(f'http://marinespecies.org/rest/AphiaIDByName/{name}?marine_only=false',
                         timeout=self._timeout)
        if r and r.text:
            return json.loads(r.text)
        else:
            return None

    def parse(self, d, hierarchy):
        taxon_rank = d['rank']
        taxon_name = d['scientificname']
        taxon_id = d['AphiaID']
        link = f'http://marinespecies.org/aphia.php?p=taxdetails&id={taxon_id}'
        provider = 'WORMS'
        if d['child']:
            self.parse(d['child'], hierarchy)
        hierarchy.append((taxon_rank, taxon_name, taxon_id, link, provider))

    def fill_hierarchy(self, name):
        hierarchy = []
        id = self.get_aphia_id_by_name(name)
    #     print(f'id={id}')
        if not id:
            return None
        r = requests.get(f'http://marinespecies.org/rest/AphiaClassificationByAphiaID/{id}',
                         timeout=self._timeout)
        if r:
            d = json.loads(r.text)
            self.parse(d, hierarchy)
        return self.prune_hierarchy(hierarchy)

    def get_common_names_by_id(self, id):
        r = requests.get(f'http://marinespecies.org/rest/AphiaVernacularsByAphiaID/{id}',
                         timeout=self._timeout)
        common_names = []
        if r and r.text:
            d = json.loads(r.text)
            for rec in d:
                if rec.get('vernacular') and rec.get('language') == 'English':
                    common_names.append(rec.get('vernacular'))
        return [common_name.strip() for common_name in common_names]


class NCBITaxonomy(TaxonomySource):
    """
    The NCBI taxonomy authority's implementation of the TaxonomySource interface.
    """

    # FIXME - get api_key from config file
    def __init__(self, api_key='c75b4a9d0b39da79a3f180e82d18b8246f08'):
        super().__init__(TaxonomySourceEnum.NCBI)
        self.api_key = api_key

    def search_by_sciname(self, name):
        r = requests.get(
            f'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=taxonomy&api_key={self.api_key}&term={name}',
                         timeout=self._timeout)
        return r.text

    def get_taxon_id(self, name):
        xml = self.search_by_sciname(name)
        if xml:
            parser = etree.XMLParser(ns_clean=True, recover=True, encoding='utf-8')
            tree = fromstring(xml.encode('utf-8'), parser=parser)
            id = tree.xpath("//IdList/Id")
            if id:
                return id[0].text
        return None

    def fetch_by_taxon_id(self, id):
        r = requests.get(
            f'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=taxonomy&api_key={self.api_key}&ID={id}',
                         timeout=self._timeout)
        return r.text

    def get_summary_by_taxon_id(self, id):
        r = requests.get(
            f'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?db=taxonomy&api_key={self.api_key}&ID={id}',
                         timeout=self._timeout)
        return r.text

    def fill_hierarchy(self, name, levels=None):
        hierarchy = []
        parser = etree.XMLParser(ns_clean=True, recover=True, encoding='utf-8')
        id = self.get_taxon_id(name)
        while id and not id == '0':
            rec = self.fetch_by_taxon_id(id)
            if rec:
                tree = fromstring(rec.encode('utf-8'), parser=parser)
                if tree is None:
                    break
                try:
                    parent_id = tree.xpath("//TaxaSet/Taxon/ParentTaxId")[0].text
                    rank_name = tree.xpath("//TaxaSet/Taxon/Rank")[0].text
                    taxon_name = tree.xpath("//TaxaSet/Taxon/ScientificName")[0].text
                    link = f'https://www.ncbi.nlm.nih.gov/Taxonomy/Browser/wwwtax.cgi?id={id}'
                    provider = 'NCBI'
                    hierarchy.append((rank_name, taxon_name, id, link, provider))
                    id = parent_id
                    if levels and len(hierarchy) >= levels:
                        break
                except Exception as e:
                    break
            else:
                break
        return self.prune_hierarchy(hierarchy)

    def get_common_names_by_id(self, id):
        common_names = []
        r = requests.get(
            f'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?db=taxonomy&api_key={self.api_key}&ID={id}',
                         timeout=self._timeout)
        parser = etree.XMLParser(ns_clean=True, recover=True, encoding='utf-8')
        tree = fromstring(r.text.encode('utf-8'), parser=parser)
        common_name_entry = tree.xpath("//DocSum/Item[@Name='CommonName']")
        if common_name_entry and common_name_entry[0].text:
            common_names = common_name_entry[0].text.split(',')
        return [common_name.strip() for common_name in common_names]

def load_taxonomic_coverage_csv_file(csv_file, delimiter, quotechar):
    """
    Load a taxonomic coverage CSV file into a list of tuples: (taxon_scientific_name, general_taxonomic_coverage, taxon_rank)
    """
    taxa = []
    with open(csv_file, 'r', encoding='utf-8-sig') as f:
        reader = csv.reader(f, delimiter=delimiter, quotechar=quotechar)
        header_row = next(reader)
        if header_row and header_row != ['taxon_scientific_name', 'general_taxonomic_coverage', 'taxon_rank']:
            raise InvalidHeaderRow(f'{csv_file} has invalid header row: {header_row}')
        for row in reader:
            taxon, general_coverage, rank = (str.strip(x) for x in row)
            if taxon:
                taxa.append((taxon, general_coverage,  rank))
    return taxa


def process_taxonomic_coverage_file(taxa, authority):
    """
    Process a list of tuples: (taxon_scientific_name, general_taxonomic_coverage, taxon_rank) to fill in the taxonomic
    hierarchy for each taxon.  If a taxon rank is provided, the taxonomic authority is not queried for that taxon.

    Returns a list of hierarchies, a list of errors, and a list of general coverages.
    """
    row = 0
    hierarchies = []
    errors = []
    general_coverages = []
    for taxon, general_coverage, rank in taxa:
        row += 1
        general_coverages.append(general_coverage)
        # If rank is provided, we don't access the taxonomic authority but just use the provided rank.
        if rank:
            rank = str.capitalize(rank)
            hierarchies.append([(rank, taxon, None, None, None, None)])
            errors.append(f'Row {row}: Taxon "{taxon}" - Because a taxon rank ("{rank}") was specified for "{taxon}" in'
                          f' the CSV file, {authority} was not queried for this taxon. To cause {authority} to be '
                          f' queried for a taxon, leave its taxon rank empty in the CSV file.')
            continue
        if authority == 'ITIS':
            t = ITISTaxonomy()
            source_type = TaxonomySourceEnum.ITIS
        elif authority == 'NCBI':
            t = NCBITaxonomy()
            source_type = TaxonomySourceEnum.NCBI
        elif authority == 'WORMS':
            t = WORMSTaxonomy()
            source_type = TaxonomySourceEnum.WORMS
        try:
            hierarchy = coverage.fill_taxonomic_coverage(taxon, source_type, '', row, True)
            hierarchies.append(hierarchy)
        except TaxonNotFound as e:
            hierarchies.append(None) # We need a placeholder for the hierarchy so subsequent hierarchies and general_coverages are in sync.
            errors.append(e.message)
    return hierarchies, general_coverages, errors


if __name__ == "__main__":
    pass
