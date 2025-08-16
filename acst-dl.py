#!/usr/bin/env python3
"""
Podcast Downloader Script

This script reads URLs from a config file and downloads content from each URL.
The downloaded content is saved to files in a specified output directory.
Additionally, it extracts all .mp3 links from the downloaded content (HTML pages, RSS feeds, etc.).
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
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
import warnings
import urllib3
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, TALB, TRCK, TDRC


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
            print(f"📄 Using config file: {config_path}")
            return config
        except FileNotFoundError:
            continue
        except json.JSONDecodeError as e:
            print(f"❌ Error: Invalid JSON in config file '{config_path}': {e}")
            sys.exit(1)

    # If we get here, no config file was found
    print(f"❌ Error: Config file '{config_file}' not found in:")
    for path in config_paths:
        print(f"  📁 {path}")
    sys.exit(1)


def create_output_directory(output_dir):
    """Create output directory if it doesn't exist."""
    Path(output_dir).mkdir(parents=True, exist_ok=True)


def compare_tag_values(current_tags, new_album, new_track=None, new_release_date=None):
    """Compare current tag values with new values to determine if update is needed."""
    changes_needed = False
    changes = []

    # Check Album tag (TALB)
    current_album = None
    if current_tags and "TALB" in current_tags:
        current_album = (
            str(current_tags["TALB"].text[0]) if current_tags["TALB"].text else None
        )

    if current_album != new_album:
        changes_needed = True
        changes.append(f"Album: '{current_album}' → '{new_album}'")

    # Check Track tag (TRCK)
    if new_track is not None:
        current_track = None
        if current_tags and "TRCK" in current_tags:
            current_track = (
                str(current_tags["TRCK"].text[0]) if current_tags["TRCK"].text else None
            )

        if current_track != str(new_track):
            changes_needed = True
            changes.append(f"Track: '{current_track}' → '{new_track}'")

    # Check Release Date tag (TDRC)
    if new_release_date is not None:
        current_release_date = None
        if current_tags and "TDRC" in current_tags:
            current_release_date = (
                str(current_tags["TDRC"].text[0]) if current_tags["TDRC"].text else None
            )

        if current_release_date != new_release_date:
            changes_needed = True
            changes.append(
                f"Release Date: '{current_release_date}' → '{new_release_date}'"
            )

    return changes_needed, changes


def update_mp3_tags(
    filepath,
    album_name,
    track_number=None,
    enable_track_tagging=False,
    enable_release_date_tagging=False,
):
    """Update MP3 tags, specifically setting the Album tag to the folder name and optionally the track number and release date."""
    try:
        # Calculate release date once if track_number is provided and release date tagging is enabled
        release_date = None
        if track_number is not None and enable_release_date_tagging:
            current_time = time.localtime()
            release_date = (
                f"{current_time.tm_year}-{current_time.tm_mon:02d}-{track_number:02d}"
            )

        # Build tag info for display
        tag_info = f"Album = '{album_name}'"
        if track_number is not None and enable_track_tagging:
            tag_info += f", Track = {track_number}"
        if track_number is not None and enable_release_date_tagging:
            tag_info += f", Release Date = {release_date}"

        # Add disabled status info
        disabled_tags = []
        if track_number is not None and not enable_track_tagging:
            disabled_tags.append("Track")
        if track_number is not None and not enable_release_date_tagging:
            disabled_tags.append("Release Date")
        if disabled_tags:
            tag_info += f" ({', '.join(disabled_tags)} tagging disabled)"

        print(f"    🏷️ Checking MP3 tags: {tag_info}")

        # Load the MP3 file
        audio_file = MP3(filepath, ID3=ID3)

        # Add ID3 tag if it doesn't exist
        if audio_file.tags is None:
            audio_file.add_tags()
            print(f"    🏷️ Added new ID3 tags to file")

        # Determine which values we want to set
        new_track = track_number if enable_track_tagging else None
        new_release_date = release_date if enable_release_date_tagging else None

        # Compare current tags with new values
        changes_needed, changes = compare_tag_values(
            audio_file.tags, album_name, new_track, new_release_date
        )

        if not changes_needed:
            print(f"    ⏭️ MP3 tags already up-to-date - skipping write operation")
            return True

        # Log what changes will be made
        print(f"    🔄 Tag changes needed: {', '.join(changes)}")

        # Set the Album tag (TALB) - always overwrite existing
        audio_file.tags.delall("TALB")
        audio_file.tags.add(TALB(encoding=3, text=album_name))

        # Set the Track number tag (TRCK) if provided and track tagging is enabled (always overwrite existing)
        if track_number is not None and enable_track_tagging:
            audio_file.tags.delall("TRCK")
            audio_file.tags.add(TRCK(encoding=3, text=str(track_number)))

        # Set the Release Date tag (TDRC) if provided and release date tagging is enabled (always overwrite existing)
        if track_number is not None and enable_release_date_tagging:
            audio_file.tags.delall("TDRC")
            audio_file.tags.add(TDRC(encoding=3, text=release_date))

        # Save the changes
        audio_file.save()
        success_msg = f"Successfully updated Album tag to '{album_name}'"
        if track_number is not None and enable_track_tagging:
            success_msg += f", Track number to {track_number}"
        if track_number is not None and enable_release_date_tagging:
            success_msg += f", Release Date to {release_date}"

        # Add disabled status to success message
        if disabled_tags:
            success_msg += f" ({', '.join(disabled_tags)} tagging disabled)"

        print(f"    ✅ {success_msg}")
        return True

    except Exception as e:
        print(f"    ❌ Error updating MP3 tags: {e}")
        return False


def get_mp3_metadata(url, timeout=10, verify_ssl=True):
    """Get metadata for an MP3 URL using HEAD request to identify content."""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        
        # Disable SSL warnings if SSL verification is disabled
        if not verify_ssl:
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        response = requests.head(url, timeout=timeout, headers=headers, verify=verify_ssl, allow_redirects=True)
        
        if response.status_code == 200:
            # Extract key metadata that identifies content
            content_length = response.headers.get('content-length', '0')
            last_modified = response.headers.get('last-modified', '')
            etag = response.headers.get('etag', '')
            content_type = response.headers.get('content-type', '')
            
            # Create a content signature from available metadata
            # Use content-length as primary identifier, with last-modified and etag as secondary
            metadata_signature = f"{content_length}|{last_modified}|{etag}|{content_type}"
            
            return {
                'success': True,
                'content_length': content_length,
                'last_modified': last_modified,
                'etag': etag,
                'content_type': content_type,
                'signature': metadata_signature,
                'final_url': response.url  # In case of redirects
            }
        else:
            return {'success': False, 'error': f'HTTP {response.status_code}'}
            
    except Exception as e:
        return {'success': False, 'error': str(e)}


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


def extract_mp3_links(html_content, base_url, max_links=None, verify_ssl=True):
    """Extract .mp3 links from content (HTML, RSS, etc.) in order of appearance, with content-based deduplication and optional limit."""
    mp3_links_with_positions = []
    seen_urls = set()

    try:
        # Filter XML parsed as HTML warning for RSS feeds and XML content
        warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)
        soup = BeautifulSoup(html_content, "html.parser")

        # Find all elements that could contain MP3 links and track their positions
        all_elements = soup.find_all(["a", "audio", "source"])

        for element in all_elements:
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

            # Add to list if found and not already seen by URL
            if mp3_url and mp3_url not in seen_urls:
                seen_urls.add(mp3_url)
                # Get the position of this element in the original HTML
                element_position = html_content.find(str(element))
                mp3_links_with_positions.append((element_position, mp3_url))

        # Use regex to find any additional .mp3 URLs in the HTML content
        mp3_pattern = r'https?://[^\s<>"\']+\.mp3(?:\?[^\s<>"\']*)?'
        for match in re.finditer(mp3_pattern, html_content, re.IGNORECASE):
            mp3_url = match.group()
            if mp3_url not in seen_urls:
                seen_urls.add(mp3_url)
                mp3_links_with_positions.append((match.start(), mp3_url))

        # Sort by position in HTML to maintain order
        mp3_links_with_positions.sort(key=lambda x: x[0])
        
        # Limit content deduplication to max_links * 2 to avoid performance issues on large lists
        dedup_limit = (max_links * 2) if max_links else len(mp3_links_with_positions)
        links_to_check = mp3_links_with_positions[:dedup_limit]
        
        print(f"  🔍 Performing content-based deduplication on first {len(links_to_check)} of {len(mp3_links_with_positions)} MP3 links...")
        
        seen_content = set()  # Track content signatures
        unique_links_with_positions = []
        
        for position, url in links_to_check:
            # Get metadata for this URL
            metadata = get_mp3_metadata(url, timeout=10, verify_ssl=verify_ssl)
            
            if metadata['success']:
                content_signature = metadata['signature']
                
                # Only include if we haven't seen this content before
                if content_signature not in seen_content:
                    seen_content.add(content_signature)
                    unique_links_with_positions.append((position, url))
                    print(f"    ✅ Unique content: {url} (size: {metadata['content_length']} bytes)")
                else:
                    print(f"    🔄 Duplicate content: {url} (same as previous)")
            else:
                # If we can't get metadata, include the link anyway but warn
                unique_links_with_positions.append((position, url))
                print(f"    ⚠️ Could not verify: {url} ({metadata['error']}) - including anyway")

        # Extract just the URLs in order
        ordered_mp3_links = [url for position, url in unique_links_with_positions]

        # Apply final limit if specified - take from the beginning of the list
        if max_links:
            ordered_mp3_links = ordered_mp3_links[:max_links]

        # Reverse order so the last-found MP3 is downloaded first
        ordered_mp3_links = list(reversed(ordered_mp3_links))

        print(f"  📊 Content deduplication result: {len(mp3_links_with_positions)} → {len(ordered_mp3_links)} unique links")

        return ordered_mp3_links

    except Exception as e:
        print(f"❌ Error extracting MP3 links: {e}")
        return []


def save_mp3_links(mp3_links, output_dir, source_url, url_name=None):
    """Save extracted MP3 links to a text file."""
    if not mp3_links:
        return None

    try:
        # Generate filename for MP3 links file
        base_name = url_name or urlparse(source_url).netloc.replace(":", "_")

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
        print(f"❌ Error saving MP3 links: {e}")
        return None


def parse_track_numbers_from_txt(txt_filepath):
    """Parse track numbers from MP3 links text file and return a mapping of URL to track number."""
    track_mapping = {}

    try:
        if not os.path.exists(txt_filepath):
            return track_mapping

        with open(txt_filepath, "r", encoding="utf-8") as f:
            lines = f.readlines()

        # Look for numbered lines in format "1. http://..." or "1) http://..."
        for line in lines:
            line = line.strip()
            # Match patterns like "1. http://..." or "1) http://..."
            match = re.match(r"^(\d+)[\.\)]\s+(.+)$", line)
            if match:
                track_number = int(match.group(1))
                url = match.group(2).strip()
                track_mapping[url] = track_number

        print(
            f"    📋 Parsed {len(track_mapping)} track numbers from {os.path.basename(txt_filepath)}"
        )
        return track_mapping

    except Exception as e:
        print(f"    ❌ Error parsing track numbers from {txt_filepath}: {e}")
        return track_mapping


def download_mp3_file(
    mp3_url,
    output_dir,
    timeout=30,
    verify_ssl=True,
    album_name=None,
    enable_album_tagging=False,
    track_number=None,
    enable_track_tagging=False,
    enable_release_date_tagging=False,
):
    """Download a single MP3 file with hash-based duplicate detection across any local filename."""
    try:
        # Extract base filename from URL
        parsed_url = urlparse(mp3_url)
        base_filename = os.path.basename(parsed_url.path)

        # Compute URL hash once (used for duplicate detection and fallback filename)
        url_hash = hashlib.md5(mp3_url.encode()).hexdigest()[:8]

        # If no filename in path, generate one from the URL
        if not base_filename or not base_filename.endswith(".mp3"):
            # Use the last part of the path or generate from URL hash
            url_parts = parsed_url.path.strip("/").split("/")
            if url_parts and url_parts[-1]:
                base_filename = f"{url_parts[-1]}.mp3"
            else:
                # Generate filename from URL hash
                base_filename = f"audio_{url_hash}.mp3"
        name_part = base_filename.rsplit(".", 1)[0]

        # Add high-resolution timestamp prefix YYYY-MM-DD-HHMMSSSSSS (microseconds)
        ts = (
            time.strftime("%Y-%m-%d-%H%M%S")
            + f"{int((time.time() % 1) * 1_000_000):06d}"
        )

        # Proposed filename with timestamp prefix and hash suffix
        filename = f"{ts}_{name_part}_{url_hash}.mp3"
        filepath = os.path.join(output_dir, filename)

        # Skip if any existing MP3 in this subfolder already contains this hash in its filename
        # This supports different base names while preventing re-download by URL hash.
        try:
            # Check for existing files with same hash
            existing_files = [
                f
                for f in os.listdir(output_dir)
                if f.lower().endswith(".mp3") and url_hash in f
            ]

            if existing_files:
                existing = existing_files[0]  # Take first match
                print(
                    f"    ⏭ Skipping download (duplicate by hash {url_hash}) -> {existing}"
                )

                # Update tags for existing file if album tagging is enabled
                tag_success = False
                if enable_album_tagging and album_name:
                    print(f"    🏷️ Updating tags for existing file...")
                    existing_filepath = os.path.join(output_dir, existing)
                    tag_success = update_mp3_tags(
                        existing_filepath,
                        album_name,
                        track_number,
                        enable_track_tagging,
                        enable_release_date_tagging,
                    )

                return {
                    "success": True,
                    "filename": existing,
                    "skipped": True,
                    "duplicate": True,
                    "tags_updated": tag_success,
                }
        except FileNotFoundError:
            # Directory may not exist yet; will be created by caller
            pass

        # Set headers to mimic a real browser
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }

        print(f"    📥 Downloading {filename}...")

        # Disable SSL warnings if SSL verification is disabled
        if not verify_ssl:
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        response = requests.get(
            mp3_url, timeout=timeout, headers=headers, stream=True, verify=verify_ssl
        )
        response.raise_for_status()

        # Download with progress indication for large files
        total_size = int(response.headers.get("content-length", 0))

        with open(filepath, "wb") as f:
            if total_size > 0:
                downloaded = 0
                show_progress = (
                    total_size > 1024 * 1024
                )  # Show progress for files > 1MB
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        # Simple progress indication for large files (>1MB)
                        if show_progress and downloaded % (1024 * 1024) == 0:
                            progress = (downloaded / total_size) * 100
                            print(
                                f"\r      ⏳ Progress: {progress:.1f}%",
                                end="",
                                flush=True,
                            )

                # Show 100% completion for large files
                if show_progress:
                    print(f"\r      ⏳ Progress: 100.0%", end="", flush=True)
                    print()  # Print newline after progress is complete
            else:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)

        file_size = os.path.getsize(filepath)
        size_mb = file_size / (1024 * 1024)
        print(f"    ✅ Downloaded {filename} ({size_mb:.1f} MB)")

        # Update MP3 tags with Album name and track number (if enabled)
        tag_success = False
        if enable_album_tagging and album_name:
            tag_success = update_mp3_tags(
                filepath,
                album_name,
                track_number,
                enable_track_tagging,
                enable_release_date_tagging,
            )
        elif not enable_album_tagging:
            print(f"    🏷️ Album tagging disabled - skipping tag update")
        else:
            print(f"    🏷️ No album name provided - skipping tag update")

        return {
            "success": True,
            "filename": filename,
            "size": file_size,
            "duplicate": False,
            "tags_updated": tag_success,
        }

    except requests.exceptions.RequestException as e:
        error_msg = str(e)
        # Categorize common network errors
        if (
            "Name or service not known" in error_msg
            or "NameResolutionError" in error_msg
        ):
            print(f"    🌐 DNS resolution failed for {mp3_url}: Domain not found")
        elif "certificate verify failed" in error_msg or "SSLError" in error_msg:
            print(
                f"    🔒 SSL certificate error for {mp3_url}: Try setting 'verify_ssl': false"
            )
        elif "Connection refused" in error_msg:
            print(f"    🚫 Connection refused for {mp3_url}: Server may be down")
        elif "timeout" in error_msg.lower():
            print(
                f"    ⏱️ Timeout downloading {mp3_url}: Server too slow or unresponsive"
            )
        else:
            print(f"    ❌ Error downloading {mp3_url}: {e}")
        return {"success": False, "error": str(e)}
    except Exception as e:
        print(f"    ❌ Unexpected error downloading {mp3_url}: {e}")
        return {"success": False, "error": str(e)}


def clear_mp3_files(output_dir):
    """Clear all MP3 files from the target directory."""
    try:
        if not os.path.exists(output_dir):
            return 0

        mp3_files = [
            os.path.join(output_dir, f)
            for f in os.listdir(output_dir)
            if f.lower().endswith(".mp3")
        ]

        if mp3_files:
            print(
                f"  🗑️ Clearing {len(mp3_files)} existing MP3 file(s) from {output_dir}..."
            )
            for mp3_file in mp3_files:
                try:
                    os.remove(mp3_file)
                    print(f"    🗑️ Removed {os.path.basename(mp3_file)}")
                except Exception as e:
                    print(f"    ❌ Failed to remove {os.path.basename(mp3_file)}: {e}")

        return len(mp3_files)

    except Exception as e:
        print(f"  ❌ Error clearing MP3 files from {output_dir}: {e}")
        return 0


def clear_all_mp3_files(base_output_dir):
    """Clear all MP3 files from the entire target directory and all subdirectories."""
    try:
        if not os.path.exists(base_output_dir):
            return 0

        total_cleared = 0
        mp3_files = []

        # Walk through all directories and subdirectories
        for root, _, files in os.walk(base_output_dir):
            mp3_files.extend(
                os.path.join(root, f) for f in files if f.lower().endswith(".mp3")
            )

        if mp3_files:
            print(
                f"🗑️ Clearing {len(mp3_files)} existing MP3 file(s) from entire target directory..."
            )
            for mp3_file in mp3_files:
                try:
                    relative_path = os.path.relpath(mp3_file, base_output_dir)
                    os.remove(mp3_file)
                    print(f"  🗑️ Removed {relative_path}")
                    total_cleared += 1
                except Exception as e:
                    relative_path = os.path.relpath(mp3_file, base_output_dir)
                    print(f"  ❌ Failed to remove {relative_path}: {e}")

        return total_cleared

    except Exception as e:
        print(f"❌ Error clearing MP3 files from {base_output_dir}: {e}")
        return 0


def cleanup_old_mp3_files(output_dir, current_filenames):
    """Remove MP3 files that are not in the current set of expected filenames."""
    try:
        if not os.path.exists(output_dir):
            return 0

        cleaned_count = 0

        # Get all MP3 files in the directory that are not in current set
        old_files = [
            f
            for f in os.listdir(output_dir)
            if f.lower().endswith(".mp3") and f not in current_filenames
        ]

        for file in old_files:
            file_path = os.path.join(output_dir, file)
            try:
                os.remove(file_path)
                print(f"    🗑️ Removed old file: {file}")
                cleaned_count += 1
            except Exception as e:
                print(f"    ❌ Failed to remove old file {file}: {e}")

        return cleaned_count

    except Exception as e:
        print(f"  ❌ Error cleaning up old MP3 files from {output_dir}: {e}")
        return 0


def download_mp3_files(
    mp3_links,
    output_dir,
    timeout=30,
    verify_ssl=True,
    album_name=None,
    enable_album_tagging=False,
    track_mapping=None,
    enable_track_tagging=False,
    enable_release_date_tagging=False,
):
    """Download all MP3 files from the provided links with hash-based filename duplicate detection."""
    if not mp3_links:
        return {"total": 0, "successful": 0, "failed": 0, "skipped": 0, "duplicates": 0}

    print(f"  📁 Downloading {len(mp3_links)} MP3 file(s) to {output_dir}...")
    print(f"  🔍 Hash-based filename duplicate detection: ENABLED")

    successful = 0
    failed = 0
    skipped = 0
    duplicates = 0
    total_size = 0
    current_filenames = set()  # Track all current hash-based filenames

    for i, mp3_url in enumerate(mp3_links, 1):
        # Get track number from mapping if available
        track_number = track_mapping.get(mp3_url) if track_mapping else None
        track_info = f" (Track {track_number})" if track_number else ""
        print(f"  [{i}/{len(mp3_links)}] {mp3_url}{track_info}")

        result = download_mp3_file(
            mp3_url,
            output_dir,
            timeout,
            verify_ssl,
            album_name,
            enable_album_tagging,
            track_number,
            enable_track_tagging,
            enable_release_date_tagging,
        )

        if result["success"]:
            # Add filename to current set regardless of whether it was downloaded or skipped
            current_filenames.add(result["filename"])

            if result.get("skipped"):
                skipped += 1
                if result.get("duplicate"):
                    duplicates += 1
            else:
                successful += 1
                total_size += result.get("size", 0)
        else:
            failed += 1

    # Clean up old MP3 files that are not in the current set
    cleaned_count = cleanup_old_mp3_files(output_dir, current_filenames)

    total_size_mb = total_size / (1024 * 1024)

    # Enhanced summary with duplicate information
    summary_parts = [
        f"{successful} downloaded",
        f"{skipped} skipped",
        f"{failed} failed",
    ]
    if duplicates > 0:
        summary_parts.insert(1, f"{duplicates} duplicates")

    summary = ", ".join(summary_parts)
    print(f"  📊 MP3 Download Summary: {summary} ({total_size_mb:.1f} MB total)")

    if cleaned_count > 0:
        print(f"  🧹 Cleaned up {cleaned_count} old MP3 file(s)")

    return {
        "total": len(mp3_links),
        "successful": successful,
        "failed": failed,
        "skipped": skipped,
        "duplicates": duplicates,
        "total_size": total_size,
        "cleaned": cleaned_count,
    }


def download_html(
    url,
    output_dir,
    timeout=30,
    max_mp3_links=None,
    url_name=None,
    download_mp3s=False,
    verify_ssl=True,
    album_name=None,
    enable_album_tagging=False,
    enable_track_tagging=False,
    enable_release_date_tagging=False,
):
    """Download content from URL and save to file, then extract MP3 links."""
    try:
        print(f"🌐 Downloading: {url}")

        # Set headers to mimic a real browser
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }

        # Disable SSL warnings if SSL verification is disabled
        if not verify_ssl:
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        response = requests.get(
            url, timeout=timeout, headers=headers, verify=verify_ssl
        )
        response.raise_for_status()  # Raise an exception for bad status codes

        # Generate filename
        filename = generate_filename(url)
        filepath = os.path.join(output_dir, filename)

        # Save content to file
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(response.text)

        print(f"✅ Successfully downloaded: {url} -> {filename}")

        # Extract MP3 links from the downloaded content
        limit_text = f" (limit: {max_mp3_links})" if max_mp3_links else ""
        print(f"  🔍 Extracting MP3 links from {filename}{limit_text}...")
        mp3_links = extract_mp3_links(response.text, url, max_mp3_links, verify_ssl)

        mp3_download_stats = {"total": 0, "successful": 0, "failed": 0, "skipped": 0}

        if mp3_links:
            # Save MP3 links to a separate file
            links_filename = save_mp3_links(mp3_links, output_dir, url, url_name)
            if links_filename:
                print(f"  🎵 Found {len(mp3_links)} MP3 link(s) -> {links_filename}")
            else:
                print(f"  ❌ Error saving MP3 links")

            # Download MP3 files if enabled
            if download_mp3s:
                # Parse track numbers from the links file if it exists
                track_mapping = {}
                if links_filename:
                    links_filepath = os.path.join(output_dir, links_filename)
                    track_mapping = parse_track_numbers_from_txt(links_filepath)

                mp3_download_stats = download_mp3_files(
                    mp3_links,
                    output_dir,
                    timeout,
                    verify_ssl,
                    album_name,
                    enable_album_tagging,
                    track_mapping,
                    enable_track_tagging,
                    enable_release_date_tagging,
                )

            # Always clean up content and MP3 links files when MP3 downloading is enabled
            if download_mp3s:
                cleanup_files = []

                # Add content file to cleanup list
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
                        except Exception as e:
                            print(f"    ❌ Failed to remove {file_name}: {e}")
        else:
            print(f"  ℹ️ No MP3 links found in {filename}")

        return {
            "success": True,
            "html_file": filename,
            "mp3_count": len(mp3_links),
            "mp3_downloads": mp3_download_stats,
        }

    except requests.exceptions.RequestException as e:
        error_msg = str(e)
        # Categorize common network errors
        if (
            "Name or service not known" in error_msg
            or "NameResolutionError" in error_msg
        ):
            print(f"🌐 DNS resolution failed for {url}: Domain not found")
        elif "certificate verify failed" in error_msg or "SSLError" in error_msg:
            print(
                f"🔒 SSL certificate error for {url}: Try setting 'verify_ssl': false"
            )
        elif "Connection refused" in error_msg:
            print(f"🚫 Connection refused for {url}: Server may be down")
        elif "timeout" in error_msg.lower():
            print(f"⏱️ Timeout downloading {url}: Server too slow or unresponsive")
        else:
            print(f"❌ Error downloading {url}: {e}")
        return {"success": False, "error": str(e)}
    except Exception as e:
        print(f"❌ Unexpected error downloading {url}: {e}")
        return {"success": False, "error": str(e)}


def main():
    """Main function to orchestrate the download process."""
    print("🚀 Podcast Downloader Starting...")

    # Load configuration
    config = load_config()

    # Extract configuration values
    urls_config = config.get("urls", {})
    output_dir_config = config.get("output_directory", "downloads")
    timeout = config.get("timeout", 30)
    max_mp3_links = config.get("max_mp3_links", None)
    download_mp3s = config.get("download_mp3_files", False)
    verify_ssl = config.get("verify_ssl", True)
    enable_album_tagging = config.get("enable_album_tagging", False)
    enable_track_tagging = config.get("enable_track_tagging", False)
    enable_release_date_tagging = config.get("enable_release_date_tagging", False)

    # Hash-based duplicate detection is always enabled

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
        print("❌ Error: Invalid URLs configuration format.")
        sys.exit(1)

    if not urls_dict:
        print("❌ Error: No URLs found in config file.")
        sys.exit(1)

    # Create main output directory
    create_output_directory(output_dir)
    print(f"📁 Output directory: {output_dir}")

    if max_mp3_links:
        print(f"🔢 MP3 links limit: {max_mp3_links}")

    if download_mp3s:
        print(f"🎵 MP3 file downloading: ENABLED")
        print(f"🔐 Hash-based filename duplicate detection: ENABLED")
        album_status = "ENABLED" if enable_album_tagging else "DISABLED"
        track_status = "ENABLED" if enable_track_tagging else "DISABLED"
        release_date_status = "ENABLED" if enable_release_date_tagging else "DISABLED"
        print(f"🏷️ Album tagging: {album_status}")
        print(f"🔢 Track number tagging: {track_status}")
        print(f"📅 Release date tagging: {release_date_status}")
        ssl_status = (
            "ENABLED"
            if verify_ssl
            else "DISABLED (bypassed for problematic certificates)"
        )
        print(f"🔒 SSL certificate verification: {ssl_status}")
    else:
        print(f"🎵 MP3 file downloading: DISABLED")

    # Download each URL and extract MP3 links
    successful_downloads = 0
    total_mp3_links = 0
    total_mp3_downloads = 0
    total_mp3_failed = 0
    total_mp3_skipped = 0
    total_urls = len(urls_dict)

    for i, (url_name, url) in enumerate(urls_dict.items(), 1):
        print(f"\n📋 [{i}/{total_urls}] Processing '{url_name}': {url}")

        # Create subfolder for this URL
        url_output_dir = os.path.join(output_dir, url_name)
        create_output_directory(url_output_dir)
        print(f"  📂 Subfolder: {url_output_dir}")

        result = download_html(
            url,
            url_output_dir,
            timeout,
            max_mp3_links,
            url_name,
            download_mp3s,
            verify_ssl,
            url_name,  # Pass url_name as album_name
            enable_album_tagging,
            enable_track_tagging,
            enable_release_date_tagging,
        )

        if isinstance(result, dict) and result.get("success"):
            successful_downloads += 1
            total_mp3_links += result.get("mp3_count", 0)
            if download_mp3s:
                mp3_stats = result.get("mp3_downloads", {})
                total_mp3_downloads += mp3_stats.get("successful", 0)
                total_mp3_failed += mp3_stats.get("failed", 0)
                total_mp3_skipped += mp3_stats.get("skipped", 0)
        elif result is True:  # Backward compatibility
            successful_downloads += 1

    # Summary
    print(f"\n{'='*60}")
    print(f"📊 Podcast Download Summary:")
    print(f"🌐 Total URLs processed: {total_urls}")
    print(f"✅ Successful downloads: {successful_downloads}")
    print(f"❌ Failed downloads: {total_urls - successful_downloads}")
    print(f"🎵 Total MP3 links found: {total_mp3_links}")
    if download_mp3s:
        print(f"💾 Total MP3 files downloaded: {total_mp3_downloads}")
        if total_mp3_failed > 0:
            print(f"❌ Total MP3 download failures: {total_mp3_failed}")
        if total_mp3_skipped > 0:
            print(f"⏭ Total MP3 files skipped: {total_mp3_skipped}")
    if max_mp3_links:
        print(f"🔢 MP3 links limit per URL: {max_mp3_links}")
    print(f"📁 Output directory: {output_dir}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
