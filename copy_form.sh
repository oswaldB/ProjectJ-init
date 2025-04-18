
#!/bin/bash

# Check if form ID is provided
if [ -z "$1" ]; then
    echo "Usage: ./copy_form.sh <form_id>"
    exit 1
fi

FORM_ID=$1
SOURCE="local_bucket/sultan/forms/${FORM_ID}.json"
DEST_DIR="local_bucket/jaffar/configs"
DEST="${DEST_DIR}/${FORM_ID}.json"

# Create destination directory if it doesn't exist
mkdir -p "$DEST_DIR"

# Copy the file
if [ -f "$SOURCE" ]; then
    cp "$SOURCE" "$DEST"
    echo "Form copied successfully to ${DEST}"
else
    echo "Error: Source file ${SOURCE} not found"
    exit 1
fi
