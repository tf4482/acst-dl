package main

import (
	"context"
	"crypto/tls"
	"errors"
	"fmt"
	"html"
	"io"
	"net"
	"net/http"
	"net/url"
	"path/filepath"
	"regexp"
	"slices"
	"sort"
	"strings"
	"sync"
	"syscall"
	"time"
	"unicode"
)

const (
	// Browser identity; some hosts block unknown clients
	userAgent = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

	connectTimeout = 10 * time.Second
	maxFeedBytes   = 64 << 20

	// Smaller reported sizes say nothing about an episode
	realisticBytes = 100_000
	// Shortest path part that counts as an episode identifier
	identifierLength = 16
)

// One feed's way through the run
type FeedRun struct {
	Feed      Feed
	Directory string
	Found     int      // distinct links in the feed
	Links     []string // candidates in page order, then the selection oldest first
	Library   []string // audio files present before downloading
	Episodes  []Episode
	Reason    string // why the feed failed
}

var (
	linkAttribute = regexp.MustCompile(`(?i)<(?:a|audio|source|enclosure)\s[^>]*?\b(?:href|src|url)\s*=\s*(?:"([^"]*)"|'([^']*)')`)
	absoluteLink  = regexp.MustCompile(`(?i)https?://[^\s<>"']+\.mp3(?:\?[^\s<>"']*)?`)

	// Path parts that never identify an episode
	genericParts = map[string]bool{
		"media": true, "audio": true, "mp3": true, "file": true, "download": true, "public": true,
		"shows": true, "episodes": true, "e": true, "s": true, "p": true, "open": true,
	}
)

// Pooled keep-alive connections shared by all requests
func newClient(verifyTLS bool) *http.Client {
	return &http.Client{Transport: &http.Transport{
		Proxy:               http.ProxyFromEnvironment,
		DialContext:         (&net.Dialer{Timeout: connectTimeout, KeepAlive: 30 * time.Second}).DialContext,
		ForceAttemptHTTP2:   true,
		MaxIdleConns:        64,
		MaxIdleConnsPerHost: 16,
		IdleConnTimeout:     90 * time.Second,
		TLSHandshakeTimeout: connectTimeout,
		TLSClientConfig:     &tls.Config{InsecureSkipVerify: !verifyTLS},
		ReadBufferSize:      copyBuffer,
	}}
}

// Bounded fan-out; work stores its result at its own index
func parallel(ctx context.Context, count, limit int, work func(index int)) {
	slots := make(chan struct{}, limit)
	var group sync.WaitGroup
	for index := range count {
		group.Go(func() {
			select {
			case slots <- struct{}{}:
				defer func() { <-slots }()
				work(index)
			case <-ctx.Done():
			}
		})
	}
	group.Wait()
}

// Request that only succeeds with a 2xx answer
func open(ctx context.Context, client *http.Client, method, address string) (*http.Response, error) {
	request, err := http.NewRequestWithContext(ctx, method, address, nil)
	if err != nil {
		return nil, errors.New("invalid url")
	}
	request.Header.Set("User-Agent", userAgent)
	request.Header.Set("Accept", "*/*")
	response, err := client.Do(request)
	if err != nil {
		return nil, err
	}
	if response.StatusCode/100 != 2 {
		response.Body.Close()
		return nil, fmt.Errorf("http %d", response.StatusCode)
	}
	return response, nil
}

// Short, stable reason for a failed operation
func failureReason(err error) string {
	var urlError *url.Error
	if errors.As(err, &urlError) {
		err = urlError.Err
	}
	var dnsError *net.DNSError
	var tlsError *tls.CertificateVerificationError
	var netError net.Error
	switch {
	case errors.Is(err, context.Canceled):
		return "cancelled"
	case errors.Is(err, context.DeadlineExceeded):
		return "timeout"
	case errors.As(err, &dnsError):
		return "dns lookup failed"
	case errors.As(err, &tlsError):
		return "tls certificate rejected (settings.verify_tls: false accepts it)"
	case errors.Is(err, syscall.ECONNREFUSED):
		return "connection refused"
	case errors.As(err, &netError) && netError.Timeout():
		return "timeout"
	}
	return strings.Join(strings.Fields(err.Error()), " ")
}

// Fetch every feed and collect its MP3 links
func scanFeeds(ctx context.Context, out printer, client *http.Client, config Config) []FeedRun {
	runs := make([]FeedRun, len(config.Feeds))
	for index, feed := range config.Feeds {
		runs[index] = FeedRun{Feed: feed, Directory: filepath.Join(config.Directory, feed.Name)}
	}
	bar := out.progress("Scanning", len(runs))
	parallel(ctx, len(runs), config.Settings.FeedConcurrency, func(index int) {
		run := &runs[index]
		links, err := fetchLinks(ctx, client, run.Feed.URL, config.Settings.FeedTimeout)
		if err != nil {
			run.Reason = failureReason(err)
		}
		run.Found, run.Links = len(links), links
		bar.step(run.Feed.Name)
	})
	bar.done()
	return runs
}

// Download one page and extract its links
func fetchLinks(ctx context.Context, client *http.Client, address string, timeout time.Duration) ([]string, error) {
	ctx, cancel := context.WithTimeout(ctx, timeout)
	defer cancel()
	response, err := open(ctx, client, http.MethodGet, address)
	if err != nil {
		return nil, err
	}
	defer response.Body.Close()
	content, err := io.ReadAll(io.LimitReader(response.Body, maxFeedBytes))
	if ctx.Err() != nil {
		return nil, ctx.Err()
	}
	if err != nil {
		return nil, err
	}
	// Relative links resolve against the redirect target
	return extractLinks(content, response.Request.URL), nil
}

// Distinct MP3 links in order of appearance
func extractLinks(content []byte, base *url.URL) []string {
	type located struct {
		position int
		link     string
	}
	var found []located
	for _, match := range linkAttribute.FindAllSubmatchIndex(content, -1) {
		start, end := match[2], match[3]
		if start < 0 {
			start, end = match[4], match[5]
		}
		value := strings.TrimSpace(html.UnescapeString(string(content[start:end])))
		target, err := base.Parse(value)
		if err != nil || target.Scheme != "http" && target.Scheme != "https" ||
			!strings.HasSuffix(strings.ToLower(target.Path), audioSuffix) {
			continue
		}
		// Absolute links stay untouched so both patterns agree
		if lower := strings.ToLower(value); !strings.HasPrefix(lower, "http://") && !strings.HasPrefix(lower, "https://") {
			value = target.String()
		}
		found = append(found, located{start, value})
	}
	for _, match := range absoluteLink.FindAllIndex(content, -1) {
		found = append(found, located{match[0], html.UnescapeString(string(content[match[0]:match[1]]))})
	}
	sort.SliceStable(found, func(a, b int) bool { return found[a].position < found[b].position })

	seen := map[string]bool{}
	var links []string
	for _, item := range found {
		if !seen[item.link] {
			seen[item.link] = true
			links = append(links, item.link)
		}
	}
	return links
}

// Drop mirrored episodes and keep the newest ones, oldest first
func selectEpisodes(ctx context.Context, out printer, client *http.Client, runs []FeedRun, settings Settings) {
	type probe struct{ run, link int }
	var probes []probe
	signatures := make([][]string, len(runs))
	for index := range runs {
		run := &runs[index]
		// Probing twice the limit leaves room for duplicates
		if settings.MaxEpisodes > 0 {
			run.Links = run.Links[:min(len(run.Links), 2*settings.MaxEpisodes)]
		}
		signatures[index] = make([]string, len(run.Links))
		for link := range run.Links {
			probes = append(probes, probe{index, link})
		}
	}

	bar := out.progress("Comparing", len(probes))
	parallel(ctx, len(probes), settings.ProbeConcurrency, func(index int) {
		target := probes[index]
		signatures[target.run][target.link] = probeSignature(ctx, client, runs[target.run].Links[target.link], settings.ProbeTimeout)
		bar.step(runs[target.run].Feed.Name)
	})
	bar.done()

	for index := range runs {
		runs[index].Links = pickLinks(runs[index].Links, signatures[index], settings.MaxEpisodes)
	}
}

// Content signature from a HEAD request; empty when unknown
func probeSignature(ctx context.Context, client *http.Client, address string, timeout time.Duration) string {
	ctx, cancel := context.WithTimeout(ctx, timeout)
	defer cancel()
	response, err := open(ctx, client, http.MethodHead, address)
	if err != nil {
		return ""
	}
	response.Body.Close()
	if response.StatusCode != http.StatusOK {
		return ""
	}
	header := response.Header
	return contentSignature(address, response.ContentLength,
		header.Get("Last-Modified"), header.Get("ETag"), header.Get("Content-Type"))
}

// Same signature means same audio behind different links
func contentSignature(address string, size int64, modified, etag, contentType string) string {
	// Size plus a validator identifies the audio wherever it is linked from
	if size >= realisticBytes && (modified != "" || etag != "") {
		return fmt.Sprintf("content:%d|%s|%s", size, modified, etag)
	}
	identifier := linkIdentifier(address)
	if size < realisticBytes {
		return fmt.Sprintf("url:%s|%s|%s|%s", identifier, modified, etag, contentType)
	}
	return fmt.Sprintf("size:%d|%s|%s|%s|%s", size, modified, etag, contentType, identifier)
}

// Most distinctive parts of the link path, such as UUIDs or hashes
func linkIdentifier(address string) string {
	path := ""
	if parsed, err := url.Parse(address); err == nil {
		path = parsed.EscapedPath()
	}
	parts := strings.FieldsFunc(path, func(char rune) bool { return char == '/' })
	var unique []string
	for _, part := range parts {
		stem, _, _ := strings.Cut(part, ".")
		if !genericParts[strings.ToLower(stem)] && len(stem) >= identifierLength && isIdentifier(stem) {
			unique = append(unique, stem)
		}
	}
	if len(unique) > 0 {
		sort.SliceStable(unique, func(a, b int) bool { return len(unique[a]) > len(unique[b]) })
		return strings.Join(unique[:min(len(unique), 2)], "_")
	}
	if len(parts) > 0 {
		stem, _, _ := strings.Cut(parts[len(parts)-1], ".")
		return stem
	}
	return path
}

// Letters and digits, optionally joined by dashes or underscores
func isIdentifier(text string) bool {
	plain := strings.NewReplacer("-", "", "_", "").Replace(text)
	return plain != "" && !strings.ContainsFunc(plain, func(char rune) bool {
		return !unicode.IsLetter(char) && !unicode.IsDigit(char)
	})
}

// First unique links up to the limit, reversed for download order
func pickLinks(links, signatures []string, limit int) []string {
	seen := map[string]bool{}
	var picked []string
	for index, link := range links {
		signature := signatures[index]
		// Unknown content is kept
		if signature != "" && seen[signature] {
			continue
		}
		seen[signature] = true
		picked = append(picked, link)
	}
	if limit > 0 {
		picked = picked[:min(len(picked), limit)]
	}
	slices.Reverse(picked)
	return picked
}
