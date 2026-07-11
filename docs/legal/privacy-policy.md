> **DRAFT — NOT LEGAL ADVICE.** Prepared by an AI assistant as a product-accurate starting point
> for your lawyer, not a replacement for one. Do not publish until reviewed by counsel.
> Bracketed items must be filled in or confirmed before use.

# Privacy Policy

**Effective date:** [DATE]
**Controller:** [Company Legal Name] ("Company," "we," "us"), contactable at
[privacy contact email]

This Privacy Policy explains what personal data Company collects from people who register an
account or otherwise log into Phantom Investigator (the "Service"), why, and what rights you
have over it.

This policy covers **account data belonging to the people who use the Service's console**
(registered users). It does not cover the operational data (Jira tickets, logs, metrics, deploy
history) that a Client organization connects for investigation — that is covered by the
[Data Processing Agreement](./data-processing-agreement.md), under which Company acts as a
processor on the Client's instructions, not as the controller.

## 1. What We Collect

| Data | Source | Purpose |
|---|---|---|
| Username, email address | You, at registration, or via Google Sign-In | Account identification, login, communication about your account |
| Password (hashed with argon2 — we never store or can recover the plaintext) | You, at registration | Authentication |
| Google account ID | Google, if you use "Continue with Google" | Alternate sign-in, linked to your account by verified email |
| Session cookie (signed, not readable by us as arbitrary storage) | Generated at login | Keeps you signed in for up to 12 hours |
| Monthly spend limit, if you set one | You, via account settings | Lets you cap your own AI-provider usage |
| Investigation history, connected integration configuration (Jira/GitHub/Azure/AWS/Prometheus/
Loki endpoints and credentials — credentials encrypted at rest) | You, when you configure the
Service | Operating the Service for your account |

We do not collect payment card data directly (see Terms of Service, Section 5, regarding
billing).

## 2. How We Use It

- To provide, maintain, and secure the Service.
- To authenticate you and enforce that your data (clients, deployments, investigations, and
  integration credentials) is visible only to your account.
- To communicate with you about your account or material changes to the Service.
- To enforce your own configured spend limits.

We do not sell personal data, and we do not use your account data to train AI models.

## 3. Third Parties We Share Data With

Registering an account does not, by itself, send your personal data to an AI provider. However,
using the Service — triggering an investigation — does send the content of that investigation
(which may include your account's identifiers in logs/traces) to:

- **Your configured AI provider** (Anthropic, OpenAI, or an OpenAI-compatible endpoint you
  specify) — processes the investigation content to generate a postmortem.
- **Voyage AI** (or your configured embedding provider) — processes runbook text to generate
  search embeddings.
- **Self-hosted Langfuse** — an observability tool Company operates on its own infrastructure to
  trace and debug the Service's AI calls; not a separate company, but noted here since it stores
  a copy of prompts/outputs.
- **Google**, only if you use "Continue with Google" — receives the OAuth request per Google's
  own privacy policy.

A current list of sub-processors is maintained in the
[Data Processing Agreement's appendix](./data-processing-agreement.md#appendix-a-sub-processors).

## 4. Retention

Account data is retained for as long as your account is active. [POLICY TO BE FINALIZED: e.g.,
investigation history and traces are retained for 12 months and then purged, or retained until
account deletion.] You may request deletion at any time (Section 6).

## 5. Security

Passwords are hashed with argon2 and never stored or transmitted in plaintext. Integration
credentials you save (e.g., API tokens) are encrypted at rest. Access to your account's data is
restricted to your own session; other registered users cannot see your clients, deployments,
investigations, or credentials. See the Data Processing Agreement for the fuller technical and
organizational measures.

## 6. Your Rights

Depending on your jurisdiction (e.g., under the GDPR if you are in the EU/EEA/UK), you may have
the right to:

- access the personal data we hold about you;
- correct inaccurate data;
- request deletion of your account and associated data;
- export your data in a portable format;
- object to or restrict certain processing;
- lodge a complaint with your local data protection authority.

To exercise these rights, contact [privacy contact email]. [NOTE: as of this draft, the Service
does not yet have a self-service account-deletion or data-export feature in the UI — requests are
handled manually. Flag to engineering if this needs to become self-service before scaling.]

## 7. Cookies

The Service uses one strictly necessary cookie (`phantom_session`) to keep you signed in, and a
short-lived state cookie during Google Sign-In. Neither is used for advertising or cross-site
tracking, and neither requires cookie-consent-banner disclosure under most frameworks (which
generally exempt strictly necessary cookies) — [confirm with counsel if you later add analytics
or marketing cookies, which would change this].

## 8. International Transfers

[TO BE COMPLETED based on where you host the Service and where your AI/embedding providers
process data relative to your users' location — e.g., if you are in the EU and your AI provider
processes data in the US, reference that provider's Standard Contractual Clauses / GDPR DPA.]

## 9. Children's Privacy

The Service is intended for business use by adults acting on behalf of an organization and is not
directed at children. We do not knowingly collect personal data from children.

## 10. Changes to This Policy

We will post updates here and, for material changes, notify account holders by email.

## 11. Contact

[privacy contact email] — for any question about this policy or to exercise your rights.
