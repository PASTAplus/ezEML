#!/bin/bash

# Script to download and set up NCBI taxonomy database with backup
# Date: September 10, 2025

# Set up logging
LOGFILE="setup_ncbi_taxonomy.log"
exec > >(tee -a "$LOGFILE") 2>&1
echo "Starting NCBI taxonomy setup at $(date)"

# Define directories and files
NCBI_DIR="webapp/static/taxonomies/NCBI"
TAXDUMP_URL="https://ftp.ncbi.nlm.nih.gov/pub/taxonomy/taxdump.tar.gz"
TAXDUMP_FILE="$NCBI_DIR/taxdump.tar.gz"
DB_DIR="webapp/static/taxonomy_dbs/NCBI"
DB_FILE="$DB_DIR/ncbi_taxonomy.db"
BACKUP_FILE="$DB_DIR/ncbi_taxonomy_backup.db"
SETUP_SCRIPT="webapp/views/coverage/setup_ncbi_db.py"

# Create NCBI directory if it doesn't exist
if [ ! -d "$NCBI_DIR" ]; then
    echo "Creating directory $NCBI_DIR"
    mkdir -p "$NCBI_DIR"
    if [ $? -ne 0 ]; then
        echo "ERROR: Failed to create directory $NCBI_DIR"
        exit 1
    fi
else
    echo "Directory $NCBI_DIR already exists"
fi

# Download taxdump.tar.gz
echo "Downloading $TAXDUMP_URL to $TAXDUMP_FILE"
curl -L -o "$TAXDUMP_FILE" "$TAXDUMP_URL"
if [ $? -ne 0 ]; then
    echo "ERROR: Failed to download $TAXDUMP_URL"
    exit 1
fi
if [ ! -f "$TAXDUMP_FILE" ]; then
    echo "ERROR: Downloaded file $TAXDUMP_FILE does not exist"
    exit 1
fi

# Unzip taxdump.tar.gz
echo "Unzipping $TAXDUMP_FILE to $NCBI_DIR"
tar -xzf "$TAXDUMP_FILE" -C "$NCBI_DIR"
if [ $? -ne 0 ]; then
    echo "ERROR: Failed to unzip $TAXDUMP_FILE"
    exit 1
fi

# Create database directory if it doesn't exist
if [ ! -d "$DB_DIR" ]; then
    echo "Creating directory $DB_DIR"
    mkdir -p "$DB_DIR"
    if [ $? -ne 0 ]; then
        echo "ERROR: Failed to create directory $DB_DIR"
        exit 1
    fi
else
    echo "Directory $DB_DIR already exists"
fi

# Backup existing ncbi_taxonomy.db if it exists
if [ -f "$DB_FILE" ]; then
    echo "Backing up $DB_FILE to $BACKUP_FILE"
    cp "$DB_FILE" "$BACKUP_FILE"
    if [ $? -ne 0 ]; then
        echo "ERROR: Failed to create backup $BACKUP_FILE"
        exit 1
    fi
    echo "Backup created successfully"
else
    echo "No existing $DB_FILE to backup"
fi

# Run setup_ncbi_db.py
echo "Running $SETUP_SCRIPT"
if [ ! -f "$SETUP_SCRIPT" ]; then
    echo "ERROR: Setup script $SETUP_SCRIPT does not exist"
    exit 1
fi
python3 "$SETUP_SCRIPT" --nodes_file="$NCBI_DIR/nodes.dmp" --names_file="$NCBI_DIR/names.dmp" --db_path="$DB_FILE"
if [ $? -ne 0 ]; then
    echo "ERROR: Failed to run $SETUP_SCRIPT"
    exit 1
fi

echo "NCBI taxonomy setup completed successfully at $(date)"
exit 0

