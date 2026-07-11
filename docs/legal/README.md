Draft legal documents for Phantom Investigator, prepared as a starting point for attorney
review — not final, not legal advice. See the disclaimer at the top of each file.

- [`terms-of-service.md`](./terms-of-service.md) — the B2B agreement with each Client.
- [`privacy-policy.md`](./privacy-policy.md) — covers registered console-user account data
  (Company is Controller).
- [`data-processing-agreement.md`](./data-processing-agreement.md) — the GDPR Art. 28 contract
  covering Client Data processed on a Client's behalf (Company is Processor). **Get this one
  reviewed first** — it's the one that actually needs to be signed before real Client data flows
  through the Service.

## Before any of these go out to a real Client

1. Fill in every `[bracketed placeholder]` — legal entity name, jurisdiction, contact emails,
   fee structure, liability cap, retention periods, hosting provider.
2. Get all three reviewed by a lawyer licensed in your jurisdiction (Greece/EU, given GDPR
   applicability) — the DPA in particular assigns real regulatory liability.
3. Decide the actual processing location for the AI/embedding provider and hosting, then fill in
   the DPA's Section 5 (International Transfers) and Appendix A accordingly.
4. Build the account-deletion/data-export capability the Privacy Policy Section 6 currently
   describes as "handled manually" — becomes worth automating once you have more than a
   handful of accounts.
5. If any prospective Client's connected systems might contain health, financial, or other
   special-category/regulated data, stop and get a specific addendum in place before connecting
   them — see the DPA's Appendix B note.
