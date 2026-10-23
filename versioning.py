import json


def compare_versions(db, v1_name: str, v2_name: str):
  from models import DocumentVersion, NodeModel

  v1 = (
      db.query(DocumentVersion)
      .filter(DocumentVersion.version_name == v1_name)
      .first()
  )
  v2 = (
      db.query(DocumentVersion)
      .filter(DocumentVersion.version_name == v2_name)
      .first()
  )

  if not v1 or not v2:
    return {"error": "One or both versions not found."}

  v1_nodes = {n.node_key: n for n in v1.nodes}
  v2_nodes = {n.node_key: n for n in v2.nodes}

  diff_summary = {
      "added_nodes": [],
      "removed_nodes": [],
      "modified_nodes": [],
      "unchanged_nodes": [],
  }

  all_keys = set(v1_nodes.keys()).union(set(v2_nodes.keys()))

  for key in sorted(all_keys):
    if key not in v1_nodes:
      diff_summary["added_nodes"].append(
          {"node_key": key, "heading": v2_nodes[key].heading}
      )
    elif key not in v2_nodes:
      diff_summary["removed_nodes"].append(
          {"node_key": key, "heading": v1_nodes[key].heading}
      )
    elif v1_nodes[key].content_hash != v2_nodes[key].content_hash:
      diff_summary["modified_nodes"].append({
          "node_key": key,
          "heading": v2_nodes[key].heading,
          "v1_hash": v1_nodes[key].content_hash,
          "v2_hash": v2_nodes[key].content_hash,
      })
    else:
      diff_summary["unchanged_nodes"].append(key)

  return diff_summary


def check_staleness(db, generation_id: int):
  from models import GenerationModel, NodeModel, SelectionModel

  gen = db.query(GenerationModel).get(generation_id)
  if not gen:
    return {"error": "Generation not found."}

  selection = db.query(SelectionModel).get(gen.selection_id)
  source_hashes = json.loads(gen.source_hashes_json)  # {node_key: hash}
  current_version_id = selection.document_version_id

  staleness_report = {}
  is_stale = False

  for node_key, original_hash in source_hashes.items():
    current_node = (
        db.query(NodeModel)
        .filter(
            NodeModel.document_version_id == current_version_id,
            NodeModel.node_key == node_key,
        )
        .first()
    )

    if not current_node:
      staleness_report[node_key] = {
          "status": "REMOVED_OR_MISSING",
          "stale": True,
      }
      is_stale = True
    elif current_node.content_hash != original_hash:
      staleness_report[node_key] = {"status": "MODIFIED", "stale": True}
      is_stale = True
    else:
      staleness_report[node_key] = {"status": "UNCHANGED", "stale": False}

  return {"overall_stale": is_stale, "node_details": staleness_report}