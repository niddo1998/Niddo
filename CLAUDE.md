# Niddo

Administración de consorcios: Flask (`app.py`) + Postgres en Neon + Vercel.

**Si te preguntan qué falta o qué está pendiente, leé [docs/PENDIENTES.md](docs/PENDIENTES.md).** Es la lista de lo que sólo puede hacer Pedro (cuentas, claves, decisiones). Cuando él te diga que hizo algo, actualizala.

**Antes de hacer nada, leé [docs/ESTADO.md](docs/ESTADO.md)** si ya está en `main` (llega con el PR #11). Tiene qué se hizo, las decisiones que no hay que revertir, cómo correr los tests y cómo trabaja Pedro: español rioplatense, una rama por cambio, preguntar antes de mergear o de suponer decisiones de producto.

Lo básico mientras tanto:

- Tests: `python3.13 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt && .venv/bin/python -m pytest -q`.
- Migraciones nuevas en `migraciones/NNN_nombre.sql`, sólo agregando; QA las corre sobre `schema.sql`.
- El repo es público: nada de secretos, datos de clientes ni detalles de vulnerabilidades.

El `AGENTS.md` del home de Pedro habla de Cloudflare Workers y D1: no aplica a este repo.
