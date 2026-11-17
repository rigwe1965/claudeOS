# Security policy

## Reporting a problem

Please do not open a public issue for a security problem. Email **info@facyke.com** with:

- what you found and where (file, endpoint or page),
- how to reproduce it,
- what an attacker could do with it.

You will get a first reply within 5 working days. We fix confirmed problems in a patch release and credit you in the changelog if you want that.

## What is in scope

The code in this repository: the Flask API, the Streamlit dashboard, the memory and sync layers, the MCP server, and the standalone skills in `skills/`.

## What to remember when you run it

- Set your own `CLAUDEOS_SECRET_KEY` (a long random value) and your own `ANTHROPIC_API_KEY` in `.env`. Never commit `.env`.
- Run the API behind HTTPS if it is reachable from outside your machine.
- The standalone skills send nothing anywhere except the web searches and page fetches you can see in the session.

## Supported versions

Only the latest release and `main` receive fixes.
