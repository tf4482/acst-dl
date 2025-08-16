# A Podcast Downloader (acst-dl)

A powerful Python-based podcast downloader that extracts and downloads MP3 files from web pages and RSS feeds. Features intelligent duplicate detection, MP3 tag management, and organized file storage.

## 🎵 Features

- **Multi-source Support**: Download from HTML pages, RSS feeds, and any web content containing MP3 links
- **Smart Content-Based Duplicate Detection**: Advanced duplicate detection using file metadata prevents re-downloading the same content from different URLs
- **MP3 Tag Management**: Automatically tag downloaded files with album, track number, and release date information
- **Organized Storage**: Creates structured output directories with subfolders for each podcast source
- **Progress Tracking**: Real-time download progress with detailed logging and emoji indicators
- **Robust Error Handling**: Comprehensive error messages for network issues, SSL problems, and timeouts
- **Flexible Configuration**: JSON-based configuration with support for multiple podcast sources
- **Browser Simulation**: Uses realistic user-agent headers to avoid blocking
- **SSL Flexibility**: Option to bypass SSL verification for problematic certificates
- **Cleanup Features**: Automatic cleanup of old files and temporary content

## 📋 Requirements

- Python 3.8 or higher
- Poetry (recommended) or pip for dependency management

## 🚀 Installation

### Using Poetry (Recommended)

```bash
# Clone the repository
git clone <repository-url>
cd acst-dl

# Install dependencies
poetry install

# Activate virtual environment
poetry shell
```

### Using pip

```bash
# Clone the repository
git clone <repository-url>
cd acst-dl

# Install dependencies
pip install requests beautifulsoup4 mutagen
```

## ⚙️ Configuration

Create a configuration file named [`acst-dl-config.json`](acst-dl-config.json) in the project directory:

```json
{
  "urls": {
    "Podcast Name": "https://example.com/podcast-feed",
    "Another Podcast": "https://example.com/another-feed"
  },
  "output_directory": "downloads",
  "timeout": 30,
  "max_mp3_links": 5,
  "download_mp3_files": true,
  "enable_album_tagging": true,
  "enable_track_tagging": true,
  "enable_release_date_tagging": false,
  "verify_ssl": true
}
```

### Configuration Options

| Option                                                  | Type    | Default       | Description                                |
| ------------------------------------------------------- | ------- | ------------- | ------------------------------------------ |
| [`urls`](acst-dl-config.json:3)                         | Object  | Required      | Dictionary of podcast names and their URLs |
| [`output_directory`](acst-dl-config.json:5)             | String  | `"downloads"` | Base directory for downloaded files        |
| [`timeout`](acst-dl-config.json:6)                      | Number  | `30`          | Request timeout in seconds                 |
| [`max_mp3_links`](acst-dl-config.json:7)                | Number  | `null`        | Maximum MP3 links to extract per URL       |
| [`download_mp3_files`](acst-dl-config.json:8)           | Boolean | `false`       | Whether to download MP3 files              |
| [`enable_album_tagging`](acst-dl-config.json:9)         | Boolean | `false`       | Set album tag to podcast name              |
| [`enable_track_tagging`](acst-dl-config.json:10)        | Boolean | `false`       | Add track numbers to MP3 files             |
| [`enable_release_date_tagging`](acst-dl-config.json:11) | Boolean | `false`       | Add release date tags                      |
| [`verify_ssl`](acst-dl-config.json:12)                  | Boolean | `true`        | Verify SSL certificates                    |

## 📖 Usage

### Basic Usage

```bash
# Run with default config
python acst-dl.py

# Run with custom config file
python acst-dl.py --config /path/to/config.json
```

### Example Configuration

```json
{
  "urls": {
    "Tech News": "https://feeds.feedburner.com/TechCrunch",
    "Daily Update": "https://example.com/daily-podcast.rss"
  },
  "output_directory": "./podcasts",
  "download_mp3_files": true,
  "enable_album_tagging": true,
  "max_mp3_links": 10
}
```

## 📁 Output Structure

The tool creates an organized directory structure:

```
downloads/
├── Tech News/
│   ├── 2024-01-15-120000000000_episode1_a1b2c3d4.mp3
│   ├── 2024-01-15-120500000000_episode2_e5f6g7h8.mp3
│   └── ...
└── Daily Update/
    ├── 2024-01-15-130000000000_daily1_i9j0k1l2.mp3
    └── ...
```

### Filename Format

Downloaded MP3 files use the format:
`YYYY-MM-DD-HHMMSSSSSSSS_basename_hash.mp3`

- **Timestamp**: High-precision timestamp for unique ordering
- **Basename**: Original filename from URL
- **Hash**: 8-character URL hash for duplicate detection

## 🎯 Features in Detail

### Duplicate Detection

The tool uses advanced content-based duplicate detection:
- **URL-based deduplication**: Removes identical URLs during link extraction
- **Content-based deduplication**: Uses HEAD requests to compare file metadata (size, modification date, ETag)
- **Performance optimized**: Only checks first `max_mp3_links * 2` files to avoid delays on large feeds
- **Smart identification**: Detects when different URLs point to the same content
- **Hash-based filename detection**: Prevents re-downloading during subsequent runs
- Updates tags on existing files if needed

#### How Content Deduplication Works

1. **Link Collection**: Extracts all MP3 links from HTML/RSS content
2. **URL Deduplication**: Removes any identical URLs
3. **Metadata Checking**: Performs HEAD requests on up to `max_mp3_links * 2` links
4. **Content Comparison**: Compares file size, last-modified date, and ETag to identify duplicates
5. **Final Selection**: Takes unique content from the top of the list up to `max_mp3_links`

This approach effectively handles cases where the same podcast episode is available from multiple URLs (e.g., CDN mirrors, feed redirects).

### MP3 Tag Management

Supports ID3v2 tags:
- **Album**: Set to podcast name
- **Track**: Sequential track numbers
- **Release Date**: Current date with track number as day

### Error Handling

Comprehensive error handling for:
- DNS resolution failures
- SSL certificate issues
- Connection timeouts
- Server unavailability
- Invalid MP3 files

## 🔧 Advanced Usage

### SSL Certificate Issues

For sites with SSL problems:

```json
{
  "verify_ssl": false
}
```

### Limited Downloads

To limit MP3 downloads per source:

```json
{
  "max_mp3_links": 5
}
```

### Extract Links Only

To extract MP3 links without downloading:

```json
{
  "download_mp3_files": false
}
```

## 🐛 Troubleshooting

### Common Issues

**SSL Certificate Errors**
```
🔒 SSL certificate error: Try setting 'verify_ssl': false
```
Solution: Set [`verify_ssl`](acst-dl-config.json:12) to `false` in config.

**DNS Resolution Failed**
```
🌐 DNS resolution failed: Domain not found
```
Solution: Check URL validity and internet connection.

**Connection Timeout**
```
⏱️ Timeout downloading: Server too slow or unresponsive
```
Solution: Increase [`timeout`](acst-dl-config.json:6) value in config.

### Debug Mode

For verbose output, check the console logs. The tool provides detailed emoji-coded status messages:
- 🚀 Starting operations
- 🌐 Network operations
- 📥 Download progress
- ✅ Successful operations
- ❌ Errors and failures
- 🏷️ Tag operations
- 🧹 Cleanup operations

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [`LICENSE`](LICENSE) file for details.

## 🛠️ Dependencies

- **requests**: HTTP library for downloading content
- **beautifulsoup4**: HTML/XML parsing for link extraction
- **mutagen**: MP3 metadata manipulation
- **pyinstaller**: For creating standalone executables

## 💡 Tips

- Use descriptive names in the [`urls`](acst-dl-config.json:3) configuration for better organization
- Enable [`enable_album_tagging`](acst-dl-config.json:9) for better music library integration
- Set [`max_mp3_links`](acst-dl-config.json:7) to avoid downloading entire archives
- Check the [`output_directory`](acst-dl-config.json:5) permissions before running

## 🔄 Version History

- **v0.2.0**: Enhanced duplicate detection and extraction improvements
  - **Content-based duplicate detection**: Uses file metadata (size, modification date, ETag) to identify duplicate content from different URLs
  - **Performance optimized deduplication**: Limits metadata checking to `max_mp3_links * 2` for faster processing on large feeds
  - **Improved link extraction**: Collects all MP3 links first, then applies deduplication and limits from the top
  - Enhanced HEAD request handling with proper SSL and timeout configuration

- **v0.1.0**: Initial release with core downloading functionality
  - MP3 link extraction from HTML/RSS
  - Hash-based duplicate detection
  - MP3 tag management
  - Organized file storage
  - Comprehensive error handling
