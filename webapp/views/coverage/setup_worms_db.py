import pandas as pd
import sqlite3
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def setup_worms_db(taxon_file='path/to/taxon.txt', db_path='worms.db'):
    """Import WoRMS CSVs into a SQLite database."""
    try:
        conn = sqlite3.connect(db_path)
        logger.info(f"Connected to database: {db_path}")

        # Import taxon.txt
        logger.info(f"Importing {taxon_file}")
        df_taxon = pd.read_csv(taxon_file, sep='\t', low_memory=False)
        df_taxon.to_sql('taxon', conn, if_exists='replace', index=False)
        logger.info("Imported taxon.txt")

        # Create indexes for performance
        conn.execute("CREATE INDEX IF NOT EXISTS idx_taxonid ON taxon(taxonID)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_scientificname ON taxon(scientificName)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_parentnameusageid ON taxon(parentNameUsageID)")
        conn.commit()
        logger.info("Created indexes")

        # Test database integrity
        cursor = conn.cursor()
        cursor.execute("PRAGMA integrity_check;")
        result = cursor.fetchone()
        if result[0] != 'ok':
            logger.error(f"Database integrity check failed: {result}")
            raise sqlite3.DatabaseError(f"Invalid SQLite database: {db_path}, integrity check failed: {result}")

        conn.close()
        logger.info("Database setup complete")
    except Exception as e:
        logger.error(f"Error setting up database: {e}")
        raise

if __name__ == "__main__":
    download_path = '../../static/taxonomies/WoRMS/WoRMS_download'
    setup_worms_db(taxon_file=f'{download_path}/taxon.txt', db_path='../../static/taxonomy_dbs/WoRMS/worms.db')
