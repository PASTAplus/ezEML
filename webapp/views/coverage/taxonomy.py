import json
from lxml import etree
from lxml.etree import fromstring
import requests

from enum import Enum, auto

class TaxonomySourceEnum(Enum):
    ITIS = auto()
    NCBI = auto()
    WORMS = auto()

class TaxonomySource:

    def __init__(self, source):
        self.source = source

    def prune_hierarchy(self, hierarchy):
        pruned = []
        for rank_name, taxon_name, taxon_id, link, provider in hierarchy:
            if rank_name.capitalize() not in (
                    'Subspecies', 'Species', 'Subgenus', 'Genus', 'Subfamily', 'Family', 'Superfamily',
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
                common_name = self.get_common_name_by_id(taxon_id)
                filled.append((rank_name, taxon_name, common_name, taxon_id, link, provider))
        return filled


class ITISTaxonomy(TaxonomySource):

    def __init__(self):
        super().__init__(TaxonomySourceEnum.ITIS)

    def search_by_sciname(self, name):
        r = requests.get(f'http://www.itis.gov/ITISWebService/jsonservice/searchByScientificName?srchKey={name}')
        return json.loads(r.text)

    def search_by_combined_name(self, name):
        d = self.search_by_sciname(name)
        for rec in d['scientificNames']:
            if rec and rec.get('combinedName') == name:
                return rec
        return None

    def get_hierarchy_up_from_tsn(self, tsn):
        r = requests.get(f'http://www.itis.gov/ITISWebService/jsonservice/getHierarchyUpFromTSN?tsn={tsn}')
        return json.loads(r.text)

    def fill_hierarchy(self, name):
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
                else:
                    break
        return self.prune_hierarchy(hierarchy)

    def get_common_name_by_id(self, tsn):
        r = requests.get(f'http://www.itis.gov/ITISWebService/jsonservice/getCommonNamesFromTSN?tsn={tsn}')
        d = json.loads(r.text)
        for rec in d['commonNames']:
            if rec and rec.get('language') == 'English':
                return rec.get('commonName')
        return ''


class WORMSTaxonomy(TaxonomySource):

    def __init__(self):
        super().__init__(TaxonomySourceEnum.WORMS)

    def get_aphia_id_by_name(self, name):
        r = requests.get(f'http://marinespecies.org/rest/AphiaIDByName/{name}?marine_only=false')
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
        r = requests.get(f'http://marinespecies.org/rest/AphiaClassificationByAphiaID/{id}')
        if r:
            d = json.loads(r.text)
            self.parse(d, hierarchy)
        return self.prune_hierarchy(hierarchy)

    def get_common_name_by_id(self, id):
        r = requests.get(f'http://marinespecies.org/rest/AphiaVernacularsByAphiaID/{id}')
        if r and r.text:
            d = json.loads(r.text)
            for rec in d:
                if rec.get('vernacular') and rec.get('language') == 'English':
                    return rec.get('vernacular')
        return ''


class NCBITaxonomy(TaxonomySource):

    # FIXME - get api_key from config file
    def __init__(self, api_key='c75b4a9d0b39da79a3f180e82d18b8246f08'):
        super().__init__(TaxonomySourceEnum.NCBI)
        self.api_key = api_key

    def search_by_sciname(self, name):
        r = requests.get(
            f'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=taxonomy&api_key={self.api_key}&term={name}')
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
            f'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=taxonomy&api_key={self.api_key}&ID={id}')
        return r.text

    def get_summary_by_taxon_id(self, id):
        r = requests.get(
            f'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?db=taxonomy&api_key={self.api_key}&ID={id}')
        return r.text

    def fill_hierarchy(self, name):
        hierarchy = []
        parser = etree.XMLParser(ns_clean=True, recover=True, encoding='utf-8')
        id = self.get_taxon_id(name)
        while id:
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
                except Exception as e:
                    break
            else:
                break
        return self.prune_hierarchy(hierarchy)

    def get_common_name_by_id(self, id):
        r = requests.get(
            f'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?db=taxonomy&api_key={self.api_key}&ID={id}')
        parser = etree.XMLParser(ns_clean=True, recover=True, encoding='utf-8')
        tree = fromstring(r.text.encode('utf-8'), parser=parser)
        common_name = tree.xpath("//DocSum/Item[@Name='CommonName']")[0].text
        if not common_name:
            return ''
        else:
            return common_name
