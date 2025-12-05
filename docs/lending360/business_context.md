# Business Context Document  
# Business Context Document  
_Project: Lending360 SME Credit Platform_  
_Version: 1.0_  
_Last Updated: Initial Draft_

---

## 1. Overview

The Unified Customer Onboarding Platform (UCOP) aims to streamline the end-to-end onboarding process for retail and SME customers across all digital and assisted channels. Currently, onboarding journeys are fragmented, inconsistent across business units, and require manual interventions that lead to delays, drop-offs, and compliance risks.  

The goal of this program is to consolidate onboarding workflows, automate verification steps, improve regulatory compliance, and provide a unified experience across web, mobile, and partner channels.

---

## 2. Strategic Objectives

### 2.1 Primary Objectives
- Reduce onboarding completion time from **7–10 days to under 48 hours**.
- Achieve **customer onboarding success rate of ≥ 85%** within the first 6 months.
- Reduce manual document review effort by **40%** using automated KYC, fraud checks, and OCR.
- Ensure full compliance with 2023–2025 regulatory guidelines for KYC, AML, and data privacy.

### 2.2 Secondary Objectives
- Improve Net Promoter Score (NPS) for onboarding from **45 → 55** over 12 months.
- Provide real-time onboarding analytics to business, compliance, and risk teams.
- Enable self-service onboarding for SMEs with minimal manual touchpoints.

---

## 3. Current Challenges

- **Fragmented Systems:** Multiple legacy onboarding tools across business units with no centralized workflow.
- **High Manual Dependency:** Compliance and risk checks often done manually, creating delays.
- **Document Quality Issues:** Poor-quality scans and inconsistent document formats reduce automation accuracy.
- **Inconsistent Customer Journeys:** Different teams use different flows, causing confusion and misalignment.
- **Limited Observability:** No unified analytics layer, making it difficult to track bottlenecks and abandonment patterns.

---

## 4. Scope

### 4.1 In Scope
- Retail customer onboarding (digital and assisted)
- SME onboarding with KYC, AML, and risk checks
- OCR extraction and automated document classification
- Integration with fraud detection and credit engines
- Unified case management workflow

### 4.2 Out of Scope (Phase 1)
- Corporate onboarding
- International KYC variations
- Lending decision automation (beyond data collection)
- Cross-sell journey orchestration

---

## 5. Key Constraints

- Must comply with **RBI KYC/AML guidelines** and internal compliance frameworks.
- All data must be encrypted at rest and in transit (AES-256, TLS 1.2+).
- Solution must support peak load of **10,000 onboarding requests/day**.
- Document verification accuracy must be **≥ 90%** before reduction of manual review.
- Phase 1 delivery timeline capped at **16 weeks** from project start.

---

## 6. Dependencies

- Integration with Fraud Engine v2 (target delivery: Q2 2025)
- API gateway upgrade for partner channels
- Pending compliance sign-off for digital signature framework
- Availability of updated KYC ruleset from Risk team

---

## 7. Assumptions

- Customer-provided documents will follow standard formats (Aadhaar, PAN, GST).
- Risk and compliance teams will provide updated regulations within agreed timelines.
- Business teams will migrate legacy onboarding flows to the new platform post rollout.
- OCR engine will maintain ≥ 90% accuracy for readable documents.

---

## 8. Risks & Mitigations

### High Risks
1. **Regulatory delays**  
   _Mitigation:_ Parallel workshops with compliance team.

2. **OCR accuracy below acceptable levels**  
   _Mitigation:_ Hybrid human-in-loop review system for low-confidence extracts.

3. **Integration delays from partner systems**  
   _Mitigation:_ Provide stubbed integration layer for interim testing.

### Medium Risks
1. **Customer drop-offs during long KYC flows**  
   _Mitigation:_ Introduce progressive disclosure and save-and-resume.

2. **Operational resistance to workflow changes**  
   _Mitigation:_ Early training and rollout in pilot branches.

---

## 9. KPIs

- Average onboarding completion time (target: <48 hours)
- Onboarding success rate (target: ≥85%)
- Manual review time reduction (target: ≥40%)
- NPS improvement (45 → 55)
- OCR accuracy (≥90%)
- Compliance exceptions per 1,000 applications (target: <5)

---

## 10. Future Enhancements (Not Part of MVP)

- AI-driven anomaly detection for fraud risk scoring
- Auto-refinement of extracted fields using LLM cross-checking
- End-to-end assisted onboarding workflow for corporate accounts
- Multi-country onboarding compliance packs
- API productization for partner ecosystem onboarding

---

# Appendix: Document History

| Version | Date       | Author | Summary |
|--------|------------|--------|---------|
| 1.0    | YYYY-MM-DD | Team   | Initial creation |
