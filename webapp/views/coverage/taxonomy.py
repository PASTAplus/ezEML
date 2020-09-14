import json
import requests

from enum import Enum, auto

class TaxonomySourceEnum(Enum):
    ITIS = auto()
    WORMS = auto()

class TaxonomySource:

    def __init__(self, source):
        self.source = source

    def prune_hierarchy(self, hierarchy):
        pruned = []
        for rank_name, taxon_name, taxon_id, link, provider in hierarchy:
            # if rank_name.lower() not in ('kingdom', 'phylum', 'division', 'class', 'order', 'family', 'genus', 'species'):
            #     continue
            # if rank_name.lower() == 'division':
            #     rank_name = 'Phylum'
            pruned.append((rank_name, taxon_name, taxon_id, link, provider))
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

