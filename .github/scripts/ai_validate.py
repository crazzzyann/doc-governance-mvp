import argparse
import os
import sys
import json
import requests

from textwrap import dedent
from openai import OpenAI

GITHUB_API_BASE = "https://api.github.com"

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
        return ""
    resp.raise_for_status()
    return resp.text

def call_llm(system_prompt, user_prompt):
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    resp = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
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
    # ignore errors if label not created yet etc.
    if resp.status_code not in (200, 201):
        print(f"Warning: could not add label {label}: {resp.status_code} {resp.text}", file=sys.stderr)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True)
    parser.add_argument("--pr-number", required=True, type=int)
    args = parser.parse_args()

    github_token = os.environ["GITHUB_TOKEN"]

    pr_data, files_data = get_pr_details(args.repo, args.pr_number, github_token)

    # Only care if business_context.md is modified
    touched_bc = any(
        f["filename"] == "docs/business_context.md" for f in files_data
    )
    if not touched_bc:
        print("Business context doc not changed; skipping AI validation.")
        return 0

    base_sha = pr_data["base"]["sha"]
    head_sha = pr_data["head"]["sha"]

    original_text = get_file_content_at_ref(args.repo, "docs/business_context.md", base_sha, github_token)
    modified_text = get_file_content_at_ref(args.repo, "docs/business_context.md", head_sha, github_token)

    pr_body = pr_data.get("body") or ""

    system_prompt = dedent("""
    You are an AI governance validator for a Business Context document.
    Your job: evaluate whether the justification for a proposed change is
    logically sound, specific, and supported by any references.

    You will be given:
    - original_doc: the previous version of the document
    - modified_doc: the new proposed version
    - justification: text from the PR, including references

    You MUST respond in pure JSON with this schema:
    {
      "decision": "APPROVE" | "ESCALATE" | "REJECT",
      "confidence": float between 0 and 1,
      "reasons": [ "short bullet strings" ],
      "risk_flags": [ "missing_reference" | "contradiction_with_existing_text" | "too_vague" | "policy_violation" | "other" ]
    }

    Semantics:
    - APPROVE: justification is clear, specific, and aligns with the change.
    - ESCALATE: not clearly wrong, but ambiguous/risky enough that a human should review.
    - REJECT: justification is clearly weak, irrelevant, or contradicts the document with no support.
    """)

    user_prompt = json.dumps({
        "original_doc": original_text,
        "modified_doc": modified_text,
        "justification": pr_body[:8000]  # avoid overly huge
    })

    try:
        result = call_llm(system_prompt, user_prompt)
    except Exception as e:
        # If LLM call itself fails, escalate to manual review
        msg = f"AI validation failed due to error: {e}. Escalating to manual review."
        print(msg, file=sys.stderr)
        comment_on_pr(args.repo, args.pr_number, msg, github_token)
        add_label(args.repo, args.pr_number, "needs-manual-review", github_token)
        # Do NOT block merge because the infra failed, not the content
        return 0

    decision = result.get("decision", "ESCALATE")
    reasons = result.get("reasons", [])
    risk_flags = result.get("risk_flags", [])
    confidence = result.get("confidence", 0.0)

    comment_body = (
        "### AI Governance Check Result\n"
        f"**Decision:** `{decision}`\n"
        f"**Confidence:** `{confidence:.2f}`\n\n"
        f"**Reasons:**\n" +
        "".join(f"- {r}\n" for r in reasons) +
        "\n**Risk Flags:**\n" +
        ( "".join(f"- {f}\n" for f in risk_flags) or "- none\n" )
    )

    comment_on_pr(args.repo, args.pr_number, comment_body, github_token)

    if decision == "APPROVE":
        add_label(args.repo, args.pr_number, "ai-approved", github_token)
        print("AI APPROVED change.")
        return 0
    elif decision == "ESCALATE":
        add_label(args.repo, args.pr_number, "needs-manual-review", github_token)
        print("AI ESCALATED change for manual review.")
        return 0
    else:  # REJECT or anything else
        add_label(args.repo, args.pr_number, "ai-rejected", github_token)
        print("AI REJECTED change. Failing the check.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
