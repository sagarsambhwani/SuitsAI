// ==========================================
// Neo4j Regulatory Knowledge Graph Schema
// ==========================================

// Constraints for Unique IDs
CREATE CONSTRAINT c_regulatory_source_id IF NOT EXISTS FOR (rs:RegulatorySource) REQUIRE rs.id IS UNIQUE;
CREATE CONSTRAINT c_regulatory_provision_id IF NOT EXISTS FOR (rp:RegulatoryProvision) REQUIRE rp.id IS UNIQUE;
CREATE CONSTRAINT c_regulatory_obligation_id IF NOT EXISTS FOR (ro:RegulatoryObligation) REQUIRE ro.id IS UNIQUE;
CREATE CONSTRAINT c_applicability_assessment_id IF NOT EXISTS FOR (aa:ApplicabilityAssessment) REQUIRE aa.id IS UNIQUE;
CREATE CONSTRAINT c_regulator_id IF NOT EXISTS FOR (r:Regulator) REQUIRE r.id IS UNIQUE;
CREATE CONSTRAINT c_regulation_id IF NOT EXISTS FOR (reg:Regulation) REQUIRE reg.id IS UNIQUE;
CREATE CONSTRAINT c_section_id IF NOT EXISTS FOR (s:Section) REQUIRE s.id IS UNIQUE;
CREATE CONSTRAINT c_requirement_id IF NOT EXISTS FOR (req:Requirement) REQUIRE req.id IS UNIQUE;
CREATE CONSTRAINT c_policy_id IF NOT EXISTS FOR (p:Policy) REQUIRE p.id IS UNIQUE;
CREATE CONSTRAINT c_clause_id IF NOT EXISTS FOR (pc:PolicyClause) REQUIRE pc.id IS UNIQUE;
CREATE CONSTRAINT c_control_id IF NOT EXISTS FOR (c:Control) REQUIRE c.id IS UNIQUE;
CREATE CONSTRAINT c_business_unit_id IF NOT EXISTS FOR (bu:BusinessUnit) REQUIRE bu.id IS UNIQUE;
CREATE CONSTRAINT c_business_process_id IF NOT EXISTS FOR (bp:BusinessProcess) REQUIRE bp.id IS UNIQUE;
CREATE CONSTRAINT c_system_id IF NOT EXISTS FOR (sys:System) REQUIRE sys.id IS UNIQUE;
CREATE CONSTRAINT c_vendor_id IF NOT EXISTS FOR (v:Vendor) REQUIRE v.id IS UNIQUE;
CREATE CONSTRAINT c_internal_document_id IF NOT EXISTS FOR (doc:InternalDocument) REQUIRE doc.id IS UNIQUE;
CREATE CONSTRAINT c_compliance_gap_id IF NOT EXISTS FOR (g:ComplianceGap) REQUIRE g.id IS UNIQUE;
CREATE CONSTRAINT c_remediation_action_id IF NOT EXISTS FOR (rem:RemediationAction) REQUIRE rem.id IS UNIQUE;
CREATE CONSTRAINT c_control_test_id IF NOT EXISTS FOR (ct:ControlTest) REQUIRE ct.id IS UNIQUE;
CREATE CONSTRAINT c_compliance_evidence_id IF NOT EXISTS FOR (ev:ComplianceEvidence) REQUIRE ev.id IS UNIQUE;

// Multi-tenant indexes for rapid tenant-scoped traversal
CREATE INDEX idx_policy_tenant IF NOT EXISTS FOR (p:Policy) ON (p.tenant_id);
CREATE INDEX idx_clause_tenant IF NOT EXISTS FOR (pc:PolicyClause) ON (pc.tenant_id);
CREATE INDEX idx_control_tenant IF NOT EXISTS FOR (c:Control) ON (c.tenant_id);
CREATE INDEX idx_doc_tenant IF NOT EXISTS FOR (doc:InternalDocument) ON (doc.tenant_id);
CREATE INDEX idx_gap_tenant IF NOT EXISTS FOR (g:ComplianceGap) ON (g.tenant_id);
CREATE INDEX idx_rem_tenant IF NOT EXISTS FOR (rem:RemediationAction) ON (rem.tenant_id);
CREATE INDEX idx_req_jurisdiction IF NOT EXISTS FOR (req:Requirement) ON (req.jurisdiction);
CREATE INDEX idx_obligation_jurisdiction IF NOT EXISTS FOR (ro:RegulatoryObligation) ON (ro.jurisdiction);
CREATE INDEX idx_reg_status IF NOT EXISTS FOR (reg:Regulation) ON (reg.status);
