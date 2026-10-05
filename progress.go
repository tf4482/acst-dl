// Shared progress frame: transient spinner and bar for long phases.
// Copy unchanged; needs printer from cli.go.
package main

import (
	"fmt"
	"os"
	"strings"
	"sync"
	"time"

	"golang.org/x/term"
)

// Look of the progress line
const (
	progressCells    = 20
	progressInterval = 100 * time.Millisecond
	progressFrames   = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
)

// Live progress line; silent when output is not a terminal
type progress struct {
	out     printer
	label   string
	total   int
	width   int
	mutex   sync.Mutex
	current int
	message string
	frame   int
	stop    chan struct{}
	stopped chan struct{}
}

// Start a bar for a phase of total steps; always pair with done
func (p printer) progress(label string, total int) *progress {
	bar := &progress{out: p, label: label, total: total, width: 80}
	file, ok := p.out.(*os.File)
	if !ok || !term.IsTerminal(int(file.Fd())) {
		return bar
	}
	if width, _, err := term.GetSize(int(file.Fd())); err == nil && width > 0 {
		bar.width = width
	}
	bar.stop, bar.stopped = make(chan struct{}), make(chan struct{})
	go bar.animate()
	return bar
}

// Count one finished step; safe to call from goroutines
func (b *progress) step(message string) {
	b.mutex.Lock()
	defer b.mutex.Unlock()
	b.current++
	b.message = message
	b.draw()
}

// Erase the line so normal output can continue
func (b *progress) done() {
	if b.stop == nil {
		return
	}
	close(b.stop)
	<-b.stopped
	fmt.Fprint(b.out.out, "\r\033[K")
}

// Keep the spinner moving while steps take long
func (b *progress) animate() {
	defer close(b.stopped)
	ticker := time.NewTicker(progressInterval)
	defer ticker.Stop()
	for {
		b.mutex.Lock()
		b.draw()
		b.frame++
		b.mutex.Unlock()
		select {
		case <-b.stop:
			return
		case <-ticker.C:
		}
	}
}

// Redraw in place, cut to the terminal width so it never wraps
func (b *progress) draw() {
	if b.stop == nil {
		return
	}
	frames := []rune(progressFrames)
	filled := progressCells * min(b.current, b.total) / max(b.total, 1)
	text := fmt.Sprintf("%c %s %s%s %d/%d", frames[b.frame%len(frames)], b.label,
		strings.Repeat("━", filled), strings.Repeat("─", progressCells-filled), b.current, b.total)
	if b.message != "" {
		text += " · " + b.message
	}
	if runes := []rune(text); len(runes) >= b.width {
		text = string(runes[:b.width-1])
	}
	if b.out.color {
		text = "\033[" + cyan + "m" + text + "\033[0m"
	}
	fmt.Fprint(b.out.out, "\r\033[K"+text)
}
