# Security

## Reporting a flaw

Please do not open a public issue for a security flaw. Write to **security@3adala.com** instead. The site's
`/.well-known/security.txt` gives its contact address, which is read too.

Say what you found, where (an address of the site, a file and line of this repository), and how to see it happen. We
read reports in Arabic, French and English.

We will:

- answer within five working days that the report has been read;
- tell you what we are doing about it, and when it is fixed;
- credit you when the fix is published, if you want to be named.

## What is in scope

- The site and its API, the MCP server at `/mcp`, and the sign-in for assistants (`/oauth/`, `/.well-known/`).
- The code in this repository, including the deploy templates in `deploy/`.

## What we ask

- Test against your own copy (the README's quick start runs the whole site on a sample), not against the live site.
- Do not read, change or delete other people's data, and stop as soon as you reach any.
- No load tests or automated scans against the live site: it serves readers from one small server, and many of them
  share one address on mobile networks.
- Give us a reasonable time to fix a flaw before you publish it.

Reports made in good faith under these rules will not be pursued.
