# A Podcast MP3 Downloader (acst-dl)

A Python script with a modern web interface for downloading MP3 files from podcast feeds. This tool extracts MP3 links from podcast feeds (HTML pages, RSS feeds, etc.) and downloads the audio files with intelligent duplicate detection and automatic organization.

**Primary Purpose: MP3 Audio File Downloading with Web Management Interface**

## Features

### Core Features
- 🎵 **Primary Focus: MP3 file downloading from podcast feeds**
- 📥 Extract MP3 links from podcast feeds (HTML pages, RSS feeds, etc.)
- 💾 Download MP3 audio files with status tracking
- 📁 Organize downloads into named subdirectories
- 🔐 **Hash-based duplicate detection** (prevents re-downloading same files)
- 🧹 **Automatic cleanup of old files** (keeps only the most recent episodes)
- ⚡ Configurable download limits and timeouts
- 🗑️ Automatic cleanup of temporary files
- 📊 Detailed download statistics and session tracking
- 🎨 Rich emoji-enhanced console output
- 🔄 Support for both old list format and new dictionary format URLs

### Web Interface Features
- 🌐 **Modern Web Interface**: FastAPI-based web application with Tailwind CSS
- 📊 **Real-time Dashboard**: Live session tracking with WebSocket updates
- ⚙️ **Configuration Management**: Web-based podcast feed and settings management
- 📁 **File Browser**: Browse, play, and download MP3 files through the web interface
- 🔄 **Live Updates**: Real-time session status updates without page refresh
- 📱 **Mobile Responsive**: Works seamlessly on desktop, tablet, and mobile devices
- 🎧 **Audio Player**: Built-in audio player for listening to downloaded podcasts
- 📈 **Statistics Dashboard**: Visual overview of download sessions and success rates
- ⏰ **Automatic Scheduler**: Configurable automatic downloads at set intervals

## Installation

### Prerequisites

- Python 3.8 or higher
- Poetry (recommended) or pip
- Docker (optional, for containerized deployment)

### Option 1: Docker from GitHub Container Registry (Recommended)

The easiest way to run ACST-DL is using the pre-built Docker image from GitHub Container Registry:

```bash
# Pull and run the latest image directly
docker run -d -p 5000:5000 \
  -v ./podcasts:/app/podcasts \
  -v ./acst-dl-config.json:/app/acst-dl-config.json \
  --name acst-dl-app \
  ghcr.io/OWNER/REPO:latest

# Or using Docker Compose with the pre-built image
curl -O https://raw.githubusercontent.com/OWNER/REPO/main/docker-compose.ghcr.yml
docker compose -f docker-compose.ghcr.yml up -d
```

### Option 2: Docker Build from Source

If you want to build the image yourself:

```bash
# Clone the repository
git clone <repository-url>
cd acst-dl

# Using Docker Compose (builds from source)
docker compose up -d

# Or using Docker directly
docker build -t acst-dl .
docker run -d -p 5000:5000 -v ./podcasts:/app/podcasts -v ./acst-dl-config.json:/app/acst-dl-config.json acst-dl
```

The application will be available at `http://localhost:5000`

### Option 2: Using Poetry (Development)

```bash
# Clone the repository
git clone <repository-url>
cd acst-dl

# Install dependencies (includes web interface dependencies)
poetry install

# Activate the virtual environment
poetry shell
```

### Option 3: Using pip

```bash
# Clone the repository
git clone <repository-url>
cd acst-dl

# Install core dependencies
pip install requests beautifulsoup4

# Install web interface dependencies
pip install fastapi uvicorn jinja2 python-multipart websockets aiofiles
```

## Usage

### Web Interface (Recommended)

1. **Start the web server:**
   ```bash
   poetry run python web_app.py
   # or if using pip:
   python web_app.py
   ```

2. **Access the web interface:**
   Open your browser and navigate to: **http://localhost:5000**

3. **Configure podcast feeds:**
   - Go to the Configuration page (`/config`)
   - Add podcast feed URLs with descriptive names
   - Adjust download settings (timeout, max links, etc.)
   - Save configuration

4. **Start downloads:**
   - Return to the Dashboard (`/`)
   - Click "Start Download" to begin downloading from all configured feeds
   - Monitor real-time session status and statistics

5. **Manage files:**
   - Visit the Files page (`/files`)
   - Browse downloaded MP3 files organized by podcast name
   - Play audio files directly in the browser
   - Download individual files

### Command Line Interface

```bash
python acst-dl.py
```

The script will:
1. Read configuration from `acst-dl-config.json`
2. Create output directories as needed
3. Download content from each configured URL
4. Extract MP3 links from the downloaded content
5. **Download the MP3 audio files** (primary function when `download_mp3_files` is `true`)

## Configuration

### Web Interface Configuration

The web interface provides an intuitive form-based configuration system. All settings can be managed through the Configuration page at `/config`.

### Manual Configuration

Create or modify the `acst-dl-config.json` file:

```json
{
  "urls": {
    "Podcast Name 1": "https://feeds.acast.com/public/shows/podcast-name-1",
    "Podcast Name 2": "https://feeds.acast.com/public/shows/podcast-name-2"
  },
  "timeout": 30,
  "max_mp3_links": 5,
  "download_mp3_files": true,
  "verify_ssl": true,
  "scheduler": {
    "enabled": false,
    "interval_minutes": 60
  }
}
```

**Note**: The `output_directory` setting has been removed and is hardcoded to `./podcasts` for consistency.

### Configuration Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `urls` | Object/Array | Required | Dictionary of named URLs or array of URLs to process |
| `timeout` | Number | `30` | Request timeout in seconds |
| `max_mp3_links` | Number | `null` | Maximum number of MP3 links to extract per URL |
| `download_mp3_files` | Boolean | `false` | **Set to `true` for MP3 downloading (main purpose)** |
| `verify_ssl` | Boolean | `true` | Whether to verify SSL certificates |
| `scheduler.enabled` | Boolean | `false` | Enable automatic downloads at scheduled intervals |
| `scheduler.interval_minutes` | Number | `60` | Download interval in minutes (1-10080) |

## Web Interface Pages

### Dashboard (`/`)
- **Overview Statistics**: Total URLs, recent sessions, active downloads, success rate
- **Current Configuration Preview**: Quick view of current settings
- **Scheduler Status**: Real-time automatic download scheduler monitoring
- **Recent Download Sessions**: Live session tracking with status indicators
- **Quick Actions**: Start downloads, refresh data, clear all files

### Configuration (`/config`)
- **Podcast Feed Management**: Add, edit, and remove podcast feeds
- **Download Settings**: Configure timeout, max links, SSL verification
- **Scheduler Configuration**: Enable/disable automatic downloads with configurable intervals
- **Live Validation**: Real-time URL validation and error checking
- **Import/Export**: Backup and restore configuration settings

### Files (`/files`)
- **File Browser**: Navigate downloaded files organized by podcast name
- **Audio Player**: Built-in player with play/pause controls
- **File Management**: Download individual files or clear all files
- **Live Updates**: Real-time file structure updates

## Output Structure

```
./podcasts/
├── Podcast Name 1/
│   └── 2025-08-07-023015123456_media_43e4489f.mp3   (timestamp prefix + URL hash)
│   └── 2025-08-07-023020654321_episodeA_7ac9803d.mp3
└── Podcast Name 2/
    └── 2025-08-07-030001000111_audio_20830c0e.mp3
    └── 2025-08-07-030501222333_ep-12_32758bac.mp3
```

- Filenames are prefixed with a high-resolution timestamp in the format `YYYY-MM-DD-HHMMSSSSSS` (microseconds)
- MP3 downloads per page are initiated in reverse order of appearance (last-found first)
- Files are organized into subdirectories based on podcast feed names

## Features in Detail

### Hash-Based Duplicate Detection & Automatic Cleanup 🔐

The script automatically prevents downloading duplicate files and maintains clean directories by:
- **URL-based hashing**: Each MP3 URL generates a unique MD5 hash (first 8 chars used)
- **Timestamped, clean filenames**: Files are named as: `{YYYY-MM-DD-HHMMSSSSSS}_{base_name}_{hash}.mp3`
- **Subfolder hash matching**: Before download, the current feed's subfolder is scanned; if any existing `.mp3` filename contains the same hash, the download is skipped as a duplicate
- **Memory tracking**: Stores current filenames during download process for summary and cleanup
- **Automatic cleanup**: Removes old MP3 files not in current download set
- **Keep only recent**: Maintains clean directories with latest episodes only
- **No configuration needed**: Works automatically without any setup
- **Bandwidth savings**: Skips re-downloading identical content
- **Storage efficiency**: Prevents duplicate files and removes outdated ones

### Real-time Web Interface 🌐

- **WebSocket Communication**: Real-time updates without page refresh
- **Session Management**: Track multiple download sessions with unique IDs
- **Live Statistics**: Dashboard updates automatically with current data
- **Status Indicators**: Visual feedback for session states (pending, running, completed, failed)
- **Error Handling**: Comprehensive error display with user-friendly messages
- **Mobile Responsive**: Optimized for all device sizes

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
- **Web-based file browser**: Navigate and manage files through the web interface
- **Audio streaming**: Play MP3 files directly in the browser
- **Secure file serving**: Protected file access with proper security checks

### Automatic Download Scheduler ⏰

- **Background Scheduling**: Automatic downloads run at configurable intervals
- **Configurable Intervals**: Set download frequency from 1 minute to 1 week
- **Real-time Status**: Live scheduler status monitoring on dashboard
- **Auto-start**: Scheduler automatically starts on server startup if enabled
- **Session Tracking**: Scheduled downloads are tracked like manual downloads
- **WebSocket Updates**: Real-time scheduler status updates across all clients
- **Start/Stop Control**: Easy enable/disable through web interface

## Dependencies

### Core Dependencies
- [`requests`](https://pypi.org/project/requests/) - HTTP library for downloading content
- [`beautifulsoup4`](https://pypi.org/project/beautifulsoup4/) - HTML parsing library

### Web Interface Dependencies
- [`fastapi`](https://pypi.org/project/fastapi/) - Modern, fast web framework for building APIs
- [`uvicorn`](https://pypi.org/project/uvicorn/) - ASGI server for running FastAPI applications
- [`jinja2`](https://pypi.org/project/jinja2/) - Template engine for rendering HTML pages
- [`python-multipart`](https://pypi.org/project/python-multipart/) - For handling form data
- [`websockets`](https://pypi.org/project/websockets/) - Real-time communication support
- [`aiofiles`](https://pypi.org/project/aiofiles/) - Asynchronous file operations

### Development Dependencies
- [`pyinstaller`](https://pypi.org/project/pyinstaller/) - For creating standalone executables

## Examples

### Web Interface Usage (Recommended)

1. Start the web server: `python web_app.py`
2. Open http://localhost:5000 in your browser
3. Configure podcast feeds in the Configuration page
4. Start downloads from the Dashboard
5. Monitor progress and manage files through the web interface

### Command Line Usage

```json
{
  "urls": {
    "Daily News": "https://feeds.acast.com/public/shows/daily-news",
    "Tech Podcast": "https://feeds.example.com/tech-show"
  },
  "download_mp3_files": true,
  "max_mp3_links": 3,
  "timeout": 60,
  "verify_ssl": true
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

## Docker Deployment

### GitHub Container Registry (Production Ready)

ACST-DL is automatically built and published to GitHub Container Registry with every release. This provides:

- **Multi-architecture support** (AMD64 and ARM64)
- **Automatic security scanning**
- **Signed container images** with cosign
- **Version tags** for stable deployments

#### Quick Start with GHCR

```bash
# Pull and run the latest stable version
docker run -d -p 5000:5000 \
  -v ./podcasts:/app/podcasts \
  -v ./acst-dl-config.json:/app/acst-dl-config.json \
  --name acst-dl-app \
  --restart unless-stopped \
  ghcr.io/OWNER/REPO:latest

# Or use a specific version
docker run -d -p 5000:5000 \
  -v ./podcasts:/app/podcasts \
  -v ./acst-dl-config.json:/app/acst-dl-config.json \
  --name acst-dl-app \
  --restart unless-stopped \
  ghcr.io/OWNER/REPO:v3.1.0
```

#### Using Docker Compose with GHCR

```bash
# Download the GHCR compose file
curl -O https://raw.githubusercontent.com/OWNER/REPO/main/docker-compose.ghcr.yml

# Start the application
docker compose -f docker-compose.ghcr.yml up -d

# View logs
docker compose -f docker-compose.ghcr.yml logs -f

# Stop the application
docker compose -f docker-compose.ghcr.yml down

# Update to latest version
docker compose -f docker-compose.ghcr.yml pull
docker compose -f docker-compose.ghcr.yml up -d
```

#### Available Image Tags

- `latest` - Latest stable release from main branch
- `v3.1.0`, `v3.0.0` - Specific version releases
- `main` - Latest development build from main branch

### Docker Compose (Build from Source)

If you prefer to build from source:

```bash
# Start the application
docker compose up -d

# View logs
docker compose logs -f

# Stop the application
docker compose down

# Update the application
docker compose pull
docker compose up -d
```

### Docker Configuration

The Docker setup includes:

- **Automatic dependency management** using Poetry
- **Non-root user** for security
- **Health checks** for monitoring
- **Volume mounts** for persistent data
- **Port mapping** (5000:5000)

### Environment Variables

You can customize the deployment using environment variables:

```yaml
# docker-compose.override.yml
version: '3.8'
services:
  acst-dl:
    environment:
      - PYTHONUNBUFFERED=1
    ports:
      - "8080:5000"  # Change port mapping
```

### Persistent Data

The Docker setup automatically mounts:
- `./podcasts` - Downloaded MP3 files
- `./acst-dl-config.json` - Configuration file

### Production Deployment

For production deployment, consider:

1. **Reverse Proxy**: Use nginx or traefik
2. **SSL/TLS**: Enable HTTPS
3. **Monitoring**: Add health check endpoints
4. **Backup**: Regular backup of podcasts and config
5. **Updates**: Automated container updates

Example nginx configuration:
```nginx
server {
    listen 80;
    server_name your-domain.com;
    
    location / {
        proxy_pass http://localhost:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    
    # WebSocket support
    location /ws {
        proxy_pass http://localhost:5000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
    }
}
```

## API Endpoints

The web interface provides RESTful API endpoints:

- `GET /` - Dashboard page
- `GET /config` - Configuration management page
- `POST /config/save` - Save configuration
- `GET /files` - File browser page
- `POST /download/start` - Start new download session
- `GET /download/sessions` - Get all download sessions
- `GET /download/session/{id}` - Get specific session details
- `POST /files/clear` - Clear all downloaded files
- `GET /files/serve/{folder}/{file}` - Serve MP3 files
- `GET /scheduler/status` - Get current scheduler status
- `POST /scheduler/start` - Start automatic scheduler
- `POST /scheduler/stop` - Stop automatic scheduler
- `WS /ws` - WebSocket endpoint for real-time updates

## Building Standalone Executable

Use PyInstaller to create a standalone executable:

```bash
pyinstaller --onefile acst-dl.py
```

## Troubleshooting

### Common Issues

**Web server won't start**: Ensure port 5000 is available or modify the port in `web_app.py`.

**Config file not found**: The web interface will create a default configuration if none exists.

**Permission errors**: Check that the `./podcasts` directory is writable and you have sufficient permissions.

**Network timeouts**: Increase the `timeout` value in the configuration for slow connections.

**No MP3 links found**: Some podcast feeds may use different formats or require authentication.

**SSL certificate errors**: Set `"verify_ssl": false` in the configuration to bypass SSL certificate verification.

**WebSocket connection issues**: Check browser console for connection errors and ensure no firewall is blocking the connection.

### Console Output

The script provides rich emoji-enhanced output including:
- 🚀 Startup and configuration loading
- 📋 Processing status with session tracking
- 🎵 MP3 extraction and download status
- ⏭ Duplicate detection notifications
- 🗑️ Old file cleanup notifications
- ✅ Success confirmations
- ❌ Error messages with clear indicators
- 📊 Detailed summary statistics

### Web Interface Debugging

- Check browser developer tools for JavaScript errors
- Monitor WebSocket connection status in the Network tab
- Review server logs for backend errors
- Ensure all dependencies are properly installed

## License

This project is licensed under the MIT License - see the [`LICENSE`](LICENSE) file for details.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## Version History

- **3.0.0** - Major update with complete web interface, real-time updates, and enhanced file management
- **2.1.0** - Added reversed download order, timestamped filenames, and enhanced console output
- **2.0.0** - Major update with hash-based duplicate detection and simplified configuration
- **0.1.0** - Initial release with basic download and extraction functionality

## Automatic Download Scheduler

The scheduler feature allows you to automate podcast downloads at regular intervals, ensuring your collection stays up-to-date without manual intervention.

### Configuration

Enable the scheduler through the web interface Configuration page or by editing the config file:

```json
{
  "scheduler": {
    "enabled": true,
    "interval_minutes": 60
  }
}
```

### Features

- **Flexible Intervals**: Configure download frequency from 1 minute to 1 week (10080 minutes)
- **Auto-start**: Scheduler automatically starts when the web server launches if enabled
- **Real-time Monitoring**: Dashboard shows current status, next run time, and last run
- **Session Tracking**: Scheduled downloads appear in session history with a "scheduled" flag
- **Easy Control**: Start/stop scheduler directly from the dashboard
- **Live Updates**: Scheduler status updates in real-time via WebSocket

### Usage

1. **Enable via Web Interface**:
   - Go to Configuration page (`/config`)
   - Check "Enable automatic downloads"
   - Set desired interval in minutes
   - Save configuration

2. **Monitor Status**:
   - Dashboard shows scheduler status section
   - View next scheduled run time
   - See last run timestamp
   - Start/stop scheduler with one click

3. **Scheduled Downloads**:
   - Run automatically at configured intervals
   - Process all configured podcast feeds
   - Appear in session history
   - Follow same duplicate detection rules

### API Endpoints

- `GET /scheduler/status` - Get current scheduler status
- `POST /scheduler/start` - Start scheduler with specified interval
- `POST /scheduler/stop` - Stop automatic scheduler
