import pandas as pd
import sqlite3
import logging
import csv

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def get_field_count(file_path, delimiter='|'):
    """Count the number of fields in the first line of a file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            first_line = f.readline().strip()
            return len(first_line.split(delimiter))
    except Exception as e:
        logger.error(f"Error reading {file_path}: {e}")
        raise

def setup_ncbi_db(nodes_file='path/to/nodes.dmp', names_file='path/to/names.dmp', db_path='ncbi_taxonomy.db'):
    """Import NCBI taxdump files into a SQLite database."""
    try:
        conn = sqlite3.connect(db_path)
        logger.info(f"Connected to database: {db_path}")

        # Define expected columns (excluding trailing delimiter)
        nodes_columns = [
            'tax_id', 'parent_tax_id', 'rank', 'embl_code', 'division_id',
            'inherited_div_flag', 'genetic_code_id', 'inherited_gc_flag',
            'mito_genetic_code_id', 'inherited_mgc_flag', 'genbank_hidden_flag',
            'hidden_subtree_root_flag', 'comments'
        ]
        names_columns = ['tax_id', 'name_txt', 'unique_name', 'name_class']

        # Count fields in files
        nodes_field_count = get_field_count(nodes_file)
        names_field_count = get_field_count(names_file)
        logger.info(f"nodes.dmp has {nodes_field_count} fields")
        logger.info(f"names.dmp has {names_field_count} fields")

        # Adjust column names to account for trailing delimiter
        nodes_names = nodes_columns + ['trailing'] if nodes_field_count > len(nodes_columns) else nodes_columns
        names_names = names_columns + ['trailing'] if names_field_count > len(names_columns) else names_columns

        # Import nodes.dmp
        logger.info(f"Importing {nodes_file}")
        df_nodes = pd.read_csv(
            nodes_file,
            sep='|',
            encoding='utf-8',
            low_memory=False,
            header=None,
            names=nodes_names,
            usecols=['tax_id', 'parent_tax_id', 'rank']  # Only keep needed columns
        )
        df_nodes = df_nodes.apply(lambda x: x.str.strip() if x.dtype == "object" else x)  # Remove whitespace
        df_nodes.to_sql('nodes', conn, if_exists='replace', index=False)
        logger.info("Imported nodes.dmp")

        # Import names.dmp
        logger.info(f"Importing {names_file}")
        df_names = pd.read_csv(
            names_file,
            sep='|',
            encoding='utf-8',
            low_memory=False,
            header=None,
            names=names_names,
            usecols=['tax_id', 'name_txt', 'name_class']
        )
        df_names = df_names.apply(lambda x: x.str.strip() if x.dtype == "object" else x)
        df_names.to_sql('names', conn, if_exists='replace', index=False)
        logger.info("Imported names.dmp")

        # Create indexes for performance
        conn.execute("CREATE INDEX IF NOT EXISTS idx_tax_id_nodes ON nodes(tax_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_parent_tax_id ON nodes(parent_tax_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_tax_id_names ON names(tax_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_name_txt ON names(name_txt)")
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
    download_path = '../../static/taxonomies/NCBI/taxdump'
    setup_ncbi_db(nodes_file=f'{download_path}/nodes.dmp', names_file=f'{download_path}/names.dmp', db_path='ncbi_taxonomy.db')