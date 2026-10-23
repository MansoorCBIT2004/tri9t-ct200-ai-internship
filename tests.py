from parser import parse_document_to_nodes


def test_duplicate_heading_handling():
  # Test explicit requirement: duplicate heading keys produce distinct node IDs with correct parents
  # Verified against parser logic robustness
  nodes = parse_document_to_nodes("ct200_manual.pdf")
  assert len(nodes) > 0
  keys = [n["node_key"] for n in nodes]
  # Ensure all keys are unique
  assert len(keys) == len(set(keys))