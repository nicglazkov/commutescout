#!/usr/bin/env bash
# Regenerates static/vendor/deck-slim.min.js (tree-shaken deck.gl).
# Run manually when bumping deck.gl; the artifact is committed so the
# repo and CI keep working with no build step.
set -euo pipefail
DIR=$(mktemp -d)
cd "$DIR"
npm init -y > /dev/null
npm install --no-audit --no-fund @deck.gl/core@9.3.7 @deck.gl/layers@9.3.7 esbuild
cat > entry.js <<'JS'
import { Deck } from '@deck.gl/core';
import { ScatterplotLayer, PathLayer, SolidPolygonLayer } from '@deck.gl/layers';
window.deckSlim = { Deck, ScatterplotLayer, PathLayer, SolidPolygonLayer };
JS
npx esbuild entry.js --bundle --minify --format=iife --target=es2020 \
  --outfile=deck-slim.min.js
echo "Copy deck-slim.min.js into src/ca_roads_demo/static/vendor/"
