// acst-dl downloads the newest podcast episodes of the configured feeds once.
package main

import (
	"context"
	"fmt"
	"os"
	"path/filepath"
	"strings"
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
  Audio files that left the selection are removed from the feed folder,
  unless one of the feed's episodes failed.
  With download_files off, only links.txt is written per feed.

Exit codes:
  0    Every feed and episode succeeded; feeds without links are not errors
  1    Configuration, feed, download, or file error
  130  Interrupted by the user
`

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

	queues := make([][]download, len(runs))
	for index := range runs {
		run := &runs[index]
		if run.Reason != "" || len(run.Links) == 0 {
			continue
		}
		if err := planLibrary(run, started); err != nil {
			run.Reason = failureReason(err)
			continue
		}
		for episode := range run.Episodes {
			if run.Episodes[episode].State == "" {
				queues[index] = append(queues[index], download{run, &run.Episodes[episode]})
			}
		}
	}
	downloads := interleave(queues)

	if len(downloads) > 0 {
		out.line("📥", "Downloading "+plural(len(downloads), "episode"), "")
	}
	bar := out.progress("Downloading", len(downloads))
	parallel(ctx, len(downloads), settings.DownloadConcurrency, func(index int) {
		item := downloads[index]
		downloadEpisode(ctx, client, item.episode, item.run.Directory,
			feedTags(item.run.Feed, settings, started), settings.DownloadTimeout)
		bar.step(item.run.Feed.Name + " · " + item.episode.Name)
	})
	bar.done()
	if ctx.Err() != nil {
		return 130
	}

	var sum totals
	for index := range runs {
		finishFeed(out, &runs[index], feedTags(runs[index].Feed, settings, started), &sum)
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

// Retag present files, remove stale ones, and print the feed's lines
func finishFeed(out printer, run *FeedRun, tags Tags, sum *totals) {
	name := run.Feed.Name
	if run.Reason != "" {
		sum.failed = true
		out.line("❌", fmt.Sprintf("%s · feed · %s", name, run.Reason), red)
		return
	}
	if len(run.Links) == 0 {
		out.line("⚠️", name+" · no MP3 links found", yellow)
		return
	}

	downloaded, present, failed := 0, 0, 0
	for _, episode := range run.Episodes {
		switch episode.State {
		case statePresent:
			present++
			if _, err := retagFile(filepath.Join(run.Directory, episode.Filename), tags); err != nil {
				failed++
				out.line("⚠️", fmt.Sprintf("%s · %s · tags not updated · %s", name, episode.Name, failureReason(err)), yellow)
			}
		case stateDownloaded:
			downloaded++
			sum.bytes += episode.Size
			if episode.Untagged {
				out.line("⚠️", fmt.Sprintf("%s · %s · %s · %s · untagged, unsupported ID3 tag",
					name, episode.Name, episode.State, megabytes(episode.Size)), yellow)
			} else {
				out.line("✅", fmt.Sprintf("%s · %s · %s · %s", name, episode.Name, episode.State, megabytes(episode.Size)), green)
			}
		default:
			failed++
			out.line("❌", fmt.Sprintf("%s · %s · %s · %s", name, episode.Name, stateFailed, episode.Reason), red)
		}
	}

	// Old episodes stay until the new ones are safely there
	removed := 0
	if failed == 0 {
		var err error
		if removed, err = removeStale(run); err != nil {
			failed++
			out.line("⚠️", fmt.Sprintf("%s · old file not removed · %s", name, failureReason(err)), yellow)
		}
	}
	sum.downloaded += downloaded
	sum.present += present
	sum.removed += removed

	icon, color := "✅", green
	if failed > 0 {
		sum.failed = true
		icon, color = "⚠️", yellow
	}
	fields := []string{name, fmt.Sprintf("%d of %s", len(run.Episodes), plural(run.Found, "link")),
		fmt.Sprintf("%d downloaded", downloaded), fmt.Sprintf("%d present", present)}
	if removed > 0 {
		fields = append(fields, fmt.Sprintf("%d removed", removed))
	}
	if failed > 0 {
		fields = append(fields, fmt.Sprintf("%d failed", failed))
	}
	out.line(icon, strings.Join(fields, " · "), color)
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

func megabytes(size int64) string {
	return fmt.Sprintf("%.1f MB", float64(size)/(1<<20))
}
