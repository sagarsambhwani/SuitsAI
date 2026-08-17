// ==========================================
// Neo4j Regulatory Knowledge Graph Schema
// ==========================================

// Constraints for Unique IDs
CREATE CONSTRAINT c_regulator_id IF NOT EXISTS FOR (r:Regulator) REQUIRE r.id IS UNIQUE;
CREATE CONSTRAINT c_regulation_id IF NOT EXISTS FOR (reg:Regulation) REQUIRE reg.id IS UNIQUE;
CREATE CONSTRAINT c_section_id IF NOT EXISTS FOR (s:Section) REQUIRE s.id IS UNIQUE;
CREATE CONSTRAINT c_requirement_id IF NOT EXISTS FOR (req:Requirement) REQUIRE req.id IS UNIQUE;
CREATE CONSTRAINT c_policy_id IF NOT EXISTS FOR (p:Policy) REQUIRE p.id IS UNIQUE;
CREATE CONSTRAINT c_clause_id IF NOT EXISTS FOR (pc:PolicyClause) REQUIRE pc.id IS UNIQUE;
CREATE CONSTRAINT c_control_id IF NOT EXISTS FOR (c:Control) REQUIRE c.id IS UNIQUE;
CREATE CONSTRAINT c_business_unit_id IF NOT EXISTS FOR (bu:BusinessUnit) REQUIRE bu.id IS UNIQUE;

// Multi-tenant indexes for rapid tenant-scoped traversal
CREATE INDEX idx_policy_tenant IF NOT EXISTS FOR (p:Policy) ON (p.tenant_id);
CREATE INDEX idx_clause_tenant IF NOT EXISTS FOR (pc:PolicyClause) ON (pc.tenant_id);
CREATE INDEX idx_control_tenant IF NOT EXISTS FOR (c:Control) ON (c.tenant_id);
CREATE INDEX idx_req_jurisdiction IF NOT EXISTS FOR (req:Requirement) ON (req.jurisdiction);
CREATE INDEX idx_reg_status IF NOT EXISTS FOR (reg:Regulation) ON (reg.status);
