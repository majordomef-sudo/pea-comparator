#!/bin/bash
# Wrapper pour lancer Chromium snap en mode headless sans sandbox
# Résout les problèmes de sandboxing avec snap chromium

# Nettoyer les traces de sessions précédentes
rm -rf /tmp/.com.google.Chrome.* /tmp/chromium.* 2>/dev/null

# Lancer chromium headless avec les flags nécessaires
/snap/bin/chromium \
  --headless \
  --no-sandbox \
  --disable-gpu \
  --disable-dev-shm-usage \
  --disable-software-rasterizer \
  --disable-features=VizDisplayCompositor \
  --remote-debugging-port=18800 \
  "$@"
