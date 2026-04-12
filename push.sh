#!/bin/bash

# Configuration
IMAGE_NAME="ghcr.io/sudo-py-dev/lex-tg:latest"

echo "📦 Building Lex Bot image..."
docker build -t $IMAGE_NAME .

if [ $? -eq 0 ]; then
    echo "🚀 Pushing to GitHub Registry..."
    docker push $IMAGE_NAME
    if [ $? -eq 0 ]; then
        echo "✅ Success! Your image is now on GitHub."
        echo "🔗 View it here: https://github.com/sudo-py-dev/lex-tg/pkgs/container/lex-tg"
    else
        echo "❌ Push failed. Did you run 'docker login'?"
    fi
else
    echo "❌ Build failed."
fi
