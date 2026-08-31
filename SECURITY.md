# Security Policy

## Secrets

Never commit `.env`, Telegram bot tokens, payment keys, wallet private keys, database passwords, or webhook secrets. Store them in the hosting provider's encrypted environment variables.

If a token is exposed, revoke it in BotFather immediately. Removing it from a later Git commit does not remove it from Git history.

## Payment activation

Payment integrations are disabled by two independent flags. Before activation:

1. Use a fresh HTTPS callback URL.
2. Validate signatures and invoice amount server-side.
3. Make verification idempotent.
4. Test success, failure, retry, timeout and replay cases in a sandbox.
5. Never store crypto private keys in this project.

## Data

Use PostgreSQL and encrypted backups for production. SQLite is appropriate for local development and small single-instance installations but not ephemeral hosting without a persistent volume.

## Reporting

Report vulnerabilities privately to the repository owner. Do not include real tokens, passwords or customer data in an issue.

