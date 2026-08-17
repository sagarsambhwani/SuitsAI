/* ==========================================================================
   SuitsAI Compliance Platform — Defensible Client Application
   ========================================================================== */

const API_BASE = '/api/v1';
let currentTenant = 'BANK-GLOBAL-001';
let lastRunId = '';

document.addEventListener('DOMContentLoaded', () => {
  initTabs();
  initTenantSelector();
  initForms();
  loadDashboardData();
});

function initTabs() {
  const buttons = document.querySelectorAll('.nav-item');
  const panes = document.querySelectorAll('.tab-pane');

  buttons.forEach((btn) => {
    btn.addEventListener('click', () => {
      const tabId = btn.getAttribute('data-tab');
      buttons.forEach((b) => b.classList.remove('active'));
      panes.forEach((p) => p.classList.remove('active'));

      btn.classList.add('active');
      const targetPane = document.getElementById(`tab-${tabId}`);
      if (targetPane) targetPane.classList.add('active');

      if (tabId === 'regulations') loadRegulations();
      if (tabId === 'policies') loadPolicies();
      if (tabId === 'graph') loadKnowledgeGraph();
      if (tabId === 'impact') loadImpactView();
      if (tabId === 'replay' && lastRunId) loadReplayView(lastRunId);
      if (tabId === 'approvals') loadApprovalsView();
      if (tabId === 'audit') loadAuditLog();
    });
  });
}

function initTenantSelector() {
  const select = document.getElementById('tenantSelect');
  select.addEventListener('change', (e) => {
    currentTenant = e.target.value;
    document.getElementById('graphTenantLabel').innerText = currentTenant;
    loadDashboardData();
  });
}

function initForms() {
  // Ingest Regulation Form
  const ingestForm = document.getElementById('ingestForm');
  ingestForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const btn = document.getElementById('btnIngest');
    btn.disabled = true;
    btn.innerText = '⏳ Ingesting & Verifying Evidence...';

    const payload = {
      code: document.getElementById('inCode').value,
      title: document.getElementById('inTitle').value,
      regulator_name: document.getElementById('inRegulator').value,
      regulator_acronym: document.getElementById('inRegulator').value.split(' ')[0],
      jurisdiction: document.getElementById('inJurisdiction').value,
      doc_type: 'Circular',
      raw_text: document.getElementById('inRawText').value,
    };

    try {
      const res = await fetch(`${API_BASE}/regulations/ingest`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Tenant-ID': currentTenant,
        },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      alert(`✅ Evidence Ingested!\nRegulation: ${data.code} (v${data.current_version})\nExtracted Obligations: ${data.requirements_count}\nSHA-256: ${data.sha256_hash.substring(0, 16)}...`);
      loadDashboardData();
    } catch (err) {
      alert('Error ingesting regulation: ' + err);
    } finally {
      btn.disabled = false;
      btn.innerText = '🚀 Ingest & Extract Obligations';
    }
  });

  // Seed Demo Scenario
  document.getElementById('btnSeedDemo').addEventListener('click', async () => {
    await seedDemoScenario();
  });

  // Run Impact Analysis
  document.getElementById('btnRunImpactAnalysis').addEventListener('click', async () => {
    const sel = document.getElementById('selectRegulationForImpact');
    const modeSel = document.getElementById('selectExecMode');
    const regId = sel.value;
    if (!regId) {
      alert('Please select a regulation first.');
      return;
    }
    await executeImpactAnalysis(regId, modeSel.value);
  });

  // Fetch Replay
  document.getElementById('btnFetchReplay').addEventListener('click', async () => {
    const runId = document.getElementById('inReplayRunId').value.trim();
    if (!runId) {
      alert('Please enter a valid Compliance Run ID.');
      return;
    }
    await loadReplayView(runId);
  });
}

async function loadDashboardData() {
  try {
    const [regsRes, polsRes, auditsRes] = await Promise.all([
      fetch(`${API_BASE}/regulations`, { headers: { 'X-Tenant-ID': currentTenant } }),
      fetch(`${API_BASE}/policies`, { headers: { 'X-Tenant-ID': currentTenant } }),
      fetch(`${API_BASE}/audit`, { headers: { 'X-Tenant-ID': currentTenant } }),
    ]);

    const regs = await regsRes.json();
    const pols = await polsRes.json();
    const audits = await auditsRes.json();

    document.getElementById('statRegCount').innerText = regs.length;
    document.getElementById('statPolicyCount').innerText = pols.length;
    document.getElementById('statAuditCount').innerText = audits.length;

    let reqCount = 0;
    regs.forEach((r) => (reqCount += r.requirements_count || 0));
    document.getElementById('statReqCount').innerText = reqCount;

    let ctlCount = 0;
    pols.forEach((p) => (ctlCount += p.controls ? p.controls.length : 0));
    document.getElementById('statControlCount').innerText = ctlCount;
  } catch (err) {
    console.error('Error loading dashboard metrics:', err);
  }
}

async function seedDemoScenario() {
  // 1. Seed Base Policy (Layer 3)
  const policyPayload = {
    policy_code: 'POL-INF-001',
    title: 'Information Security & API Management Policy',
    category: 'Cybersecurity',
    jurisdiction: 'IN',
    owner_department: 'Cybersecurity & IT Operations',
    clauses: [
      {
        clause_number: 'Clause 4.2.1',
        title: 'Cryptographic Credential Lifecycle',
        text: 'All internal and partner API keys, secret tokens, and security credentials shall be rotated at least every 180 calendar days.',
      },
    ],
    controls: [
      {
        control_code: 'CTL-SEC-09',
        name: 'API Credential Rotation Monitor',
        description: 'Automated scan checking API credential age against standard retention windows.',
        frequency: 'CONTINUOUS',
        control_type: 'PREVENTIVE',
      },
    ],
  };

  await fetch(`${API_BASE}/policies`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-Tenant-ID': currentTenant },
    body: JSON.stringify(policyPayload),
  });

  // 2. Ingest New Circular (Layer 1 Evidence)
  const circularPayload = {
    code: 'RBI/2026-27/04',
    title: 'Master Direction on Digital Lending API Security and Key Management',
    regulator_name: 'Reserve Bank of India',
    regulator_acronym: 'RBI',
    jurisdiction: 'IN',
    doc_type: 'Circular',
    raw_text: `[Page 1]
Section 4.1 Cryptographic Key Lifecycle and Authentication
1. Regulated entities shall ensure cryptographic keys and API tokens are rotated at intervals not exceeding 90 days.
2. In the event of detected key exposure or inactivity exceeding 30 days, automated revocation and audit logging shall trigger immediately.
3. Regulated entities must maintain immutable audit trails of all customer authorization grants and API access tokens for a minimum period of 10 years, except when customer is central government entity.`,
  };

  await fetch(`${API_BASE}/regulations/ingest`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-Tenant-ID': currentTenant },
    body: JSON.stringify(circularPayload),
  });

  alert('⚡ Demo scenario seeded with Layer 1 Evidence, Layer 2 Requirements, and Layer 3 Policies!');
  loadDashboardData();
}

async function loadRegulations() {
  const container = document.getElementById('regulationsList');
  container.innerHTML = '<p>Loading regulations...</p>';

  const res = await fetch(`${API_BASE}/regulations`, { headers: { 'X-Tenant-ID': currentTenant } });
  const regs = await res.json();

  if (regs.length === 0) {
    container.innerHTML = '<p class="text-muted">No regulations ingested yet. Use the Ingest form or Load Demo Scenario.</p>';
    return;
  }

  let html = '<div class="metric-grid">';
  regs.forEach((r) => {
    html += `
      <div class="card">
        <div class="card-header">
          <strong>${r.code} (v${r.current_version})</strong>
          <span class="badge badge-accent">${r.jurisdiction}</span>
        </div>
        <div class="card-body">
          <h4 style="color:#fff; margin-bottom:8px;">${r.title}</h4>
          <p style="font-size:0.82rem; color:var(--text-muted); margin-bottom:12px;">Type: ${r.doc_type} | Status: <span class="text-success">${r.status}</span></p>
          <div style="font-size:0.75rem; font-family:var(--font-mono); background:#090d14; padding:8px; border-radius:4px; margin-bottom:10px; word-break:break-all;">
            SHA-256: ${r.sha256_hash}
          </div>
          <span class="badge badge-warning">Extracted Requirements: ${r.requirements_count}</span>
        </div>
      </div>
    `;
  });
  html += '</div>';
  container.innerHTML = html;
}

async function loadPolicies() {
  const container = document.getElementById('policiesList');
  container.innerHTML = '<p>Loading policies...</p>';

  const res = await fetch(`${API_BASE}/policies`, { headers: { 'X-Tenant-ID': currentTenant } });
  const pols = await res.json();

  if (pols.length === 0) {
    container.innerHTML = '<p class="text-muted">No policies registered for this tenant. Click "Load Demo Scenario".</p>';
    return;
  }

  let html = '';
  pols.forEach((p) => {
    html += `
      <div class="amendment-card">
        <div class="amendment-header">
          <div>
            <h3 style="color:#fff;">${p.policy_code}: ${p.title}</h3>
            <span style="font-size:0.8rem; color:var(--text-muted);">Owner: ${p.owner_department || 'Compliance'} | Version: <strong>v${p.current_version}</strong></span>
          </div>
          <span class="badge badge-success">${p.status}</span>
        </div>
        <div style="margin-top:12px;">
          <strong style="font-size:0.82rem; color:var(--text-secondary);">Clauses:</strong>
          ${p.clauses.map((c) => `<div style="background:#090d14; padding:10px; border-radius:4px; margin-top:6px; font-size:0.85rem;"><span style="color:#60a5fa; font-weight:600;">${c.clause_number}:</span> ${c.text}</div>`).join('')}
        </div>
      </div>
    `;
  });
  container.innerHTML = html;
}

async function loadKnowledgeGraph() {
  const canvas = document.getElementById('graphCanvas');
  canvas.innerHTML = `
    <div class="graph-row">
      <span class="graph-node-chip chip-reg">RBI/2026-27/04 (Evidence v1.0)</span>
      <span class="graph-arrow">── CONTAINS [Provenance: VERIFIED] ──></span>
      <span class="graph-node-chip chip-req">REQ-4.1-01 (90-Day Key Rotation)</span>
      <span class="graph-arrow">── AFFECTS [Method: LLM] ──></span>
      <span class="graph-node-chip chip-pol">POL-INF-001 (InfoSec Policy)</span>
      <span class="graph-arrow">── IMPLEMENTED_BY ──></span>
      <span class="graph-node-chip chip-ctl">CTL-SEC-09 (Rotation Monitor)</span>
      <span class="graph-arrow">── OWNED_BY ──></span>
      <span class="graph-node-chip chip-bu">Cybersecurity & IT Ops</span>
    </div>
    <div class="graph-row">
      <span class="graph-node-chip chip-reg">RBI/2026-27/04 (Evidence v1.0)</span>
      <span class="graph-arrow">── CONTAINS [Provenance: VERIFIED] ──></span>
      <span class="graph-node-chip chip-req">REQ-4.1-03 (10-Yr Audit Log / Gov Exception)</span>
      <span class="graph-arrow">── AFFECTS ──></span>
      <span class="graph-node-chip chip-pol">POL-INF-001 (InfoSec Policy)</span>
      <span class="graph-arrow">── OWNED_BY ──></span>
      <span class="graph-node-chip chip-bu">Cybersecurity & IT Ops</span>
    </div>
  `;
}

async function loadImpactView() {
  const sel = document.getElementById('selectRegulationForImpact');
  sel.innerHTML = '';

  const res = await fetch(`${API_BASE}/regulations`, { headers: { 'X-Tenant-ID': currentTenant } });
  const regs = await res.json();

  regs.forEach((r) => {
    const opt = document.createElement('option');
    opt.value = r.id;
    opt.innerText = `${r.code} — ${r.title}`;
    sel.appendChild(opt);
  });
}

async function executeImpactAnalysis(regulationId, mode = 'standard') {
  const resultsArea = document.getElementById('impactResultsArea');
  resultsArea.innerHTML = '<div style="padding:20px; text-align:center; color:var(--text-muted);">⚡ Running LangGraph reasoning and 8-Gate verification scorecard...</div>';

  try {
    const res = await fetch(`${API_BASE}/compliance/analyze`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Tenant-ID': currentTenant },
      body: JSON.stringify({ regulation_id: regulationId, async_mode: false, mode: mode }),
    });
    const data = await res.json();
    lastRunId = data.run_id;

    // Render Scorecard
    const scorecard = data.verification_scorecard || {};
    const gates = scorecard.gates || {};

    let scorecardHtml = '<div class="scorecard-grid">';
    Object.keys(gates).forEach((k) => {
      const g = gates[k];
      const isPass = g.passed;
      scorecardHtml += `
        <div class="scorecard-item ${isPass ? 'pass' : 'fail'}">
          <div class="scorecard-header">
            <span>${g.gate_name}</span>
            <span class="badge ${isPass ? 'badge-success' : 'badge-danger'}">${g.status}</span>
          </div>
          <div class="scorecard-details">${g.details}</div>
        </div>
      `;
    });
    scorecardHtml += '</div>';

    let html = `
      <div class="card" style="border: 1px solid var(--accent-primary);">
        <div class="card-header">
          <div>
            <h3>Analysis & Gate Results: ${data.regulation_code}</h3>
            <span style="font-size:0.75rem; font-family:var(--font-mono); color:var(--text-muted);">Run ID: ${data.run_id} | Mode: ${data.mode.toUpperCase()}</span>
          </div>
          <div>
            <span class="badge ${data.all_gates_passed ? 'badge-success' : 'badge-danger'}">
              ${data.all_gates_passed ? '✓ ALL 8 GATES PASSED' : '⚠ GATES FAILED'}
            </span>
          </div>
        </div>
        <div class="card-body">
          <h4 style="color:#fff; margin-bottom:6px;">Deterministic 8-Gate Verification Scorecard:</h4>
          ${scorecardHtml}

          <div class="metric-grid" style="margin:20px 0;">
            <div class="metric-card"><div class="metric-title">Requirements Analyzed</div><div class="metric-value">${data.total_requirements}</div></div>
            <div class="metric-card"><div class="metric-title">Compliance Gaps Detected</div><div class="metric-value text-warning">${data.gaps_detected}</div></div>
            <div class="metric-card"><div class="metric-title">Proposed Amendments</div><div class="metric-value text-success">${data.changes.length}</div></div>
          </div>
    `;

    data.changes.forEach((ch) => {
      html += `
        <div class="amendment-card">
          <div class="amendment-header">
            <strong>Target: ${ch.policy_code} — ${ch.clause_number} (${ch.change_type})</strong>
            <span class="badge ${ch.citation_verified ? 'badge-success' : 'badge-warning'}">Status: ${ch.status}</span>
          </div>
          <div class="diff-comparison">
            <div class="diff-box original">
              <div class="diff-title">ORIGINAL BASELINE CLAUSE</div>
              <div class="diff-text">${ch.original_text || 'No previous clause recorded.'}</div>
            </div>
            <div class="diff-box proposed">
              <div class="diff-title">PROPOSED REDLINE AMENDMENT</div>
              <div class="diff-text">${ch.proposed_text}</div>
            </div>
          </div>
          <div style="font-size:0.82rem; color:var(--text-secondary); margin-bottom:8px;">
            <strong>Compliance Rationale:</strong> ${ch.justification}
          </div>
          ${
            ch.claim_lineages && ch.claim_lineages.length > 0
              ? ch.claim_lineages.map((l) => `
                <div class="lineage-box">
                  <div class="lineage-header">
                    <span>SENTENCE-LEVEL EVIDENCE LINEAGE [Page ${l.page_number}]</span>
                    <span class="badge badge-success">${l.verification_status}</span>
                  </div>
                  <div class="lineage-quote">"${l.source_verbatim_quote}"</div>
                </div>
              `).join('')
              : ''
          }
        </div>
      `;
    });

    if (data.mode !== 'shadow') {
      html += `
          <div style="margin-top:16px; display:flex; gap:12px;">
            <button class="btn btn-success" onclick="approveDirectChange('${data.changes[0]?.id || ''}')">🛡️ Approve & Publish Policy Version</button>
            <button class="btn btn-danger" onclick="rejectDirectChange('${data.changes[0]?.id || ''}')">✕ Reject with Feedback</button>
          </div>
      `;
    } else {
      html += `
          <div style="margin-top:16px; background:rgba(6,182,212,0.1); padding:12px; border-radius:6px; color:#67e8f9; font-size:0.85rem;">
            ℹ️ <strong>Shadow Mode Active:</strong> Recommendations recorded for benchmark comparison without publishing.
          </div>
      `;
    }

    html += `
        </div>
      </div>
    `;

    resultsArea.innerHTML = html;
  } catch (err) {
    resultsArea.innerHTML = `<p class="text-danger">Error running impact analysis: ${err}</p>`;
  }
}

async function approveDirectChange(changeId) {
  if (!changeId) {
    alert('Please execute impact analysis first to generate a change proposal.');
    return;
  }

  try {
    const res = await fetch(`${API_BASE}/approvals/${changeId}/decision`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Tenant-ID': currentTenant },
      body: JSON.stringify({ action: 'APPROVE', comments: 'Approved by Compliance Officer after 8-Gate verification.' }),
    });
    const data = await res.json();
    alert(`🎉 Policy Amendment Approved!\nPublished New Version: ${data.published_policy_version}\nAudit Event Sealed: ${data.audit_event_id}`);
    loadDashboardData();
  } catch (err) {
    alert('Error approving change: ' + err);
  }
}

async function rejectDirectChange(changeId) {
  const reason = prompt('Please enter rejection rationale for evaluation benchmark dataset:', 'Scope applies only to international subsidiaries.');
  if (!reason) return;

  try {
    await fetch(`${API_BASE}/compliance/feedback`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Tenant-ID': currentTenant },
      body: JSON.stringify({
        policy_change_id: changeId,
        decision: 'REJECT',
        rejection_reason_category: 'SCOPE_MISMATCH',
        reviewer_comments: reason,
      }),
    });
    alert('✓ Rejection and feedback captured in evaluation dataset.');
    loadDashboardData();
  } catch (err) {
    alert('Error recording feedback: ' + err);
  }
}

async function loadReplayView(runId) {
  const container = document.getElementById('replayResultArea');
  container.innerHTML = '<p>Loading frozen system snapshot...</p>';

  try {
    const res = await fetch(`${API_BASE}/compliance/runs/${runId}/replay`, {
      headers: { 'X-Tenant-ID': currentTenant },
    });
    if (!res.ok) {
      container.innerHTML = `<p class="text-danger">Run snapshot ${runId} not found.</p>`;
      return;
    }
    const data = await res.json();

    let html = `
      <div class="card" style="border: 1px solid var(--accent-cyan);">
        <div class="card-header">
          <h3>Replay Snapshot: ${data.run_id}</h3>
          <span class="badge badge-accent">Frozen: ${new Date(data.created_at).toLocaleString()}</span>
        </div>
        <div class="card-body">
          <div class="replay-block">
            <h4>Version Matrix Frozen at Execution:</h4>
            <div class="replay-code">
Model Version:     ${data.model_version}
Prompt Version:    ${data.prompt_version}
Workflow Version:  ${data.workflow_version}
Document SHA-256:  ${data.document_sha256}
            </div>
          </div>

          <div class="replay-block">
            <h4>8-Gate Scorecard at Time of Run:</h4>
            <div class="replay-code">${JSON.stringify(data.verification_scorecard, null, 2)}</div>
          </div>

          <div class="replay-block">
            <h4>Graph Traversal Snapshot:</h4>
            <div class="replay-code">${JSON.stringify(data.graph_query_snapshot, null, 2)}</div>
          </div>

          <div class="replay-block">
            <h4>Generated Output Redlines:</h4>
            <div class="replay-code">${JSON.stringify(data.final_output, null, 2)}</div>
          </div>
        </div>
      </div>
    `;
    container.innerHTML = html;
  } catch (err) {
    container.innerHTML = `<p class="text-danger">Error loading replay: ${err}</p>`;
  }
}

async function loadApprovalsView() {
  const container = document.getElementById('approvalsListArea');
  container.innerHTML = `
    <div class="amendment-card">
      <div class="amendment-header">
        <div>
          <h3 style="color:#fff;">POL-INF-001: Clause 4.2.1 Amendment</h3>
          <span style="font-size:0.8rem; color:var(--text-muted);">Triggered by: RBI/2026-27/04 (v1.0.0) | SHA-256 Verified</span>
        </div>
        <span class="badge badge-warning">Pending Review</span>
      </div>
      <div class="diff-comparison" style="margin-top:12px;">
        <div class="diff-box original">
          <div class="diff-title">CURRENT TEXT (v1.0.0)</div>
          <div class="diff-text">All internal and partner API keys shall be rotated at least every 180 calendar days.</div>
        </div>
        <div class="diff-box proposed">
          <div class="diff-title">PROPOSED TEXT (v2.0.0)</div>
          <div class="diff-text">All banking, partner, and customer-facing API keys, secret tokens, and cryptographic credentials shall be systematically rotated at least every 90 calendar days. Automated revocation and audit alerts must trigger immediately upon detection of credential exposure or inactivity exceeding 30 days.</div>
        </div>
      </div>
      <div class="lineage-box">
        <div class="lineage-header">
          <span>LINEAGE EVIDENCE TRACE [Page 1, Section 4.1]</span>
          <span class="badge badge-success">VERIFIED</span>
        </div>
        <div class="lineage-quote">"cryptographic keys and API tokens are rotated at intervals not exceeding 90 days" [RBI/2026-27/04]</div>
      </div>
      <div style="margin-top:16px; display:flex; gap:12px;">
        <button class="btn btn-success" onclick="approveDirectChange('demo-change-id')">✓ Approve & Publish</button>
        <button class="btn btn-danger" onclick="rejectDirectChange('demo-change-id')">✕ Reject</button>
      </div>
    </div>
  `;
}

async function loadAuditLog() {
  const tbody = document.getElementById('auditTableBody');
  tbody.innerHTML = '<tr><td colspan="6">Loading audit trail...</td></tr>';

  try {
    const res = await fetch(`${API_BASE}/audit`, { headers: { 'X-Tenant-ID': currentTenant } });
    const events = await res.json();

    if (events.length === 0) {
      tbody.innerHTML = '<tr><td colspan="6" class="text-muted">No audit events recorded yet.</td></tr>';
      return;
    }

    let html = '';
    events.forEach((e) => {
      const dt = new Date(e.timestamp).toLocaleString();
      html += `
        <tr>
          <td style="font-family:var(--font-mono); font-size:0.78rem; color:var(--text-muted);">${dt}</td>
          <td><span class="badge badge-accent">${e.event_type}</span></td>
          <td>${e.entity_type}</td>
          <td><strong style="color:${e.action === 'APPROVE' ? 'var(--accent-success)' : '#fff'};">${e.action}</strong></td>
          <td style="font-size:0.8rem; color:var(--text-secondary); max-width:300px; overflow:hidden; text-overflow:ellipsis;">${JSON.stringify(e.details)}</td>
          <td style="font-size:0.8rem;">${e.user_id || 'System'}</td>
        </tr>
      `;
    });
    tbody.innerHTML = html;
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="6" class="text-danger">Error loading audit events: ${err}</td></tr>`;
  }
}
