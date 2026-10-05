package main

import (
	"net/url"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"time"
)

// Must match config.example.yml
const defaultConfig = `feeds:
  "Example Podcast": "CHANGE_ME"

library:
  directory: "~/Podcasts"

settings:
  max_episodes: 5
  download_files: true
  tag_album: true
  tag_release_date: false
  verify_tls: true
  feed_concurrency: 4
  feed_timeout_seconds: 30
  probe_concurrency: 8
  probe_timeout_seconds: 5
  download_concurrency: 4
  download_timeout_seconds: 900
`

// Named source page or RSS feed
type Feed struct {
	Name string
	URL  string
}

// Limits, deadlines, and switches
type Settings struct {
	MaxEpisodes         int
	DownloadFiles       bool
	TagAlbum            bool
	TagReleaseDate      bool
	VerifyTLS           bool
	FeedConcurrency     int
	FeedTimeout         time.Duration
	ProbeConcurrency    int
	ProbeTimeout        time.Duration
	DownloadConcurrency int
	DownloadTimeout     time.Duration
}

// Validated configuration
type Config struct {
	Feeds     []Feed
	Directory string
	Settings  Settings
}

// Strict validation of the decoded YAML document
func parseConfig(document any) (Config, error) {
	r := &reader{}
	root := r.mapping(document, "configuration")
	feeds := r.mapping(root["feeds"], "feeds")
	library := r.mapping(root["library"], "library")
	settings := r.mapping(root["settings"], "settings")
	r.exactKeys(root, "configuration", "feeds", "library", "settings")
	r.exactKeys(library, "library", "directory")
	r.exactKeys(settings, "settings",
		"max_episodes", "download_files", "tag_album", "tag_release_date", "verify_tls",
		"feed_concurrency", "feed_timeout_seconds", "probe_concurrency", "probe_timeout_seconds",
		"download_concurrency", "download_timeout_seconds")

	config := Config{
		Feeds:     r.feeds(feeds),
		Directory: r.directory(library, "directory", "library"),
		Settings: Settings{
			MaxEpisodes:         r.count(settings, "max_episodes", "settings"),
			DownloadFiles:       r.flag(settings, "download_files", "settings"),
			TagAlbum:            r.flag(settings, "tag_album", "settings"),
			TagReleaseDate:      r.flag(settings, "tag_release_date", "settings"),
			VerifyTLS:           r.flag(settings, "verify_tls", "settings"),
			FeedConcurrency:     r.positiveInt(settings, "feed_concurrency", "settings"),
			FeedTimeout:         r.positiveSeconds(settings, "feed_timeout_seconds", "settings"),
			ProbeConcurrency:    r.positiveInt(settings, "probe_concurrency", "settings"),
			ProbeTimeout:        r.positiveSeconds(settings, "probe_timeout_seconds", "settings"),
			DownloadConcurrency: r.positiveInt(settings, "download_concurrency", "settings"),
			DownloadTimeout:     r.positiveSeconds(settings, "download_timeout_seconds", "settings"),
		},
	}
	if r.err != nil {
		return Config{}, r.err
	}
	return config, nil
}

// Feeds sorted by name; names double as folder names
func (r *reader) feeds(values map[string]any) []Feed {
	if len(values) == 0 {
		r.fail("feeds must contain at least one feed")
	}
	names := make([]string, 0, len(values))
	for name := range values {
		names = append(names, name)
	}
	sort.Strings(names)

	feeds := make([]Feed, 0, len(names))
	for _, name := range names {
		if name == "" || name != strings.TrimSpace(name) || name == "." || name == ".." ||
			strings.ContainsAny(name, "/\\\x00") {
			r.fail("feeds key %q must be a plain folder name", name)
		}
		address := r.text(values, name, "feeds")
		parsed, err := url.Parse(address)
		if r.err == nil && (err != nil || parsed.Host == "" || parsed.Scheme != "http" && parsed.Scheme != "https") {
			r.fail("feeds.%s must be an http or https URL", name)
		}
		feeds = append(feeds, Feed{name, address})
	}
	return feeds
}

// Absolute path, with ~/ expanded to the home directory
func (r *reader) directory(values map[string]any, key, location string) string {
	path := r.text(values, key, location)
	if rest, ok := strings.CutPrefix(path, "~/"); ok {
		if home, err := os.UserHomeDir(); err == nil {
			path = filepath.Join(home, rest)
		}
	}
	if r.err == nil && !filepath.IsAbs(path) {
		r.fail("%s.%s must be an absolute path or start with ~/", location, key)
	}
	return filepath.Clean(path)
}

func (r *reader) flag(values map[string]any, key, location string) bool {
	value, ok := values[key].(bool)
	if !ok {
		r.fail("%s.%s must be true or false", location, key)
	}
	return value
}

// Zero or more; zero means unlimited
func (r *reader) count(values map[string]any, key, location string) int {
	value, ok := values[key].(int)
	if !ok || value < 0 {
		r.fail("%s.%s must be a non-negative integer", location, key)
	}
	return value
}
