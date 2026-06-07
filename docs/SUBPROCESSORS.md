# Subprocessors

This register is the default subprocessor list for `Learning Hub`. It must be adjusted per actual deployment model.

## Default product-level subprocessors

| Subprocessor | Purpose | Data category | Default status |
| --- | --- | --- | --- |
| OVHcloud or chosen VPS/IaaS provider | infrastructure hosting | application data, database, media | environment-specific |
| Let's Encrypt | TLS certificate issuance | domain and certificate metadata | active in standard deployment |
| Microsoft services, where customer links are enabled | Teams, Outlook, Planner deep links or identity activation | limited identity and collaboration metadata | optional |
| OpenAI-compatible AI provider, where configured | AI assistance and content support | prompts, context snippets, operational metadata | optional |

## Important usage note

This repository supports multiple deployment shapes:

- fully self-hosted without external AI
- self-hosted with customer-managed Microsoft identity
- self-hosted with optional external AI provider

Therefore:

- this list is a baseline, not a final customer disclosure
- each customer-facing version must reflect the actual enabled integrations

## Update checklist

Before sharing externally, confirm:

- actual infrastructure provider
- actual DNS/TLS setup
- whether AI provider is enabled
- whether Microsoft identity is enabled
- whether email is routed through a third-party provider
