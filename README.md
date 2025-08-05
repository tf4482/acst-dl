# Acast Downloader (acst-dl)

A Python script for downloading HTML content from podcast feeds and extracting MP3 links. Specifically designed for Acast podcast feeds, this tool can download podcast episodes and organize them into structured directories.

## Features

- 📥 Download HTML content from multiple URLs
- 🎵 Extract MP3 links from downloaded HTML pages
- 📁 Organize downloads into named subdirectories
- ⚡ Configurable download limits and timeouts
- 🧹 Automatic cleanup of temporary files
- 📊 Detailed download statistics and progress tracking
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

### Configuration Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `urls` | Object/Array | Required | Dictionary of named URLs or array of URLs to process |
| `output_directory` | String | `"downloads"` | Directory where files will be saved |
| `timeout` | Number | `30` | Request timeout in seconds |
| `max_mp3_links` | Number | `null` | Maximum number of MP3 links to extract per URL |
| `download_mp3_files` | Boolean | `false` | Whether to download actual MP3 files |

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
│   ├── domain_path_timestamp.html
│   ├── podcast_name_1_mp3_links_timestamp.txt
│   └── audio_files_timestamp.mp3 (if download_mp3_files is true)
└── Podcast Name 2/
    ├── domain_path_timestamp.html
    ├── podcast_name_2_mp3_links_timestamp.txt
    └── audio_files_timestamp.mp3 (if download_mp3_files is true)
```

## Features in Detail

### MP3 Link Extraction

The script uses multiple methods to find MP3 links:
- Parses HTML elements (`<a>`, `<audio>`, `<source>` tags)
- Uses regex patterns to find direct MP3 URLs
- Maintains order of appearance in the original HTML
- Supports configurable limits on number of links extracted

### File Management

- **Automatic cleanup**: Removes temporary HTML and link files after successful MP3 downloads
- **Duplicate prevention**: Skips downloading files that already exist
- **Progress tracking**: Shows download progress for large files
- **Timestamped filenames**: Prevents filename conflicts

### Error Handling

- Comprehensive error handling for network issues
- Graceful handling of malformed URLs or HTML
- Detailed error reporting and logging
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

### Download Latest Episodes

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

### Debug Mode

For debugging, you can modify the script to add more verbose logging or run with Python's `-v` flag for detailed output.

## Version History

- **0.1.0** - Initial release with basic download and extraction functionality
