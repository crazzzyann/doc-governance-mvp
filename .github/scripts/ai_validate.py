import argparse
import os
import sys
import json
import requests
from textwrap import dedent
from openai import OpenAI

GITHUB_API_BASE = "https://api.github.com"

# ---- Governance config: extend here in future ----
GOVERNED_SUFFIXES = [
    "business_context.md",  # per-project business context
    "prd.md",               # future: per-project PRD
]


def is_governed_file(path: str) -> bool:
    """
    Decide whether this file should be governed by AI validation.
    For now: any markdown file whose name ends in one of the GOVERNED_SUFFIXES.
    """
    return any(path.endswith(suffix) for suffix in GOVERNED_SUFFIXES)


def extract_project_id(path: str) -> str:
    """
    Infer a project id from the path.
    Examples:
      docs/ucop/business_context.md      -> ucop
      docs/lending360/prd.md             -> lending360
      docs/business_contexts/ucop.md     -> ucop (fallback)
    """
    parts = path.split("/")

    if len(parts) >= 3 and parts[0] == "docs":
        # docs/<project>/business_context.md
        return parts[1]

    # Fallback for other structures. Best-effort.
    if len(parts) >= 2:
        # e.g. docs/ucop.md -> ucop
        return parts[-1].replace(".md", "")

    return "unknown"


def get_pr_details(repo, pr_number, github_token):
    headers = {
        "Authorization": f"Bearer {github_token}",
        "Accept": "application/vnd.github+json",
    }
    pr_url = f"{GITHUB_API_BASE}/repos/{repo}/pulls/{pr_number}"
    files_url = f"{pr_url}/files"

    pr_resp = requests.get(pr_url, headers=headers)
    pr_resp.raise_for_status()
    pr_data = pr_resp.json()

    files_resp = requests.get(files_url, headers=headers)
    files_resp.raise_for_status()
    files_data = files_resp.json()

    return pr_data, files_data


def get_file_content_at_ref(repo, path, ref, github_token):
    headers = {
        "Authorization": f"Bearer {github_token}",
        "Accept": "application/vnd.github.raw"
    }
    url = f"{GITHUB_API_BASE}/repos/{repo}/contents/{path}?ref={ref}"
    resp = requests.get(url, headers=headers)
    if resp.status_code == 404:
        # File might not exist in base (new file)
        return ""
    resp.raise_for_status()
    return resp.text


def call_llm(system_prompt, user_payload: dict):
    """
    Call GPT-4.1-mini with strict JSON response.
    user_payload is a dict containing:
      project_id, file_path, original_doc, modified_doc, justification
    """
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    resp = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(user_payload)},
        ],
        temperature=0.1,
        response_format={"type": "json_object"},
    )
    return json.loads(resp.choices[0].message.content)


def comment_on_pr(repo, pr_number, body, github_token):
    headers = {
        "Authorization": f"Bearer {github_token}",
        "Accept": "application/vnd.github+json",
    }
    url = f"{GITHUB_API_BASE}/repos/{repo}/issues/{pr_number}/comments"
    resp = requests.post(url, headers=headers, json={"body": body})
    resp.raise_for_status()


def add_label(repo, pr_number, label, github_token):
    headers = {
        "Authorization": f"Bearer {github_token}",
        "Accept": "application/vnd.github+json",
    }
    url = f"{GITHUB_API_BASE}/repos/{repo}/issues/{pr_number}/labels"
    resp = requests.post(url, headers=headers, json={"labels": [label]})
    if resp.status_code not in (200, 201):
        print(
            f"Warning: could not add label {label}: "
            f"{resp.status_code} {resp.text}",
            file=sys.stderr,
        )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True)
    parser.add_argument("--pr-number", required=True, type=int)
    args = parser.parse_args()

    github_token = os.environ["GITHUB_TOKEN"]

    pr_data, files_data = get_pr_details(args.repo, args.pr_number, github_token)

    # Determine which governed files were touched in this PR
    governed_files = [
        f["filename"]
        for f in files_data
        if is_governed_file(f["filename"])
    ]

    if not governed_files:
        print("No governed business context / PRD files changed; skipping AI validation.")
        return 0

    base_sha = pr_data["base"]["sha"]
    head_sha = pr_data["head"]["sha"]
    pr_body = pr_data.get("body") or ""

    system_prompt = dedent("""
    You are an AI governance validator for product/business context documents
    (e.g., Business Context, PRDs) across multiple projects.

    For each file, you receive:
      - project_id: short identifier for the project (e.g., ucop)
      - file_path: path to the document within the repo
      - original_doc: previous version of the document
      - modified_doc: proposed new version
      - justification: text from the Pull Request body, including references

    Your job:
      - Evaluate whether the justification logically and specifically supports the
        proposed changes in the modified_doc relative to original_doc.
      - Evaluate whether the justification is sufficiently clear, not hand-wavy,
        and references any relevant evidence or data if appropriate.
      - Identify any obvious contradictions or risky changes that are not properly justified.

    You MUST respond in pure JSON with this schema:
    {
      "decision": "APPROVE" | "ESCALATE" | "REJECT",
      "confidence": float between 0 and 1,
      "reasons": [ "short bullet strings" ],
      "risk_flags": [
        "missing_reference" | "contradiction_with_existing_text" |
        "too_vague" | "policy_violation" | "other"
      ]
    }

    Semantics:
      - APPROVE:
          Justification is clear, specific, and aligned with the change. No major
          risks or contradictions identified.
      - ESCALATE:
          Not clearly wrong, but ambiguous/risky enough that a human should review
          before accepting. Use this for borderline or complex cases.
      - REJECT:
          Justification is clearly weak, irrelevant, internally inconsistent, or
          contradicts the document with no reasonable support.

    Be strict about vague justifications like "sounds better", "more professional",
    or "minor tweak" without explaining business impact or reason.
    """)

    results = {}  # file_path -> LLM result dict

    for path in governed_files:
        project_id = extract_project_id(path)
        original_text = get_file_content_at_ref(args.repo, path, base_sha, github_token)
        modified_text = get_file_content_at_ref(args.repo, path, head_sha, github_token)

        payload = {
            "project_id": project_id,
            "file_path": path,
            "original_doc": original_text,
            "modified_doc": modified_text,
            "justification": pr_body[:8000],  # avoid going insane with length
        }

        try:
            print(f"Running AI validation for governed file: {path}")
            result = call_llm(system_prompt, payload)
        except Exception as e:
            # Infra issue -> escalate this file to manual review
            print(
                f"AI validation failed for {path} due to error: {e}. "
                f"Escalating to manual review for this file.",
                file=sys.stderr,
            )
            result = {
                "decision": "ESCALATE",
                "confidence": 0.0,
                "reasons": [f"AI call failed: {e}"],
                "risk_flags": ["other"],
            }

        results[path] = result

    # Aggregate decisions across all governed files
    decisions = [r.get("decision", "ESCALATE") for r in results.values()]

    if any(d == "REJECT" for d in decisions):
        overall_decision = "REJECT"
    elif all(d == "APPROVE" for d in decisions):
        overall_decision = "APPROVE"
    else:
        overall_decision = "ESCALATE"

    # Build a combined markdown comment
    lines = []
    lines.append("### AI Governance Check Result (Multi-Document)\n")
    lines.append(f"**Overall Decision:** `{overall_decision}`\n")

    for path, result in results.items():
        decision = result.get("decision", "ESCALATE")
        confidence = result.get("confidence", 0.0)
        reasons = result.get("reasons", [])
        risk_flags = result.get("risk_flags", [])

        project_id = extract_project_id(path)

        lines.append(f"\n#### File: `{path}` (project: `{project_id}`)\n")
        lines.append(f"- **Decision:** `{decision}`\n")
        lines.append(f"- **Confidence:** `{confidence:.2f}`\n")
        lines.append("- **Reasons:**\n")
        if reasons:
            for r in reasons:
                lines.append(f"  - {r}\n")
        else:
            lines.append("  - (none provided)\n")
        lines.append("- **Risk Flags:**\n")
        if risk_flags:
            for fflag in risk_flags:
                lines.append(f"  - {fflag}\n")
        else:
            lines.append("  - (none)\n")

    comment_body = "\n".join(lines)

    # Post comment once with all results
    comment_on_pr(args.repo, args.pr_number, comment_body, github_token)

    # Apply labels based on overall decision
    if overall_decision == "APPROVE":
        add_label(args.repo, args.pr_number, "ai-approved", github_token)
        print("AI APPROVED all governed document changes.")
        return 0
    elif overall_decision == "ESCALATE":
        add_label(args.repo, args.pr_number, "needs-manual-review", github_token)
        print("AI ESCALATED at least one governed document for manual review.")
        return 0
    else:  # REJECT
        add_label(args.repo, args.pr_number, "ai-rejected", github_token)
        print("AI REJECTED at least one governed document. Failing the check.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
