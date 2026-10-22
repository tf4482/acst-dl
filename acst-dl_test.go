package main

import (
	"bytes"
	"context"
	"errors"
	"fmt"
	"net/http"
	"net/http/httptest"
	"net/url"
	"os"
	"path/filepath"
	"slices"
	"strings"
	"sync/atomic"
	"testing"
	"time"

	"gopkg.in/yaml.v3"
)

const validConfig = `feeds:
  "News": "https://feeds.example/news.xml"
library:
  directory: "/srv/podcasts"
settings:
  max_episodes: 5
  download_files: true
  tag_album: true
  tag_release_date: false
  verify_tls: true
  feed_concurrency: 4
  feed_timeout_seconds: 30
  probe_concurrency: 8
  probe_timeout_seconds: 2.5
  download_concurrency: 4
  download_timeout_seconds: 900
`

func parseYAML(t *testing.T, text string) (Config, error) {
	t.Helper()
	var document any
	if err := yaml.Unmarshal([]byte(text), &document); err != nil {
		t.Fatal(err)
	}
	return parseConfig(document)
}

func writeFile(t *testing.T, path, content string) {
	t.Helper()
	if err := os.MkdirAll(filepath.Dir(path), 0o700); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(path, []byte(content), 0o600); err != nil {
		t.Fatal(err)
	}
}

// Leading tag of a file on disk
func readTag(t *testing.T, path string) (id3Tag, []byte) {
	t.Helper()
	data, err := os.ReadFile(path)
	if err != nil {
		t.Fatal(err)
	}
	length := id3Length(data)
	tag, supported := parseID3(data[:length])
	if !supported {
		t.Fatalf("unsupported tag in %s", path)
	}
	return tag, data[length:]
}

func audioFiles(t *testing.T, directory string) []string {
	t.Helper()
	files, err := filepath.Glob(filepath.Join(directory, "*"+audioSuffix))
	if err != nil {
		t.Fatal(err)
	}
	return files
}

func TestExecutableConfigTakesPrecedence(t *testing.T) {
	binaryDir, home := t.TempDir(), t.TempDir()
	writeFile(t, filepath.Join(binaryDir, "config.yml"), validConfig)
	writeFile(t, filepath.Join(home, ".config", projectName, "config.yml"), "not: valid")

	path, config, err := loadConfig(binaryDir, home)
	if err != nil {
		t.Fatal(err)
	}
	if path != filepath.Join(binaryDir, "config.yml") || config.Feeds[0] != (Feed{"News", "https://feeds.example/news.xml"}) {
		t.Fatalf("unexpected selection: %s %+v", path, config)
	}
	if config.Settings.ProbeTimeout != 2500*time.Millisecond {
		t.Fatalf("unexpected timeout: %v", config.Settings.ProbeTimeout)
	}
}

func TestInvalidConfigDoesNotFallBackOrLeak(t *testing.T) {
	binaryDir, home := t.TempDir(), t.TempDir()
	writeFile(t, filepath.Join(binaryDir, "config.yml"), "feeds: [secret-content\n")
	writeFile(t, filepath.Join(home, ".config", projectName, "config.yml"), validConfig)

	_, _, err := loadConfig(binaryDir, home)
	if err == nil {
		t.Fatal("expected an error")
	}
	if strings.Contains(err.Error(), "secret-content") || !strings.Contains(err.Error(), binaryDir) {
		t.Fatalf("unexpected error: %v", err)
	}
}

func TestFirstRunCreatesTemplate(t *testing.T) {
	binaryDir, home := t.TempDir(), t.TempDir()
	t.Setenv("HOME", home)
	_, _, err := loadConfig(binaryDir, home)
	var created *configCreatedError
	if !errors.As(err, &created) {
		t.Fatalf("expected a created template, got %v", err)
	}
	info, err := os.Stat(created.path)
	if err != nil || info.Mode().Perm() != 0o600 {
		t.Fatalf("unexpected template: %v %v", info, err)
	}
	if _, _, err := loadConfig(binaryDir, home); err == nil || !strings.Contains(err.Error(), "edit placeholder value at feeds.Example Podcast") {
		t.Fatalf("unedited template accepted: %v", err)
	}

	example, err := os.ReadFile("config.example.yml")
	if err != nil {
		t.Fatal(err)
	}
	var fromExample, fromDefault any
	if yaml.Unmarshal(example, &fromExample) != nil || yaml.Unmarshal([]byte(defaultConfig), &fromDefault) != nil ||
		fmt.Sprint(fromExample) != fmt.Sprint(fromDefault) {
		t.Fatal("config.example.yml differs from the embedded template")
	}
}

func TestConfigValidation(t *testing.T) {
	t.Setenv("HOME", "/home/listener")
	config, err := parseYAML(t, strings.Replace(validConfig, `"/srv/podcasts"`, `"~/Podcasts"`, 1))
	if err != nil || config.Directory != "/home/listener/Podcasts" {
		t.Fatalf("home not expanded: %q %v", config.Directory, err)
	}

	cases := map[string][2]string{
		"placeholder":        {`"https://feeds.example/news.xml"`, `"CHANGE_ME"`},
		"feed without host":  {`"https://feeds.example/news.xml"`, `"news.xml"`},
		"feed scheme":        {`"https://feeds.example/news.xml"`, `"ftp://feeds.example/news.xml"`},
		"feed name as path":  {`"News":`, `"../News":`},
		"no feeds":           {`  "News": "https://feeds.example/news.xml"`, `  {}`},
		"relative directory": {`"/srv/podcasts"`, `"podcasts"`},
		"negative episodes":  {`max_episodes: 5`, `max_episodes: -1`},
		"flag as text":       {`tag_album: true`, `tag_album: "yes"`},
		"zero concurrency":   {`download_concurrency: 4`, `download_concurrency: 0`},
		"zero timeout":       {`feed_timeout_seconds: 30`, `feed_timeout_seconds: 0`},
		"missing key":        {"  verify_tls: true\n", ""},
		"unknown key":        {`verify_tls: true`, "verify_tls: true\n  extra: 1"},
	}
	for name, replace := range cases {
		if !strings.Contains(validConfig, replace[0]) {
			t.Fatalf("%s: base text not found", name)
		}
		if _, err := parseYAML(t, strings.Replace(validConfig, replace[0], replace[1], 1)); err == nil {
			t.Errorf("%s: expected an error", name)
		}
	}
}

func TestExtractLinks(t *testing.T) {
	base, _ := url.Parse("https://feeds.example/show/feed.xml")
	content := `<rss><item>
<enclosure url="https://cdn.example/a.mp3?token=1&amp;x=2" type="audio/mpeg"/>
<link>https://cdn.example/a.mp3?token=1&amp;x=2</link></item>
<a class="x" href='episodes/b.MP3'>B</a>
<audio src="/media/c.mp3"></audio>
<a href="https://cdn.example/notes.pdf">notes</a>
<p>plain https://cdn.example/d.mp3 text</p>
<source src="/media/c.mp3"></rss>`
	want := []string{
		"https://cdn.example/a.mp3?token=1&x=2",
		"https://feeds.example/show/episodes/b.MP3",
		"https://feeds.example/media/c.mp3",
		"https://cdn.example/d.mp3",
	}
	if links := extractLinks([]byte(content), base); !slices.Equal(links, want) {
		t.Fatalf("unexpected links: %q", links)
	}
}

func TestPickLinksDropsMirrorsAndReverses(t *testing.T) {
	links := []string{"new", "mirror", "unknown", "old", "older"}
	signatures := []string{"a", "a", "", "b", "c"}
	if picked := pickLinks(links, signatures, 3); !slices.Equal(picked, []string{"old", "unknown", "new"}) {
		t.Fatalf("unexpected selection: %q", picked)
	}
	if picked := pickLinks(links, signatures, 0); len(picked) != 4 {
		t.Fatalf("unlimited selection cut: %q", picked)
	}
}

func TestContentSignature(t *testing.T) {
	first := contentSignature("https://a.example/media/0123456789abcdef0123/ep.mp3", 5_000_000, "", "", "audio/mpeg")
	mirror := contentSignature("https://b.example/audio/0123456789abcdef0123/ep.mp3?x=1", 5_000_000, "", "", "audio/mpeg")
	other := contentSignature("https://a.example/media/fedcba98765432100123/ep.mp3", 5_000_000, "", "", "audio/mpeg")
	if first != mirror || first == other {
		t.Fatalf("unexpected signatures: %q %q %q", first, mirror, other)
	}
	// Validators identify content even behind unrelated links
	direct := contentSignature("https://a.example/podcast/2026/08/ep120.mp3", 5_000_000, "", `"6a80"`, "audio/mpeg")
	tracked := contentSignature("https://a.example/podcast/2026%2F08%2Fep120.mp3", 5_000_000, "", `"6a80"`, "audio/mpeg")
	if direct != tracked || direct == first {
		t.Fatalf("unexpected signatures: %q %q", direct, tracked)
	}
	if name, hash := episodeName("https://a.example/podcast/2026%2F08%2Fep 120.MP3?x=1"); name != "ep_120" || len(hash) != hashLength {
		t.Fatalf("unexpected name: %q %q", name, hash)
	}
	if name, _ := episodeName("https://a.example/episodes/0123456789abcdef0123/media.mp3"); name != "0123456789abcdef0123" {
		t.Fatalf("generic name kept: %q", name)
	}
	// Rotating tokens keep the hash, unless the query is all that tells episodes apart
	_, plain := episodeName("https://a.example/ep120.mp3")
	_, token := episodeName("https://a.example/ep120.mp3?token=abc")
	_, firstID := episodeName("https://a.example/media.mp3?id=1")
	_, secondID := episodeName("https://a.example/media.mp3?id=2")
	if plain != token || firstID == secondID {
		t.Fatalf("unexpected hashes: %q %q %q %q", plain, token, firstID, secondID)
	}
}

func TestCopyTaggedRewritesLeadingTag(t *testing.T) {
	audio := []byte("\xFF\xFBaudio-frames")
	tags := Tags{Album: "Näws", Date: "2026-10-05"}
	old := id3Tag{version: 3}
	old.setText("TIT2", "Title")
	old.setText("TALB", "Old")

	for name, leading := range map[string][]byte{"no tag": nil, "version 3": old.serialize(40)} {
		var target bytes.Buffer
		written, tagged, err := copyTagged(&target, bytes.NewReader(append(leading, audio...)), tags)
		if err != nil || !tagged || written != int64(target.Len()) {
			t.Fatalf("%s: %d %v %v", name, written, tagged, err)
		}
		data := target.Bytes()
		tag, _ := parseID3(data[:id3Length(data)])
		if !bytes.Equal(data[id3Length(data):], audio) || tag.text("TALB") != "Näws" {
			t.Fatalf("%s: unexpected result %q", name, data)
		}
		if tag.version == 3 && (tag.text("TIT2") != "Title" || tag.text("TYER") != "2026" || tag.text("TDAT") != "0510") {
			t.Fatalf("%s: version 3 frames wrong: %+v", name, tag)
		}
		if tag.version == 4 && tag.text("TDRC") != "2026-10-05" {
			t.Fatalf("%s: date missing", name)
		}
	}

	// Older tag versions pass through untouched
	legacy := append([]byte{'I', 'D', '3', 2, 0, 0, 0, 0, 0, 2, 0, 0}, audio...)
	var target bytes.Buffer
	if _, tagged, err := copyTagged(&target, bytes.NewReader(legacy), tags); err != nil || tagged || !bytes.Equal(target.Bytes(), legacy) {
		t.Fatalf("legacy tag changed: %v %v", tagged, err)
	}
}

func TestParseTagWithPlainFrameSizes(t *testing.T) {
	// Version 4 tag whose 200-byte frame size is not synchsafe
	body := append([]byte{'T', 'I', 'T', '2', 0, 0, 0, 200, 0, 0, 3}, bytes.Repeat([]byte("x"), 199)...)
	body = append(body, 'T', 'A', 'L', 'B', 0, 0, 0, 2, 0, 0, 3, 'A')
	data := append([]byte{'I', 'D', '3', 4, 0, 0}, appendSynchsafe(nil, len(body))...)
	tag, supported := parseID3(append(data, body...))
	if !supported || len(tag.frames) != 2 || tag.text("TALB") != "A" {
		t.Fatalf("unexpected frames: %v %+v", supported, tag.frames)
	}
}

func TestRetagFile(t *testing.T) {
	path := filepath.Join(t.TempDir(), "episode.mp3")
	audio := []byte("\xFF\xFBaudio-frames")
	writeFile(t, path, string(audio))

	// No tag yet, so the file is rewritten
	if changed, err := retagFile(path, Tags{Album: "News", Date: "2026-10-05"}); err != nil || !changed {
		t.Fatalf("first retag: %v %v", changed, err)
	}
	// Padding takes the longer album in place; the date stays
	if changed, err := retagFile(path, Tags{Album: "Daily News", Date: "2027-01-01"}); err != nil || !changed {
		t.Fatalf("second retag: %v %v", changed, err)
	}
	if changed, err := retagFile(path, Tags{Album: "Daily News", Date: "2027-01-01"}); err != nil || changed {
		t.Fatalf("current tags rewritten: %v %v", changed, err)
	}
	tag, rest := readTag(t, path)
	if tag.text("TALB") != "Daily News" || tag.text("TDRC") != "2026-10-05" || !bytes.Equal(rest, audio) {
		t.Fatalf("unexpected file: %+v %q", tag, rest)
	}
}

// Feed with three episodes, one of them mirrored under a second link
func podcastServer(t *testing.T, downloads *atomic.Int32) *httptest.Server {
	t.Helper()
	mux := http.NewServeMux()
	mux.HandleFunc("/feed.xml", func(w http.ResponseWriter, r *http.Request) {
		for _, path := range []string{"/media/ep3.mp3", "/mirror/ep3.mp3", "/media/ep2.mp3", "/media/ep1.mp3"} {
			fmt.Fprintf(w, "<enclosure url=\"http://%s%s\"/>\n", r.Host, path)
		}
	})
	episode := func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "audio/mpeg")
		w.Header().Set("ETag", filepath.Base(r.URL.Path))
		if r.Method == http.MethodGet {
			downloads.Add(1)
		}
		w.Write([]byte("\xFF\xFB" + r.URL.Path))
	}
	mux.HandleFunc("/media/", episode)
	mux.HandleFunc("/mirror/", episode)
	mux.HandleFunc("/stall.xml", func(w http.ResponseWriter, r *http.Request) {
		fmt.Fprintf(w, "<enclosure url=\"http://%s/stall/slow.mp3\"/>", r.Host)
	})
	mux.HandleFunc("/stall/", func(w http.ResponseWriter, r *http.Request) {
		if r.Method == http.MethodGet {
			w.Write([]byte("\xFF\xFBstart"))
			w.(http.Flusher).Flush()
			<-r.Context().Done()
		}
	})
	server := httptest.NewServer(mux)
	t.Cleanup(server.Close)
	return server
}

func testConfig(directory, feed string) Config {
	return Config{
		Feeds:     []Feed{{"News", feed}},
		Directory: directory,
		Settings: Settings{
			MaxEpisodes: 2, DownloadFiles: true, TagAlbum: true, VerifyTLS: true,
			FeedConcurrency: 2, FeedTimeout: 5 * time.Second,
			ProbeConcurrency: 4, ProbeTimeout: 5 * time.Second,
			DownloadConcurrency: 2, DownloadTimeout: 5 * time.Second,
		},
	}
}

func TestRunDownloadsOnceAndTidies(t *testing.T) {
	var downloads atomic.Int32
	server := podcastServer(t, &downloads)
	directory := t.TempDir()
	config := testConfig(directory, server.URL+"/feed.xml")
	feedDir := filepath.Join(directory, "News")
	writeFile(t, filepath.Join(feedDir, "old-episode.mp3"), "old")
	writeFile(t, filepath.Join(feedDir, "crashed.mp3.part"), "partial")

	var output bytes.Buffer
	if code := execute(context.Background(), printer{out: &output}, config); code != 0 {
		t.Fatalf("exit %d: %s", code, output.String())
	}
	files := audioFiles(t, feedDir)
	if len(files) != 2 || downloads.Load() != 2 {
		t.Fatalf("unexpected library: %v after %d downloads\n%s", files, downloads.Load(), output.String())
	}
	// Oldest selected episode sorts first; the mirror was dropped
	if !strings.Contains(files[0], "_ep2_") || !strings.Contains(files[1], "_ep3_") {
		t.Fatalf("unexpected order: %v", files)
	}
	if tag, audio := readTag(t, files[1]); tag.text("TALB") != "News" || string(audio) != "\xFF\xFB/media/ep3.mp3" {
		t.Fatalf("unexpected episode: %+v %q", tag, audio)
	}
	if entries, _ := os.ReadDir(feedDir); len(entries) != 2 {
		t.Fatalf("leftovers kept: %v", entries)
	}

	// Second run finds everything present
	if code := execute(context.Background(), printer{out: &output}, config); code != 0 || downloads.Load() != 2 {
		t.Fatalf("second run: exit %d, %d downloads\n%s", code, downloads.Load(), output.String())
	}
	if again := audioFiles(t, feedDir); !slices.Equal(again, files) {
		t.Fatalf("library changed: %v", again)
	}
}

func TestLinksOnlyMode(t *testing.T) {
	var downloads atomic.Int32
	server := podcastServer(t, &downloads)
	config := testConfig(t.TempDir(), server.URL+"/feed.xml")
	config.Settings.DownloadFiles = false

	if code := execute(context.Background(), printer{out: &bytes.Buffer{}}, config); code != 0 || downloads.Load() != 0 {
		t.Fatalf("exit %d, %d downloads", code, downloads.Load())
	}
	links, err := os.ReadFile(filepath.Join(config.Directory, "News", linksFile))
	if err != nil || strings.Count(string(links), "\n") != 2 {
		t.Fatalf("unexpected links file: %q %v", links, err)
	}
}

func TestFailuresKeepTheLibraryClean(t *testing.T) {
	var downloads atomic.Int32
	server := podcastServer(t, &downloads)
	config := testConfig(t.TempDir(), server.URL+"/stall.xml")
	config.Feeds = append(config.Feeds, Feed{"Offline", server.URL + "/missing.xml"})
	config.Settings.DownloadTimeout = 300 * time.Millisecond
	feedDir := filepath.Join(config.Directory, "News")
	writeFile(t, filepath.Join(feedDir, "old-episode.mp3"), "old")

	var output bytes.Buffer
	started := time.Now()
	code := execute(context.Background(), printer{out: &output}, config)
	if time.Since(started) > 3*time.Second {
		t.Fatalf("deadline ignored: %v", time.Since(started))
	}
	if code != 1 || !strings.Contains(output.String(), "slow · failed · timeout") ||
		!strings.Contains(output.String(), "Offline · feed · http 404") {
		t.Fatalf("exit %d: %s", code, output.String())
	}
	// Only the old episode remains: no partial file, nothing removed
	if entries, _ := os.ReadDir(feedDir); len(entries) != 1 || entries[0].Name() != "old-episode.mp3" {
		t.Fatalf("unexpected folder: %v", entries)
	}
}
