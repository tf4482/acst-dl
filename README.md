# Acast Downloader (acst-dl)

A Python script for downloading HTML content from podcast feeds and extracting MP3 links. Specifically designed for Acast podcast feeds, this tool can download podcast episodes and organize them into structured directories with intelligent duplicate detection.

## Features

- 📥 Download HTML content from multiple URLs
- 🎵 Extract MP3 links from downloaded HTML pages
- 📁 Organize downloads into named subdirectories
- 🔐 **Hash-based duplicate detection** (prevents re-downloading same files)
- ⚡ Configurable download limits and timeouts
- 🧹 Automatic cleanup of temporary files
- 📊 Detailed download statistics and progress tracking
- 🎨 Rich emoji-enhanced console output
- ⏳ Single-line progress indicators
- 🔄 Support for both old list format and new dictionary format URLs

## Installation

### Prerequisites

- Python 3.8 or higher
- Poetry (recommended) or pip

### Using Poetry (Recommended)

```bash
# Clone the repository
git clone <repository-url>
cd acst-dl

# Install dependencies
poetry install

# Activate the virtual environment
poetry shell
```

### Using pip

```bash
# Clone the repository
git clone <repository-url>
cd acst-dl

# Install dependencies
pip install requests beautifulsoup4
```

## Configuration

Create or modify the [`acst-dl-config.json`](acst-dl-config.json) file to configure your downloads:

```json
{
  "urls": {
    "Podcast Name 1": "https://feeds.acast.com/public/shows/podcast-name-1",
    "Podcast Name 2": "https://feeds.acast.com/public/shows/podcast-name-2"
  },
  "output_directory": "~/data/podcasts",
  "timeout": 30,
  "max_mp3_links": 5,
  "download_mp3_files": true
}
```

**Note**: Hash-based duplicate detection is now enabled by default and requires no configuration.

### Configuration Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `urls` | Object/Array | Required | Dictionary of named URLs or array of URLs to process |
| `output_directory` | String | `"downloads"` | Directory where files will be saved |
| `timeout` | Number | `30` | Request timeout in seconds |
| `max_mp3_links` | Number | `null` | Maximum number of MP3 links to extract per URL |
| `download_mp3_files` | Boolean | `false` | Whether to download actual MP3 files |

### Hash-Based Duplicate Detection

The script now automatically prevents downloading duplicate MP3 files by:
- 🔐 **Generating unique filenames** using MD5 hash of the URL (e.g., `media_43e4489f.mp3`)
- 📁 **Checking file existence** before downloading
- ⚡ **Skipping duplicates** automatically without any configuration needed
- 🎯 **No database required** - uses simple filename-based detection

## Usage

### Basic Usage

```bash
python acst-dl.py
```

The script will:
1. Read configuration from [`acst-dl-config.json`](acst-dl-config.json)
2. Create output directories as needed
3. Download HTML content from each configured URL
4. Extract MP3 links from the downloaded content
5. Optionally download the MP3 files themselves

### Output Structure

```
output_directory/
├── Podcast Name 1/
│   └── media_43e4489f.mp3 (hash-based filename)
│   └── media_7ac9803d.mp3 (hash-based filename)
└── Podcast Name 2/
    └── media_20830c0e.mp3 (hash-based filename)
    └── media_32758bac.mp3 (hash-based filename)
```

**Note**: Temporary HTML and MP3 links files are automatically cleaned up after successful downloads.

## Features in Detail

### Hash-Based Duplicate Detection 🔐

The script automatically prevents downloading duplicate files by:
- **URL-based hashing**: Each MP3 URL generates a unique MD5 hash
- **Smart filename generation**: Files are named `{base_name}_{hash}.mp3`
- **Instant duplicate detection**: Same URLs always produce the same filename
- **No configuration needed**: Works automatically without any setup
- **Bandwidth savings**: Skips re-downloading identical content
- **Storage efficiency**: Prevents duplicate files from consuming disk space

### MP3 Link Extraction 🎵

The script uses multiple methods to find MP3 links:
- Parses HTML elements (`<a>`, `<audio>`, `<source>` tags)
- Uses regex patterns to find direct MP3 URLs
- Maintains order of appearance in the original HTML
- Supports configurable limits on number of links extracted

### File Management 📁

- **Automatic cleanup**: Always removes temporary HTML and link files when MP3 downloading is enabled
- **Hash-based duplicate prevention**: Intelligent detection using URL hashes
- **Single-line progress tracking**: Clean progress display for large files
- **Rich console output**: Emoji-enhanced feedback for better user experience

### Error Handling ❌

- Comprehensive error handling for network issues
- Graceful handling of malformed URLs or HTML
- Detailed error reporting with emoji indicators
- Continues processing remaining URLs even if some fail

## Dependencies

- [`requests`](https://pypi.org/project/requests/) - HTTP library for downloading content
- [`beautifulsoup4`](https://pypi.org/project/beautifulsoup4/) - HTML parsing library
- [`pyinstaller`](https://pypi.org/project/pyinstaller/) - For creating standalone executables

## Examples

### Extract Links Only

```json
{
  "urls": {
    "My Podcast": "https://feeds.acast.com/public/shows/my-podcast"
  },
  "output_directory": "./podcast_links",
  "download_mp3_files": false,
  "max_mp3_links": 10
}
```

### Download Latest Episodes with Duplicate Detection

```json
{
  "urls": {
    "Daily News": "https://feeds.acast.com/public/shows/daily-news"
  },
  "output_directory": "~/Downloads/podcasts",
  "download_mp3_files": true,
  "max_mp3_links": 3,
  "timeout": 60
}
```

**Note**: Hash-based duplicate detection is automatically enabled when `download_mp3_files` is `true`.

### Backward Compatibility

The script supports the old array format for URLs:

```json
{
  "urls": [
    "https://feeds.acast.com/public/shows/podcast-1",
    "https://feeds.acast.com/public/shows/podcast-2"
  ]
}
```

## Building Standalone Executable

Use PyInstaller to create a standalone executable:

```bash
pyinstaller --onefile acst-dl.py
```

## License

This project is licensed under the MIT License - see the [`LICENSE`](LICENSE) file for details.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## Troubleshooting

### Common Issues

**Config file not found**: Ensure [`acst-dl-config.json`](acst-dl-config.json) exists in the same directory as the script.

**Permission errors**: Check that the output directory is writable and you have sufficient permissions.

**Network timeouts**: Increase the `timeout` value in the configuration for slow connections.

**No MP3 links found**: Some podcast feeds may use different formats or require authentication.

**Duplicate detection**: Files with the same URL will always generate the same hash-based filename, preventing re-downloads.

### Console Output

The script provides rich emoji-enhanced output including:
- 🚀 Startup and configuration loading
- 📋 Processing status with progress indicators
- 🎵 MP3 extraction and download status
- ⏭ Duplicate detection notifications
- ✅ Success confirmations
- ❌ Error messages with clear indicators
- 📊 Detailed summary statistics

### Debug Mode

For debugging, you can modify the script to add more verbose logging or run with Python's `-v` flag for detailed output.

## Version History

- **2.0.0** - Major update with hash-based duplicate detection, emoji-enhanced output, and simplified configuration
- **0.1.0** - Initial release with basic download and extraction functionality

## What's New in 2.0.0

- 🔐 **Hash-based duplicate detection** - Automatically prevents re-downloading the same files
- 🎨 **Rich emoji output** - Enhanced console experience with meaningful visual indicators
- ⏳ **Single-line progress** - Clean progress display that updates in place
- 🧹 **Automatic cleanup** - Always removes temporary files when MP3 downloading is enabled
- 📁 **Smart filename generation** - Uses URL hashes for unique, consistent filenames
- ⚡ **No configuration needed** - Duplicate detection works out of the box
- 🎯 **Simplified setup** - Removed complex database configuration options
