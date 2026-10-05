# 📝 Changelog

All notable changes follow [Keep a Changelog](https://keepachangelog.com/) and [Semantic Versioning](https://semver.org/).

## [0.1.0] - 2026-10-05

### Added

- Go port of the Python CLI, built as a single static Linux binary
- Parallel feed scans, HEAD probes, and downloads over pooled connections
- ID3 tagging while streaming, with in-place updates for existing files
- Partial files renamed only when complete; leftovers removed on the next run
- Example configuration (`config.yml.example`) and systemd units
- Downloads alternate between feeds and write through a large buffer

### Changed

- Configuration moved from `acst-dl-config.json` to a strictly validated `config.yml`
- Links with identical size and ETag or Last-Modified count as one episode
- HTML entities in links are decoded, and links with a query string are found in tag attributes
- Existing files keep their release date; only new downloads get the current day
- Old episodes are only removed when all of the feed's episodes succeeded
- Files named like `media.mp3` take the identifier from their link as name
- Links-only mode writes a single `links.txt` per feed and no page copy

### Removed

- Fixed delays between requests and the `enable_dns_caching` and `max_concurrent_domains` options
