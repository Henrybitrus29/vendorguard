def sample_text(vendor: str, tax_id: str, has_terms: bool = True) -> str:
    """Fake vendor document text, used for seeded demo rows (no real client data)."""
    terms = (
        "6. Liability and Indemnity. The Vendor shall indemnify the Client against third-party claims.\n"
        "7. Service Levels. The Vendor guarantees 99.9% monthly uptime and a 4-hour incident response SLA.\n"
        if has_terms
        else "6. General. The parties will cooperate in good faith.\n"
    )
    return (
        f"MASTER SERVICES AGREEMENT (DEMO DOCUMENT)\n\nBetween {vendor} (the Vendor) and Example Client Inc.\n\n"
        f"1. Parties. {vendor} is a registered company. Tax ID / EIN: {tax_id}.\n"
        "2. Services. The Vendor will provide software development services.\n"
        "3. Term. Twelve months from the effective date.\n"
        "4. Fees. Invoiced monthly, payable within 30 days.\n"
        "5. Confidentiality. Both parties keep shared information confidential.\n"
        f"{terms}\nThis is fabricated sample content for a portfolio demo.\n"
    )
