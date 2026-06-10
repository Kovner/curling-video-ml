#!/usr/bin/env bash
# Download the test game (or just the test end) from YouTube.
#
# Notes:
# - Requires: pip install "yt-dlp[default]" yt-dlp-ejs
# - On datacenter IPs YouTube withholds formats behind a PO token; the
#   bgutil-ytdlp-pot-provider plugin (pip) + its node server fixes that:
#     git clone https://github.com/Brainicism/bgutil-ytdlp-pot-provider
#     cd bgutil-ytdlp-pot-provider/server && npm install && npx tsc && node build/main.js &
# - A JS runtime (node >= 22 or deno) is needed for YouTube's n-challenge.
# - Stream URLs are IP-bound: download must run from the same egress IP that
#   talks to youtube.com (i.e. a normal home connection works; some proxied
#   cloud environments cannot download at all).
set -euo pipefail

URL="https://www.youtube.com/watch?v=a2EJcV29ido"
mkdir -p data

# Single end for testing (15:22 - 30:58). Drop --download-sections for the full game.
yt-dlp \
  --js-runtimes node \
  --extractor-args "youtube:player_client=mweb" \
  -f "bv*[height<=480][ext=mp4]/bv*[height<=480]/bv*" \
  --download-sections "*15:22-30:58" \
  -o "data/end_test.%(ext)s" \
  "$URL"

# Fallback that works even when video formats are blocked: storyboard preview
# frames (320x180, ~1 frame / 10 s) for coarse analysis.
# yt-dlp --extractor-args "youtube:player_client=mweb" -f sb0 \
#   -o "data/storyboard.%(ext)s" "$URL"
