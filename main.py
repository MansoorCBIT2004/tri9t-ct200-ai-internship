import json
import os
from fastapi import Depends, FastAPI, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
import openai  # or any LLM client (Groq/Gemini/etc.)

from database import Base, engine, get_db
from models import (
    DocumentVersion,
    GenerationModel,
    NodeModel,
    SelectionModel,
)
from parser import parse_document_to_nodes
from versioning import check_staleness, compare_versions

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="CardioTrack CT-200 Document & QA API",
    version="1.0.0",
)


# --- Pydantic Schemas ---
class IngestRequest(BaseModel):
  version_name: str
  pdf_path: str


from pydantic import BaseModel

class SelectionCreate(BaseModel):
    node_ids: list[int]
    version_id: int

    class Config:
        arbitrary_types_allowed = True


class SelectionRequest(BaseModel):
  selection_name: str
  document_version_id: int
  node_keys: list[str]


# --- Ingestion Endpoint ---
@app.post("/api/ingest", status_code=status.HTTP_201_CREATED)
def ingest_document(payload: IngestRequest, db: Session = Depends(get_db)):
  if not os.path.exists(payload.pdf_path):
    raise HTTPException(
        status_code=404, detail=f"PDF path {payload.pdf_path} not found."
    )

  existing_version = (
      db.query(DocumentVersion)
      .filter(DocumentVersion.version_name == payload.version_name)
      .first()
  )
  if existing_version:
    raise HTTPException(
        status_code=400,
        detail=f"Version {payload.version_name} already ingested.",
    )

  doc_version = DocumentVersion(version_name=payload.version_name)
  db.add(doc_version)
  db.commit()
  db.refresh(doc_version)

  parsed_nodes = parse_document_to_nodes(payload.pdf_path)
  for node_data in parsed_nodes:
    node = NodeModel(
        document_version_id=doc_version.id,
        node_key=node_data["node_key"],
        heading=node_data["heading"],
        level=node_data["level"],
        body_text=node_data["body_text"],
        parent_node_key=node_data["parent_node_key"],
        content_hash=node_data["content_hash"],
    )
    db.add(node)
  db.commit()

  return {
      "message": (
          f"Successfully ingested {len(parsed_nodes)} nodes for version"
          f" {payload.version_name}"
      )
  }


# --- Browse APIs ---
@app.get("/api/sections")
def list_sections(version_name: str = "v1", db: Session = Depends(get_db)):
  version = (
      db.query(DocumentVersion)
      .filter(DocumentVersion.version_name == version_name)
      .first()
  )
  if not version:
    raise HTTPException(status_code=404, detail="Document version not found.")

  top_nodes = (
      db.query(NodeModel)
      .filter(
          NodeModel.document_version_id == version.id, NodeModel.level == 1
      )
      .all()
  )
  return [
      {
          "node_key": n.node_key,
          "heading": n.heading,
          "content_hash": n.content_hash,
      }
      for n in top_nodes
  ]

@app.get("/api/nodes/{node_id}")
def get_node(node_id: int, db: Session = Depends(get_db)):
  node = db.query(NodeModel).get(node_id)
  if not node:
    raise HTTPException(status_code=404, detail="Node not found.")

  children = (
      db.query(NodeModel)
      .filter(
          NodeModel.document_version_id == node.document_version_id,
          NodeModel.parent_node_key == node.node_key,
      )
      .all()
  )

  return {
      "node_key": node.node_key,
      "heading": node.heading,
      "level": node.level,
      "body_text": node.body_text,
      "content_hash": node.content_hash,
      "children": [{"node_key": c.node_key, "heading": c.heading} for c in children],
  }


@app.get("/api/search")
def search_nodes(query: str, version_name: str = "v1", db: Session = Depends(get_db)):
  version = (
      db.query(DocumentVersion)
      .filter(DocumentVersion.version_name == version_name)
      .first()
  )
  if not version:
    raise HTTPException(status_code=404, detail="Version not found.")

  results = (
      db.query(NodeModel)
      .filter(
          NodeModel.document_version_id == version.id,
          (
              NodeModel.heading.ilike(f"%{query}%")
              | NodeModel.body_text.ilike(f"%{query}%")
          ),
      )
      .all()
  )

  return [
      {"node_key": r.node_key, "heading": r.heading} for r in results
  ]


@app.get("/api/versions/diff")
def get_version_diff(v1: str = "v1", v2: str = "v2", db: Session = Depends(get_db)):
  return compare_versions(db, v1, v2)


# --- Selection API ---
@app.post("/api/selections", status_code=status.HTTP_201_CREATED)
def create_selection(payload: SelectionRequest, db: Session = Depends(get_db)):
  selection = SelectionModel(
      selection_name=payload.selection_name,
      document_version_id=payload.document_version_id,
      node_keys_json=json.dumps(payload.node_keys),
  )
  db.add(selection)
  db.commit()
  db.refresh(selection)
  return {"selection_id": selection.id, "message": "Selection pinned successfully."}


# --- LLM QA Generation API ---
class GenerationRequest(BaseModel):
  selection_id: int


@app.post("/api/generate-qa", status_code=status.HTTP_201_CREATED)
def generate_qa(payload: GenerationRequest, db: Session = Depends(get_db)):
  selection = db.query(SelectionModel).get(payload.selection_id)
  if not selection:
    raise HTTPException(status_code=404, detail="Selection not found.")

  node_keys = json.loads(selection.node_keys_json)
  nodes = (
      db.query(NodeModel)
      .filter(
          NodeModel.document_version_id == selection.document_version_id,
          NodeModel.node_key.in_(node_keys),
      )
      .all()
  )

  combined_text = "\n\n".join(
      [f"Section {n.node_key}: {n.heading}\n{n.body_text}" for n in nodes]
  )
  source_hashes = {n.node_key: n.content_hash for n in nodes}

  # Simulated LLM Prompt & Structured Response with fallback validation
  # In production, integrate Groq/Gemini/OpenAI client with structured JSON output schema.
  mock_generated_test_cases = [
      {
          "test_case_id": "TC-001",
          "title": "Verify Overpressure Venting Time",
          "steps": (
              "Simulate cuff pressure exceeding 299 mmHg or 300 mmHg for 3"
              " seconds."
          ),
          "expected_result": (
              "Emergency deflation valve triggers and vents cuff within"
              " specified time limit."
          ),
      },
      {
          "test_case_id": "TC-002",
          "title": "Verify Error E3 Auto-Deflation",
          "steps": "Trigger overpressure condition E3.",
          "expected_result": "Auto-deflates and displays E3 correctly.",
      },
  ]

  generation = GenerationModel(
      selection_id=selection.id,
      test_cases_json=json.dumps(mock_generated_test_cases),
      source_hashes_json=json.dumps(source_hashes),
  )
  db.add(generation)
  db.commit()
  db.refresh(generation)

  return {
      "generation_id": generation.id,
      "test_cases": mock_generated_test_cases,
  }


# --- Retrieval & Staleness API ---
@app.get("/api/generations/{generation_id}")
def get_generation_with_staleness(generation_id: int, db: Session = Depends(get_db)):
  gen = db.query(GenerationModel).get(generation_id)
  if not gen:
    raise HTTPException(status_code=404, detail="Generation not found.")

  staleness_status = check_staleness(db, generation_id)

  return {
      "generation_id": gen.id,
      "selection_id": gen.selection_id,
      "test_cases": json.loads(gen.test_cases_json),
      "staleness_report": staleness_status,
      "created_at": gen.created_at,
  }