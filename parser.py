import hashlib
import re
import pypdf


def extract_text_from_pdf(pdf_path: str) -> str:
  reader = pypdf.PdfReader(pdf_path)
  full_text = ""
  for page in reader.pages:
    text = page.extract_text()
    if text:
      full_text += text + "\n"
  return full_text


def parse_document_to_nodes(pdf_path: str) -> list:
  """Parses the CT-200 PDF into a structured hierarchy of nodes,

  handling headings, subheadings, section numbers, and body text.
  """
  raw_text = extract_text_from_pdf(pdf_path)
  lines = raw_text.split("\n")

  nodes = []
  current_heading = "Introduction"
  current_key = "1"
  current_level = 1
  current_body = []
  seen_keys = {}

  # Regex to detect numbered headings like "1.", "2.1", "2.1.1.1", "4.2", etc.
  heading_pattern = re.compile(r"^(\d+(?:\.\d+)*)\s+(.*)$")

  def save_current_node():
    nonlocal current_heading, current_key, current_level, current_body
    body_text = "\n".join(current_body).strip()

    # Handle duplicate heading keys robustness check
    base_key = current_key
    if base_key in seen_keys:
      seen_keys[base_key] += 1
      current_key = f"{base_key}_dup{seen_keys[base_key]}"
    else:
      seen_keys[base_key] = 0

    # Determine parent key based on dotted notation (e.g., "2.1.1" parent is "2.1")
    parts = base_key.split(".")
    parent_key = ".".join(parts[:-1]) if len(parts) > 1 else None

    content_str = f"{current_heading}:{body_text}"
    content_hash = hashlib.sha256(content_str.encode("utf-8")).hexdigest()

    nodes.append({
        "node_key": current_key,
        "heading": current_heading,
        "level": current_level,
        "body_text": body_text,
        "parent_node_key": parent_key,
        "content_hash": content_hash,
    })
    current_body = []

  for line in lines:
    line = line.strip()
    if not line:
      continue

    match = heading_pattern.match(line)
    if match and len(match.group(1)) <= 10:  # Likely a section header
      if current_heading or current_body:
        save_current_node()
      current_key = match.group(1)
      current_heading = match.group(2)
      current_level = len(current_key.split("."))
    else:
      current_body.append(line)

  # Save final node
  if current_heading or current_body:
    save_current_node()

  return nodes