#!/usr/bin/env bash
set -euo pipefail

reel_path="${1:-output/reel.mp4}"
post_path="${2:-output/static-post.jpg}"
if [[ ! -f "$reel_path" ]]; then
  echo "Reel not found: $reel_path" >&2
  exit 1
fi
if [[ -z "${GITHUB_REPOSITORY:-}" || -z "${GITHUB_TOKEN:-}" ]]; then
  echo "GITHUB_REPOSITORY and GITHUB_TOKEN are required" >&2
  exit 1
fi

media_dir="$(mktemp -d)"
trap 'rm -rf "$media_dir"' EXIT
cp "$reel_path" "$media_dir/reel.mp4"
if [[ -f "$post_path" ]]; then
  cp "$post_path" "$media_dir/static-post.jpg"
fi
git -C "$media_dir" init -q
git -C "$media_dir" checkout -q -b instagram-media
git -C "$media_dir" config user.name "Virtual Cyber Cafe Bot"
git -C "$media_dir" config user.email "actions@users.noreply.github.com"
git -C "$media_dir" add reel.mp4
if [[ -f "$media_dir/static-post.jpg" ]]; then
  git -C "$media_dir" add static-post.jpg
fi
git -C "$media_dir" commit -q -m "Host today's Instagram Reel and post"
git -C "$media_dir" remote add origin "https://x-access-token:${GITHUB_TOKEN}@github.com/${GITHUB_REPOSITORY}.git"
git -C "$media_dir" push -q --force origin instagram-media

video_url="https://raw.githubusercontent.com/${GITHUB_REPOSITORY}/instagram-media/reel.mp4?run=${GITHUB_RUN_ID:-latest}"
image_url="https://raw.githubusercontent.com/${GITHUB_REPOSITORY}/instagram-media/static-post.jpg?run=${GITHUB_RUN_ID:-latest}"
if [[ -n "${GITHUB_OUTPUT:-}" ]]; then
  echo "video_url=$video_url" >> "$GITHUB_OUTPUT"
  echo "image_url=$image_url" >> "$GITHUB_OUTPUT"
else
  echo "$video_url"
  echo "$image_url"
fi
