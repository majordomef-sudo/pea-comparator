#!/bin/bash
# Installer le proxy newsletter
echo "=== Installation du proxy newsletter ==="

# 1. Copier le service systemd
sudo cp /home/ubuntu/.openclaw/workspace/newsletter-proxy/alfred-newsletter-proxy.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable alfred-newsletter-proxy
sudo systemctl start alfred-newsletter-proxy
echo "✓ Proxy demarre"

# 2. Installer la config nginx
# NOTE: Adapte le chemin si tu utilises deja une config nginx pour le site
# Verifie d'abord: ls /etc/nginx/sites-enabled/ | grep alfred
sudo cp /home/ubuntu/.openclaw/workspace/newsletter-proxy/nginx-alfredstudio.conf /etc/nginx/sites-enabled/alfredstudio.mooo.com

# 3. Tester et recharger nginx
sudo nginx -t && sudo nginx -s reload
echo "✓ Nginx rechargé"

# 4. Verifier que le proxy tourne
sleep 2
curl -s http://127.0.0.1:3001/api/newsletter -X POST -H "Content-Type: application/json" -d '{"email":"test@example.com"}' | head -c 200
echo ""
echo "✓ Installation terminée"
