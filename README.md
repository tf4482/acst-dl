# 🎧 acst-dl

One-shot Linux CLI that scans podcast feeds or web pages for MP3 links, downloads the newest episodes
into one folder per feed, tags them, and exits. Ships as a single static binary.

## ✨ Features

- 🌐 **Any source**: RSS feeds, HTML pages, or any content with MP3 links in tags or plain text.
- ⚡ **Parallel**: feeds, HEAD probes, and downloads run concurrently over pooled connections, each
  with its own limit and hard deadline; downloads alternate between feeds to spread over hosts.
- 🧬 **Mirror detection**: links with the same size and ETag or Last-Modified, or the same identifier
  in their path, count as one episode.
- ⏭️ **No re-downloads**: an 8-character link hash in the file name marks episodes already present.
- 🏷️ **Tagging**: album (feed name) and release date (download day) are written into the ID3 tag while
  streaming; existing files are corrected when their tags differ.
- 🧹 **Tidy library**: keeps the newest `max_episodes` per feed and removes its own episode files that
  left the selection, but only when all of the feed's episodes succeeded.
- 🛡️ **Safe writes**: episodes are written as `.part` and renamed when complete; leftovers are removed.
- 🔗 **Links only**: optionally writes `links.txt` per feed instead of downloading.
- 🔓 **TLS bypass**: optional for hosts with broken certificates.
- 📝 **First run**: creates a user-only config template.
- 🌈 **Output**: colored with emojis, one line per finished download, a summary per feed with count, size, duration, and speed, and a live progress bar; plain when redirected or `NO_COLOR` is set.

## 📦 Install

Building needs Go 1.26+. Running needs nothing else.

```bash
git clone https://github.com/tf4482/acst-dl.git
cd acst-dl
CGO_ENABLED=0 go build -trimpath -ldflags "-s -w" -o dist/acst-dl .
sudo install -m 755 dist/acst-dl /usr/local/bin/acst-dl
```

## 📁 Library

```text
~/Podcasts/
└── Tech News/
    ├── 2026-10-05-171536849510_episode-41_4a229f67.mp3
    └── 2026-10-05-171536849511_episode-42_216a2633.mp3
```

File names are `<download time>_<name from link>_<link hash>.mp3`; within a run the newest episode
gets the latest time, so files sort in feed order. Query parameters such as tokens do not change the
hash, unless the file name is generic like `media.mp3`. Episode files that left the current selection
are deleted; other audio without a link hash in its name is never touched. Feeds without links,
failed feeds, and feeds with a failed episode delete nothing.

## 🔁 Migrating from the Python version

Libraries stay valid: the link hash is unchanged for links without a query, so present episodes are
recognized. Links with a query or with HTML entities such as `&amp;` are fetched once more.

| `acst-dl-config.json` | `config.yml` |
| --- | --- |
| `urls` | `feeds` |
| `output_directory` | `library.directory` (absolute or `~/…`) |
| `max_mp3_links` | `settings.max_episodes` (`0` for all) |
| `download_mp3_files` | `settings.download_files` |
| `enable_album_tagging`, `enable_release_date_tagging` | `settings.tag_album`, `settings.tag_release_date` |
| `verify_ssl` | `settings.verify_tls` |
| `timeout` | `settings.feed_timeout_seconds`, `settings.download_timeout_seconds` |
| `head_request_timeout` | `settings.probe_timeout_seconds` |
| `enable_dns_caching`, `max_concurrent_domains` | removed; see the `*_concurrency` settings |

## ⚙️ Configuration

The first existing file is used, without merging:

1. `config.yml` beside the executable
2. `~/.config/acst-dl/config.yml`

If neither exists, the second one is created with dummy values and the run exits `1`. Copy
[`config.example.yml`](config.example.yml) to one of these locations and replace `CHANGE_ME`:

| Setting | Description |
| --- | --- |
| `feeds` | Map of feed name to URL; the name is the folder and album name, feeds run in name order |
| `library.directory` | Base folder, absolute or starting with `~/` |
| `settings.max_episodes` | Newest episodes kept per feed; `0` keeps all |
| `settings.download_files` | `false` only writes `links.txt` per feed |
| `settings.tag_album`, `tag_release_date` | Set album to the feed name, release date to the download day |
| `settings.verify_tls` | `false` accepts invalid TLS certificates |
| `settings.feed_concurrency`, `probe_concurrency`, `download_concurrency` | Parallel requests per kind of work |
| `settings.feed_timeout_seconds`, `probe_timeout_seconds`, `download_timeout_seconds` | Hard deadline per request, including the whole episode transfer |

## 🚀 Usage

```bash
acst-dl
acst-dl --help   # also: -h, help
```

| Exit | Meaning |
| --- | --- |
| `0` | Every feed and episode succeeded; feeds without links are not errors |
| `1` | Configuration, feed, download, or file error |
| `130` | Interrupted by the user |

## ⏱️ Deploy

Install the binary, place the configuration, then schedule it with the example systemd units. The timer
waits for the previous run to finish, so runs never overlap.

```bash
sudo install -m 644 acst-dl.example.service /etc/systemd/system/acst-dl.service
sudo install -m 644 acst-dl.example.timer /etc/systemd/system/acst-dl.timer
sudo systemctl daemon-reload
sudo systemctl enable --now acst-dl.timer
journalctl -u acst-dl.service
```

Adjust `User=` in the service; that account needs the configuration and write access to the library.

## 🧪 Develop

```bash
go vet ./...
go test ./...
```

## 📜 License

MIT, see [LICENSE](LICENSE).
