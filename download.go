package main

import (
	"bufio"
	"context"
	"crypto/md5"
	"encoding/hex"
	"fmt"
	"net/http"
	"net/url"
	"os"
	"path/filepath"
	"regexp"
	"slices"
	"strings"
	"time"
	"unicode"
)

const (
	audioSuffix = ".mp3"
	partSuffix  = ".part"
	linksFile   = "links.txt"

	// Characters of the link hash that identify an episode on disk
	hashLength    = 8
	maxNameLength = 120
	// Large writes suit network shares
	writeBuffer = 1 << 20

	// Episode states as printed
	stateDownloaded = "downloaded"
	statePresent    = "present"
	stateFailed     = "failed"
)

// Audio file named by this tool, ending in the link hash
var ownFile = regexp.MustCompile(`_[0-9a-f]{8}\.mp3$`)

// One selected episode and what happened to it
type Episode struct {
	URL      string
	Name     string // short name from the link
	Filename string // file inside the feed folder
	State    string
	Reason   string
	Size     int64
	Untagged bool // saved without the wanted tags
	Took     time.Duration
	// From the feed; zero and empty when it has none
	Published time.Time
	Title     string
}

// Create the feed folder and match the selection against its files
func planLibrary(run *FeedRun, started time.Time) error {
	if err := os.MkdirAll(run.Directory, 0o755); err != nil {
		return err
	}
	entries, err := os.ReadDir(run.Directory)
	if err != nil {
		return err
	}
	for _, entry := range entries {
		name := strings.ToLower(entry.Name())
		switch {
		case entry.IsDir():
		case strings.HasSuffix(name, audioSuffix+partSuffix):
			// Leftover of an interrupted run
			os.Remove(filepath.Join(run.Directory, entry.Name()))
		case ownFile.MatchString(name):
			// Other audio in the folder is never touched
			run.Library = append(run.Library, entry.Name())
		}
	}

	run.Episodes = make([]Episode, len(run.Links))
	for index, link := range run.Links {
		name, hash := episodeName(link)
		release := run.Releases[link]
		episode := Episode{URL: link, Name: name, Published: release.Published, Title: release.Title}
		// Names sort by release date, or by download time without one;
		// one microsecond apart keeps equal moments in feed order
		moment := started
		if !release.Published.IsZero() {
			moment = release.Published.Local()
		}
		moment = moment.Add(time.Duration(index) * time.Microsecond)
		filename := fmt.Sprintf("%s%06d_%s_%s%s",
			moment.Format("2006-01-02-150405"), moment.Nanosecond()/1000, name, hash, audioSuffix)

		ending := "_" + hash + audioSuffix
		present := slices.IndexFunc(run.Library, func(file string) bool { return strings.HasSuffix(strings.ToLower(file), ending) })
		switch {
		case present < 0:
			episode.Filename = filename
		case release.Published.IsZero() || run.Library[present] == filename:
			episode.Filename, episode.State = run.Library[present], statePresent
		default:
			// Files named after their download time move to their release date
			episode.Filename, episode.State = run.Library[present], statePresent
			if os.Rename(filepath.Join(run.Directory, episode.Filename), filepath.Join(run.Directory, filename)) == nil {
				run.Library[present], episode.Filename = filename, filename
			}
		}
		run.Episodes[index] = episode
	}
	return nil
}

// Readable name and stable hash of an episode link
func episodeName(link string) (name, hash string) {
	if parsed, err := url.Parse(link); err == nil {
		path := strings.TrimRight(parsed.Path, "/")
		name = path[strings.LastIndex(path, "/")+1:]
	}
	if strings.HasSuffix(strings.ToLower(name), audioSuffix) {
		name = name[:len(name)-len(audioSuffix)]
	}
	stable := link
	if genericParts[strings.ToLower(name)] {
		// Names like media.mp3 say nothing, so use the link's identifier; the query may tell episodes apart
		name = linkIdentifier(link)
	} else {
		// Changing tokens or tracking parameters must not make a new episode
		stable, _, _ = strings.Cut(link, "?")
	}
	sum := md5.Sum([]byte(stable))
	hash = hex.EncodeToString(sum[:])[:hashLength]

	// Only letters, digits, dots, dashes, and underscores reach the file system
	name = strings.Map(func(char rune) rune {
		if unicode.IsLetter(char) || unicode.IsDigit(char) || strings.ContainsRune(".-_", char) {
			return char
		}
		return '_'
	}, name)
	if strings.Trim(name, "._") == "" {
		name = "audio"
	}
	if runes := []rune(name); len(runes) > maxNameLength {
		name = string(runes[:maxNameLength])
	}
	return name, hash
}

// Stream one episode to disk, tagging it on the way
func downloadEpisode(ctx context.Context, client *http.Client, episode *Episode, directory string, tags Tags, timeout time.Duration) {
	ctx, cancel := context.WithTimeout(ctx, timeout)
	defer cancel()
	path := filepath.Join(directory, episode.Filename)
	size, tagged, err := saveEpisode(ctx, client, episode.URL, path, tags)
	if err != nil {
		// An expired deadline surfaces as a broken read
		if ctx.Err() != nil {
			err = ctx.Err()
		}
		os.Remove(path + partSuffix)
		episode.State, episode.Reason = stateFailed, failureReason(err)
		return
	}
	episode.State, episode.Size = stateDownloaded, size
	episode.Untagged = tags != (Tags{}) && !tagged
	stamp(path, episode.Published)
}

// File time set to the release date, for apps that sort by it; best effort, unknown dates stay
func stamp(path string, published time.Time) {
	if !published.IsZero() {
		os.Chtimes(path, published, published)
	}
}

// Write to a partial file and rename it once complete
func saveEpisode(ctx context.Context, client *http.Client, link, path string, tags Tags) (int64, bool, error) {
	response, err := open(ctx, client, http.MethodGet, link)
	if err != nil {
		return 0, false, err
	}
	defer response.Body.Close()
	file, err := os.Create(path + partSuffix)
	if err != nil {
		return 0, false, err
	}
	writer := bufio.NewWriterSize(file, writeBuffer)
	size, tagged, err := copyTagged(writer, response.Body, tags)
	if err == nil {
		err = writer.Flush()
	}
	if closeErr := file.Close(); err == nil {
		err = closeErr
	}
	if err == nil {
		err = os.Rename(path+partSuffix, path)
	}
	return size, tagged, err
}

// Delete audio files that left the selection; returns removed count and first error
func removeStale(run *FeedRun) (int, error) {
	kept := map[string]bool{}
	for _, episode := range run.Episodes {
		if episode.State != stateFailed {
			kept[episode.Filename] = true
		}
	}
	removed := 0
	var failure error
	for _, file := range run.Library {
		if kept[file] {
			continue
		}
		if err := os.Remove(filepath.Join(run.Directory, file)); err != nil {
			if failure == nil {
				failure = err
			}
			continue
		}
		removed++
	}
	return removed, failure
}

// Save the selected links instead of the audio
func writeLinks(run *FeedRun) error {
	if err := os.MkdirAll(run.Directory, 0o755); err != nil {
		return err
	}
	content := strings.Join(run.Links, "\n") + "\n"
	return os.WriteFile(filepath.Join(run.Directory, linksFile), []byte(content), 0o644)
}
