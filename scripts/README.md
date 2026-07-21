# Scripts

One-off maintenance and utility scripts. **These are not part of the product**;
they document ad-hoc fixes or conversions performed during development.

## `maintenance/`

Helper scripts to operate on the project from the command line:

| Script | Purpose |
|--------|---------|
| `add_charts.py` | Insert per-agent charts into legacy report exports |
| `fix_barwidth.py` | Patch reportlab bar-chart bar widths (older preset) |
| `fix_import.py` | One-off package import normalizer (legacy modules) |
| `fix_polisher.py` | Patch LLM prompt-polisher regressions (legacy) |
| `get_report.py` | CLI helper to download a single report by id |
| `list_reports.py` | CLI helper to list stored reports |
| `pdf_to_png.py` | Render a PDF file into per-page PNGs (uses Poppler) |
| `smoke_pdf.py` | Quick smoke test that PDF export still works |

Run any of them directly, e.g.:

```bash
python scripts/maintenance/pdf_to_png.py path/to/report.pdf tmp/preview/
```

Future ad-hoc tasks should land here so the project root stays clean.