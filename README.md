# A Podcast MP3 Downloader (acst-dl)

A Python script specifically designed for downloading MP3 files from podcast feeds. This tool extracts MP3 links from podcast feeds (HTML pages, RSS feeds, etc.) and downloads the audio files with intelligent duplicate detection and automatic organization.

**Primary Purpose: MP3 Audio File Downloading**

## Features

- 🎵 **Primary Focus: MP3 file downloading from podcast feeds**
- 📥 Extract MP3 links from podcast feeds (HTML pages, RSS feeds, etc.)
- 💾 Download MP3 audio files with progress tracking
- 📁 Organize downloads into named subdirectories
- 🔐 **Hash-based duplicate detection** (prevents re-downloading same files)
- 🧹 **Automatic cleanup of old files** (keeps only the most recent episodes)
- ⚡ Configurable download limits and timeouts
- 🗑️ Automatic cleanup of temporary files
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

Create or modify the [`acst-dl-config.json.example`](acst-dl-config.json.example) file to configure your downloads:

```json
{
  "urls": {
    "Podcast Name 1": "https://feeds.acast.com/public/shows/podcast-name-1",
    "Podcast Name 2": "https://feeds.acast.com/public/shows/podcast-name-2"
  },
  "output_directory": "~/data/podcasts",
  "timeout": 30,
  "max_mp3_links": 5,
  "download_mp3_files": true,
  "verify_ssl": true
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
| `download_mp3_files` | Boolean | `false` | **Set to `true` for MP3 downloading (main purpose)** |
| `verify_ssl` | Boolean | `true` | Whether to verify SSL certificates (set to `false` for problematic certificates) |

### Hash-Based Duplicate Detection & Automatic Cleanup

The script now automatically prevents downloading duplicate MP3 files and keeps folders clean by:
- 🔐 **Embedding a URL hash** (MD5, first 8 chars) into filenames (e.g., `media_43e4489f.mp3`)
- 📁 **Scanning for the URL hash in the current subfolder** before downloading; if any `.mp3` already contains that hash in its filename, the file is skipped as a duplicate (even if the base name differs)
- ⚡ **Skipping duplicates** automatically without any configuration needed
- 🧹 **Automatic old file cleanup** - removes MP3 files not in current download set
- 🗑️ **Keeps only recent files** - maintains clean directories with latest episodes
- 🎯 **No database required** - uses simple hash-in-filename detection within the subfolder plus in-memory tracking during a run

## Usage

### Basic Usage

```bash
python acst-dl.py
```

The script will:
1. Read configuration from [`acst-dl-config.json.example`](acst-dl-config.json.example)
2. Create output directories as needed
3. Download content from each configured URL (HTML pages, RSS feeds, etc.)
4. Extract MP3 links from the downloaded content
5. **Download the MP3 audio files** (primary function when `download_mp3_files` is `true`)

### Output Structure

```
output_directory/
├── Podcast Name 1/
│   └── 2025-08-07-023015123456_media_43e4489f.mp3   (timestamp prefix + URL hash)
│   └── 2025-08-07-023020654321_episodeA_7ac9803d.mp3
└── Podcast Name 2/
    └── 2025-08-07-030001000111_audio_20830c0e.mp3
    └── 2025-08-07-030501222333_ep-12_32758bac.mp3
```

- Filenames are prefixed with a high-resolution timestamp in the format `YYYY-MM-DD-HHMMSSSSSS` (microseconds).
- MP3 downloads per page are initiated in reverse order of appearance (last-found first).

Note: If another file like `episode-001_43e4489f.mp3` (or with a timestamp prefix) is already present in `Podcast Name 1/`, any new URL that hashes to `43e4489f` will be skipped as a duplicate, regardless of the differing base name or timestamp.

**Note**: Temporary content and MP3 links files are automatically cleaned up after successful downloads.

## Features in Detail

### Hash-Based Duplicate Detection & Automatic Cleanup 🔐

The script automatically prevents downloading duplicate files and maintains clean directories by:
- **URL-based hashing**: Each MP3 URL generates a unique MD5 hash (first 8 chars used)
- **Timestamped, clean filenames**: Files are named as: `{YYYY-MM-DD-HHMMSSSSSS}_{base_name}_{hash}.mp3`
- **Subfolder hash matching**: Before download, the current feed’s subfolder is scanned; if any existing `.mp3` filename contains the same hash, the download is skipped as a duplicate (filename equality not required, timestamp ignored)
- **Memory tracking**: Stores current filenames during download process for summary and cleanup
- **Automatic cleanup**: Removes old MP3 files not in current download set
- **Keep only recent**: Maintains clean directories with latest episodes only
- **No configuration needed**: Works automatically without any setup
- **Bandwidth savings**: Skips re-downloading identical content
- **Storage efficiency**: Prevents duplicate files and removes outdated ones

### MP3 Link Extraction 🎵

The script uses multiple methods to find MP3 links:
- Parses content elements (`<a>`, `<audio>`, `<source>` tags for HTML)
- Uses regex patterns to find direct MP3 URLs
- Extracts in order of appearance, but downloads are initiated in reverse order per page (last-found first)
- Supports configurable limits on number of links extracted

### File Management 📁

- **Automatic cleanup**: Always removes temporary content and link files when MP3 downloading is enabled
- **Hash-based duplicate prevention**: Intelligent detection using URL hashes
- **Old file removal**: Automatically deletes MP3 files not in current download set
- **Clean directories**: Keeps only the most recent episodes, removes outdated files
- **Single-line progress tracking**: Clean progress display for large files
- **Rich console output**: Emoji-enhanced feedback for better user experience

### Error Handling ❌

- Comprehensive error handling for network issues
- Graceful handling of malformed URLs or content
- **Enhanced error categorization** (DNS, SSL, timeout, connection issues)
- Detailed error reporting with emoji indicators
- Continues processing remaining URLs even if some fail

## Dependencies

- [`requests`](https://pypi.org/project/requests/) - HTTP library for downloading content
- [`beautifulsoup4`](https://pypi.org/project/beautifulsoup4/) - HTML parsing library
- [`pyinstaller`](https://pypi.org/project/pyinstaller/) - For creating standalone executables

## Examples

### Download MP3 Files (Recommended Usage)

```json
{
  "urls": {
    "Daily News": "https://feeds.acast.com/public/shows/daily-news"
  },
  "output_directory": "~/Downloads/podcasts",
  "download_mp3_files": true,
  "max_mp3_links": 3,
  "timeout": 60,
  "verify_ssl": true
}
```

**Note**: This is the primary intended usage - downloading MP3 files with hash-based duplicate detection automatically enabled.

### Extract Links Only (Alternative Usage)

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

**Config file not found**: Ensure [`acst-dl-config.json.example`](acst-dl-config.json.example) exists in the same directory as the script.

**Permission errors**: Check that the output directory is writable and you have sufficient permissions.

**Network timeouts**: Increase the `timeout` value in the configuration for slow connections.

**No MP3 links found**: Some podcast feeds may use different formats or require authentication.

**SSL certificate errors**: Set `"verify_ssl": false` in the configuration to bypass SSL certificate verification for problematic servers.

**Duplicate detection**: Files with the same URL produce the same hash. The downloader skips a new download if any `.mp3` in the current subfolder already contains that hash in its filename, even when the base names differ.

### Console Output

The script provides rich emoji-enhanced output including:
- 🚀 Startup and configuration loading
- 📋 Processing status with progress indicators
- 🎵 MP3 extraction and download status
- ⏭ Duplicate detection notifications
- 🗑️ Old file cleanup notifications
- ✅ Success confirmations
- ❌ Error messages with clear indicators
- 📊 Detailed summary statistics with cleanup counts

### Debug Mode

For debugging, you can modify the script to add more verbose logging or run with Python's `-v` flag for detailed output.

## Version History

- **2.0.0** - Major update with hash-based duplicate detection, emoji-enhanced output, and simplified configuration
- **0.1.0** - Initial release with basic download and extraction functionality

## What's New in 2.1.0

- ⏮️ **Reversed MP3 download order per page** — last-found link is downloaded first
- 🕒 **Timestamped filenames** — prefixes each MP3 with `YYYY-MM-DD-HHMMSSSSSS` (microseconds)
- 🔐 **Hash-based duplicate detection** — unchanged behavior, works with timestamped names
- 🎨 **Rich emoji output** — enhanced console experience with meaningful visual indicators
- ⏳ **Single-line progress** — clean progress display that updates in place
- 🧹 **Automatic cleanup** — always removes temporary files when MP3 downloading is enabled
- 📁 **Smart filename generation** — uses URL hashes for unique, consistent filenames
- ⚡ **No configuration needed** — duplicate detection works out of the box
- 🎯 **Simplified setup** — removed complex database configuration options

## Web Interface

ACST-DL now includes a modern web interface built with FastAPI and Tailwind CSS for easy management of your podcast downloads.

### Features

- 🎨 **Modern UI**: Clean, responsive design with Tailwind CSS
- 📊 **Real-time Dashboard**: Live progress tracking with WebSocket updates
- ⚙️ **Configuration Management**: Easy-to-use web forms for managing podcast feeds
- 📁 **File Management**: Browse and manage downloaded podcast files
- 🔄 **Live Updates**: Real-time download progress and status updates
- 📱 **Mobile Responsive**: Works seamlessly on desktop, tablet, and mobile devices

### Running the Web Interface

1. **Install web dependencies:**
   ```bash
   poetry install
   ```

2. **Start the web server:**
   ```bash
   poetry run python web_app.py
   ```

3. **Access the web interface:**
   Open your browser and navigate to: **http://localhost:5000**

### Web Interface Pages

- **Dashboard (`/`)**: Overview of downloads, statistics, and session management
- **Configuration (`/config`)**: Manage podcast feeds and download settings
- **Files (`/files`)**: Browse and manage downloaded MP3 files

### Web-Specific Features

- **Real-time Progress**: Watch downloads progress in real-time via WebSockets
- **Session Management**: Track multiple download sessions with unique IDs
- **Interactive Configuration**: Add/remove podcast feeds with live validation
- **File Browser**: Navigate downloaded files organized by podcast name
- **One-click Operations**: Start downloads, clear files, and refresh data

### Web Interface Dependencies

The web interface adds the following production-ready dependencies:

- **FastAPI**: Modern, fast web framework for building APIs
- **Uvicorn**: ASGI server for running FastAPI applications
- **Jinja2**: Template engine for rendering HTML pages
- **python-multipart**: For handling form data
- **websockets**: Real-time communication support
- **aiofiles**: Asynchronous file operations

### Configuration for Web Interface

The web interface uses the same configuration file format, but with the `output_directory` setting removed (hardcoded to `~/podcasts`):

```json
{
  "urls": {
    "Podcast Name 1": "https://feeds.example.com/podcast1",
    "Podcast Name 2": "https://feeds.example.com/podcast2"
  },
  "timeout": 30,
  "max_mp3_links": 5,
  "download_mp3_files": true,
  "verify_ssl": true
}
```
