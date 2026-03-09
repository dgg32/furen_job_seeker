// =============================================================================
// Neo4j Import Script
// =============================================================================
// Prerequisites:
//   1. Copy all node/edge CSV files into Neo4j's import directory
//      (typically $NEO4J_HOME/import/).
//   2. Run this script via Neo4j Browser or cypher-shell:
//        cypher-shell -u neo4j -p <password> -f import_neo4j.cypher
// =============================================================================


// -----------------------------------------------------------------------------
// UNIQUE CONSTRAINTS
// Declared first so all subsequent LOAD CSV operations benefit from index lookups.
// -----------------------------------------------------------------------------

CREATE CONSTRAINT expert_id IF NOT EXISTS
  FOR (n:Expert) REQUIRE n.id IS UNIQUE;

CREATE CONSTRAINT organization_id IF NOT EXISTS
  FOR (n:Organization) REQUIRE n.id IS UNIQUE;

CREATE CONSTRAINT skill_id IF NOT EXISTS
  FOR (n:Skill) REQUIRE n.id IS UNIQUE;



// -----------------------------------------------------------------------------
// NODES — Expert
// -----------------------------------------------------------------------------

LOAD CSV WITH HEADERS FROM 'file:///nodes_expert.csv' AS row
CREATE (:Expert {
  id:        row.id,
  name:      row.name,
  education: row.education
});

// -----------------------------------------------------------------------------
// NODES — Organization
// -----------------------------------------------------------------------------

LOAD CSV WITH HEADERS FROM 'file:///nodes_organization.csv' AS row
CREATE (:Organization {
  id:   row.id,
  name: row.name
});

// -----------------------------------------------------------------------------
// NODES — Skill  (all hierarchy depths: PS# / L2_# / S#)
//   depth 1 = Primary Skills
//   depth 2 = Level 2 (Context)
//   depth 3 = Skill leaf  (I can...)
// -----------------------------------------------------------------------------

LOAD CSV WITH HEADERS FROM 'file:///nodes_skill.csv' AS row
CREATE (:Skill {
  id:    row.id,
  name:  row.name,
  depth: toInteger(row.depth)
});


// -----------------------------------------------------------------------------
// EDGES — HAS_SKILL  (Expert → Skill, any depth: level 1, 2, or 3)
// -----------------------------------------------------------------------------

LOAD CSV WITH HEADERS FROM 'file:///edges_HAS_SKILL.csv' AS row
MATCH (e:Expert   {id: row.`from`})
MATCH (s:Skill    {id: row.`to`})
CREATE (e)-[:HAS_SKILL]->(s);

// -----------------------------------------------------------------------------
// EDGES — HAS_REQUIREMENT  (Organization → Skill, any depth: level 1, 2, or 3)
// -----------------------------------------------------------------------------

LOAD CSV WITH HEADERS FROM 'file:///edges_HAS_REQUIREMENT.csv' AS row
MATCH (o:Organization {id: row.`from`})
MATCH (s:Skill        {id: row.`to`})
CREATE (o)-[:HAS_REQUIREMENT]->(s);



// -----------------------------------------------------------------------------
// EDGES — SKILL_HIERARCHY  (Skill parent → Skill child)
//   PS# -[:PARENT_OF]-> L2_#  and  L2_# -[:PARENT_OF]-> S#
// -----------------------------------------------------------------------------

LOAD CSV WITH HEADERS FROM 'file:///edges_SKILL_HIERARCHY.csv' AS row
MATCH (parent:Skill {id: row.`from`})
MATCH (child:Skill  {id: row.`to`})
CREATE (parent)-[:PARENT_OF]->(child);

