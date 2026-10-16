# CareSteps architecture submission

Use **[CareSteps_Architecture_Diagram.pptx](CareSteps_Architecture_Diagram.pptx)** for the
actual form's required **Architecture Diagram PPT** field. The latest redesigned deck
is selected under this canonical filename: 9 editable slides, 16:9, below 10 MB.
The [PDF companion](CareSteps_Architecture_Diagram.pdf) is provided for convenient reading;
it does not replace the PPT field.

The deck covers system architecture, trust boundaries, safety gates, tool confirmation,
partial failure, data provenance, prompts and design trade-offs. It describes 10
model-visible tools and 13 application tables. Some scoped tools write directly, the
fictional patient profile is shared, and software checks are not clinical validation.

| Material | Purpose |
|---|---|
| [System architecture](CareSteps_System_Architecture.png) | Single-slide 1920×1080 diagram |
| [Trust boundaries](CareSteps_Trust_Boundaries.png) | Single-slide 1920×1080 diagram |
| [Overview](CareSteps_Architecture_Overview.png) | Contact sheet of all nine slides |
| [Previews](previews/) | Individual 1080p slides |
| [Speaker notes](SPEAKER_NOTES.md) | Explanation of implementation and limitations |
| [Source fingerprints](source-verification.json) | Implementation files and actual counts checked |
| [Validation](VALIDATION.md) | Structural and rendered-text verification |
| [Build script](build_architecture.py) | Recreate the redesigned deck |
| [Verification script](verify_artifacts.py) | Check deck/PDF text, page count, previews and source hashes |

The handbook's Healthcare section asks for architecture, trust-boundary diagrams and
trade-offs; the actual form additionally makes the PPT upload mandatory.

```bash
python3 submission/architecture-diagram/build_architecture.py --test-count 170 --render
python3 submission/architecture-diagram/verify_artifacts.py
```

Use a test count from an actual run. Asset production requires python-pptx, Pillow,
LibreOffice, Poppler and pdfplumber; it is separate from application setup. Captured
visual assets are included, while the original full slide templates and previous deck
are retained in the local archive. The supplied templates' media are derived assets;
the owner should retain the corresponding original usage rights.

Health-content and third-party attribution are discussed in
[content provenance](../../docs/content-provenance.md).
