# Expert Call Analyzer - Hasamex AI Engineer Case Study

A Streamlit app that analyzes expert-call transcripts against an interview
guide: it answers each question per expert with verbatim, timestamped
evidence, synthesizes common themes and disagreements across experts, and
answers free-form questions across all transcripts.

## Running it locally

```bash
pip install -r requirements.txt
cp .env.example .env            # then fill in GEMINI_API_KEY
streamlit run app.py
```

The app reads `GEMINI_API_KEY` (and optionally `GEMINI_MODEL`) from a `.env`
file via `python-dotenv`, or from an environment variable set before launch -
there's no in-app key entry. The bundled sample data (interview guide + 3
transcripts) loads automatically from `data/`. To use different files, swap
the files in `data/` (or point `DEFAULT_GUIDE` / `DEFAULT_TRANSCRIPTS` in
`app.py` elsewhere), keeping the same format: header lines, then `MM:SS`
timestamp lines followed by `Speaker: text`.

## Architecture

```
app.py                  Streamlit UI (3 tabs) + session state
core/parser.py          Turns raw .txt transcripts into structured,
                         timestamped segments {timestamp, speaker, text}
core/llm.py              Thin Gemini wrapper, JSON-mode calls
core/analysis.py         Prompting + the anti-hallucination quote checker
data/                    The provided sample case pack
```

**Flow:**
1. `parser.py` splits each transcript into timestamped segments and pulls
   out the expert's name/role/market from the header.
2. For each interview-guide question, `analysis.answer_question_for_expert`
   sends *one expert's full transcript* to the model and asks for a short
   answer plus verbatim quotes + timestamps as evidence.
3. `analysis.verify_evidence` re-checks every returned quote against the
   actual transcript text at that timestamp before it's ever shown.
4. `analysis.synthesize_across_experts` takes the three (already-verified)
   per-expert answers for one question and asks the model to identify
   common themes and disagreements, each traceable back to an expert +
   timestamp.
5. `analysis.answer_freeform` handles open-ended questions across all
   transcripts at once, with the same citation + verification pattern.

## Model choice

Uses the Google Gemini API (`gemini-2.5-flash` by default, configurable
via `GEMINI_MODEL`) in **JSON mode**, so every response is parsed into a
fixed schema (`answer` / `evidence` / `not_addressed`, etc.) rather than
free text that has to be scraped with regex. `gemini-2.5-flash` is a good
default here: the transcripts are short, the task is extraction +
comparison rather than open-ended generation, and it's fast/cheap enough to
re-run per question during a demo. Swapping in a larger model is a one-line
env var change if answer quality needs to improve.

## How citations/timestamps are handled

The transcripts already have clean `MM:SS` markers, so timestamps are
treated as first-class data from parsing onward rather than something the
model has to infer. Every prompt requires the model to return a verbatim
quote **and** its timestamp for each claim, and the app never displays a
quote without first checking it against the actual segment text at that
timestamp (see "Reducing hallucinations" below). In the UI, verified quotes
get a ✔️ and unverified ones get a ⚠️ - flagged, not hidden, so a reviewer
can see exactly what wasn't confirmed.

## Reducing hallucinations

Three layers, from prompt to output:
1. **Grounded input, not open recall** - the model is only ever given the
   actual transcript text for the expert/question in front of it (or all
   three for free-form Q&A). It's never asked to answer from memory.
2. **Forced evidence schema** - the JSON schema *requires* a timestamp +
   verbatim quote per claim, and an explicit `not_addressed` flag when the
   transcript doesn't cover the question, so the model has an honest way
   to say "not mentioned" instead of inventing something.
3. **Programmatic verification** - after the model responds, the app does
   a plain string match (whitespace/case-normalized) between the returned
   quote and the real transcript text at that timestamp. This doesn't rely
   on the model policing itself - it's a deterministic check on the output.
   The cross-expert synthesis step is also only fed *verified* evidence, so
   an unverified quote can't propagate into the "common themes" summary.

What this doesn't catch: a verified quote used to support a subtly wrong
paraphrase in `answer`. Given more time, the next layer would be a second
LLM pass that checks the `answer` text is entailed by its own cited quotes.

## Scaling from 3 transcripts to 30+

At 3 transcripts, the whole transcript fits comfortably in context, so the
app just sends full text per expert (or all experts) and lets the model
read everything. That stops working cleanly at 30+ transcripts:

- **Retrieval instead of "send everything"**: chunk transcripts (e.g. by
  timestamped segment, as already structured) and index them in a vector
  store (Chroma/pgvector/Pinecone) with metadata (expert, market, date,
  timestamp). For a given question, retrieve top-k relevant chunks per
  expert instead of the full transcript.
- **Per-expert extraction stays parallelizable**: the "answer this question
  for this expert" step is already independent per expert/transcript, so it
  can be batched/parallelized (e.g. async calls or a queue) across 30+
  experts without changing the prompting logic.
- **Synthesis becomes map-reduce**: comparing 30 experts' answers to one
  question in a single prompt won't fit context reliably. Instead: cluster
  similar answers first (e.g. embedding similarity or a cheap
  classification pass), then synthesize within clusters, then a final pass
  reconciles cluster-level summaries into one set of themes/disagreements.
- **Free-form Q&A becomes standard RAG**: embed the question, retrieve
  relevant chunks across all 30+ transcripts, answer only from those chunks
  same verification step as today, just retrieval instead of "everything
  in context."
- **Caching**: persist per-expert per-question answers (they don't change
  once computed) so re-running synthesis or adding a 31st expert doesn't
  require re-analyzing the first 30 from scratch.

## Notes

- Not implemented (out of scope for the demo): auth, persistence across
  sessions, and audio/video transcript ingestion - the app assumes
  already-transcribed `.txt` files in the given format.
- `GEMINI_API_KEY` is read from `.env` / the environment only - there is no
  in-app key entry. If it's missing, the app shows a banner instead of
  failing silently on the first LLM call.
