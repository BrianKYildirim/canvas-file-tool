# Canvas File Sweeper

A fast, multithreaded tool that scans Canvas **file IDs** in reverse order to discover files you have permission to access. It was inspired by the need to bulk‑recover lecture slides and assignments that are no longer linked from course pages but still reside on the LMS.

> **Ethical use notice**
> This project is provided for *legitimate archival and personal‑backup* purposes.
> Always respect institutional policies, copyright law, and privacy when using it.

---

## Features

| Capability                    | Description                                                                                                |
| ----------------------------- | ---------------------------------------------------------------------------------------------------------- |
| 🔍 **Reverse ID sweep**       | Starts from a known `/files/<id>` URL and probes lower IDs, which is where Canvas allocates newer uploads. |
| ⚡ **ThreadPoolExecutor**      | Up to 32 concurrent workers using persistent HTTP connections for high throughput.                         |
| 🗄️ **Connection reuse**      | One shared opener keeps sockets alive—no external dependencies required.                                   |
| 📄 **HTML *or* JSON parsing** | Works equally well with front‑end file pages or the `/api/v1/files/<id>` endpoint.                         |
| 📦 **Structured JSON output** | Saves hits to `output/YYYYMMDD‑HHMMSS‑canvas-files.json` for easy post‑processing.                         |
| 🛑 **Graceful early abort**   | Immediately stops every worker on a fatal HTTP status (≠ 404).                                             |

---

## Quick start

```bash
# 1. Clone & enter the repo
$ git clone https://github.com/<your‑user>/canvas-file-tool.git
$ cd canvas-file-tool

# 2. (Optional) create venv
$ python -m venv .venv && source .venv/bin/activate  # PowerShell: .venv\Scripts\Activate

# 3. No external requirements – stdlib only!

# 4. Export your Canvas session cookie (or pass via `-s` later)
$ export CANVAS_SESSION="<value of canvas_session cookie>"

# 5. Scan 5 000 IDs below a known file URL with 16 workers
$ python canvas_refactored.py \
       -u "https://canvas.example.edu/courses/123/files/456789012" \
       -n 5000 -w 16
```

### Determining your `canvas_session` cookie

1. Log into Canvas in a browser.
2. Open **Developer Tools → Application / Storage → Cookies**.
3. Copy the **`canvas_session`** value for your domain.
4. Export it (Linux/macOS) or set `$Env:CANVAS_SESSION` (PowerShell).

> *Why not an API token?*  The public file pages don’t require OAuth
> tokens—and API tokens are often scoped per‑user course access—so the
> session cookie is both simpler and more reliable for a quick sweep.

---

## Command‑line reference

```text
usage: canvas_refactored.py -u URL [-n INT] [-w 1‑32] [-s TOKEN]

required arguments:
  -u, --url            Starting `/files/<id>` link (must contain a numeric id)

optional arguments:
  -n, --num-files INT  Number of IDs to scan below *start* (default: 10000)
  -w, --workers 1‑32   Concurrent threads (default: 16, max: 32)
  -s, --canvas-session TOKEN
                        Session cookie (falls back to CANVAS_SESSION env‑var)
```

---

## Output format

Each discovered file is appended to the resulting JSON list:

```json
{
  "id": 456788765,
  "url": "https://canvas.example.edu/courses/123/files/456788765",
  "display_name": "Week‑05‑Lab.pdf",
  "created_at": "2024‑10‑01T18:27:14Z",    // may be empty for HTML scrape
  "download_url": "https://canvas.example.edu/files/456788765/download?download_frd=1"
}
```

Use tools like `jq`, Python, or a spreadsheet to sort, filter, or bulk‑download the listed `download_url`s.

---

## Performance tips

* **Worker count** – 16 is a good default; higher values yield diminishing
  returns or can hit rate limits (> 32 is blocked by the CLI).
* **`-n` breadth** – If you’re unsure how many hidden files exist, start
  small (`-n 1000`) then extend.
* **Network proximity** – Running the sweeper on a campus VPN often
  doubles request throughput versus a distant location.

---

## Limitations & roadmap

* The tool **does not traverse folders**; it strictly decrements numeric
  IDs. A future enhancement could fetch folder listings to seed starting
  IDs automatically.
  
---

## Contributing

1. Fork & clone the repo.
2. Create a feature branch off `main`.
3. Run `python -m unittest discover` (coming soon) to ensure nothing breaks.
4. Submit a pull request—describe what it changes and why.

---
