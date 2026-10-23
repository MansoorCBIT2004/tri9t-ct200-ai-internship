# CardioTrack CT-200 Document & QA Engineering Pipeline

A robust backend system built with **FastAPI, SQLAlchemy, and SQLite** to parse, version, browse, and generate traceable QA test cases from technical medical device manuals (CardioTrack CT-200 v1 & v2).

## Features
- **Hierarchical PDF Parsing:** Extracts sections, subsections, headings, body text, and handles irregularities with robust node hashing.
- **Version Management:** Ingests multiple manual versions (`v1` and `v2`) concurrently without data loss and computes semantic diffs.
- **Version-Pinned Selections:** Allows users to group specific document nodes into immutable selections.
- **LLM Test Case Generation & Staleness Detection:** Automatically generates QA test cases from selections and performs real-time staleness checks if source text changes across document versions.

---

## Setup & Installation

1. Clone the repository and navigate to the project directory:
   ```bash
   git clone [https://github.com/](https://github.com/)<your-username>/tri9t-ct200-pipeline.git
   cd tri9t-ct200-pipeline