# ACST-DL - Advanced Content Stream Tool Downloader

A powerful Python-based podcast and audio content downloader with intelligent duplicate detection and advanced MP3 tagging capabilities.

## 🎯 Core Features

- 🎵 **MP3 Download from Podcast Feeds** - Primary function of the tool
- 🔍 **Intelligent MP3 Link Extraction** from HTML pages, RSS feeds, and XML content
- 🔐 **Hash-based Duplicate Detection** - Prevents duplicate downloads automatically
- 🏷️ **Advanced MP3 Metadata Tagging** with configurable options
- 🧹 **Automatic File Management** - Cleans up old files and temporary content
- 📊 **Detailed Progress Tracking** with emoji-enhanced console output
- ⚡ **High-performance Downloads** with progress tracking for large files

## 🚀 Installation

### Prerequisites

- Python 3.8 or higher
- Poetry (recommended) or pip

### Using Poetry (Recommended)

```bash
git clone <repository-url>
cd acst-dl
poetry install
poetry shell
```

### Using pip

```bash
git clone <repository-url>
cd acst-dl
pip install requests beautifulsoup4 mutagen
```

## ⚙️ Configuration

Create an `acst-dl-config.json` file based on the example:

```json
{
  "urls": {
    "Podcast Name 1": "https://feeds.example.com/podcast1",
    "Podcast Name 2": "https://feeds.example.com/podcast2"
  },
  "output_directory": "~/Downloads/podcasts",
  "timeout": 30,
  "max_mp3_links": 5,
  "download_mp3_files": true,
  "enable_album_tagging": false,
  "enable_track_tagging": false,
  "enable_release_date_tagging": false,
  "verify_ssl": true
}
```

### 📋 Configuration Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `urls` | Object/Array | **Required** | Dictionary with named URLs or array of URLs |
| `output_directory` | String | `"downloads"` | Target directory for downloads |
| `timeout` | Number | `30` | Request timeout in seconds |
| `max_mp3_links` | Number | `null` | Maximum number of MP3 links per URL |
| `download_mp3_files` | Boolean | `false` | **Main function:** Enable MP3 downloading |
| `enable_album_tagging` | Boolean | `false` | Set album tag (folder name) |
| `enable_track_tagging` | Boolean | `false` | Set track number tag |
| `enable_release_date_tagging` | Boolean | `false` | Set release date tag |
| `verify_ssl` | Boolean | `true` | SSL certificate verification |

## 🎵 MP3 Tagging System

The script provides an advanced, configurable tagging system:

### 🏷️ Album Tagging
- **ID3 Tag:** TALB (Album)
- **Value:** Download folder name
- **Purpose:** Organizes files by podcast name
- **Default:** Disabled

### 🔢 Track Number Tagging
- **ID3 Tag:** TRCK (Track Number)
- **Value:** Sequential numbering (1, 2, 3, ...)
- **Purpose:** Enables proper episode ordering in media players
- **Default:** Disabled

### 📅 Release Date Tagging
- **ID3 Tag:** TDRC (Recording Date)
- **Format:** `YYYY-MM-DD` (Current year-month, track number as day)
- **Example:** `2025-08-01`, `2025-08-02`, `2025-08-03`
- **Purpose:** Chronological sorting in media players
- **Default:** Disabled

### ⚡ Tag Behavior
- **Smart Updates:** Tags are only written when values actually change
- **Performance Optimized:** Skips unnecessary file writes to improve speed
- **Existing Files:** Tags are updated for both new downloads and existing files
- **Error Resilient:** Tagging failures don't affect the download process
- **Configurable:** Each tagging type can be independently enabled/disabled

### 🔍 Intelligent Tag Comparison
The system now includes smart tag comparison to optimize performance:

- **Pre-write Validation:** Compares current tag values with new values before writing
- **Skip Unchanged:** Automatically skips write operations when tags are already correct
- **Detailed Logging:** Shows exactly which tag changes are being made
- **Change Tracking:** Reports specific value changes (e.g., `Album: 'old' → 'new'`)
- **Write Optimization:** Reduces disk I/O and preserves file modification times

## 🔐 Duplicate Detection System

Advanced hash-based duplicate prevention:

### How It Works
1. **URL Hashing:** Each MP3 URL generates a unique MD5 hash (8 characters)
2. **Filename Integration:** Hash is embedded in filename: `{timestamp}_{name}_{hash}.mp3`
3. **Smart Detection:** Scans existing files for hash matches before downloading
4. **Cross-filename Detection:** Works regardless of original filename differences

### Benefits
- 🚫 **No Re-downloads:** Automatically skips duplicate content
- 💾 **Storage Efficient:** Prevents duplicate files
- 🧹 **Auto-cleanup:** Removes outdated files not in current download set
- ⚡ **Fast Detection:** No database required, uses filename scanning

## 📁 File Organization

### Directory Structure
```
output_directory/
├── Podcast Name 1/
│   ├── 2025-08-11-143022123456_episode1_a1b2c3d4.mp3
│   └── 2025-08-11-143045789012_episode2_e5f6g7h8.mp3
└── Podcast Name 2/
    ├── 2025-08-11-144001234567_show1_i9j0k1l2.mp3
    └── 2025-08-11-144030567890_show2_m3n4o5p6.mp3
```

### Filename Format
- **Timestamp:** `YYYY-MM-DD-HHMMSSSSSS` (microsecond precision)
- **Original Name:** Extracted from URL or generated
- **Hash:** 8-character MD5 hash of the URL
- **Extension:** Always `.mp3`

## 🎯 Usage

### Basic Usage

```bash
python acst-dl.py
```

### Workflow
1. **Configuration Loading:** Reads `acst-dl-config.json`
2. **URL Processing:** Downloads and parses each configured URL
3. **Link Extraction:** Finds MP3 links using multiple methods:
   - HTML element parsing (`<a>`, `<audio>`, `<source>` tags)
   - Regex pattern matching for direct MP3 URLs
   - Position-based ordering (downloads in reverse order)
4. **MP3 Downloading:** Downloads files with duplicate detection
5. **Metadata Tagging:** Applies configured ID3 tags
6. **Cleanup:** Removes temporary files and old MP3s

### Console Output Example

```
🚀 Podcast Downloader Starting...
📄 Using config file: ./acst-dl-config.json
📁 Output directory: /home/user/Downloads/podcasts
🎵 MP3 file downloading: ENABLED
🔐 Hash-based filename duplicate detection: ENABLED
🏷️ Album tagging: ENABLED
🔢 Track number tagging: ENABLED
📅 Release date tagging: DISABLED

📋 [1/2] Processing 'Tech Podcast': https://feeds.example.com/tech
🌐 Downloading: https://feeds.example.com/tech
✅ Successfully downloaded: https://feeds.example.com/tech -> tech_feed_1728123456.html
🔍 Extracting MP3 links from tech_feed_1728123456.html (limit: 5)...
🎵 Found 3 MP3 link(s) -> Tech_Podcast_mp3_links_1728123456.txt
📁 Downloading 3 MP3 file(s) to /home/user/Downloads/podcasts/Tech Podcast...
🔍 Hash-based filename duplicate detection: ENABLED

[1/3] https://example.com/episode1.mp3 (Track 1)
📥 Downloading 2025-08-11-143022123456_episode1_a1b2c3d4.mp3...
✅ Downloaded 2025-08-11-143022123456_episode1_a1b2c3d4.mp3 (15.2 MB)
🏷️ Checking MP3 tags: Album = 'Tech Podcast', Track = 1
🔄 Tag changes needed: Album: 'None' → 'Tech Podcast', Track: 'None' → '1'
✅ Successfully updated Album tag to 'Tech Podcast', Track number to 1

[2/3] https://example.com/episode2.mp3 (Track 2)
⏭ Skipping download (duplicate by hash e5f6g7h8) -> existing_file.mp3
🏷️ Updating tags for existing file...
🏷️ Checking MP3 tags: Album = 'Tech Podcast', Track = 2
⏭️ MP3 tags already up-to-date - skipping write operation

[3/3] https://example.com/episode3.mp3 (Track 3)
📥 Downloading 2025-08-11-143045789012_episode3_i9j0k1l2.mp3...
✅ Downloaded 2025-08-11-143045789012_episode3_i9j0k1l2.mp3 (12.8 MB)
🏷️ Checking MP3 tags: Album = 'Tech Podcast', Track = 3
🔄 Tag changes needed: Album: 'Old Album' → 'Tech Podcast'
✅ Successfully updated Album tag to 'Tech Podcast', Track number to 3

📊 MP3 Download Summary: 1 downloaded, 1 skipped, 1 duplicates, 0 failed (15.2 MB total)
🧹 Cleaned up 2 old MP3 file(s)
🧹 Cleaning up temporary files...
```

## 📦 Dependencies

- **[requests](https://pypi.org/project/requests/)** - HTTP library for content downloading
- **[beautifulsoup4](https://pypi.org/project/beautifulsoup4/)** - HTML/XML parsing
- **[mutagen](https://pypi.org/project/mutagen/)** - MP3 metadata manipulation

## 🛠️ Configuration Examples

### Minimal Configuration (Link Extraction Only)
```json
{
  "urls": {
    "My Podcast": "https://feeds.example.com/podcast"
  },
  "download_mp3_files": false
}
```

### Full Download with Tagging
```json
{
  "urls": {
    "Daily News": "https://feeds.example.com/news",
    "Tech Talk": "https://feeds.example.com/tech"
  },
  "output_directory": "~/Podcasts",
  "download_mp3_files": true,
  "enable_album_tagging": true,
  "enable_track_tagging": true,
  "enable_release_date_tagging": true,
  "max_mp3_links": 10,
  "timeout": 60
}
```

## 🚨 Troubleshooting

### Common Issues

**Config file not found**
- Ensure `acst-dl-config.json` exists in the script directory
- Check file permissions and JSON syntax

**No MP3 links found**
- Verify the URL contains MP3 links
- Check if authentication is required
- Try increasing `max_mp3_links` value

**SSL certificate errors**
- Set `"verify_ssl": false` for problematic certificates
- Check network connectivity and firewall settings

**Permission errors**
- Verify write permissions for output directory
- Check available disk space

**Network timeouts**
- Increase `timeout` value for slow connections
- Check internet connectivity


## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 🔮 Future Enhancements

- Support for additional audio formats
- Parallel download capabilities
- Web interface for configuration
- Playlist generation features
- Advanced filtering options
