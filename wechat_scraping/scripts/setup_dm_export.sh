#!/bin/bash
# Setup script for WeChat DM Export using WechatExporter
# This tool exports WeChat chat history from iPhone backups

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
TOOLS_DIR="$PROJECT_DIR/tools"

echo "=== WeChat DM Export Setup ==="
echo ""

# Create tools directory
mkdir -p "$TOOLS_DIR"

# Download WechatExporter for Mac
WECHAT_EXPORTER_VERSION="v1.8.0.10"
WECHAT_EXPORTER_URL="https://github.com/BlueMatthew/WechatExporter/releases/download/${WECHAT_EXPORTER_VERSION}/v1.8.0.10_x64_macos.zip"
WECHAT_EXPORTER_ZIP="$TOOLS_DIR/WechatExporter.zip"
WECHAT_EXPORTER_DIR="$TOOLS_DIR/WechatExporter"

if [ ! -d "$WECHAT_EXPORTER_DIR" ]; then
    echo "Downloading WechatExporter ${WECHAT_EXPORTER_VERSION}..."
    curl -L -o "$WECHAT_EXPORTER_ZIP" "$WECHAT_EXPORTER_URL"
    
    echo "Extracting..."
    unzip -o "$WECHAT_EXPORTER_ZIP" -d "$TOOLS_DIR"
    rm "$WECHAT_EXPORTER_ZIP"
    
    # Find the extracted app
    EXTRACTED_APP=$(find "$TOOLS_DIR" -name "WechatExporter.app" -type d 2>/dev/null | head -1)
    if [ -n "$EXTRACTED_APP" ]; then
        echo "Found: $EXTRACTED_APP"
    fi
    
    echo "WechatExporter downloaded successfully!"
else
    echo "WechatExporter already exists at $WECHAT_EXPORTER_DIR"
fi

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Next steps:"
echo "1. Connect your iPhone to Mac"
echo "2. Open Finder (macOS Catalina+) or iTunes"
echo "3. Create a backup WITHOUT encryption"
echo "   - Backup location: ~/Library/Application Support/MobileSync/Backup/"
echo ""
echo "4. Run WechatExporter:"
echo "   open '$TOOLS_DIR/WechatExporter.app' (if extracted)"
echo "   OR double-click the app in Finder"
echo ""
echo "5. In WechatExporter:"
echo "   - Select your backup folder"
echo "   - Choose conversations to export"
echo "   - Export to: $PROJECT_DIR/output/chats/"
echo ""
