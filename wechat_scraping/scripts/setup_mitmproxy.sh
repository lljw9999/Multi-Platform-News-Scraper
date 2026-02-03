#!/bin/bash
# Setup script for mitmproxy - used to capture WeChat article credentials
# mitmproxy intercepts HTTPS traffic to extract authentication tokens

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "=== Mitmproxy Setup for 公众号 Article Scraping ==="
echo ""

# Check if Homebrew is installed
if ! command -v brew &> /dev/null; then
    echo "Homebrew not found. Please install it first:"
    echo '/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"'
    exit 1
fi

# Install mitmproxy
if ! command -v mitmproxy &> /dev/null; then
    echo "Installing mitmproxy..."
    brew install mitmproxy
else
    echo "mitmproxy already installed: $(mitmproxy --version | head -1)"
fi

# Get local IP
LOCAL_IP=$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || echo "Unable to detect")

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Your Mac's IP address: $LOCAL_IP"
echo ""
echo "=== IMPORTANT: Configure your iPhone ==="
echo ""
echo "Step 1: Connect iPhone to same Wi-Fi as Mac"
echo ""
echo "Step 2: Configure iPhone proxy:"
echo "   Settings → Wi-Fi → [Your Network] → Configure Proxy → Manual"
echo "   Server: $LOCAL_IP"
echo "   Port: 8080"
echo ""
echo "Step 3: Start mitmproxy (run in another terminal):"
echo "   mitmweb --listen-port 8080"
echo ""
echo "Step 4: Install mitmproxy CA certificate on iPhone:"
echo "   - Open Safari on iPhone"
echo "   - Go to: http://mitm.it"
echo "   - Download the iOS certificate"
echo "   - Settings → General → VPN & Device Management → Install"
echo "   - Settings → General → About → Certificate Trust Settings → Enable"
echo ""
echo "Step 5: Capture credentials:"
echo "   - Open WeChat on iPhone"
echo "   - Open any 公众号 article"
echo "   - In mitmproxy web UI (http://localhost:8081), look for:"
echo "     * Host: mp.weixin.qq.com"
echo "     * Find 'cookie' and 'appmsg_token' in request headers/params"
echo ""
echo "Step 6: Run the scraper:"
echo "   python3 $PROJECT_DIR/scrapers/article_scraper.py"
echo ""
echo "=== Security Reminder ==="
echo "After scraping, remove the mitmproxy certificate from your iPhone:"
echo "   Settings → General → VPN & Device Management → mitmproxy → Remove"
echo ""
