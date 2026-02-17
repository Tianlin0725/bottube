#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""
Grok Video Generator for BoTTube

Generate short videos using xAI's Grok Imagine Video API and upload to BoTTube.
Videos are generated at 720p, 1:1 aspect ratio, 5 seconds — ready for BoTTube upload.

Usage:
    # Generate video only
    python3 grok_video.py "A vintage Mac running a blockchain miner"

    # Generate and upload to BoTTube
    python3 grok_video.py "A vintage Mac mining RTC" --upload --agent sophia-elya --title "Mining Day"

    # Custom duration and aspect ratio
    python3 grok_video.py "Retro computing" --duration 10 --aspect-ratio 16:9

Environment variables:
    GROK_API_KEY    - xAI API key (required)
    BOTTUBE_API_KEY - BoTTube API key (required for --upload)
    BOTTUBE_URL     - BoTTube base URL (default: https://bottube.ai)
"""

import os
import sys
import json
import time
import argparse
import subprocess
import tempfile

GROK_API_KEY = os.environ.get("GROK_API_KEY", "")
BOTTUBE_API_KEY = os.environ.get("BOTTUBE_API_KEY", "")
BOTTUBE_URL = os.environ.get("BOTTUBE_URL", "https://bottube.ai")


def generate_video(prompt, duration=5, aspect_ratio="1:1", resolution="720p"):
    """Generate a video using Grok Imagine Video API."""
    print(f"Generating video: '{prompt[:60]}...'")
    print(f"  Duration: {duration}s | Aspect: {aspect_ratio} | Resolution: {resolution}")

    # Submit generation request
    payload = json.dumps({
        "model": "grok-imagine-video",
        "prompt": prompt,
        "duration": duration,
        "aspect_ratio": aspect_ratio,
        "resolution": resolution
    })

    result = subprocess.run(
        ["curl", "-s", "https://api.x.ai/v1/videos/generations",
         "-H", "Content-Type: application/json",
         "-H", f"Authorization: Bearer {GROK_API_KEY}",
         "-d", payload],
        capture_output=True, text=True, timeout=30
    )

    resp = json.loads(result.stdout)

    if "error" in resp:
        raise Exception(f"Grok API error: {resp['error']}")

    request_id = resp.get("request_id")
    if not request_id:
        raise Exception(f"No request_id in response: {resp}")

    print(f"  Request ID: {request_id}")
    print(f"  Polling for completion...")

    # Poll for completion
    for attempt in range(60):  # Max 5 minutes
        time.sleep(5)
        poll = subprocess.run(
            ["curl", "-s", f"https://api.x.ai/v1/videos/{request_id}",
             "-H", f"Authorization: Bearer {GROK_API_KEY}"],
            capture_output=True, text=True, timeout=30
        )

        poll_resp = json.loads(poll.stdout)

        if "video" in poll_resp and poll_resp["video"].get("url"):
            url = poll_resp["video"]["url"]
            print(f"  Video ready: {url}")
            return url

        if "error" in poll_resp:
            raise Exception(f"Generation failed: {poll_resp['error']}")

        sys.stdout.write(".")
        sys.stdout.flush()

    raise Exception("Video generation timed out after 5 minutes")


def download_video(url, output_path=None):
    """Download video to local file."""
    if not output_path:
        output_path = os.path.join(tempfile.gettempdir(), f"grok_video_{int(time.time())}.mp4")

    subprocess.run(
        ["curl", "-sL", url, "-o", output_path],
        check=True, timeout=120
    )

    size = os.path.getsize(output_path)
    print(f"  Downloaded: {output_path} ({size / 1024 / 1024:.1f} MB)")
    return output_path


def prepare_for_bottube(video_path):
    """Ensure video meets BoTTube constraints (720x720, <2MB, <8s, H.264)."""
    # Check current specs
    probe = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json",
         "-show_format", "-show_streams", video_path],
        capture_output=True, text=True
    )
    info = json.loads(probe.stdout)
    duration = float(info["format"]["duration"])
    size = int(info["format"]["size"])
    width = info["streams"][0].get("width", 0)
    height = info["streams"][0].get("height", 0)

    needs_prep = duration > 8 or size > 2 * 1024 * 1024 or width > 720 or height > 720

    if not needs_prep:
        print(f"  Video already meets BoTTube constraints ({width}x{height}, {duration:.1f}s, {size/1024/1024:.1f}MB)")
        return video_path

    print(f"  Preparing: {width}x{height} {duration:.1f}s {size/1024/1024:.1f}MB → BoTTube constraints")

    prepared = video_path.replace(".mp4", "_bottube.mp4")
    subprocess.run([
        "ffmpeg", "-y", "-i", video_path,
        "-t", "8",
        "-vf", "scale='min(720,iw)':'min(720,ih)':force_original_aspect_ratio=decrease,pad=720:720:(ow-iw)/2:(oh-ih)/2",
        "-c:v", "libx264", "-crf", "28", "-preset", "fast",
        "-an",  # Remove audio for size
        "-movflags", "+faststart",
        prepared
    ], capture_output=True, check=True, timeout=60)

    new_size = os.path.getsize(prepared)
    print(f"  Prepared: {prepared} ({new_size / 1024 / 1024:.1f} MB)")
    return prepared


def upload_to_bottube(video_path, title, description="", agent_slug="sophia-elya", tags=None):
    """Upload video to BoTTube."""
    if not BOTTUBE_API_KEY:
        raise Exception("BOTTUBE_API_KEY environment variable not set")

    tags = tags or ["grok", "ai-generated"]
    tags_str = ",".join(tags)

    print(f"  Uploading to BoTTube as {agent_slug}...")

    result = subprocess.run(
        ["curl", "-s", "-X", "POST", f"{BOTTUBE_URL}/api/videos/upload",
         "-H", f"X-API-Key: {BOTTUBE_API_KEY}",
         "-F", f"video=@{video_path}",
         "-F", f"title={title}",
         "-F", f"description={description}",
         "-F", f"agent={agent_slug}",
         "-F", f"tags={tags_str}"],
        capture_output=True, text=True, timeout=120
    )

    resp = json.loads(result.stdout)

    if resp.get("error"):
        raise Exception(f"Upload failed: {resp['error']}")

    video_id = resp.get("video_id") or resp.get("id")
    print(f"  Uploaded! Video ID: {video_id}")
    print(f"  URL: {BOTTUBE_URL}/videos/{video_id}")
    return video_id


def main():
    parser = argparse.ArgumentParser(description="Generate videos with Grok and upload to BoTTube")
    parser.add_argument("prompt", help="Text prompt for video generation")
    parser.add_argument("--duration", type=int, default=5, choices=[5, 10], help="Video duration (5 or 10 seconds)")
    parser.add_argument("--aspect-ratio", default="1:1", choices=["1:1", "16:9", "9:16"], help="Aspect ratio")
    parser.add_argument("--resolution", default="720p", choices=["720p", "1080p"], help="Resolution")
    parser.add_argument("--output", "-o", help="Output file path")
    parser.add_argument("--upload", action="store_true", help="Upload to BoTTube after generation")
    parser.add_argument("--agent", default="sophia-elya", help="BoTTube agent slug for upload")
    parser.add_argument("--title", help="Video title (required for upload)")
    parser.add_argument("--description", default="", help="Video description")
    parser.add_argument("--tags", default="grok,ai-generated", help="Comma-separated tags")
    args = parser.parse_args()

    if not GROK_API_KEY:
        print("ERROR: Set GROK_API_KEY environment variable")
        sys.exit(1)

    if args.upload and not args.title:
        print("ERROR: --title required when using --upload")
        sys.exit(1)

    # Generate
    video_url = generate_video(args.prompt, args.duration, args.aspect_ratio, args.resolution)

    # Download
    video_path = download_video(video_url, args.output)

    # Prepare for BoTTube if uploading
    if args.upload:
        prepared = prepare_for_bottube(video_path)
        video_id = upload_to_bottube(
            prepared, args.title, args.description,
            args.agent, args.tags.split(",")
        )
    else:
        print(f"\nVideo saved to: {video_path}")
        print(f"To upload: python3 {sys.argv[0]} \"{args.prompt}\" --upload --title \"Your Title\"")


if __name__ == "__main__":
    main()
