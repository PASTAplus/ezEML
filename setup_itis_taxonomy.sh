#!/bin/bash

# Script to download and set up ITIS taxonomy database with backup
# Date: September 10, 2025

# Set up logging
LOGFILE="setup_itis_taxonomy.log"
exec > >(tee -a "$LOGFILE") 2>&1
echo "Starting ITIS taxonomy setup at $(date)"

# Define directories and files
ITIS_DIR="webapp/static/taxonomies/ITIS"
ITIS_ZIP_URL="https://www.itis.gov/downloads/itisSqlite.zip"
ITIS_ZIP_FILE="$ITIS_DIR/itisSqlite.zip"
DB_DIR="webapp/static/taxonomy_dbs/ITIS"
DB_FILE="$DB_DIR/ITIS.sqlite"
BACKUP_FILE="$DB_DIR/ITIS_backup.sqlite"

# Create ITIS directory if it doesn't exist
if [ ! -d "$ITIS_DIR" ]; then
    echo "Creating directory $ITIS_DIR"
    mkdir -p "$ITIS_DIR"
    if [ $? -ne 0 ]; then
        echo "ERROR: Failed to create directory $ITIS_DIR"
        exit 1
    fi
else
    echo "Directory $ITIS_DIR already exists"
fi

# Download itisSqlite.zip
echo "Downloading $ITIS_ZIP_URL to $ITIS_ZIP_FILE"
curl -L -o "$ITIS_ZIP_FILE" "$ITIS_ZIP_URL"
if [ $? -ne 0 ]; then
    echo "ERROR: Failed to download $ITIS_ZIP_URL"
    exit 1
fi
if [ ! -f "$ITIS_ZIP_FILE" ]; then
    echo "ERROR: Downloaded file $ITIS_ZIP_FILE does not exist"
    exit 1
fi

# Unzip itisSqlite.zip
echo "Unzipping $ITIS_ZIP_FILE to $ITIS_DIR"
python3 extract_zip.py "$ITIS_ZIP_FILE" "$ITIS_DIR"
if [ $? -ne 0 ]; then
    echo "ERROR: Failed to unzip $ITIS_ZIP_FILE"
    exit 1
fi

# Rename subdirectory (e.g., itisSqlite080125) to itisSqlite
echo "Renaming subdirectory to itisSqlite"
SUBDIR=$(find "$ITIS_DIR" -maxdepth 1 -type d -name 'itisSqlite[0-9]*')
if [ -n "$SUBDIR" ]; then
    mv "$SUBDIR" "$ITIS_DIR/itisSqlite"
    if [ $? -ne 0 ]; then
        echo "ERROR: Failed to rename $SUBDIR to $ITIS_DIR/itisSqlite"
        exit 1
    fi
else
    echo "ERROR: No subdirectory matching itisSqlite[0-9]* found"
    exit 1
fi

# Verify ITIS.sqlite exists in the renamed directory
ITIS_SQLITE="$ITIS_DIR/itisSqlite/ITIS.sqlite"
if [ ! -f "$ITIS_SQLITE" ]; then
    echo "ERROR: $ITIS_SQLITE does not exist after unzip"
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

# Backup existing ITIS.sqlite if it exists
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

# Copy ITIS.sqlite to the database directory
echo "Copying $ITIS_SQLITE to $DB_FILE"
cp "$ITIS_SQLITE" "$DB_FILE"
if [ $? -ne 0 ]; then
    echo "ERROR: Failed to copy $ITIS_SQLITE to $DB_FILE"
    exit 1
fi

# Verify database integrity
echo "Checking integrity of $DB_FILE"
sqlite3 "$DB_FILE" "PRAGMA integrity_check;" > /dev/null
if [ $? -ne 0 ]; then
    echo "ERROR: Database integrity check failed for $DB_FILE"
    exit 1
fi
echo "Database integrity check passed"

echo "ITIS taxonomy setup completed successfully at $(date)"
exit 0
