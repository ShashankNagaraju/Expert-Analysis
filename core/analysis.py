import re
from .llm import call_json

# Prompts
PER_EXPERT_SYSTEM = """You are a careful market-research analyst assistant.
You will be given ONE expert's transcript (tagged with timestamps) and ONE
interview-guide question.

Rules (must follow exactly):
- Answer using ONLY information present in the transcript excerpts given to you.
- Never invent, infer beyond, or embellish what the expert said.
- Every claim in your answer must be backed by at least one piece of evidence:
  an exact, verbatim quote copied character-for-character from the transcript,
  plus its timestamp.
- If the transcript does not address the question at all, set "not_addressed"
  to true and leave "answer" as an empty string and "evidence" as an empty list.
- Do not paraphrase inside the quote fields - copy the exact wording.

Respond ONLY with a JSON object of this exact shape:
{
  "answer": "<2-4 sentence synthesized answer in your own words>",
  "not_addressed": false,
  "evidence": [
    {"timestamp": "MM:SS", "quote": "<exact verbatim quote from the transcript>"}
  ]
}
"""

SYNTHESIS_SYSTEM = """You are a market-research analyst comparing what three
experts said about the same interview question. You will be given each
expert's already-verified answer (with quotes and timestamps).

Rules:
- Base your synthesis ONLY on the provided per-expert answers/evidence.
- Do not introduce new facts not present in the inputs.
- Identify genuine common themes (points at least two experts agree on).
- Identify genuine disagreements or differences in emphasis, if any exist.
- If experts simply didn't address something, don't count that as disagreement.
- Reference which expert(s) and which timestamp support each point.

Respond ONLY with a JSON object of this exact shape:
{
  "common_themes": [
    {"theme": "<short theme label>", "summary": "<1-2 sentences>",
     "support": [{"expert": "<name>", "timestamp": "MM:SS"}]}
  ],
  "disagreements": [
    {"topic": "<short topic label>", "summary": "<1-2 sentences on how views differ>",
     "positions": [{"expert": "<name>", "timestamp": "MM:SS", "position": "<short phrase>"}]}
  ]
}
"""

FREEFORM_SYSTEM = """You are a research assistant answering questions about
three expert-call transcripts (robotic surgery market, France/Germany/UK).
You are given the full tagged transcript text: each line is
"[Expert Name | Market | Timestamp | Speaker]: text".

Rules:
- Answer ONLY using the transcript content provided.
- Every claim must cite the supporting expert, market and timestamp, with an
  exact verbatim quote.
- If the transcripts do not contain the answer, say so plainly in "answer"
  and return an empty "citations" list - do not guess or use outside knowledge.

Respond ONLY with a JSON object of this exact shape:
{
  "answer": "<direct answer in your own words, 1-5 sentences>",
  "not_addressed": false,
  "citations": [
    {"expert": "<name>", "market": "<market>", "timestamp": "MM:SS", "quote": "<exact verbatim quote>"}
  ]
}
"""

def _normalize(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip().lower())


def verify_evidence(evidence: list, segments: list) -> list:
    """Check each {timestamp, quote} against the actual transcript segments.
    Adds a "verified" boolean to each evidence item. This is the main
    anti-hallucination guardrail: it never trusts the model's citation
    at face value."""
    by_ts = {}
    for seg in segments:
        by_ts.setdefault(seg["timestamp"], []).append(seg["text"])

    checked = []
    for item in evidence:
        ts = item.get("timestamp", "")
        quote = item.get("quote", "")
        texts = by_ts.get(ts, [])
        verified = any(_normalize(quote) in _normalize(t) for t in texts)
        checked.append({**item, "verified": verified})
    return checked


def answer_question_for_expert(question: str, transcript: dict, api_key: str = None) -> dict:
    """Answer one interview-guide question for one expert's transcript."""
    context_lines = [
        f'[{seg["timestamp"]} | {seg["speaker"]}]: {seg["text"]}'
        for seg in transcript["segments"]
    ]
    context = "\n".join(context_lines)

    user_prompt = (
        f"Expert: {transcript['name']} ({transcript.get('role','')}, {transcript.get('market','')})\n\n"
        f"Interview question: {question}\n\n"
        f"Transcript:\n{context}"
    )
    result = call_json(PER_EXPERT_SYSTEM, user_prompt, api_key=api_key)
    result["evidence"] = verify_evidence(result.get("evidence", []), transcript["segments"])
    return result


def synthesize_across_experts(question: str, per_expert_results: dict, api_key: str = None) -> dict:
    """per_expert_results: {expert_name: answer_dict} for this question."""
    payload_lines = []
    for name, res in per_expert_results.items():
        payload_lines.append(f"Expert: {name}")
        if res.get("not_addressed"):
            payload_lines.append("  (Not addressed by this expert)")
        else:
            payload_lines.append(f"  Answer: {res.get('answer','')}")
            for ev in res.get("evidence", []):
                flag = "" if ev.get("verified") else " [UNVERIFIED - excluded from synthesis input]"
                if ev.get("verified"):
                    payload_lines.append(f"  Evidence [{ev['timestamp']}]: \"{ev['quote']}\"{flag}")
        payload_lines.append("")

    user_prompt = f"Interview question: {question}\n\n" + "\n".join(payload_lines)
    return call_json(SYNTHESIS_SYSTEM, user_prompt, api_key=api_key)


def answer_freeform(question: str, transcripts: list, api_key: str = None) -> dict:
    """Answer an arbitrary user question against all transcripts combined."""
    from .parser import format_context
    context = format_context(transcripts)
    user_prompt = f"Question: {question}\n\nTranscripts:\n{context}"
    result = call_json(FREEFORM_SYSTEM, user_prompt, api_key=api_key)

    # verify citations against the right expert's segments
    seg_lookup = {t["name"]: t["segments"] for t in transcripts}
    checked = []
    for c in result.get("citations", []):
        segs = seg_lookup.get(c.get("expert", ""), [])
        verified = verify_evidence([{"timestamp": c.get("timestamp", ""), "quote": c.get("quote", "")}], segs)
        checked.append({**c, "verified": verified[0]["verified"] if verified else False})
    result["citations"] = checked
    return result
