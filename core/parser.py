import re

TIMESTAMP_RE = re.compile(r"^(\d{1,2}:\d{2})$")


def parse_header(text: str) -> dict:
    """Extract Expert name / Role / Market from the lines before the first timestamp."""
    header = {"name": "Unknown Expert", "role": "", "market": ""}
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if TIMESTAMP_RE.match(line):
            break
        if line.lower().startswith("expert"):
            # "Expert 1 – Dr. Jean Martin" -> "Dr. Jean Martin"
            if "–" in line:
                header["name"] = line.split("–", 1)[1].strip()
            elif "-" in line:
                header["name"] = line.split("-", 1)[1].strip()
        elif line.lower().startswith("role:"):
            header["role"] = line.split(":", 1)[1].strip()
        elif line.lower().startswith("market:"):
            header["market"] = line.split(":", 1)[1].strip()
    return header


def parse_segments(text: str) -> list:
    """Parse the timestamp / speaker / text blocks into a list of segments."""
    lines = [l.strip() for l in text.splitlines()]
    segments = []
    current_ts = None
    speaker = None
    buf = []

    def flush():
        if current_ts and speaker and buf:
            segments.append({
                "timestamp": current_ts,
                "speaker": speaker,
                "text": " ".join(buf).strip(),
            })

    for line in lines:
        if not line:
            continue
        m = TIMESTAMP_RE.match(line)
        if m:
            flush()
            current_ts = m.group(1)
            speaker, buf = None, []
            continue
        if current_ts is None:
            continue  # header lines, skip
        if speaker is None and ":" in line:
            spk, _, rest = line.partition(":")
            speaker = spk.strip()
            buf = [rest.strip()]
        else:
            buf.append(line)
    flush()
    return segments


def parse_transcript(text: str) -> dict:
    header = parse_header(text)
    segments = parse_segments(text)
    header["segments"] = segments
    return header


def format_context(transcripts: list, exclude_interviewer: bool = False) -> str:
    """
    Flatten all parsed transcripts into one tagged text block that can be
    dropped straight into an LLM prompt, e.g.:

        [Dr. Jean Martin | France | 00:18 | Dr. Martin]: Adoption is growing...

    This is small enough (3 transcripts) to pass in full rather than
    retrieving chunks - see README for how this changes at scale.
    """
    lines = []
    for t in transcripts:
        for seg in t["segments"]:
            if exclude_interviewer and seg["speaker"].lower().startswith("interview"):
                continue
            lines.append(
                f'[{t["name"]} | {t["market"]} | {seg["timestamp"]} | {seg["speaker"]}]: {seg["text"]}'
            )
    return "\n".join(lines)


def parse_interview_guide(text: str) -> list:
    """Extract numbered questions from the interview guide file."""
    questions = []
    for line in text.splitlines():
        line = line.strip()
        m = re.match(r"^\d+\.\s*(.+)$", line)
        if m:
            questions.append(m.group(1).strip())
    return questions
