"""
Helper functions for accessing taxonomic authorities.

There is are classes for each supported taxonomic authority, implementing the TaxonomySource interface.

In each case, there are two implementations. One that uses the authority's REST API and one that accesses a local
copy of the authority's database. The REST versions were implemented first and have been retained in case issues arise
with the database accesses -- e.g., if an authority no longer makes their database available for download. Which version
is used in each case is controlled by config entries.
"""

import csv
import json
from lxml import etree
from lxml.etree import fromstring
import os
import re
import requests
import sqlite3

from enum import Enum, auto

from webapp.home.exceptions import *
import webapp.views.coverage.coverage as coverage
from webapp.home.home_utils import log_error, log_info

class TaxonomySourceEnum(Enum):
    ITIS = auto()
    NCBI = auto()
    WORMS = auto()


class TaxonomySource:

    def __init__(self, source):
        self.source = source
        self._timeout = 15

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, name):
        self._name = name

    def prune_hierarchy(self, hierarchy):
        pruned = []
        for rank_name, taxon_name, taxon_id, link, provider in hierarchy:
            if not rank_name or rank_name.capitalize() not in (
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

###############################################################################################################
#  Implementations using local databases
###############################################################################################################

class ITISTaxonomy_DB(TaxonomySource):
    """
    The ITIS taxonomy authority's implementation of the TaxonomySource interface, using a local SQLite database.
    """

    def __init__(self, db_path='webapp/static/taxonomy_dbs/ITIS/ITIS.sqlite'):
        super().__init__(TaxonomySourceEnum.ITIS)
        self.db_path = db_path
        try:
            self.conn = sqlite3.connect(db_path)
        except Exception as e:
            log_error(e)
        self.cursor = self.conn.cursor()

    def __del__(self):
        """Close the database connection when the object is destroyed."""
        self.conn.close()

    def search_by_sciname(self, name):
        """Search for taxonomic records by scientific name in the local ITIS database."""
        try:
            self.cursor.execute("""
                SELECT tsn, complete_name, kingdom_id, rank_id
                FROM taxonomic_units
                WHERE complete_name = ? AND (name_usage = 'accepted' OR name_usage = 'valid')
            """, (name,))
            results = self.cursor.fetchall()
            # Mimic API response structure
            return {
                'scientificNames': [
                    {
                        'combinedName': row[1],
                        'tsn': str(row[0]),
                        'kingdom_id': row[2],
                        'rank_id': row[3]
                    } for row in results
                ]
            }
        except sqlite3.Error as e:
            log_error(f"Database error in search_by_sciname: {e}")
            return {'scientificNames': []}

    def search_by_combined_name(self, name):
        """Find a single record by exact combined name match."""
        d = self.search_by_sciname(name)
        for rec in d['scientificNames']:
            if rec and rec.get('combinedName') == name:
                return rec
        return None

    def get_hierarchy_up_from_tsn(self, tsn):
        """Retrieve the parent taxon for a given TSN from the local database."""
        try:
            # Get current taxon details
            self.cursor.execute("""
                SELECT tu.complete_name, tut.rank_name, tu.parent_tsn
                FROM taxonomic_units tu
                JOIN taxon_unit_types tut ON tu.rank_id = tut.rank_id
                WHERE tu.tsn = ? AND (tu.name_usage = 'accepted' OR tu.name_usage = 'valid')
            """, (tsn,))
            result = self.cursor.fetchone()
            if result:
                return {
                    'taxonName': result[0],
                    'rankName': result[1],
                    'parentTsn': str(result[2]) if result[2] else ''
                }
            return None
        except sqlite3.Error as e:
            log_error(f"Database error in get_hierarchy_up_from_tsn: {e}")
            return None

    def fill_hierarchy(self, name, levels=None):
        """Build the taxonomic hierarchy for a given name up to the specified level."""
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
        """Retrieve the English common name for a given TSN from the local database."""
        common_names = []
        try:
            self.cursor.execute("""
                SELECT vernacular_name
                FROM vernaculars
                WHERE tsn = ? AND language = 'English'
            """, (tsn,))
            results = self.cursor.fetchall()
            if results:
                for result in results:
                    common_names.append(result[0])
            # return result[0] if result else ''
        except sqlite3.Error as e:
            log_error(f"Database error in get_common_name_by_id: {e}")
        return [common_name.strip() for common_name in common_names]


class NCBITaxonomy_DB(TaxonomySource):
    """
    The NCBI taxonomy authority's implementation of the TaxonomySource interface, using a local SQLite database.
    """

    def __init__(self, db_path='webapp/static/taxonomy_dbs/NCBI/ncbi_taxonomy.db'):
        super().__init__(TaxonomySourceEnum.NCBI)
        self.db_path = os.path.abspath(db_path)  # Ensure absolute path
        log_info(f"Attempting to connect to database: {self.db_path}")

        # Validate database file
        if not os.path.exists(self.db_path):
            log_error(f"Database file does not exist: {self.db_path}")
            raise FileNotFoundError(f"Database file not found: {self.db_path}")
        if not os.access(self.db_path, os.R_OK | os.W_OK):
            log_error(f"No read/write permissions for database file: {self.db_path}")
            raise PermissionError(f"No read/write permissions for: {self.db_path}")

        try:
            self.conn = sqlite3.connect(self.db_path)
            self.cursor = self.conn.cursor()
            log_info("Successfully connected to NCBI database")
        except sqlite3.OperationalError as e:
            log_error(f"Failed to open database: {e} (SQLite error code: {e.sqlite_errorcode})")
            raise
        except sqlite3.DatabaseError as e:
            log_error(f"Database error: {e}")
            raise

    def __del__(self):
        """Close the database connection when the object is destroyed."""
        try:
            self.conn.close()
            log_info("Database connection closed")
        except AttributeError:
            pass  # Connection might not have been initialized

    def get_taxon_id(self, name):
        """Retrieve taxID for a scientific name from the local NCBI database."""
        try:
            self.cursor.execute("""
                SELECT tax_id
                FROM names
                WHERE name_txt = ? AND name_class = 'scientific name'
            """, (name,))
            result = self.cursor.fetchone()
            tax_id = result[0] if result else None
            return tax_id
        except sqlite3.Error as e:
            log_error(f"Database error in get_taxon_id: {e}")
            return None

    def fill_hierarchy(self, name, levels=None):
        """Build the taxonomic hierarchy for a given name up to the specified level."""
        hierarchy = []
        tax_id = self.get_taxon_id(name)
        while tax_id and tax_id > 1:
            try:
                self.cursor.execute("""
                    SELECT n.tax_id, n.parent_tax_id, n.rank, m.name_txt
                    FROM nodes n
                    JOIN names m ON n.tax_id = m.tax_id
                    WHERE n.tax_id = ? AND m.name_class = 'scientific name'
                """, (tax_id,))
                result = self.cursor.fetchone()
                if not result:
                    log_error(f"No taxon found for taxID {tax_id}")
                    break
                tax_id, parent_tax_id, rank_name, taxon_name = result
                link = f'https://www.ncbi.nlm.nih.gov/Taxonomy/Browser/wwwtax.cgi?id={tax_id}'
                provider = 'NCBI'
                hierarchy.append((rank_name, taxon_name, tax_id, link, provider))
                tax_id = parent_tax_id
                if levels and len(hierarchy) >= levels:
                    break
            except sqlite3.Error as e:
                log_error(f"Database error in fill_hierarchy: {e}")
                break
        return self.prune_hierarchy(hierarchy)

    def get_common_names_by_id(self, tax_id):
        """Retrieve common names for a given taxID from the local database."""
        try:
            self.cursor.execute("""
                SELECT name_txt
                FROM names
                WHERE tax_id = ? AND (name_class = 'genbank common name' OR name_class = 'common name')
            """, (tax_id,))
            results = self.cursor.fetchall()
            common_names = [row[0].strip() for row in results if row[0]]
            return common_names
        except sqlite3.Error as e:
            log_error(f"Database error in get_common_names_by_id: {e}")
            return []

    def get_common_name_by_id(self, tax_id):
        """Override base class method to return a single common name (first available)."""
        common_names = self.get_common_names_by_id(tax_id)
        return common_names[0] if common_names else ''


class WORMSTaxonomy_DB(TaxonomySource):
    """
    The WoRMS taxonomy authority's implementation of the TaxonomySource interface, using a local SQLite database.
    """

    def __init__(self, db_path='webapp/static/taxonomy_dbs/WoRMS/worms.db'):
        super().__init__(TaxonomySourceEnum.WORMS)
        self.db_path = os.path.abspath(db_path)  # Ensure absolute path
        log_info(f"Attempting to connect to database: {self.db_path}")

        # Validate database file
        if not os.path.exists(self.db_path):
            log_error(f"Database file does not exist: {self.db_path}")
            raise FileNotFoundError(f"Database file not found: {self.db_path}")
        if not os.access(self.db_path, os.R_OK | os.W_OK):
            log_error(f"No read/write permissions for database file: {self.db_path}")
            raise PermissionError(f"No read/write permissions for: {self.db_path}")

        try:
            self.conn = sqlite3.connect(self.db_path)
            self.cursor = self.conn.cursor()
            log_info("Successfully connected to WoRMS database")
        except sqlite3.OperationalError as e:
            log_error(f"Failed to open database: {e} (SQLite error code: {e.sqlite_errorcode})")
            raise
        except sqlite3.DatabaseError as e:
            log_error(f"Database error: {e}")
            raise

    def __del__(self):
        """Close the database connection when the object is destroyed."""
        try:
            self.conn.close()
            log_info("Database connection closed")
        except AttributeError:
            pass  # Connection might not have been initialized

    def _extract_taxon_id(self, taxon_id):
        """Extract numeric ID from taxonID if it's an LSID (e.g., urn:lsid:marinespecies.org:taxname:<ID>)."""
        if isinstance(taxon_id, str) and taxon_id.startswith('urn:lsid:marinespecies.org:taxname:'):
            return re.search(r'\d+$', taxon_id).group() if re.search(r'\d+$', taxon_id) else taxon_id
        return taxon_id

    def get_aphia_id_by_name(self, name):
        """Retrieve taxonID for a scientific name from the local WoRMS database."""
        try:
            self.cursor.execute("""
                SELECT taxonID
                FROM taxon
                WHERE scientificName = ? AND taxonomicStatus = 'accepted'
            """, (name,))
            result = self.cursor.fetchone()
            taxon_id = result[0] if result else None
            return taxon_id
        except sqlite3.Error as e:
            log_error(f"Database error in get_aphia_id_by_name: {e}")
            return None

    def parse(self, taxon_id, hierarchy):
        """Recursively build hierarchy by querying taxon table."""
        try:
            self.cursor.execute("""
                SELECT scientificName, taxonRank, taxonID, parentNameUsageID
                FROM taxon
                WHERE taxonID = ? AND taxonomicStatus = 'accepted'
            """, (taxon_id,))
            result = self.cursor.fetchone()
            if result:
                taxon_name, taxon_rank, taxon_id, parent_id = result
                numeric_id = self._extract_taxon_id(taxon_id)  # For URL
                link = f'http://marinespecies.org/aphia.php?p=taxdetails&id={numeric_id}'
                provider = 'WORMS'
                hierarchy.append((taxon_rank, taxon_name, taxon_id, link, provider))
                if parent_id:  # Recurse for parent
                    self.parse(parent_id, hierarchy)
            else:
                log_error(f"No taxon found for taxonID {taxon_id}")
        except sqlite3.Error as e:
            log_error(f"Database error in parse: {e}")

    def fill_hierarchy(self, name, levels=None):
        """Build the taxonomic hierarchy for a given name up to the specified level."""
        hierarchy = []
        taxon_id = self.get_aphia_id_by_name(name)
        if taxon_id:
            self.parse(taxon_id, hierarchy)
            if levels:
                hierarchy = hierarchy[:levels]  # Truncate to specified levels
        return self.prune_hierarchy(hierarchy) if hierarchy else None

    def get_common_names_by_id(self, id):
        """ WoRMS does not provide common names in their database download, so we need to use the REST API. """
        numeric_id = self._extract_taxon_id(id)  # For URL
        r = requests.get(f'http://marinespecies.org/rest/AphiaVernacularsByAphiaID/{numeric_id}',
                         timeout=self._timeout)
        common_names = []
        if r and r.text:
            d = json.loads(r.text)
            for rec in d:
                if rec.get('vernacular') and rec.get('language') == 'English':
                    common_names.append(rec.get('vernacular'))
        return [common_name.strip() for common_name in common_names]

    def get_common_name_by_id(self, aphia_id):
        """Override base class method to return a single common name (first available)."""
        common_names = self.get_common_names_by_id(aphia_id)
        return common_names[0] if common_names else ''


###############################################################################################################
#  Implementations using REST APIs
###############################################################################################################

class ITISTaxonomy_REST(TaxonomySource):
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


class WORMSTaxonomy_REST(TaxonomySource):
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


class NCBITaxonomy_REST(TaxonomySource):
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


###############################################################################################################
#  Handle taxonomic coverage CSV file
###############################################################################################################

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
