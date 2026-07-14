#!/bin/bash

set -e

echo "====================================="
echo " SandSwap AI Local Deployment"
echo "====================================="

PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"

echo ""
echo "[1/5] Building frontend..."
cd "$PROJECT_ROOT/frontend"
npm run build

echo ""
echo "[2/5] Deploying frontend..."
sudo rm -rf /var/www/sandswap/*
sudo cp -r dist/* /var/www/sandswap/

echo ""
echo "[3/5] Restarting Nginx..."
sudo systemctl restart nginx

echo ""
echo "[4/5] Verifying frontend deployment..."
ls -lh /var/www/sandswap/assets

echo ""
echo "[5/5] Deployment completed successfully!"

echo ""
echo "SandSwap AI is available at:"
echo "https://ai.testlabs.co.in"
