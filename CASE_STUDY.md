# Case study: VendorGuard

> Fill the [brackets] with YOUR real numbers from the demo dashboard. Do not invent figures.

## The problem
Companies that onboard vendors receive stacks of contracts, tax certificates and insurance documents. Reviewing each
one by hand is slow and inconsistent, and handing the job to an AI naively is risky: vendor documents are written by
outsiders, so a document can contain text that tries to trick the AI reviewer into approving it.

## What I built
A full-stack review system: vendors upload documents, an AI agent classifies and audits them, clear cases are decided
automatically, and exceptions go to a human reviewer who can override with a required reason. Every override is
logged and exportable.

## Key design decisions
1. **The model extracts, code decides.** The LLM never produces the final verdict. Approval requires every
   deterministic check to pass, no security flags, and high confidence.
2. **Fail closed.** If the AI is down, returns garbage, or sees suspicious text, the document goes to a person.
3. **Hostile input is assumed.** I wrote a red-team test suite (hijacked model, fabricated Tax ID, injected
   instructions, hidden characters) and run it in CI on every push.
4. **Vendors get no feedback beyond the outcome**, so attackers cannot tune payloads.
5. **Human oversight is measurable.** The dashboard tracks how often humans overturn the AI.

## Results (from the demo)
- Automation rate: [X]% of documents decided without a human
- AI agreement: [Y]% of automatic decisions upheld by reviewers
- Security: [N] injection attempts and fabricated IDs caught in my test set, [0] reached "Approved"
- Backend tests: 58 passing, including the attack, OCR and alerting suites

## Real-world hardening (v1.1)
- **Scanned documents:** an OCR fallback reads scans and images. Because OCR can misread digits and can surface faint
  hidden text, OCR'd files face a stricter approval threshold and the same injection scan.
- **Incident response:** a suspected injection attempt triggers a signed Slack/Teams/webhook alert. The alert never
  contains document text, vendor-controlled titles are escaped so they cannot @-mention a channel, and a per-vendor cap
  prevents an attacker from flooding the security team.

## Stack
Next.js 15 · Tailwind · FastAPI · SQLAlchemy · Postgres · Redis + RQ · LangGraph · Groq (Llama 3.3 70B) · Docker · GitHub Actions

## What I would do next
S3 storage, OCR for scanned PDFs, email notifications, SSO, and a labelled evaluation set to track accuracy over time.
