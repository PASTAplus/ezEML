#!/bin/bash

# =============================================
# ezEML Disk Usage Monitor with 90% Alert
# =============================================

TARGET_DIR="/home/pasta/ezeml/user-data"
LOG_FILE="${TARGET_DIR}/disk_usage.log"
ALERT_EMAIL="support@edirepository.org"
THRESHOLD=90

# Ensure log file exists
touch "$LOG_FILE"

TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

echo "==================================================" >> "$LOG_FILE"
echo "Disk Usage Report - $TIMESTAMP" >> "$LOG_FILE"
echo "==================================================" >> "$LOG_FILE"
echo "" >> "$LOG_FILE"

log_command() {
    echo ">>> $1" >> "$LOG_FILE"
    echo "----------------------------------------" >> "$LOG_FILE"
    eval "$1" >> "$LOG_FILE" 2>&1
    echo "" >> "$LOG_FILE"
}

# Run the monitoring commands
log_command "df -h \"$TARGET_DIR\""
log_command "du -sh \"$TARGET_DIR\""
log_command "du -sh \"$TARGET_DIR\"/* | sort -hr | head -n 10"

echo "Disk usage check completed at $TIMESTAMP" >> "$LOG_FILE"
echo "" >> "$LOG_FILE"

# === Check disk usage percentage and send alert if over threshold ===
USAGE_PERCENT=$(df "$TARGET_DIR" | awk 'NR==2 {print $5}' | tr -d '%')

if [ "$USAGE_PERCENT" -ge "$THRESHOLD" ]; then
    SUBJECT="⚠️ ezEML Disk Usage Alert: ${USAGE_PERCENT}% on $(hostname)"

    {
        echo "WARNING: ezEML user-data directory disk usage has exceeded ${THRESHOLD}%!"
        echo ""
        echo "Current usage: ${USAGE_PERCENT}%"
        echo "Directory: ${TARGET_DIR}"
        echo "Hostname: $(hostname)"
        echo "Time: ${TIMESTAMP}"
        echo ""
        echo "=== Full Disk Usage Report ==="
        echo ""
        cat "$LOG_FILE" | tail -n 100   # Last 100 lines (recent report)
    } | mail -s "$SUBJECT" "$ALERT_EMAIL"

    echo "🚨 ALERT: Usage at ${USAGE_PERCENT}% — Email sent to ${ALERT_EMAIL}" >> "$LOG_FILE"
fi

echo "✅ Disk usage check completed." >> "$LOG_FILE"