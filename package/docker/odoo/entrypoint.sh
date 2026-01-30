#!/bin/bash
set -e

# Fix permissions for filestore and odoo directories
# This must run as root (before switching to odoo user)
# When volumes are mounted, they may have incorrect ownership
if [ "$(id -u)" = "0" ]; then
    # Fix permissions for filestore if it exists
    if [ -d "/var/lib/odoo/filestore" ]; then
        echo "Fixing permissions for /var/lib/odoo/filestore..."
        chown -R odoo:odoo /var/lib/odoo/filestore 2>/dev/null || true
        chmod -R u+rwX /var/lib/odoo/filestore 2>/dev/null || true
    fi
    
    # Fix permissions for odoo app data directory if it exists
    if [ -d "/var/lib/odoo" ]; then
        echo "Fixing permissions for /var/lib/odoo..."
        chown -R odoo:odoo /var/lib/odoo 2>/dev/null || true
        chmod -R u+rwX /var/lib/odoo 2>/dev/null || true
    fi
    
    # Ensure /etc/odoo is accessible
    if [ -d "/etc/odoo" ]; then
        chown -R odoo:odoo /etc/odoo 2>/dev/null || true
    fi
fi

# Execute the original Odoo entrypoint
# The base Odoo entrypoint will handle user switching if needed
exec /entrypoint.sh "$@"
