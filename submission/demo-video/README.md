# CareSteps demo video

Selected artifact: **[caresteps-demo-gemini.mp4](caresteps-demo-gemini.mp4)**,
**441.934 seconds (7:22)**, 1920×1080, 30 fps, H.264/AAC, 24,491,605 bytes.
It contains English synthetic narration and burned-in English subtitles, with a
[separate SRT](caresteps-demo-gemini.en.srt), [chapter list](caresteps-demo-gemini.chapters.txt),
[narration](NARRATION.md) and [verification record](caresteps-demo-gemini.verification.json).

The supplied actual submission form requires a **Demo Video Link**, with a 5–8 minute
video covering overview, core Agent use and build reflection. The hosted demo is available on
[YouTube](https://www.youtube.com/watch?v=gTVs-9tpJL8). The owner supplied this URL on October 16, 2026;
YouTube oEmbed metadata was retrieved without login (title: "Caresteps Demo"). A local filesystem path
or source-repository link is not the requested hosted video experience.

## Recorded content

The browser recording demonstrates reading entry/confirmation, trends and missing days,
optional barrier classification, matching support, confirmed medicines and sources,
chat, a medication-boundary refusal, the emergency panel, `/trace`, limited mode and
patient-controlled appointment printing. All patient records are fictional.

It includes an actually recorded live model turn and tool retrieval, plus a separate
instance deliberately running without a model. The configured gateway model label is
not independently verified vendor identity. This release audit does not make external
model calls.

The WorkBuddy reflection uses the existing 22:52:18 conversation screenshot and describes
the statistics API and deployment-guide tasks. It does not claim WorkBuddy implemented
the original application. See [development workflow](../../docs/development.md).

The later voiceover used the owner-selected gateway model identifier
`gemini-3.8-flash-tts` and Kore voice. The verification record distinguishes the requested
identifier from independently verified provider identity. No human voice is claimed.

## Production sources

`record_demo.js`, `speak_narration.ps1` and `finish_demo.py` preserve the original browser
capture/postproduction workflow. `gemini-voiceover/` retains the replacement scripts,
segment text and timing inputs. These optional tools need Playwright/Chromium, FFmpeg,
Python media packages and the appropriate owner-provided audio API configuration
(`TTS_API_HOST` selects the authorized speech gateway hostname).
They are not runtime dependencies of the application.

Raw WebM/WAV recordings, generated audio, retakes, handoff archives and the superseded
voiceover video remain in the local release archive. To regenerate with those original
media inputs, restore them to the expected `source/` and `gemini-voiceover/generated/`
locations. The published scripts and text alone do not include the raw audio/video.

The existing verification record reports a successful full decode, subtitle checks and
SHA-256. This audit also verifies the final file's encoding, duration and hash.

The recording preserves the pre-deployment 170-test snapshot. The deployed release adds
one concurrency regression for health checks during a waiting model turn; current
software validation has 171 tests. See [evaluation](../../docs/evaluation.md).
