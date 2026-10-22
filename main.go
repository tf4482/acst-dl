// acst-dl downloads the newest podcast episodes of the configured feeds once.
package main

import (
	"context"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"time"
)

const projectName = "acst-dl"

const help = projectName + ` — download the newest podcast episodes once

Usage:
  ` + projectName + `
  ` + projectName + ` --help | -h | help

Configuration:
  Uses the first existing file without merging:
  1. config.yml beside the executable
  2. ~/.config/` + projectName + `/config.yml
  The working directory is not searched.
  With no file, creates a user-only template at location 2 and exits 1.

Behavior:
  Scans every feed or page for MP3 links in parallel, drops mirrored
  episodes by comparing HEAD metadata, and keeps the newest max_episodes.
  Missing episodes are downloaded in parallel into one folder per feed,
  tagged while streaming; episodes already present are not fetched again.
  Episode files that left the selection are removed from the feed folder,
  unless one of the feed's episodes failed.
  With download_files off, only links.txt is written per feed.

Exit codes:
  0    Every feed and episode succeeded; feeds without links are not errors
  1    Configuration, feed, download, or file error
  130  Interrupted by the user
`

// Feed summary color
const boldGreen = "1;" + green

// Counters for the closing line
type totals struct {
	downloaded int
	present    int
	removed    int
	bytes      int64
	failed     bool
}

// Pending download with its feed
type download struct {
	run     *FeedRun
	episode *Episode
}

func main() {
	os.Exit(run(os.Args[1:]))
}

// Scan, select, download, tidy, report
func execute(ctx context.Context, out printer, config Config) int {
	started := time.Now()
	settings := config.Settings
	client := newClient(settings.VerifyTLS)
	defer client.CloseIdleConnections()

	out.line("📡", fmt.Sprintf("Scanning %s · %s", plural(len(config.Feeds), "feed"), config.Directory), "")
	runs := scanFeeds(ctx, out, client, config)
	if ctx.Err() != nil {
		return 130
	}
	selectEpisodes(ctx, out, client, runs, settings)
	if ctx.Err() != nil {
		return 130
	}
	if !settings.DownloadFiles {
		return listLinks(out, runs)
	}

	var sum totals
	queues := make([][]download, len(runs))
	for index := range runs {
		run := &runs[index]
		if run.Reason == "" && len(run.Links) > 0 {
			if err := planLibrary(run, started); err != nil {
				run.Reason = failureReason(err)
			}
		}
		for episode := range run.Episodes {
			if run.Reason == "" && run.Episodes[episode].State == "" {
				queues[index] = append(queues[index], download{run, &run.Episodes[episode]})
			}
		}
		// Feeds with nothing to fetch report right away
		if run.Pending = len(queues[index]); run.Pending == 0 {
			finishFeed(out.line, run, feedTags(run.Feed, settings, started), &sum)
		}
	}
	downloads := interleave(queues)

	if len(downloads) > 0 {
		out.line("📥", "Downloading "+plural(len(downloads), "episode"), "")
	}
	bar := out.progress("Downloading", len(downloads))
	var mutex sync.Mutex
	parallel(ctx, len(downloads), settings.DownloadConcurrency, func(index int) {
		run, episode := downloads[index].run, downloads[index].episode
		tags := feedTags(run.Feed, settings, started)
		mutex.Lock()
		if run.Began.IsZero() {
			run.Began = time.Now()
		}
		mutex.Unlock()

		began := time.Now()
		downloadEpisode(ctx, client, episode, run.Directory, tags, settings.DownloadTimeout)
		episode.Took = time.Since(began)
		bar.step(run.Feed.Name + " · " + episode.Name)
		if ctx.Err() != nil {
			return
		}

		// One line per download, then the feed summary after its last one
		mutex.Lock()
		defer mutex.Unlock()
		bar.line(episodeLine(run.Feed.Name, episode))
		if run.Pending--; run.Pending == 0 {
			finishFeed(bar.line, run, tags, &sum)
		}
	})
	bar.done()
	if ctx.Err() != nil {
		return 130
	}

	icon, color, verdict := "✅", green, "Done"
	if sum.failed {
		icon, color, verdict = "⚠️", yellow, "Done with errors"
	}
	out.line(icon, fmt.Sprintf("%s · %s · %d downloaded · %s · %d present · %d removed · %s",
		verdict, plural(len(runs), "feed"), sum.downloaded, megabytes(sum.bytes), sum.present, sum.removed,
		time.Since(started).Round(100*time.Millisecond)), color)
	if sum.failed {
		return 1
	}
	return 0
}

// Alternate between feeds so parallel downloads spread over hosts
func interleave(queues [][]download) []download {
	var mixed []download
	for round := 0; ; round++ {
		added := false
		for _, queue := range queues {
			if round < len(queue) {
				mixed = append(mixed, queue[round])
				added = true
			}
		}
		if !added {
			return mixed
		}
	}
}

// Tags a feed's episodes should carry
func feedTags(feed Feed, settings Settings, started time.Time) Tags {
	var tags Tags
	if settings.TagAlbum {
		tags.Album = feed.Name
	}
	if settings.TagReleaseDate {
		tags.Date = started.Format("2006-01-02")
	}
	return tags
}

// Permanent line above the live progress bar
func (b *progress) line(icon, text, color string) {
	b.mutex.Lock()
	defer b.mutex.Unlock()
	if b.stop != nil {
		fmt.Fprint(b.out.out, "\r\033[K")
	}
	b.out.line(icon, text, color)
	b.draw()
}

// Output line of one finished download
func episodeLine(name string, episode *Episode) (icon, text, color string) {
	if episode.State != stateDownloaded {
		return "❌", fmt.Sprintf("%s · %s · %s · %s", name, episode.Name, stateFailed, episode.Reason), red
	}
	text = fmt.Sprintf("%s · %s · %s · %s", name, episode.Name, episode.State, pace(episode.Size, episode.Took))
	if episode.Untagged {
		return "⚠️", text + " · untagged, unsupported ID3 tag", yellow
	}
	return "✅", text, green
}

// Retag present files, remove stale ones, and print the feed summary
func finishFeed(say func(icon, text, color string), run *FeedRun, tags Tags, sum *totals) {
	name := run.Feed.Name
	if run.Reason != "" {
		sum.failed = true
		say("❌", fmt.Sprintf("%s · feed · %s", name, run.Reason), red)
		return
	}
	if len(run.Links) == 0 {
		say("⚠️", name+" · no MP3 links found", yellow)
		return
	}

	downloaded, present, failed, size := 0, 0, 0, int64(0)
	for _, episode := range run.Episodes {
		switch episode.State {
		case statePresent:
			present++
			if _, err := retagFile(filepath.Join(run.Directory, episode.Filename), tags); err != nil {
				failed++
				say("⚠️", fmt.Sprintf("%s · %s · tags not updated · %s", name, episode.Name, failureReason(err)), yellow)
			}
		case stateDownloaded:
			downloaded++
			size += episode.Size
		default:
			failed++
		}
	}

	// Old episodes stay until the new ones are safely there
	removed := 0
	if failed == 0 {
		var err error
		if removed, err = removeStale(run); err != nil {
			failed++
			say("⚠️", fmt.Sprintf("%s · old file not removed · %s", name, failureReason(err)), yellow)
		}
	}
	sum.downloaded += downloaded
	sum.present += present
	sum.removed += removed
	sum.bytes += size

	icon, color := "🎙️", boldGreen
	if failed > 0 {
		sum.failed = true
		icon, color = "⚠️", yellow
	}
	fields := []string{name, fmt.Sprintf("%d of %s", len(run.Episodes), plural(run.Found, "link"))}
	if downloaded > 0 {
		fields = append(fields, fmt.Sprintf("⬇️ %d downloaded", downloaded), pace(size, time.Since(run.Began)))
	}
	fields = append(fields, fmt.Sprintf("📁 %d present", present))
	if removed > 0 {
		fields = append(fields, fmt.Sprintf("🧹 %d removed", removed))
	}
	if failed > 0 {
		fields = append(fields, fmt.Sprintf("%d failed", failed))
	}
	say(icon, strings.Join(fields, " · "), color)
}

// Links-only mode: one links.txt per feed
func listLinks(out printer, runs []FeedRun) int {
	code := 0
	for index := range runs {
		run := &runs[index]
		if run.Reason == "" && len(run.Links) > 0 {
			if err := writeLinks(run); err != nil {
				run.Reason = failureReason(err)
			}
		}
		switch {
		case run.Reason != "":
			code = 1
			out.line("❌", fmt.Sprintf("%s · feed · %s", run.Feed.Name, run.Reason), red)
		case len(run.Links) == 0:
			out.line("⚠️", run.Feed.Name+" · no MP3 links found", yellow)
		default:
			out.line("✅", fmt.Sprintf("%s · %d of %s · %s", run.Feed.Name, len(run.Links),
				plural(run.Found, "link"), linksFile), green)
		}
	}
	return code
}

func plural(count int, noun string) string {
	if count == 1 {
		return "1 " + noun
	}
	return fmt.Sprintf("%d %ss", count, noun)
}

// Size, duration, and average speed of finished downloads
func pace(size int64, took time.Duration) string {
	return fmt.Sprintf("📦 %s · ⏱️ %s · ⚡ %s/s", megabytes(size), took.Round(100*time.Millisecond),
		megabytes(int64(float64(size)/max(took.Seconds(), 0.001))))
}

func megabytes(size int64) string {
	return fmt.Sprintf("%.1f MB", float64(size)/(1<<20))
}
