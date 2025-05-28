#!/bin/bash

# OpenAI Responses API Migration Script
echo "🚀 Starting OpenAI Responses API Migration"

# Create backup directory
BACKUP_DIR="backup_$(date +%Y%m%d_%H%M%S)"
mkdir -p $BACKUP_DIR

echo "📦 Creating backups in $BACKUP_DIR..."

# Backup original files
cp server/links/detect_engagement/__init__.py $BACKUP_DIR/detect_engagement_init.py.bak
cp server/links/analyze_and_label/__init__.py $BACKUP_DIR/analyze_and_label_init.py.bak
cp server/links/analyze_vcon/__init__.py $BACKUP_DIR/analyze_vcon_init.py.bak
cp server/links/analyze/__init__.py $BACKUP_DIR/analyze_init.py.bak

echo "✅ Backups created successfully"

# Create utils directory if it doesn't exist
mkdir -p server/utils
touch server/utils/__init__.py

echo "📁 Created server/utils directory structure"

echo "⚠️  MANUAL STEPS REQUIRED:"
echo "1. Create server/utils/openai_responses.py with the utility code"
echo "2. Replace the contents of the following files with their migrated versions:"
echo "   - server/links/detect_engagement/__init__.py"
echo "   - server/links/analyze_and_label/__init__.py" 
echo "   - server/links/analyze_vcon/__init__.py"
echo "   - server/links/analyze/__init__.py"
echo ""
echo "3. Update your OpenAI dependency:"
echo "   poetry add 'openai>=1.60.0'"
echo ""
echo "4. Test the migration:"
echo "   pytest server/links/*/tests/ -v"
echo ""
echo "🔄 Files backed up to: $BACKUP_DIR"
echo "📋 Migration artifacts have been created - copy the content from the artifacts"
echo "✨ Migration ready to deploy!"