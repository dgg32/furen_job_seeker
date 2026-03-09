"""
convert_to_graph.py

Converts raw CSV files into node and edge CSVs suitable for graph database import.

Node files
----------
  nodes_expert.csv          id, name
  nodes_organization.csv    id, name
  nodes_skill.csv           id, name, depth
                              depth 1 = Primary Skills
                              depth 2 = Level 2 (Context)
                              depth 3 = Skills leaf  (I can...)
  nodes_capability.csv      id, name, depth, description
                              depth 1 = Pillar
                              depth 2 = Primary Process
                              depth 3 = Secondary (Context)
                              depth 4 = Capability leaf  (description only on depth-4)

Edge files
----------
  edges_HAS_SKILL.csv             Expert  → Skill leaf
  edges_HAS_CAPABILITY.csv        Org     → Capability leaf
  edges_SKILL_TO_CAPABILITY.csv   Skill leaf → Capability leaf
  edges_SKILL_HIERARCHY.csv       parent  → child within skill tree
  edges_CAPABILITY_HIERARCHY.csv  parent  → child within capability tree

Usage
-----
  python convert_to_graph.py --output /path/to/output/folder
"""

import argparse
import csv
import os

# ── Input file paths (relative to this script) ──────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

PERSON_CSV      = os.path.join(SCRIPT_DIR, "raw",  "seeker.csv")
ORG_CSV         = os.path.join(SCRIPT_DIR, "raw",  "organization.csv")
SKILL_CSV       = os.path.join(SCRIPT_DIR, "raw",  "skill.csv")



def read_csv(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def write_csv(path, fieldnames, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"  Written: {path}  ({len(rows)} rows)")


def build_skill_graph(skills_raw):
    """
    Returns:
        skill_nodes        : list of dicts {id, name, depth}
        skill_name_to_id   : {name -> id} for all depths (for HAS_SKILL lookups)
        skill_hier_edges   : list of {from, to}
    """
    # Ordered insertion dicts preserve first-seen order
    ps_name_to_id  = {}   # Primary Skills   depth=1
    l2_name_to_id  = {}   # Level 2 Context  depth=2
    sk_name_to_id  = {}   # Skill leaf       depth=3

    ps_counter = l2_counter = sk_counter = 0

    for row in skills_raw:
        ps  = row["Level 1"].strip()
        l2  = row["Level 2"].strip()
        sk  = row["Level 3"].strip()

        if ps and ps not in ps_name_to_id:
            ps_counter += 1
            ps_name_to_id[ps] = f"PS{ps_counter}"

        # Level-2 key is (ps, l2) so same label under different parents stays distinct
        l2_key = (ps, l2)
        if l2 and l2_key not in l2_name_to_id:
            l2_counter += 1
            l2_name_to_id[l2_key] = f"L2_{l2_counter}"

        if sk and sk not in sk_name_to_id:
            sk_counter += 1
            sk_name_to_id[sk] = f"S{sk_counter}"

    # Build node list
    skill_nodes = []
    for name, sid in ps_name_to_id.items():
        skill_nodes.append({"id": sid, "name": name, "depth": 1})
    for (ps, l2), lid in l2_name_to_id.items():
        skill_nodes.append({"id": lid, "name": l2, "depth": 2})
    for name, sid in sk_name_to_id.items():
        skill_nodes.append({"id": sid, "name": name, "depth": 3})

    # Build hierarchy edges (parent → child), dedup with a seen set
    hier_edges = []
    seen_edges = set()

    for row in skills_raw:
        ps  = row["Level 1"].strip()
        l2  = row["Level 2"].strip()
        sk  = row["Level 3"].strip()
        l2_key = (ps, l2)

        if ps and l2:
            e = (ps_name_to_id[ps], l2_name_to_id[l2_key])
            if e not in seen_edges:
                seen_edges.add(e)
                hier_edges.append({"from": e[0], "to": e[1]})

        if l2 and sk:
            e = (l2_name_to_id[l2_key], sk_name_to_id[sk])
            if e not in seen_edges:
                seen_edges.add(e)
                hier_edges.append({"from": e[0], "to": e[1]})

    # Build a combined name→id lookup across all depths so job seekers can
    # match at level 1, 2, or 3.  Level-2 names may repeat under different
    # parents; first-seen wins for the flat lookup.
    combined_name_to_id = {}
    for name, sid in ps_name_to_id.items():
        combined_name_to_id.setdefault(name, sid)
    for (ps, l2), lid in l2_name_to_id.items():
        combined_name_to_id.setdefault(l2, lid)
    for name, sid in sk_name_to_id.items():
        combined_name_to_id.setdefault(name, sid)

    return skill_nodes, combined_name_to_id, hier_edges


def main(output_dir):
    os.makedirs(output_dir, exist_ok=True)

    # ── Load raw data ────────────────────────────────────────────────────────
    persons    = read_csv(PERSON_CSV)
    orgs       = read_csv(ORG_CSV)
    skills_raw = read_csv(SKILL_CSV)


    # ── NODE: Expert ─────────────────────────────────────────────────────────
    expert_nodes = [{"id": row["id"], "name": row["name"], "education": row["education"]} for row in persons]
    write_csv(os.path.join(output_dir, "nodes_expert.csv"),
              ["id", "name", "education"], expert_nodes)

    # ── NODE: Organization ───────────────────────────────────────────────────
    org_nodes = [{"id": row["id"], "name": row["name"]} for row in orgs]
    write_csv(os.path.join(output_dir, "nodes_organization.csv"),
              ["id", "name"], org_nodes)

    # ── NODE: Skill (all depths) + SKILL hierarchy edges ────────────────────
    skill_nodes, skill_name_to_id, skill_hier_edges = build_skill_graph(skills_raw)
    write_csv(os.path.join(output_dir, "nodes_skill.csv"),
              ["id", "name", "depth"], skill_nodes)
    write_csv(os.path.join(output_dir, "edges_SKILL_HIERARCHY.csv"),
              ["from", "to"], skill_hier_edges)

    # ── EDGE: HAS_SKILL (Expert → Skill leaf) ────────────────────────────────
    has_skill_edges = []
    for row in persons:
        expert_id = row["id"]
        for skill_name in row["skill"].split(","):
            skill_name = skill_name.strip()
            if skill_name in skill_name_to_id:
                has_skill_edges.append({"from": expert_id,
                                        "to": skill_name_to_id[skill_name]})
            else:
                print(f"  [WARN] Skill not found: '{skill_name}'")
    write_csv(os.path.join(output_dir, "edges_HAS_SKILL.csv"),
              ["from", "to"], has_skill_edges)

    # ── EDGE: HAS_CAPABILITY (Org → Capability leaf) ─────────────────────────
    has_cap_edges = []
    for row in orgs:
        org_id = row["id"]
        for cap_name in row["requirement"].split(","):
            cap_name = cap_name.strip()
            if cap_name in skill_name_to_id:
                has_cap_edges.append({"from": org_id,
                                      "to": skill_name_to_id[cap_name]})
            else:
                print(f"  [WARN] Capability not found: '{cap_name}'")
    write_csv(os.path.join(output_dir, "edges_HAS_REQUIREMENT.csv"),
              ["from", "to"], has_cap_edges)


    print("\nDone. Output files:")
    for f in sorted(os.listdir(output_dir)):
        print(f"  {os.path.join(output_dir, f)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Convert raw CSVs to graph node/edge CSVs.")
    parser.add_argument(
        "--output", "-o",
        default=os.path.join(SCRIPT_DIR, "graph_output"),
        help="Destination folder for output CSVs (default: ./graph_output)"
    )
    args = parser.parse_args()
    main(args.output)
