package main

import (
	"bufio"
	"bytes"
	"encoding/binary"
	"errors"
	"io"
	"os"
	"slices"
	"strings"
	"time"
	"unicode/utf16"
)

const (
	id3HeaderSize = 10
	// Spare room so later tag edits happen in place
	id3Padding  = 256
	maxTagBytes = 32 << 20
	copyBuffer  = 256 << 10

	// ID3v2 header flags
	id3Unsynchronised = 0x80
	id3Extended       = 0x40
	id3Footer         = 0x10
)

// Wanted tag values; empty ones are left alone
type Tags struct {
	Album string
	Title string    // only fills a missing title
	Date  time.Time // release moment
	// Date is the feed's release date and replaces any other; otherwise it only fills a missing date
	Published bool
}

// Raw ID3v2 frame, kept verbatim unless replaced
type id3Frame struct {
	id    string
	flags [2]byte
	body  []byte
}

// ID3v2.3 or ID3v2.4 tag
type id3Tag struct {
	version byte
	flags   byte
	frames  []id3Frame
}

// Copy audio while writing the wanted tags into its leading ID3 tag
func copyTagged(destination io.Writer, source io.Reader, tags Tags) (written int64, tagged bool, err error) {
	reader := bufio.NewReaderSize(source, copyBuffer)
	header, err := reader.Peek(id3HeaderSize)
	if len(header) == 0 {
		if err == nil || err == io.EOF {
			err = errors.New("empty response")
		}
		return 0, false, err
	}
	length := id3Length(header)
	if tags == (Tags{}) || length > maxTagBytes {
		written, err = io.Copy(destination, reader)
		return written, false, err
	}

	leading := make([]byte, length)
	if _, err := io.ReadFull(reader, leading); err != nil {
		return 0, false, err
	}
	tag, supported := parseID3(leading)
	if supported {
		tag.apply(tags)
		leading = tag.serialize(id3Padding)
	}
	if _, err := destination.Write(leading); err != nil {
		return 0, false, err
	}
	written, err = io.Copy(destination, reader)
	return written + int64(len(leading)), supported, err
}

// Bring an existing file's tags up to date; true when it was changed
func retagFile(path string, tags Tags) (bool, error) {
	if tags == (Tags{}) {
		return false, nil
	}
	file, err := os.OpenFile(path, os.O_RDWR, 0)
	if err != nil {
		return false, err
	}
	defer file.Close()

	header := make([]byte, id3HeaderSize)
	if _, err := io.ReadFull(file, header); err != nil {
		return false, nil
	}
	length := id3Length(header)
	if length > maxTagBytes {
		return false, nil
	}
	leading := make([]byte, length)
	if _, err := file.ReadAt(leading, 0); err != nil {
		return false, err
	}
	tag, supported := parseID3(leading)
	if !supported || !tag.apply(tags) {
		return false, nil
	}

	// Reuse the old tag's space when the new one fits
	if spare := length - len(tag.serialize(0)); spare >= 0 {
		_, err := file.WriteAt(tag.serialize(spare), 0)
		return err == nil, err
	}

	// A grown tag shifts the audio, so rewrite and swap
	temporary := path + partSuffix
	target, err := os.Create(temporary)
	if err != nil {
		return false, err
	}
	_, err = target.Write(tag.serialize(id3Padding))
	if err == nil {
		_, err = io.Copy(target, io.NewSectionReader(file, int64(length), 1<<62))
	}
	if closeErr := target.Close(); err == nil {
		err = closeErr
	}
	if err == nil {
		err = os.Rename(temporary, path)
	}
	if err != nil {
		os.Remove(temporary)
		return false, err
	}
	return true, nil
}

// Byte length of the tag a file starts with; zero without a tag
func id3Length(header []byte) int {
	if len(header) < id3HeaderSize || string(header[:3]) != "ID3" {
		return 0
	}
	length := id3HeaderSize + synchsafe(header[6:10])
	if header[5]&id3Footer != 0 {
		length += id3HeaderSize
	}
	return length
}

// Split a complete tag into frames; false for versions that cannot be rewritten
func parseID3(data []byte) (id3Tag, bool) {
	if len(data) == 0 {
		return id3Tag{version: 4}, true
	}
	tag := id3Tag{version: data[3]}
	end := id3HeaderSize + synchsafe(data[6:10])
	if tag.version != 3 && tag.version != 4 || end > len(data) {
		return tag, false
	}
	flags, body := data[5], data[id3HeaderSize:end]
	if flags&id3Unsynchronised != 0 {
		if tag.version == 4 {
			// Version 4 frames carry their own unsynchronisation
			tag.flags = id3Unsynchronised
		} else {
			body = bytes.ReplaceAll(body, []byte{0xFF, 0x00}, []byte{0xFF})
		}
	}
	if flags&id3Extended != 0 {
		if len(body) < 4 {
			return tag, false
		}
		skip := synchsafe(body[:4])
		if tag.version == 3 {
			skip = int(binary.BigEndian.Uint32(body[:4])) + 4
		}
		if skip > len(body) {
			return tag, false
		}
		body = body[skip:]
	}

	for len(body) >= id3HeaderSize && isFrameID(body[:4]) {
		size := int(binary.BigEndian.Uint32(body[4:8]))
		if tag.version == 4 {
			// Some writers store plain sizes where synchsafe ones belong
			if safe := synchsafe(body[4:8]); frameEnds(body, safe) || !frameEnds(body, size) {
				size = safe
			}
		}
		if size > len(body)-id3HeaderSize {
			break
		}
		tag.frames = append(tag.frames, id3Frame{string(body[:4]), [2]byte{body[8], body[9]}, body[id3HeaderSize : id3HeaderSize+size]})
		body = body[id3HeaderSize+size:]
	}
	return tag, true
}

// Whether a frame of this size is followed by padding, a frame, or the end
func frameEnds(body []byte, size int) bool {
	end := id3HeaderSize + size
	if end >= len(body) {
		return end == len(body)
	}
	return body[end] == 0 || end+4 <= len(body) && isFrameID(body[end:end+4])
}

func isFrameID(id []byte) bool {
	for _, char := range id {
		if (char < 'A' || char > 'Z') && (char < '0' || char > '9') {
			return false
		}
	}
	return true
}

func synchsafe(data []byte) int {
	return int(data[0]&0x7F)<<21 | int(data[1]&0x7F)<<14 | int(data[2]&0x7F)<<7 | int(data[3]&0x7F)
}

// Set the wanted values; true when anything changed
func (t *id3Tag) apply(tags Tags) bool {
	changed := false
	set := func(id, value string) {
		if t.text(id) != value {
			t.setText(id, value)
			changed = true
		}
	}
	if tags.Album != "" {
		set("TALB", tags.Album)
	}
	if tags.Title != "" && t.text("TIT2") == "" {
		set("TIT2", tags.Title)
	}
	if tags.Date.IsZero() {
		return changed
	}
	if t.version == 4 {
		// Exact moment only from the feed; the download day is just a day
		value := tags.Date.Format("2006-01-02")
		if tags.Published {
			value = tags.Date.Format("2006-01-02T15:04:05")
		}
		if tags.Published || t.text("TDRC") == "" {
			set("TDRC", value)
		}
	} else if tags.Published || t.text("TYER") == "" {
		// Version 3 splits the date into year, DDMM, and HHMM
		if slices.ContainsFunc(t.frames, func(frame id3Frame) bool { return frame.id == "TDRC" }) {
			t.remove("TDRC")
			changed = true
		}
		set("TYER", tags.Date.Format("2006"))
		set("TDAT", tags.Date.Format("0201"))
		if tags.Published {
			set("TIME", tags.Date.Format("1504"))
		}
	}
	return changed
}

// First value of a text frame
func (t *id3Tag) text(id string) string {
	for _, frame := range t.frames {
		if frame.id == id && len(frame.body) > 0 {
			return decodeText(frame.body[0], frame.body[1:])
		}
	}
	return ""
}

// Replace a text frame, encoded as the tag version expects
func (t *id3Tag) setText(id, value string) {
	t.remove(id)
	body := append([]byte{3}, value...)
	if t.version == 3 {
		// Version 3 knows no UTF-8, so UTF-16 with byte order mark
		body = []byte{1, 0xFF, 0xFE}
		for _, unit := range utf16.Encode([]rune(value)) {
			body = append(body, byte(unit), byte(unit>>8))
		}
	}
	t.frames = append(t.frames, id3Frame{id: id, body: body})
}

func (t *id3Tag) remove(id string) {
	t.frames = slices.DeleteFunc(t.frames, func(frame id3Frame) bool { return frame.id == id })
}

// Tag bytes with the given amount of trailing padding
func (t *id3Tag) serialize(padding int) []byte {
	data := []byte{'I', 'D', '3', t.version, 0, t.flags, 0, 0, 0, 0}
	for _, frame := range t.frames {
		data = append(data, frame.id...)
		if t.version == 4 {
			data = appendSynchsafe(data, len(frame.body))
		} else {
			data = binary.BigEndian.AppendUint32(data, uint32(len(frame.body)))
		}
		data = append(data, frame.flags[:]...)
		data = append(data, frame.body...)
	}
	data = append(data, make([]byte, padding)...)
	copy(data[6:10], appendSynchsafe(nil, len(data)-id3HeaderSize))
	return data
}

func appendSynchsafe(data []byte, value int) []byte {
	return append(data, byte(value>>21)&0x7F, byte(value>>14)&0x7F, byte(value>>7)&0x7F, byte(value)&0x7F)
}

// Text frame content by its ID3 encoding byte
func decodeText(encoding byte, data []byte) string {
	text := string(data)
	switch encoding {
	case 0:
		// Latin-1 bytes map directly to code points
		runes := make([]rune, len(data))
		for index, char := range data {
			runes[index] = rune(char)
		}
		text = string(runes)
	case 1, 2:
		order := binary.ByteOrder(binary.BigEndian)
		if encoding == 1 {
			order = binary.LittleEndian
			if len(data) >= 2 && data[0] == 0xFE && data[1] == 0xFF {
				order = binary.BigEndian
			}
			if len(data) >= 2 && (data[0] == 0xFF && data[1] == 0xFE || data[0] == 0xFE && data[1] == 0xFF) {
				data = data[2:]
			}
		}
		units := make([]uint16, len(data)/2)
		for index := range units {
			units[index] = order.Uint16(data[2*index:])
		}
		text = string(utf16.Decode(units))
	}
	text, _, _ = strings.Cut(text, "\x00")
	return text
}
