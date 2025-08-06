#!/usr/bin/env python3
"""
A-Cast Downloader Script

This script reads URLs from a config file and downloads HTML content from each URL.
The downloaded content is saved to files in a specified output directory.
Additionally, it extracts all .mp3 links from the downloaded HTML files.
"""

import json
import os
import sys
import requests
from urllib.parse import urlparse, urljoin
from pathlib import Path
import time
import re
import hashlib
from bs4 import BeautifulSoup


def load_config(config_file="acst-dl-config.json"):
    """Load configuration from JSON file."""
    # First, try to load from the same directory as the script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    local_config_path = os.path.join(script_dir, config_file)

    # If config_file is already an absolute path, use it directly
    if os.path.isabs(config_file):
        config_paths = [config_file]
    else:
        # Try local path first, then /etc
        config_paths = [local_config_path, os.path.join("/etc", config_file)]

    for config_path in config_paths:
        try:
            with open(config_path, "r") as f:
                config = json.load(f)
            print(f"Using config file: {config_path}")
            return config
        except FileNotFoundError:
            continue
        except json.JSONDecodeError as e:
            print(f"Error: Invalid JSON in config file '{config_path}': {e}")
            sys.exit(1)

    # If we get here, no config file was found
    print(f"Error: Config file '{config_file}' not found in:")
    for path in config_paths:
        print(f"  - {path}")
    sys.exit(1)


def create_output_directory(output_dir):
    """Create output directory if it doesn't exist."""
    Path(output_dir).mkdir(parents=True, exist_ok=True)


def generate_filename(url):
    """Generate a safe filename from URL."""
    parsed_url = urlparse(url)
    domain = parsed_url.netloc.replace(":", "_")
    path = parsed_url.path.replace("/", "_").replace("\\", "_")

    # Remove leading/trailing underscores and handle empty paths
    if not path or path == "_":
        path = "index"
    else:
        path = path.strip("_")

    # Add timestamp to avoid conflicts
    timestamp = int(time.time())
    filename = f"{domain}_{path}_{timestamp}.html"

    # Remove any remaining problematic characters
    filename = "".join(c for c in filename if c.isalnum() or c in "._-")

    return filename


def extract_mp3_links(html_content, base_url, max_links=None):
    """Extract .mp3 links from HTML content in order of appearance, with optional limit."""
    mp3_links_with_positions = []
    seen = set()

    try:
        soup = BeautifulSoup(html_content, "html.parser")

        # Find all elements that could contain MP3 links and track their positions
        all_elements = soup.find_all(["a", "audio", "source"])

        for element in all_elements:
            # Stop if we've reached the maximum number of links
            if max_links and len(mp3_links_with_positions) >= max_links:
                break

            mp3_url = None

            # Check href attribute for <a> tags
            if element.name == "a" and element.get("href"):
                href = element["href"]
                if href.lower().endswith(".mp3"):
                    mp3_url = urljoin(base_url, href)

            # Check src attribute for <audio> and <source> tags
            elif element.name in ["audio", "source"] and element.get("src"):
                src = element["src"]
                if src.lower().endswith(".mp3"):
                    mp3_url = urljoin(base_url, src)

            # Add to list if found and not already seen
            if mp3_url and mp3_url not in seen:
                seen.add(mp3_url)
                # Get the position of this element in the original HTML
                element_position = html_content.find(str(element))
                mp3_links_with_positions.append((element_position, mp3_url))

        # Use regex to find any additional .mp3 URLs in the HTML content
        # Only if we haven't reached the limit yet
        if not max_links or len(mp3_links_with_positions) < max_links:
            mp3_pattern = r'https?://[^\s<>"\']+\.mp3(?:\?[^\s<>"\']*)?'
            for match in re.finditer(mp3_pattern, html_content, re.IGNORECASE):
                # Stop if we've reached the maximum number of links
                if max_links and len(mp3_links_with_positions) >= max_links:
                    break

                mp3_url = match.group()
                if mp3_url not in seen:
                    seen.add(mp3_url)
                    mp3_links_with_positions.append((match.start(), mp3_url))

        # Sort by position in HTML and return only the URLs
        mp3_links_with_positions.sort(key=lambda x: x[0])
        ordered_mp3_links = [url for position, url in mp3_links_with_positions]

        # Apply final limit if specified
        if max_links:
            ordered_mp3_links = ordered_mp3_links[:max_links]

        return ordered_mp3_links

    except Exception as e:
        print(f"Error extracting MP3 links: {e}")
        return []


def save_mp3_links(mp3_links, output_dir, source_url, url_name=None):
    """Save extracted MP3 links to a text file."""
    if not mp3_links:
        return None

    try:
        # Generate filename for MP3 links file
        if url_name:
            base_name = url_name
        else:
            parsed_url = urlparse(source_url)
            base_name = parsed_url.netloc.replace(":", "_")

        timestamp = int(time.time())
        links_filename = f"{base_name}_mp3_links_{timestamp}.txt"
        links_filepath = os.path.join(output_dir, links_filename)

        # Save MP3 links to file
        with open(links_filepath, "w", encoding="utf-8") as f:
            f.write(f"MP3 Links extracted from: {source_url}\n")
            if url_name:
                f.write(f"Source name: {url_name}\n")
            f.write(f"Extraction time: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Total links found: {len(mp3_links)}\n")
            f.write("=" * 50 + "\n\n")

            for i, link in enumerate(mp3_links, 1):
                f.write(f"{i}. {link}\n")

        return links_filename

    except Exception as e:
        print(f"Error saving MP3 links: {e}")
        return None


def download_mp3_file(
    mp3_url,
    output_dir,
    timeout=30,
    enable_hash_detection=False,
):
    """Download a single MP3 file with hash-based filename duplicate detection."""
    try:
        # Extract base filename from URL
        parsed_url = urlparse(mp3_url)
        base_filename = os.path.basename(parsed_url.path)

        # If no filename in path, generate one from the URL
        if not base_filename or not base_filename.endswith(".mp3"):
            # Use the last part of the path or generate from URL hash
            url_parts = parsed_url.path.strip("/").split("/")
            if url_parts and url_parts[-1]:
                base_filename = f"{url_parts[-1]}.mp3"
            else:
                # Generate filename from URL hash
                url_hash = hashlib.md5(mp3_url.encode()).hexdigest()[:8]
                base_filename = f"audio_{url_hash}.mp3"

        # Generate filename (use URL hash for unique naming when hash detection is enabled)
        if enable_hash_detection:
            # Use URL hash to create unique filenames for hash-based detection
            url_hash = hashlib.md5(mp3_url.encode()).hexdigest()[:8]
            name_part = base_filename.rsplit(".", 1)[0]
            filename = f"{name_part}_{url_hash}.mp3"
        else:
            # Add timestamp to filename (original behavior)
            timestamp = int(time.time())
            name_part = base_filename.rsplit(".", 1)[0]
            filename = f"{name_part}_{timestamp}.mp3"

        filepath = os.path.join(output_dir, filename)

        # Skip if file already exists (filename-based check with hash)
        if os.path.exists(filepath):
            print(f"    ⏭ Skipping {filename} (file already exists)")
            return {
                "success": True,
                "filename": filename,
                "skipped": True,
                "duplicate": enable_hash_detection,
            }

        # Set headers to mimic a real browser
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }

        print(f"    📥 Downloading {filename}...")
        response = requests.get(mp3_url, timeout=timeout, headers=headers, stream=True)
        response.raise_for_status()

        # Download with progress indication for large files
        total_size = int(response.headers.get("content-length", 0))

        with open(filepath, "wb") as f:
            if total_size > 0:
                downloaded = 0
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        # Simple progress indication for large files (>1MB)
                        if total_size > 1024 * 1024 and downloaded % (1024 * 1024) == 0:
                            progress = (downloaded / total_size) * 100
                            print(f"      Progress: {progress:.1f}%")
            else:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)

        file_size = os.path.getsize(filepath)
        size_mb = file_size / (1024 * 1024)
        print(f"    ✓ Downloaded {filename} ({size_mb:.1f} MB)")

        return {
            "success": True,
            "filename": filename,
            "size": file_size,
            "duplicate": False,
        }

    except requests.exceptions.RequestException as e:
        print(f"    ✗ Error downloading {mp3_url}: {e}")
        return {"success": False, "error": str(e)}
    except Exception as e:
        print(f"    ✗ Unexpected error downloading {mp3_url}: {e}")
        return {"success": False, "error": str(e)}


def clear_mp3_files(output_dir):
    """Clear all MP3 files from the target directory."""
    try:
        if not os.path.exists(output_dir):
            return 0

        mp3_files = []
        for file in os.listdir(output_dir):
            if file.lower().endswith(".mp3"):
                mp3_files.append(os.path.join(output_dir, file))

        if mp3_files:
            print(
                f"  🗑️ Clearing {len(mp3_files)} existing MP3 file(s) from {output_dir}..."
            )
            for mp3_file in mp3_files:
                try:
                    os.remove(mp3_file)
                    print(f"    ✓ Removed {os.path.basename(mp3_file)}")
                except Exception as e:
                    print(f"    ✗ Failed to remove {os.path.basename(mp3_file)}: {e}")

        return len(mp3_files)

    except Exception as e:
        print(f"  ✗ Error clearing MP3 files from {output_dir}: {e}")
        return 0


def clear_all_mp3_files(base_output_dir):
    """Clear all MP3 files from the entire target directory and all subdirectories."""
    try:
        if not os.path.exists(base_output_dir):
            return 0

        total_cleared = 0
        mp3_files = []

        # Walk through all directories and subdirectories
        for root, dirs, files in os.walk(base_output_dir):
            for file in files:
                if file.lower().endswith(".mp3"):
                    mp3_files.append(os.path.join(root, file))

        if mp3_files:
            print(
                f"🗑️ Clearing {len(mp3_files)} existing MP3 file(s) from entire target directory..."
            )
            for mp3_file in mp3_files:
                try:
                    relative_path = os.path.relpath(mp3_file, base_output_dir)
                    os.remove(mp3_file)
                    print(f"  ✓ Removed {relative_path}")
                    total_cleared += 1
                except Exception as e:
                    relative_path = os.path.relpath(mp3_file, base_output_dir)
                    print(f"  ✗ Failed to remove {relative_path}: {e}")

        return total_cleared

    except Exception as e:
        print(f"✗ Error clearing MP3 files from {base_output_dir}: {e}")
        return 0


def download_mp3_files(mp3_links, output_dir, timeout=30, enable_hash_detection=False):
    """Download all MP3 files from the provided links with optional hash-based filename duplicate detection."""
    if not mp3_links:
        return {"total": 0, "successful": 0, "failed": 0, "skipped": 0, "duplicates": 0}

    # Clear existing MP3 files before downloading new ones (only if hash detection is disabled)
    cleared_count = 0
    if not enable_hash_detection:
        cleared_count = clear_mp3_files(output_dir)

    print(f"  📁 Downloading {len(mp3_links)} MP3 file(s) to {output_dir}...")
    if enable_hash_detection:
        print(f"  🔍 Hash-based filename duplicate detection: ENABLED")

    successful = 0
    failed = 0
    skipped = 0
    duplicates = 0
    total_size = 0

    for i, mp3_url in enumerate(mp3_links, 1):
        print(f"  [{i}/{len(mp3_links)}] {mp3_url}")
        result = download_mp3_file(
            mp3_url,
            output_dir,
            timeout,
            enable_hash_detection=enable_hash_detection,
        )

        if result["success"]:
            if result.get("skipped"):
                skipped += 1
                if result.get("duplicate"):
                    duplicates += 1
            else:
                successful += 1
                total_size += result.get("size", 0)
        else:
            failed += 1

    total_size_mb = total_size / (1024 * 1024)

    # Enhanced summary with duplicate information
    summary_parts = [
        f"{successful} downloaded",
        f"{skipped} skipped",
        f"{failed} failed",
    ]
    if enable_hash_detection and duplicates > 0:
        summary_parts.insert(1, f"{duplicates} duplicates")

    summary = ", ".join(summary_parts)
    print(f"  📊 MP3 Download Summary: {summary} ({total_size_mb:.1f} MB total)")

    return {
        "total": len(mp3_links),
        "successful": successful,
        "failed": failed,
        "skipped": skipped,
        "duplicates": duplicates,
        "total_size": total_size,
        "cleared": cleared_count,
    }


def download_html(
    url,
    output_dir,
    timeout=30,
    max_mp3_links=None,
    url_name=None,
    download_mp3s=False,
    enable_hash_detection=False,
):
    """Download HTML content from URL and save to file, then extract MP3 links."""
    try:
        print(f"Downloading: {url}")

        # Set headers to mimic a real browser
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }

        response = requests.get(url, timeout=timeout, headers=headers)
        response.raise_for_status()  # Raise an exception for bad status codes

        # Generate filename
        filename = generate_filename(url)
        filepath = os.path.join(output_dir, filename)

        # Save content to file
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(response.text)

        print(f"✓ Successfully downloaded: {url} -> {filename}")

        # Extract MP3 links from the downloaded HTML
        limit_text = f" (limit: {max_mp3_links})" if max_mp3_links else ""
        print(f"  Extracting MP3 links from {filename}{limit_text}...")
        mp3_links = extract_mp3_links(response.text, url, max_mp3_links)

        mp3_download_stats = {"total": 0, "successful": 0, "failed": 0, "skipped": 0}

        if mp3_links:
            # Save MP3 links to a separate file
            links_filename = save_mp3_links(mp3_links, output_dir, url, url_name)
            if links_filename:
                print(f"  ✓ Found {len(mp3_links)} MP3 link(s) -> {links_filename}")
            else:
                print(f"  ✗ Error saving MP3 links")

            # Download MP3 files if enabled
            if download_mp3s:
                mp3_download_stats = download_mp3_files(
                    mp3_links,
                    output_dir,
                    timeout,
                    enable_hash_detection=enable_hash_detection,
                )

            # Always clean up HTML and MP3 links files when MP3 downloading is enabled
            if download_mp3s:
                cleanup_files = []

                # Add HTML file to cleanup list
                html_filepath = os.path.join(output_dir, filename)
                if os.path.exists(html_filepath):
                    cleanup_files.append((html_filepath, filename))

                # Add MP3 links file to cleanup list
                if links_filename:
                    links_filepath = os.path.join(output_dir, links_filename)
                    if os.path.exists(links_filepath):
                        cleanup_files.append((links_filepath, links_filename))

                # Perform cleanup
                if cleanup_files:
                    print(f"  🧹 Cleaning up temporary files...")
                    for file_path, file_name in cleanup_files:
                        try:
                            os.remove(file_path)
                            print(f"    ✓ Removed {file_name}")
                        except Exception as e:
                            print(f"    ✗ Failed to remove {file_name}: {e}")
        else:
            print(f"  ℹ No MP3 links found in {filename}")

        return {
            "success": True,
            "html_file": filename,
            "mp3_count": len(mp3_links),
            "mp3_downloads": mp3_download_stats,
        }

    except requests.exceptions.RequestException as e:
        print(f"✗ Error downloading {url}: {e}")
        return {"success": False, "error": str(e)}
    except Exception as e:
        print(f"✗ Unexpected error downloading {url}: {e}")
        return {"success": False, "error": str(e)}


def main():
    """Main function to orchestrate the download process."""
    print("A-Cast Downloader Starting...")

    # Load configuration
    config = load_config()

    # Extract configuration values
    urls_config = config.get("urls", {})
    output_dir_config = config.get("output_directory", "downloads")
    timeout = config.get("timeout", 30)
    max_mp3_links = config.get("max_mp3_links", None)
    download_mp3s = config.get("download_mp3_files", False)

    # Hash-based duplicate detection configuration
    hash_detection_config = config.get("hash_duplicate_detection", {})
    enable_hash_detection = hash_detection_config.get("enabled", False)

    # Handle absolute and relative paths for output directory
    output_dir = os.path.abspath(os.path.expanduser(output_dir_config))

    # Handle both old list format and new dict format for backward compatibility
    if isinstance(urls_config, list):
        # Old format: list of URLs
        urls_dict = {f"url_{i+1}": url for i, url in enumerate(urls_config)}
    elif isinstance(urls_config, dict):
        # New format: dict with names and URLs
        urls_dict = urls_config
    else:
        print("Error: Invalid URLs configuration format.")
        sys.exit(1)

    if not urls_dict:
        print("Error: No URLs found in config file.")
        sys.exit(1)

    # Create main output directory
    create_output_directory(output_dir)
    print(f"Output directory: {output_dir}")

    if max_mp3_links:
        print(f"MP3 links limit: {max_mp3_links}")

    if download_mp3s:
        print(f"🎵 MP3 file downloading: ENABLED")
        if enable_hash_detection:
            print(f"🔐 Hash-based filename duplicate detection: ENABLED")
        else:
            print(f"🔐 Hash-based duplicate detection: DISABLED")
    else:
        print(f"🎵 MP3 file downloading: DISABLED")

    # Download each URL and extract MP3 links
    successful_downloads = 0
    total_mp3_links = 0
    total_mp3_downloads = 0
    total_urls = len(urls_dict)

    for i, (url_name, url) in enumerate(urls_dict.items(), 1):
        print(f"\n[{i}/{total_urls}] Processing '{url_name}': {url}")

        # Create subfolder for this URL
        url_output_dir = os.path.join(output_dir, url_name)
        create_output_directory(url_output_dir)
        print(f"  Subfolder: {url_output_dir}")

        result = download_html(
            url,
            url_output_dir,
            timeout,
            max_mp3_links,
            url_name,
            download_mp3s,
            enable_hash_detection=enable_hash_detection,
        )

        if isinstance(result, dict) and result.get("success"):
            successful_downloads += 1
            total_mp3_links += result.get("mp3_count", 0)
            if download_mp3s:
                mp3_stats = result.get("mp3_downloads", {})
                total_mp3_downloads += mp3_stats.get("successful", 0)
        elif result is True:  # Backward compatibility
            successful_downloads += 1

    # Summary
    print(f"\n{'='*60}")
    print(f"A-Cast Download Summary:")
    print(f"Total URLs processed: {total_urls}")
    print(f"Successful downloads: {successful_downloads}")
    print(f"Failed downloads: {total_urls - successful_downloads}")
    print(f"Total MP3 links found: {total_mp3_links}")
    if download_mp3s:
        print(f"Total MP3 files downloaded: {total_mp3_downloads}")
    if max_mp3_links:
        print(f"MP3 links limit per URL: {max_mp3_links}")
    print(f"Output directory: {output_dir}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
