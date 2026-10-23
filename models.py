import hashlib
import json
from datetime import datetime
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from database import Base


class DocumentVersion(Base):
  __tablename__ = "document_versions"

  id = Column(Integer, primary_key=True, index=True)
  version_name = Column(
      String, unique=True, index=True, nullable=False
  )  # e.g., "v1", "v2"
  created_at = Column(DateTime, default=datetime.utcnow)

  nodes = relationship(
      "NodeModel", back_populates="document_version", cascade="all, delete-orphan"
  )


class NodeModel(Base):
  __tablename__ = "nodes"

  id = Column(Integer, primary_key=True, index=True)
  node_key = Column(
      String, index=True, nullable=False
  )  # Logical identifier across versions (e.g., "2.1.1")
  document_version_id = Column(
      Integer, ForeignKey("document_versions.id"), nullable=False
  )
  heading = Column(String, nullable=False)
  level = Column(Integer, nullable=False)
  body_text = Column(Text, default="")
  parent_node_key = Column(
      String, nullable=True
  )  # Parent logical node key for hierarchy
  content_hash = Column(String, nullable=False)

  document_version = relationship("DocumentVersion", back_populates="nodes")

  def compute_hash(self):
    content = f"{self.heading}:{self.body_text}"
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


class SelectionModel(Base):
  __tablename__ = "selections"

  id = Column(Integer, primary_key=True, index=True)
  selection_name = Column(String, nullable=False)
  document_version_id = Column(
      Integer, ForeignKey("document_versions.id"), nullable=False
  )
  node_keys_json = Column(
      Text, nullable=False
  )  # JSON list of node keys included in selection
  created_at = Column(DateTime, default=datetime.utcnow)

  generations = relationship(
      "GenerationModel",
      back_populates="selection",
      cascade="all, delete-orphan",
  )


class GenerationModel(Base):
  __tablename__ = "generations"

  id = Column(Integer, primary_key=True, index=True)
  selection_id = Column(Integer, ForeignKey("selections.id"), nullable=False)
  test_cases_json = Column(
      Text, nullable=False
  )  # Stored LLM-generated test cases
  source_hashes_json = Column(
      Text, nullable=False
  )  # Map of node_key -> content_hash at generation time
  created_at = Column(DateTime, default=datetime.utcnow)

  selection = relationship("SelectionModel", back_populates="generations")