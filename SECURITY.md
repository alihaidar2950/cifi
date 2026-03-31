# Security Policy

## Supported Versions

Only the latest release is supported with security updates.

## Reporting a Vulnerability

If you discover a security vulnerability in CIFI, please report it responsibly:

1. **Do not** open a public GitHub issue for security vulnerabilities
2. Email **ali.haidar.2950@gmail.com** with:
   - A description of the vulnerability
   - Steps to reproduce
   - Potential impact
3. You will receive an acknowledgment within 48 hours
4. A fix will be prioritized based on severity

## Security Considerations

### Tier 1 — GitHub Action
- `GITHUB_TOKEN` is the only required secret — provided automatically by GitHub Actions
- LLM API keys (if using paid providers) must be stored as GitHub Actions secrets
- CI logs may contain sensitive data — a scrubbing layer strips secrets before sending to external LLM APIs
- Ollama provider available for fully local analysis — no data leaves the GitHub runner

### Tier 2 — Backend API
- All endpoints require API key authentication via `X-API-Key` header
- Input validation on all API endpoints (Pydantic)
- Rate limiting on analysis endpoints
- Database credentials managed via environment variables — never committed to source
- HTTPS enforced via the deployment platform (Fly.io / Railway / Cloud Run)

## Best Practices for Users

- Never hardcode API keys or secrets in workflow files
- Use GitHub Actions secrets for all sensitive configuration
- Review the analysis output before acting on suggested fixes
- If using Ollama (self-hosted LLM), no data leaves your infrastructure

---

Thank you for helping keep CIFI and its users safe.
