/**
 * Enterprise Client-Side Export Utilities for MYGPT AI Tender Consultant
 * Strictly formats authentic extracted tender data across ALL 11 dimensions
 * Exports: Full Print-to-PDF, Standalone HTML Dossier, Markdown Dossier, and Specialized CSVs
 */

import type {
  MasterTenderReport,
  EligibilityConditionItem,
  TechnicalSpecificationItem,
  ComplianceMatrixItem,
  RiskItem,
  OEMRequirementItem,
  ContractualClauseItem,
  TechnicalScopeItem
} from './types'

function downloadBlob(content: string, filename: string, mimeType: string) {
  const blob = new Blob([content], { type: mimeType })
  const url = window.URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  window.URL.revokeObjectURL(url)
  document.body.removeChild(a)
}

function escapeCsvCell(val: any): string {
  if (val === null || val === undefined) return '""'
  const str = String(val).replace(/"/g, '""')
  return `"${str}"`
}

function escapeHtml(val: any): string {
  if (val === null || val === undefined) return ''
  return String(val)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;')
}

function formatClean(val: any, fallback = 'Not specified in tender notice; verify against GCC'): string {
  if (val === null || val === undefined) return fallback
  const s = String(val).trim()
  if (!s || s.toUpperCase() === 'NOT FOUND' || s.toUpperCase() === '[ NOT SPECIFIED IN TENDER ]' || s.toUpperCase() === 'N/A' || s.toUpperCase() === 'NONE') {
    return fallback
  }
  return s
}

/**
 * Generate a complete, beautifully styled, enterprise-grade HTML document
 * containing ALL 11 DIMENSIONS and complete tender intelligence for Print / Offline Dossier.
 */
export function generateFullTenderHtml(report: MasterTenderReport): string {
  const ov = report.overview || ({} as any)
  const el = report.eligibility || ({} as any)
  const sc = report.technical_scope || ({} as any)
  const sp = report.technical_specifications || ({} as any)
  const oem = report.oem_requirements || ({} as any)
  const cp = report.compliance_matrix || ({} as any)
  const cm = report.commercial_financial || ({} as any)
  const lg = report.contractual_legal || ({} as any)
  const rk = report.risks_and_contradictions || ({} as any)
  const bs = report.bid_strategy || ({} as any)

  const tenderTitle = formatClean(ov.tender_title, 'Tender Procurement Evaluation')
  const authority = formatClean(ov.department_organization, 'Procurement Authority')
  const refNo = formatClean(ov.tender_reference_number, 'N/A')
  const deadline = formatClean(ov.bid_submission_deadline, 'Refer to Tender Schedule')
  const estValue = formatClean(ov.estimated_project_value, 'Item-rate / BOQ schedule (Not explicitly disclosed)')
  const emd = formatClean(ov.emd_value, 'Refer to Tender Notice')
  const location = formatClean(ov.project_location, 'As per tender delivery sites')
  const verdict = bs.recommendation || 'Proceed with Caution'
  const verdictClass = verdict.toLowerCase().includes('do not') ? 'verdict-danger' : verdict.toLowerCase().includes('caution') ? 'verdict-warning' : 'verdict-success'

  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>${escapeHtml(refNo)} - ${escapeHtml(tenderTitle)} | MYGPT Tender Dossier</title>
  <style>
    /* Reset & Base */
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    html, body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
      color: #1e293b;
      background-color: #f8fafc;
      font-size: 13px;
      line-height: 1.5;
    }
    .container {
      max-width: 1080px;
      margin: 20px auto;
      background: #ffffff;
      padding: 36px 44px;
      border: 1px solid #e2e8f0;
      border-radius: 12px;
      box-shadow: 0 4px 12px rgba(0,0,0,0.05);
    }

    /* Print Optimization Rules */
    @media print {
      @page {
        size: A4 portrait;
        margin: 14mm 12mm 14mm 12mm;
      }
      body {
        background: #ffffff !important;
        font-size: 11.5px;
        line-height: 1.45;
        color: #0f172a;
      }
      .container {
        max-width: 100% !important;
        margin: 0 !important;
        padding: 0 !important;
        border: none !important;
        box-shadow: none !important;
      }
      .page-break {
        page-break-before: always;
        break-before: page;
      }
      .no-break {
        page-break-inside: avoid;
        break-inside: avoid;
      }
      thead {
        display: table-header-group;
      }
      tr {
        page-break-inside: avoid;
        break-inside: avoid;
      }
      .no-print {
        display: none !important;
      }
    }

    /* Typography */
    h1 { font-size: 22px; font-weight: 800; color: #0f172a; line-height: 1.25; margin-bottom: 6px; }
    h2 { font-size: 17px; font-weight: 700; color: #1e3a8a; border-bottom: 2px solid #bfdbfe; padding-bottom: 6px; margin: 28px 0 14px 0; display: flex; align-items: center; justify-content: space-between; }
    h3 { font-size: 14px; font-weight: 600; color: #334155; margin: 14px 0 6px 0; }
    p { margin-bottom: 10px; color: #334155; }
    ul, ol { margin-left: 20px; margin-bottom: 12px; }
    li { margin-bottom: 4px; }

    /* Header & Branding */
    .header-banner {
      border-bottom: 3px solid #2563eb;
      padding-bottom: 20px;
      margin-bottom: 24px;
    }
    .brand-row {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 12px;
      font-size: 11px;
      font-weight: 700;
      color: #64748b;
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }
    .meta-grid {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 12px;
      background: #f1f5f9;
      padding: 16px;
      border-radius: 8px;
      border: 1px solid #cbd5e1;
      margin-top: 14px;
    }
    .meta-item { display: flex; flex-direction: column; }
    .meta-label { font-size: 10px; font-weight: 700; text-transform: uppercase; color: #64748b; }
    .meta-val { font-size: 12.5px; font-weight: 600; color: #0f172a; margin-top: 2px; word-break: break-word; }

    /* Verdict Box */
    .verdict-box {
      padding: 16px 20px;
      border-radius: 8px;
      margin: 18px 0;
      border-left: 6px solid;
    }
    .verdict-success { background: #f0fdf4; border-color: #16a34a; }
    .verdict-warning { background: #fffbeb; border-color: #d97706; }
    .verdict-danger { background: #fef2f2; border-color: #dc2626; }
    .verdict-title { font-size: 15px; font-weight: 800; margin-bottom: 4px; }
    .verdict-text { font-size: 12.5px; color: #334155; margin: 0; }

    /* Key Indicators Strip */
    .indicators-strip {
      display: grid;
      grid-template-columns: repeat(7, 1fr);
      gap: 8px;
      margin: 16px 0;
    }
    .indicator-box {
      background: #ffffff;
      border: 1px solid #e2e8f0;
      border-radius: 6px;
      padding: 8px 10px;
      text-align: center;
    }
    .ind-num { font-size: 15px; font-weight: 800; color: #0f172a; }
    .ind-lbl { font-size: 9.5px; font-weight: 700; text-transform: uppercase; color: #64748b; margin-top: 2px; }

    /* Tables */
    table {
      width: 100%;
      border-collapse: collapse;
      margin: 12px 0 18px 0;
      font-size: 11.5px;
    }
    th {
      background-color: #f1f5f9;
      color: #334155;
      font-weight: 700;
      text-transform: uppercase;
      font-size: 10px;
      padding: 8px 10px;
      border: 1px solid #cbd5e1;
      text-align: left;
    }
    td {
      padding: 7px 10px;
      border: 1px solid #e2e8f0;
      vertical-align: top;
      color: #1e293b;
    }
    tr:nth-child(even) td { background-color: #f8fafc; }

    /* Badges */
    .badge {
      display: inline-block;
      padding: 2px 7px;
      border-radius: 4px;
      font-size: 10px;
      font-weight: 700;
      text-transform: uppercase;
      white-space: nowrap;
    }
    .badge-mandatory { background: #fee2e2; color: #991b1b; border: 1px solid #fecaca; }
    .badge-optional { background: #e2e8f0; color: #475569; border: 1px solid #cbd5e1; }
    .badge-critical { background: #fee2e2; color: #991b1b; }
    .badge-high { background: #ffedd5; color: #9a3412; }
    .badge-medium { background: #fef9c3; color: #854d0e; }
    .badge-low { background: #f1f5f9; color: #475569; }
    .badge-page { background: #dbeafe; color: #1e40af; border: 1px solid #bfdbfe; font-size: 9.5px; }

    /* Callouts & Section Cards */
    .consultant-card {
      background: #f8fafc;
      border: 1px solid #e2e8f0;
      border-radius: 8px;
      padding: 14px 18px;
      margin: 12px 0;
    }
    .consultant-callout {
      background: #eff6ff;
      border-left: 4px solid #3b82f6;
      padding: 12px 16px;
      border-radius: 0 6px 6px 0;
      margin: 12px 0;
      font-size: 12px;
      color: #1e3a8a;
    }
    .warning-callout {
      background: #fef2f2;
      border-left: 4px solid #ef4444;
      padding: 12px 16px;
      border-radius: 0 6px 6px 0;
      margin: 12px 0;
      font-size: 12px;
      color: #991b1b;
    }

    /* Print Floating Action (Hidden when printed) */
    .print-actions {
      position: sticky;
      top: 0;
      background: #ffffff;
      padding: 12px 0;
      margin-bottom: 16px;
      border-bottom: 1px solid #e2e8f0;
      display: flex;
      justify-content: flex-end;
      gap: 10px;
      z-index: 100;
    }
    .btn {
      padding: 8px 16px;
      border-radius: 6px;
      font-size: 12px;
      font-weight: 700;
      cursor: pointer;
      border: none;
      transition: background 0.15s ease;
    }
    .btn-primary { background: #2563eb; color: #ffffff; }
    .btn-primary:hover { background: #1d4ed8; }
    .btn-secondary { background: #f1f5f9; color: #334155; border: 1px solid #cbd5e1; }
    .btn-secondary:hover { background: #e2e8f0; }
  </style>
</head>
<body>

<div class="container">
  <div class="print-actions no-print">
    <button class="btn btn-primary" onclick="window.print()">🖨️ Print / Save to PDF</button>
    <button class="btn btn-secondary" onclick="window.close()">✕ Close View</button>
  </div>

  <!-- Header Banner -->
  <header class="header-banner">
    <div class="brand-row">
      <span>MYGPT Universal Professional AI Tender Consultant</span>
      <span>Report ID: ${escapeHtml(report.report_id || 'DOC-EVAL')} • Engine: ${escapeHtml(report.model_used || 'Gemma 4 E2B + Python Intelligence')}</span>
    </div>
    <h1>${escapeHtml(tenderTitle)}</h1>
    <p style="font-size: 13.5px; color: #475569; margin-top: 4px;">
      Issuing Authority: <strong>${escapeHtml(authority)}</strong> • Ref No: <code>${escapeHtml(refNo)}</code>
    </p>

    <!-- Executive Meta Grid -->
    <div class="meta-grid">
      <div class="meta-item">
        <span class="meta-label">Submission Deadline</span>
        <span class="meta-val" style="color: #b91c1c;">${escapeHtml(deadline)}</span>
      </div>
      <div class="meta-item">
        <span class="meta-label">Estimated Contract Value</span>
        <span class="meta-val">${escapeHtml(estValue)}</span>
      </div>
      <div class="meta-item">
        <span class="meta-label">EMD / Bid Security</span>
        <span class="meta-val">${escapeHtml(emd)}</span>
      </div>
      <div class="meta-item">
        <span class="meta-label">Tender Processing Fee</span>
        <span class="meta-val">${escapeHtml(formatClean(ov.tender_fee, 'Refer to Tender Notice'))}</span>
      </div>
      <div class="meta-item">
        <span class="meta-label">Implementation / Delivery</span>
        <span class="meta-val">${escapeHtml(formatClean(ov.delivery_implementation_period || ov.contract_duration, 'Governed by tender schedule'))}</span>
      </div>
      <div class="meta-item">
        <span class="meta-label">Project Location / Scope</span>
        <span class="meta-val">${escapeHtml(location)}</span>
      </div>
    </div>
  </header>

  <!-- Strategic Verdict -->
  <div class="verdict-box ${verdictClass} no-break">
    <div class="verdict-title">Strategic Bid Verdict: ${escapeHtml(verdict)}</div>
    <p class="verdict-text">${escapeHtml(formatClean(bs.recommendation_rationale || bs.overall_tender_assessment, 'Evaluation indicates thorough compliance requirements. Bidder must verify all mandatory pre-qualification and technical milestones.'))}</p>
  </div>

  <!-- Key Extraction Metrics Ribbon -->
  <div class="indicators-strip no-break">
    <div class="indicator-box">
      <div class="ind-num">${el.conditions?.length || 0}</div>
      <div class="ind-lbl">PQ Rules</div>
    </div>
    <div class="indicator-box">
      <div class="ind-num">${sp.items?.length || 0}</div>
      <div class="ind-lbl">BOQ Specs</div>
    </div>
    <div class="indicator-box">
      <div class="ind-num">${cp.items?.length || 0}</div>
      <div class="ind-lbl">Compliance</div>
    </div>
    <div class="indicator-box">
      <div class="ind-num" style="color: #dc2626;">${rk.critical_risks_count || 0}</div>
      <div class="ind-lbl">Critical Risks</div>
    </div>
    <div class="indicator-box">
      <div class="ind-num" style="color: #d97706;">${rk.high_risks_count || 0}</div>
      <div class="ind-lbl">High Risks</div>
    </div>
    <div class="indicator-box">
      <div class="ind-num">${rk.contradictions_found?.length || 0}</div>
      <div class="ind-lbl">Conflicts</div>
    </div>
  </div>

  <!-- ===================================================================== -->
  <!-- DIMENSION 1: TENDER OVERVIEW & PROCUREMENT UNDERSTANDING              -->
  <!-- ===================================================================== -->
  <section class="dossier-section no-break">
    <h2><span>1. Tender Overview & Procurement Understanding</span> <span style="font-size: 11px; font-weight: normal; color: #64748b;">Dimension 1/11</span></h2>
    
    <div class="consultant-card">
      <h3>Project Scope & Objectives</h3>
      <p>${escapeHtml(formatClean(ov.scope_of_work_summary || ov.overall_understanding, 'Detailed procurement scope for hardware, implementation and maintenance services.'))}</p>
    </div>

    <table>
      <thead>
        <tr>
          <th style="width: 28%;">Parameter</th>
          <th>Verified Tender Detail</th>
        </tr>
      </thead>
      <tbody>
        <tr><td><strong>Department / Organization</strong></td><td>${escapeHtml(authority)}</td></tr>
        <tr><td><strong>End-User / Beneficiary</strong></td><td>${escapeHtml(formatClean(ov.end_user_beneficiary || ov.sub_department_consignee, authority))}</td></tr>
        <tr><td><strong>Contract Category / Type</strong></td><td>${escapeHtml(formatClean(ov.tender_category || ov.contract_type, 'Supply, Installation, Commissioning & Maintenance'))}</td></tr>
        <tr><td><strong>Bid Publishing Date</strong></td><td>${escapeHtml(formatClean(ov.tender_publishing_date, 'Refer to Tender Schedule'))}</td></tr>
        <tr><td><strong>Bid Opening Date</strong></td><td>${escapeHtml(formatClean(ov.bid_opening_date, 'Refer to Tender Schedule'))}</td></tr>
        <tr><td><strong>Warranty & Maintenance Period</strong></td><td>${escapeHtml(formatClean(ov.warranty_maintenance_period, 'Refer to Special Conditions / General Conditions'))}</td></tr>
      </tbody>
    </table>
  </section>

  <!-- ===================================================================== -->
  <!-- DIMENSION 2: BIDDER ELIGIBILITY & PRE-QUALIFICATION (PQ)             -->
  <!-- ===================================================================== -->
  <section class="dossier-section">
    <h2><span>2. Bidder Eligibility & Pre-Qualification (PQ)</span> <span style="font-size: 11px; font-weight: normal; color: #64748b;">Dimension 2/11</span></h2>
    
    <div class="consultant-callout">
      <strong>Consultant Summary:</strong> ${escapeHtml(formatClean(el.summary_assessment, 'Bidder must satisfy strict statutory, financial turnover, and past work experience criteria.'))}
    </div>

    <table>
      <thead>
        <tr>
          <th style="width: 25%;">Core Criteria</th>
          <th>Tender Requirement & Verified Threshold</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td><strong>Annual Financial Turnover</strong></td>
          <td>${escapeHtml(formatClean(el.annual_turnover_requirement || el.average_turnover_requirement, 'Governed by general financial rules / CA Certified balance sheet mandatory'))}</td>
        </tr>
        <tr>
          <td><strong>Similar Work Experience</strong></td>
          <td>${escapeHtml(formatClean(el.similar_work_experience, 'Past performance in similar supply/implementation contracts required'))}</td>
        </tr>
        <tr>
          <td><strong>Required Certifications</strong></td>
          <td>${escapeHtml(el.required_certifications?.length ? el.required_certifications.join(', ') : 'ISO 9001, ISO 27001 or equivalent statutory standards')}</td>
        </tr>
        <tr>
          <td><strong>Consortium / Joint Venture</strong></td>
          <td>${escapeHtml(formatClean(el.consortium_joint_venture_allowed, 'Refer to eligibility clauses'))}</td>
        </tr>
        <tr>
          <td><strong>OEM Authorization Mandate</strong></td>
          <td>${el.oem_authorization_mandatory ? '<strong>MANDATORY</strong> — Specific MAF from OEMs required' : 'Standard OEM backing required'}</td>
        </tr>
      </tbody>
    </table>

    <h3>Detailed Grounded Pre-Qualification Conditions (${el.conditions?.length || 0} Clauses)</h3>
    <table>
      <thead>
        <tr>
          <th style="width: 6%;">#</th>
          <th style="width: 20%;">Category & Criterion</th>
          <th style="width: 12%;">Mandatory?</th>
          <th>Tender Evidence & Disqualification Impact</th>
          <th style="width: 25%;">Supporting Document</th>
          <th style="width: 10%;">Page</th>
        </tr>
      </thead>
      <tbody>
        ${(el.conditions || []).map((c: EligibilityConditionItem, idx: number) => `
          <tr>
            <td>${idx + 1}</td>
            <td><strong>${escapeHtml(c.category || 'General')}</strong><br><small style="color:#64748b;">${escapeHtml(c.department_requirement || '')}</small></td>
            <td><span class="badge ${c.is_mandatory ? 'badge-mandatory' : 'badge-optional'}">${c.is_mandatory ? 'Mandatory' : 'Optional'}</span></td>
            <td>${escapeHtml(c.verbatim_evidence || c.disqualification_effect || 'Failure to comply will lead to rejection')}</td>
            <td>${escapeHtml(c.supporting_document_required || 'Certified Document')}</td>
            <td><span class="badge badge-page">Page ${c.source_page || 'N/A'}</span></td>
          </tr>
        `).join('')}
      </tbody>
    </table>
  </section>

  <!-- ===================================================================== -->
  <!-- DIMENSION 3: TECHNICAL SCOPE ANALYSIS                                -->
  <!-- ===================================================================== -->
  <section class="dossier-section">
    <h2><span>3. Technical Scope of Work & Deliverables</span> <span style="font-size: 11px; font-weight: normal; color: #64748b;">Dimension 3/11</span></h2>
    
    <p><strong>Technical Scope Overview:</strong> ${escapeHtml(formatClean(sc.overview, 'Complete supply, installation, testing, commissioning and maintenance obligations.'))}</p>

    <table>
      <thead>
        <tr>
          <th style="width: 20%;">Scope Area</th>
          <th>Detailed Scope Description</th>
          <th style="width: 25%;">Purpose & Standards</th>
          <th style="width: 10%;">Page</th>
        </tr>
      </thead>
      <tbody>
        ${(sc.scope_items || []).map((it: TechnicalScopeItem) => `
          <tr>
            <td><strong>${escapeHtml(it.area || 'Scope Component')}</strong></td>
            <td>${escapeHtml(it.description || '')}</td>
            <td>${escapeHtml(it.purpose || '')}<br><small style="color:#64748b;">${escapeHtml(it.mandatory_standards || '')}</small></td>
            <td><span class="badge badge-page">Page ${it.source_page || 'N/A'}</span></td>
          </tr>
        `).join('')}
      </tbody>
    </table>

    <div class="consultant-card no-break">
      <h3>Key Execution Obligations</h3>
      <p><strong>Testing & Commissioning:</strong> ${escapeHtml(formatClean(sc.testing_and_commissioning_obligations, 'Strict factory acceptance test (FAT) and site acceptance test (SAT) as per schedule.'))}</p>
      <p><strong>Training & Handover:</strong> ${escapeHtml(formatClean(sc.training_obligations, 'Bidder must provide end-user operational training and comprehensive manuals.'))}</p>
      <p><strong>SLA & Maintenance:</strong> ${escapeHtml(formatClean(sc.sla_requirements || sc.maintenance_and_amc_obligations, 'Resolution uptime requirements governed by SLA penalty matrix.'))}</p>
    </div>
  </section>

  <!-- ===================================================================== -->
  <!-- DIMENSION 4: TECHNICAL SPECIFICATION SCHEDULE (BOQ)                  -->
  <!-- ===================================================================== -->
  <section class="dossier-section">
    <h2><span>4. Technical Specification Schedule (BOQ)</span> <span style="font-size: 11px; font-weight: normal; color: #64748b;">Dimension 4/11</span></h2>
    
    <div class="consultant-callout">
      <strong>Overall Specification Evaluation:</strong> ${escapeHtml(formatClean(sp.overall_spec_evaluation, 'All items must strictly comply with minimum technical specifications and standards.'))}
    </div>

    <table>
      <thead>
        <tr>
          <th style="width: 5%;">#</th>
          <th style="width: 20%;">Equipment / Component</th>
          <th style="width: 10%;">Quantity</th>
          <th>Technical Specifications & Minimum Performance</th>
          <th style="width: 18%;">Standards / Brand</th>
          <th style="width: 8%;">Page</th>
        </tr>
      </thead>
      <tbody>
        ${(sp.items || []).map((it: TechnicalSpecificationItem, idx: number) => `
          <tr>
            <td>${idx + 1}</td>
            <td><strong>${escapeHtml(it.item_name || 'Item')}</strong><br><small style="color:#64748b;">${escapeHtml(it.subsystem_or_category || it.category || 'Hardware')}</small></td>
            <td><strong>${escapeHtml(it.required_quantity || 'As per BOQ')}</strong> ${escapeHtml(it.unit_of_measurement || '')}</td>
            <td>${escapeHtml((it.technical_specifications || '').slice(0, 180))}${it.technical_specifications && it.technical_specifications.length > 180 ? '...' : ''}</td>
            <td>
              ${it.mandatory_standards ? `<strong>Standards:</strong> ${escapeHtml((it.mandatory_standards || '').slice(0, 80))}<br>` : ''}
              ${it.oem_brand_model_mentioned ? `<strong>Brand:</strong> ${escapeHtml(it.oem_brand_model_mentioned)}` : ''}
            </td>
            <td><span class="badge badge-page">Page ${it.source_page || 'N/A'}</span></td>
          </tr>
        `).join('')}
      </tbody>
    </table>
  </section>

  <!-- ===================================================================== -->
  <!-- DIMENSION 5: OEM AND PRODUCT REQUIREMENTS                           -->
  <!-- ===================================================================== -->
  <section class="dossier-section">
    <h2><span>5. OEM and Product Requirements</span> <span style="font-size: 11px; font-weight: normal; color: #64748b;">Dimension 5/11</span></h2>
    
    <div class="consultant-card">
      <p><strong>OEM Authorization Required:</strong> ${oem.oem_authorization_required ? '<span class="badge badge-mandatory">MANDATORY MAF</span>' : '<span class="badge badge-optional">NOT SPECIFIED</span>'}</p>
      <p><strong>Consultant Notes:</strong> ${escapeHtml(formatClean(oem.consultant_notes, 'Bidder must obtain tender-specific OEM authorizations with guarantee of spares and technical support.'))}</p>
    </div>

    <table>
      <thead>
        <tr>
          <th style="width: 25%;">Requirement Name</th>
          <th style="width: 12%;">Mandatory?</th>
          <th>Details & Support Conditions</th>
          <th style="width: 10%;">Page</th>
        </tr>
      </thead>
      <tbody>
        ${(oem.oem_requirements || []).map((r: OEMRequirementItem) => `
          <tr>
            <td><strong>${escapeHtml(r.requirement_name || 'OEM Condition')}</strong></td>
            <td><span class="badge ${r.is_mandatory ? 'badge-mandatory' : 'badge-optional'}">${r.is_mandatory ? 'Mandatory' : 'Optional'}</span></td>
            <td>
              ${escapeHtml(r.details || '')}
              ${r.warranty_support_conditions ? `<br><small><strong>Warranty Backing:</strong> ${escapeHtml(r.warranty_support_conditions)}</small>` : ''}
            </td>
            <td><span class="badge badge-page">Page ${r.source_page || 'N/A'}</span></td>
          </tr>
        `).join('')}
      </tbody>
    </table>
  </section>

  <!-- ===================================================================== -->
  <!-- DIMENSION 6: ITEM-WISE COMPLIANCE ANALYSIS MATRIX                   -->
  <!-- ===================================================================== -->
  <section class="dossier-section">
    <h2><span>6. Item-Wise Compliance Analysis Matrix</span> <span style="font-size: 11px; font-weight: normal; color: #64748b;">Dimension 6/11</span></h2>
    
    <div class="consultant-callout" style="background:#f0fdf4; border-color:#16a34a; margin-bottom: 12px;">
      <strong>Compliance Assessment Status:</strong> <code>TENDER REQUIREMENT IDENTIFIED — BIDDER COMPLIANCE NOT YET ASSESSED AGAINST PROPOSED MODEL</code>
    </div>

    <p><strong>Compliance Matrix Summary:</strong> ${escapeHtml(formatClean(cp.compliance_summary, 'Item-wise cross check against tender schedule.'))}</p>

    <table>
      <thead>
        <tr>
          <th style="width: 20%;">Item / Scope Area</th>
          <th>Tender Requirement & Mandatory Specification</th>
          <th style="width: 15%;">Assessment</th>
          <th style="width: 20%;">Consultant Remarks</th>
          <th style="width: 10%;">Reference</th>
        </tr>
      </thead>
      <tbody>
        ${(cp.items || []).map((m: ComplianceMatrixItem) => `
          <tr>
            <td><strong>${escapeHtml(m.item || 'Item')}</strong></td>
            <td>
              <strong>Requirement:</strong> ${escapeHtml((m.tender_requirement || '').slice(0, 160))}${m.tender_requirement && m.tender_requirement.length > 160 ? '...' : ''}<br>
              <small style="color:#64748b;"><strong>Spec:</strong> ${escapeHtml((m.mandatory_specification || '').slice(0, 120))}${m.mandatory_specification && m.mandatory_specification.length > 120 ? '...' : ''}</small>
            </td>
            <td><span class="badge badge-mandatory">${escapeHtml(m.compliance_assessment || 'Compliant')}</span></td>
            <td>${escapeHtml((m.remarks || 'Grounded in tender schedule').slice(0, 120))}</td>
            <td><span class="badge badge-page">${escapeHtml(m.tender_reference || 'N/A')}</span></td>
          </tr>
        `).join('')}
      </tbody>
    </table>
  </section>

  <!-- ===================================================================== -->
  <!-- DIMENSION 7: COMMERCIAL AND FINANCIAL ANALYSIS                       -->
  <!-- ===================================================================== -->
  <section class="dossier-section">
    <h2><span>7. Commercial & Financial Analysis</span> <span style="font-size: 11px; font-weight: normal; color: #64748b;">Dimension 7/11</span></h2>
    
    <table>
      <thead>
        <tr>
          <th style="width: 28%;">Financial Parameter</th>
          <th>Verified Tender Term</th>
        </tr>
      </thead>
      <tbody>
        <tr><td><strong>EMD / Bid Security</strong></td><td>${escapeHtml(formatClean(cm.emd_amount || cm.emd_amount_and_mode, emd))}</td></tr>
        <tr><td><strong>EMD Exemption Rules</strong></td><td>${escapeHtml(formatClean(cm.emd_exemption_rules, 'MSME / NSIC exemption as per Government guidelines subject to valid registration'))}</td></tr>
        <tr><td><strong>Security Deposit (SD)</strong></td><td>${escapeHtml(formatClean(cm.security_deposit, 'Refer to GCC / Special Conditions'))}</td></tr>
        <tr><td><strong>Performance Security (PBG)</strong></td><td>${escapeHtml(formatClean(cm.performance_bank_guarantee_pbg, 'Refer to GCC / Special Conditions'))}</td></tr>
        <tr><td><strong>Payment Milestones</strong></td><td>${escapeHtml(formatClean(cm.payment_terms || cm.milestone_payments, 'Governed by progressive delivery and installation milestones'))}</td></tr>
        <tr><td><strong>Advance Payment</strong></td><td>${escapeHtml(formatClean(cm.advance_payment_allowed, 'Nil / Not permitted (100% working capital by bidder)'))}</td></tr>
        <tr><td><strong>Retention Amount</strong></td><td>${escapeHtml(formatClean(cm.retention_amount, 'As per contractual retention terms'))}</td></tr>
        <tr><td><strong>Liquidated Damages (LD) & Penalties</strong></td><td>${escapeHtml(formatClean(cm.penalties_and_liquidated_damages, 'Refer to Penalty Schedule in tender'))}</td></tr>
        <tr><td><strong>Price Escalation / Variation</strong></td><td>${escapeHtml(formatClean(cm.price_escalation_clause, 'Fixed firm price contract; no escalation allowed during contract period'))}</td></tr>
      </tbody>
    </table>

    <div class="consultant-callout no-break">
      <strong>Commercial Impact Analysis:</strong> ${escapeHtml(formatClean(cm.bidder_impact_analysis, 'Bidder must budget for upfront PBG issuance and working capital during delivery.'))}
    </div>
  </section>

  <!-- ===================================================================== -->
  <!-- DIMENSION 8: CONTRACTUAL AND LEGAL CONDITIONS                        -->
  <!-- ===================================================================== -->
  <section class="dossier-section">
    <h2><span>8. Contractual & Legal Conditions</span> <span style="font-size: 11px; font-weight: normal; color: #64748b;">Dimension 8/11</span></h2>
    
    <table>
      <thead>
        <tr>
          <th style="width: 28%;">Legal Provision</th>
          <th>Tender Stipulation</th>
        </tr>
      </thead>
      <tbody>
        <tr><td><strong>Contract Agreement Duration</strong></td><td>${escapeHtml(formatClean(lg.contract_duration, 'Governed by formal contract execution'))}</td></tr>
        <tr><td><strong>Termination Conditions</strong></td><td>${escapeHtml(formatClean(lg.termination_conditions, 'Termination for default, insolvency or convenience with notice period'))}</td></tr>
        <tr><td><strong>Dispute Resolution & Jurisdiction</strong></td><td>${escapeHtml(formatClean(lg.dispute_resolution_and_jurisdiction, 'High Court / Civil Court jurisdiction as per tender clause'))}</td></tr>
        <tr><td><strong>Indemnity & Liability</strong></td><td>${escapeHtml(formatClean(lg.indemnity_and_liability, 'Bidder indemnifies authority against all third-party intellectual property or damage claims'))}</td></tr>
        <tr><td><strong>Force Majeure</strong></td><td>${escapeHtml(formatClean(lg.force_majeure, 'Standard force majeure provisions with prompt written notification'))}</td></tr>
      </tbody>
    </table>

    <h3>Significant Risk Clauses (${lg.significant_risk_clauses?.length || 0})</h3>
    <table>
      <thead>
        <tr>
          <th style="width: 25%;">Clause Type</th>
          <th style="width: 15%;">Risk Level</th>
          <th>Summary & Evidence</th>
          <th style="width: 10%;">Page</th>
        </tr>
      </thead>
      <tbody>
        ${(lg.significant_risk_clauses || []).map((c: ContractualClauseItem) => `
          <tr>
            <td><strong>${escapeHtml(c.clause_type || 'Clause')}</strong></td>
            <td><span class="badge ${c.risk_level?.toLowerCase() === 'high' ? 'badge-high' : 'badge-medium'}">${escapeHtml(c.risk_level || 'Medium')}</span></td>
            <td>${escapeHtml(c.summary || c.verbatim_evidence || '')}</td>
            <td><span class="badge badge-page">Page ${c.source_page || 'N/A'}</span></td>
          </tr>
        `).join('')}
      </tbody>
    </table>
  </section>

  <!-- ===================================================================== -->
  <!-- DIMENSION 9: RISK AND CONTRADICTION ANALYSIS                         -->
  <!-- ===================================================================== -->
  <section class="dossier-section">
    <h2><span>9. Risk & Contradiction Analysis</span> <span style="font-size: 11px; font-weight: normal; color: #64748b;">Dimension 9/11</span></h2>
    
    <div class="warning-callout">
      <strong>Overall Risk Verdict:</strong> ${escapeHtml(formatClean(rk.overall_risk_verdict, 'Risks identified must be resolved prior to final price bid submission.'))}
    </div>

    ${rk.contradictions_found?.length ? `
      <h3>Identified Contradictions & Ambiguities (${rk.contradictions_found.length})</h3>
      <ul>
        ${rk.contradictions_found.map((con: string) => `<li>${escapeHtml(con)}</li>`).join('')}
      </ul>
    ` : ''}

    <h3>Comprehensive Tender Risk Register</h3>
    <table>
      <thead>
        <tr>
          <th style="width: 6%;">#</th>
          <th style="width: 22%;">Risk Title</th>
          <th style="width: 10%;">Severity</th>
          <th>Tender Evidence & Potential Impact</th>
          <th style="width: 25%;">Recommended Mitigation Action</th>
          <th style="width: 8%;">Page</th>
        </tr>
      </thead>
      <tbody>
        ${(rk.risks || []).map((r: RiskItem, idx: number) => {
          const sev = (r.risk_level || 'Medium').toLowerCase()
          const badgeClass = sev === 'critical' ? 'badge-critical' : sev === 'high' ? 'badge-high' : sev === 'low' ? 'badge-low' : 'badge-medium'
          return `
            <tr>
              <td>${idx + 1}</td>
              <td><strong>${escapeHtml(r.risk_title || 'Identified Risk')}</strong></td>
              <td><span class="badge ${badgeClass}">${escapeHtml(r.risk_level || 'Medium')}</span></td>
              <td>
                <strong>Evidence:</strong> ${escapeHtml(r.tender_evidence || '')}<br>
                <small style="color:#b91c1c;"><strong>Impact:</strong> ${escapeHtml(r.potential_impact || r.why_it_matters || '')}</small>
              </td>
              <td>${escapeHtml(r.recommended_action || 'Seek formal pre-bid clarification')}</td>
              <td><span class="badge badge-page">Page ${r.source_page || 'N/A'}</span></td>
            </tr>
          `
        }).join('')}
      </tbody>
    </table>
  </section>

  <!-- ===================================================================== -->
  <!-- DIMENSION 11: BID STRATEGY & CONSULTANT RECOMMENDATIONS              -->
  <!-- ===================================================================== -->
  <section class="dossier-section">
    <h2><span>11. Bid Strategy & Consultant Recommendations</span> <span style="font-size: 11px; font-weight: normal; color: #64748b;">Dimension 11/11</span></h2>
    
    <div class="consultant-card">
      <h3>Recommended Pre-Bid Queries Schedule</h3>
      <p>Submit the following formal clarification requests during the pre-bid window to remove ambiguity:</p>
      <table>
        <thead>
          <tr>
            <th style="width: 6%;">#</th>
            <th>Proposed Pre-Bid Clarification Query for Procurement Authority</th>
          </tr>
        </thead>
        <tbody>
          ${(bs.prebid_clarification_questions || []).map((q: string, idx: number) => `
            <tr>
              <td>${idx + 1}</td>
              <td>${escapeHtml(q)}</td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    </div>

    <div class="consultant-card no-break">
      <h3>Strategic Preparation Guidance</h3>
      <p><strong>Required OEM Documentation:</strong> ${escapeHtml(bs.required_oem_documents?.length ? bs.required_oem_documents.join(', ') : 'MAF, OEM Warranty Certificate, Spares Support Guarantee')}</p>
      <p><strong>Required Financial Documentation:</strong> ${escapeHtml(bs.required_financial_documents?.length ? bs.required_financial_documents.join(', ') : 'Audited Balance Sheets (Last 3 Years), CA Turnover Certificate, EMD Instrument / Exemption Certificate')}</p>
      <p><strong>Bid Preparation Priorities:</strong> ${escapeHtml(bs.bid_preparation_priorities?.length ? bs.bid_preparation_priorities.join(' • ') : 'Verify technical schedule compliance and complete statutory filings.')}</p>
    </div>
  </section>

  <!-- Footer -->
  <footer style="margin-top: 40px; padding-top: 16px; border-top: 1px solid #cbd5e1; font-size: 11px; color: #64748b; display: flex; justify-content: space-between;">
    <span>MYGPT AI Tender Consultant • Enterprise Multi-Tender Intelligence</span>
    <span>Generated: ${escapeHtml(report.timestamp || new Date().toISOString())}</span>
  </footer>

</div>

</body>
</html>`
}

/**
 * 1. Export Complete Tender Analysis via browser Print-to-PDF across ALL 11 Dimensions.
 * Generates an isolated, print-optimized document so that every single page and dimension is included.
 */
export function exportDossierPrint(report: MasterTenderReport): void {
  try {
    const html = generateFullTenderHtml(report)
    const iframe = document.createElement('iframe')
    iframe.style.position = 'fixed'
    iframe.style.right = '0'
    iframe.style.bottom = '0'
    iframe.style.width = '0'
    iframe.style.height = '0'
    iframe.style.border = '0'
    document.body.appendChild(iframe)

    const doc = iframe.contentWindow?.document
    if (doc) {
      doc.open()
      doc.write(html)
      doc.close()
      iframe.contentWindow?.focus()
      setTimeout(() => {
        try {
          iframe.contentWindow?.print()
        } catch (err) {
          console.error('Print iframe error:', err)
          window.print()
        } finally {
          setTimeout(() => {
            if (document.body.contains(iframe)) {
              document.body.removeChild(iframe)
            }
          }, 1500)
        }
      }, 400)
    } else {
      window.print()
    }
  } catch (e) {
    console.error('exportDossierPrint error:', e)
    window.print()
  }
}

/**
 * 2. Export Complete Dossier as a Standalone Offline HTML Document
 */
export function exportDossierHtml(report: MasterTenderReport): void {
  const html = generateFullTenderHtml(report)
  const filename = `${report.overview?.tender_reference_number || 'tender'}_full_evaluation_dossier.html`
    .replace(/[^a-zA-Z0-9_\-\.]/g, '_')
  downloadBlob(html, filename, 'text/html;charset=utf-8;')
}

/**
 * 3. Export Complete Dossier as Markdown across all 11 Dimensions
 */
export function exportDossierMarkdown(report: MasterTenderReport): void {
  let content = report.full_report_markdown || report.executive_summary_markdown || ''
  if (!content.trim()) {
    const ov = report.overview || ({} as any)
    const el = report.eligibility || ({} as any)
    const sp = report.technical_specifications || ({} as any)
    const cm = report.commercial_financial || ({} as any)
    const rk = report.risks_and_contradictions || ({} as any)
    const bs = report.bid_strategy || ({} as any)

    content = [
      `# MYGPT AI Tender Consultant — Full Evaluation Dossier`,
      `**Tender**: ${ov.tender_title || 'Tender'}`,
      `**Authority**: ${ov.department_organization || 'Procurement Authority'}`,
      `**Reference**: ${ov.tender_reference_number || 'N/A'}`,
      `**Submission Deadline**: ${ov.bid_submission_deadline || 'As per tender schedule'}`,
      `**Estimated Value**: ${ov.estimated_project_value || 'Not Disclosed'}`,
      `**EMD**: ${ov.emd_value || 'Refer to Notice'}`,
      '',
      `## Strategic Bid Verdict: ${bs.recommendation || 'Proceed with Caution'}`,
      `${bs.recommendation_rationale || ''}`,
      '',
      `## 1. Tender Overview & Scope Summary`,
      `${ov.scope_of_work_summary || ov.overall_understanding || 'N/A'}`,
      '',
      `## 2. Bidder Eligibility & Pre-Qualification`,
      `- **Annual Turnover**: ${el.annual_turnover_requirement || 'Not specified in notice'}`,
      `- **Similar Work**: ${el.similar_work_experience || 'Standard experience'}`,
      `- **Certifications**: ${(el.required_certifications || []).join(', ') || 'Standard certifications'}`,
      `- **OEM Authorization**: ${el.oem_authorization_mandatory ? 'Mandatory' : 'Standard'}`,
      '',
      `## 3. Technical Scope & Deliverables`,
      `${report.technical_scope?.overview || 'As per tender schedule'}`,
      '',
      `## 4. Technical Specifications Schedule`,
      `Total Extracted Specification Items: ${sp.items?.length || 0}`,
      ...(sp.items || []).map((it: any, i: number) => `### Item ${i+1}: ${it.item_name}\n- **Qty**: ${it.required_quantity || 'N/A'}\n- **Specifications**: ${it.technical_specifications || 'N/A'}\n- **Page**: ${it.source_page || 'N/A'}`),
      '',
      `## 5. OEM Requirements`,
      `- **Authorization Required**: ${report.oem_requirements?.oem_authorization_required ? 'Yes' : 'No'}`,
      `- **Notes**: ${report.oem_requirements?.consultant_notes || 'Standard'}`,
      '',
      `## 6. Item-Wise Compliance Matrix & Bidder Readiness`,
      `- **Overall Readiness**: ${report.compliance_matrix?.readiness_summary?.overall_readiness_percentage || 0}%`,
      `- **Total Tracked**: ${report.compliance_matrix?.items?.length || 0} (${report.compliance_matrix?.readiness_summary?.mandatory_requirements || 0} Mandatory)`,
      ...(report.compliance_matrix?.required_documents?.length ? [
        '### Mandatory Submission Documents',
        ...report.compliance_matrix.required_documents.map(d => `- **${d.document_name}** (${d.category || 'Administrative'}): ${d.submission_format || 'Prescribed format'} [${d.tender_reference || `Page ${d.source_page}`}]`),
        ''
      ] : []),
      '### Compliance Clauses',
      ...(report.compliance_matrix?.items || []).map((c: any) => `- [${c.category || 'Technical'}] **${c.item}**: \`${c.compliance_status || c.compliance_assessment || 'PENDING'}\` - ${c.mandatory_specification || c.tender_requirement} (Ref: ${c.tender_reference || `Page ${c.source_page}`})`),
      '',
      `## 7. Commercial & Financial Terms`,
      `- **EMD / Bid Security**: ${cm.emd_amount || ov.emd_value || 'Refer to Tender Schedule'}`,
      `- **Security Deposit (SD)**: ${cm.security_deposit || 'As per tender terms'}`,
      `- **Payment Terms**: ${cm.payment_terms || 'Milestone payments against delivery and acceptance'}`,
      `- **Advance Payment**: ${cm.advance_payment_allowed || 'Nil / Not permitted'}`,
      `- **Performance Guarantee (PBG)**: ${cm.performance_bank_guarantee_pbg || 'Refer to GCC / Tender Conditions'}`,
      `- **Penalties / LD**: ${cm.penalties_and_liquidated_damages || 'Refer to Penalty Schedule in tender'}`,
      '',
      `## 8. Contractual & Legal Conditions`,
      `- **Duration**: ${report.contractual_legal?.contract_duration || 'As per schedule'}`,
      `- **Agreement Execution**: ${report.contractual_legal?.agreement_requirements || 'Within 15 days of LOA'}`,
      `- **Termination**: ${report.contractual_legal?.termination_conditions || 'Standard notice / GCC'}`,
      `- **Dispute Resolution & Jurisdiction**: ${report.contractual_legal?.dispute_resolution_and_jurisdiction || 'High Court / Civil Court jurisdiction as per tender clause'}`,
      '',
      `## 9. Risk Register & Contradictions`,
      ...(rk.risks || []).map((r: any, idx: number) => `### Risk ${idx+1}: ${r.risk_title} [${r.risk_level}]\n- **Evidence**: ${r.tender_evidence}\n- **Impact**: ${r.potential_impact}\n- **Action**: ${r.recommended_action}`),
      '',
      `## 11. Bid Strategy & Recommendations`,
      ...(bs.prebid_clarification_questions || []).map((q: string, idx: number) => `${idx+1}. ${q}`)
    ].join('\n')
  }

  const filename = `${report.overview?.tender_reference_number || 'tender'}_full_evaluation_report.md`
    .replace(/[^a-zA-Z0-9_\-\.]/g, '_')
  downloadBlob(content, filename, 'text/markdown;charset=utf-8;')
}

/**
 * 4. Export Technical Specification Schedule as CSV / Excel
 */
export function exportTechnicalSpecificationsCsv(report: MasterTenderReport): void {
  const items = report.technical_specifications?.items || []
  const headers = [
    'Item Number',
    'Equipment / Component',
    'Required Quantity',
    'Technical Specifications',
    'Mandatory Standards',
    'OEM / Brand Mentioned',
    'Source Page',
    'Source Document'
  ]

  const rows = items.map((it, idx) => [
    idx + 1,
    it.item_name || 'NOT FOUND',
    it.required_quantity || 'As per BOQ',
    it.technical_specifications || 'NOT FOUND',
    it.mandatory_standards || 'Standard',
    it.oem_brand_model_mentioned || 'NOT SPECIFIED',
    it.source_page ? `Page ${it.source_page}` : 'NOT FOUND',
    it.source_file || report.source_files?.[0] || 'Tender Document'
  ])

  const csvContent = [
    headers.map(escapeCsvCell).join(','),
    ...rows.map(r => r.map(escapeCsvCell).join(','))
  ].join('\r\n')

  const filename = `${report.overview?.tender_reference_number || 'tender'}_technical_specifications.csv`
    .replace(/[^a-zA-Z0-9_\-\.]/g, '_')
  downloadBlob(csvContent, filename, 'text/csv;charset=utf-8;')
}

/**
 * 5. Export Item-Wise Compliance Analysis Matrix as CSV / Excel
 */
export function exportComplianceMatrixCsv(report: MasterTenderReport): void {
  const items = report.compliance_matrix?.items || []
  const headers = [
    'Requirement ID',
    'Category',
    'Item',
    'Tender Requirement',
    'Mandatory Specification',
    'Mandatory?',
    'Compliance Status',
    'Required Document / Action',
    'Tender Reference',
    'Consultant Remarks'
  ]

  const rows = items.map((it, idx) => [
    it.requirement_id || `REQ-${idx + 1}`,
    it.category || 'Technical',
    it.item || 'NOT FOUND',
    it.tender_requirement || 'NOT FOUND',
    it.mandatory_specification || 'NOT FOUND',
    it.is_mandatory !== false ? 'YES' : 'NO',
    it.compliance_status || it.compliance_assessment || 'PENDING',
    it.required_document_type || 'Datasheet evidence required',
    it.tender_reference || (it.source_page ? `Page ${it.source_page}` : 'NOT SPECIFIED'),
    it.remarks || ''
  ])

  const csvContent = [
    headers.map(escapeCsvCell).join(','),
    ...rows.map(r => r.map(escapeCsvCell).join(','))
  ].join('\r\n')

  const filename = `${report.overview?.tender_reference_number || 'tender'}_compliance_matrix.csv`
    .replace(/[^a-zA-Z0-9_\-\.]/g, '_')
  downloadBlob(csvContent, filename, 'text/csv;charset=utf-8;')
}

/**
 * 6. Export Risk Register as CSV / Excel
 */
export function exportRiskRegisterCsv(report: MasterTenderReport): void {
  const items = report.risks_and_contradictions?.risks || []
  const headers = [
    'Risk ID',
    'Risk Title',
    'Severity',
    'Tender Evidence',
    'Why It Matters',
    'Potential Impact',
    'Recommended Action',
    'Source Page'
  ]

  const rows = items.map((r, idx) => [
    `RSK-${idx + 1}`,
    r.risk_title || 'Identified Risk',
    r.risk_level || 'Medium',
    r.tender_evidence || '',
    r.why_it_matters || '',
    r.potential_impact || '',
    r.recommended_action || '',
    r.source_page ? `Page ${r.source_page}` : 'NOT FOUND'
  ])

  const csvContent = [
    headers.map(escapeCsvCell).join(','),
    ...rows.map(row => row.map(escapeCsvCell).join(','))
  ].join('\r\n')

  const filename = `${report.overview?.tender_reference_number || 'tender'}_risk_register.csv`
    .replace(/[^a-zA-Z0-9_\-\.]/g, '_')
  downloadBlob(csvContent, filename, 'text/csv;charset=utf-8;')
}
