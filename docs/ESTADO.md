# Niddo: estado y traspaso

**Actualizado:** 16 de octubre de 2026
**Producción:** https://niddo-eta.vercel.app
**Repo:** https://github.com/niddo1998/Niddo

Este documento es para quien siga el trabajo, con o sin un agente: qué se hizo, en qué estado quedó cada cosa y qué falta, en orden. Si sos un agente, leé también [Para el agente que sigue](#para-el-agente-que-sigue) antes de tocar nada.

---

## 1. Qué se hizo

El objetivo era dejar Niddo listo para que administraciones reales lo prueben. El punto de partida fue la auditoría [docs/auditorias/2026-10-16-que-falta-para-pilotos.md](auditorias/2026-10-16-que-falta-para-pilotos.md), que compara Niddo con Octopus, CONSO, Unitify y ExpensasPagas y con la normativa de CABA.

| PR | Qué cambió | Estado |
|---|---|---|
| [#5](https://github.com/niddo1998/Niddo/pull/5) | QR de CABA en la liquidación, matrícula RPA del admin, envío de mails por lotes, saldo anterior por unidad, avisos push y mora automática, Sentry, términos y privacidad, landing nueva | Mergeado |
| [#6](https://github.com/niddo1998/Niddo/pull/6) | El botón de la landing abre el registro de Auth0; Mercado Pago queda apagado; los legales no muestran razón social, CUIT ni domicilio | Mergeado |
| [#7](https://github.com/niddo1998/Niddo/pull/7) | El mail de contacto es niddo1998@gmail.com | Mergeado |
| [#8](https://github.com/niddo1998/Niddo/pull/8) | Botón para probar Sentry | Cerrado sin mergear (no se usa Sentry) |
| [#9](https://github.com/niddo1998/Niddo/pull/9) | Se saca Sentry del código y de la política de privacidad | Mergeado |
| [#10](https://github.com/niddo1998/Niddo/pull/10) | Los botones de la landing dicen «Empezar Demo» | Mergeado |
| [#11](https://github.com/niddo1998/Niddo/pull/11) | Los mails salen gratis por Gmail; este documento y los scripts de `scripts/` | **Abierto**, falta probar y mergear |

### Lo que ya anda en producción

- **Liquidación según CABA.** El PDF imprime un QR a `/l/<token>`, una página pública con los comprobantes del mes, el reglamento del consorcio y el Manual de Buenas Prácticas (Disp. DGDyPC 1146/2024 y 521/2025). También trae la matrícula RPA, el CUIT y la dirección del admin, que se cargan en Mi perfil, y la composición del saldo al cierre.
- **Reglamento por consorcio.** Se sube en Configuración y lo abre el QR.
- **Envío de la liquidación sin timeout.** Los mails salen todos juntos y los envíos se registran de una vez. El mail lleva el link a la liquidación, no el PDF adjunto.
- **Migrar desde otro sistema.** La planilla de carga masiva tiene la columna `saldo_anterior`, que también se puede cargar en la ficha de la unidad. Entra una sola vez, en la primera liquidación de la unidad.
- **Notificaciones push** (probadas en un iPhone el 16/10):
  - al instante: expensa nueva, pago aceptado o rechazado, reclamo respondido o resuelto, alta del vecino aprobada, y para el admin reclamos, mensajes, solicitudes y pagos informados;
  - programadas: recordatorio 3 días antes y el día del vencimiento, aviso de vencida y recordatorio de reserva 1 a 3 horas antes.
- **Mora automática.** El cron diario pasa a `vencido` el cobro impago después de los días de gracia del consorcio. El interés lo suma la liquidación siguiente, una sola vez.
- **Cron por GitHub Actions** ([.github/workflows/avisos.yml](../.github/workflows/avisos.yml)): todos los días a las 9:00 (Argentina) y cada hora. Se probó a mano el 16/10 y respondió bien.
- **Términos y privacidad** en `/terminos` y `/privacidad`.
- **Landing nueva** con la ruta Barrio del manual de marca, sin números inventados. «Empezar Demo» lleva a crear cuenta de administrador en Auth0; después sigue la solicitud y la aprobación del superadmin.
- **Migración de base `supabase_schema_v24.sql`**: ya aplicada en Neon (proyecto Niddo-SP, São Paulo). Sólo agrega columnas y tablas.

### Lo que ya está configurado

| Dónde | Qué | Para qué |
|---|---|---|
| Vercel | `CRON_SECRET` | Autoriza a GitHub a disparar los avisos programados |
| Vercel | `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY` | Notificaciones push |
| GitHub → Secrets → Actions | `CRON_SECRET` (el mismo valor que en Vercel), `NIDDO_URL` | El workflow de avisos |

Las claves de push también están en `~/.niddo-vapid.json`, en la Mac de Pedro. **No las cambies:** si cambian, todos los celulares que activaron notificaciones dejan de recibirlas.

### Decisiones tomadas (no volver atrás sin preguntar)

- **Mercado Pago: no se usa por ahora.** El backend quedó en el repo (`mercadopago_niddo.py`, `cifrado.py`, webhook, tabla `consorcio_secretos`), pero no hay pantalla para conectarlo y ningún vecino ve el botón.
- **Sentry: no se usa.** Se sacó del todo. Los errores se ven en los logs de Vercel (proyecto → Logs).
- **Mails gratis por Gmail**, desde niddo1998@gmail.com, con un límite de unos 500 destinatarios por día. Resend queda como alternativa para cuando haya un dominio propio.
- **Niddo no tiene** razón social, CUIT, domicilio ni WhatsApp. El único contacto es niddo1998@gmail.com.
- **Los cron jobs corren en GitHub Actions** y no en Vercel, porque Vercel Hobby permite un solo cron por día.

---

## 2. Lo que falta, en orden

Primero lo de Gmail (pasos 2 a 6): es lo que está a medio hacer. Para los pasos con claves: **no las pegues en el chat de un agente.** Los comandos de abajo las pasan por el portapapeles sin mostrarlas.

### Paso 1. Verificación en 2 pasos en Google (requisito)

1. Entrá a **myaccount.google.com** con **niddo1998@gmail.com**.
2. **Seguridad** → **Verificación en 2 pasos** → activala.

Si ya estaba activada, seguí con el paso 2.

### Paso 2. Generar la contraseña de aplicación

1. Entrá a **myaccount.google.com/apppasswords** con niddo1998@gmail.com.
2. En el nombre poné `Niddo` → **Crear**.
3. Google muestra una clave de 16 letras en 4 grupos. **Se ve una sola vez.** Copiala con Cmd+C y no cierres la ventana hasta terminar el paso 4.

### Paso 3. Guardarla en el `.env` local

Con la clave en el portapapeles, en la carpeta del repo:

```bash
printf '\nGMAIL_USUARIO=niddo1998@gmail.com\nGMAIL_APP_PASSWORD=%s\n' "$(pbpaste | tr -d ' ')" >> .env && echo "Guardada en el .env"
```

El `.env` está en `.gitignore` y nunca se sube. Si trabajás en otra compu, primero copiá el `.env` de Pedro por un canal seguro; no lo mandes por mail ni por chat.

### Paso 4. Cargarla en Vercel

1. Vercel (cuenta niddo1998, team niddoar) → proyecto **niddo** → **Settings** → **Environment Variables**.
2. `GMAIL_APP_PASSWORD` → pegar con Cmd+V → sólo **Production** → Save.
3. `GMAIL_USUARIO` = `niddo1998@gmail.com` → sólo **Production** → Save.
4. No hace falta redeploy: el merge del paso 6 ya dispara uno.

### Paso 5. Probar un mail real desde la compu

```bash
git switch feat/mail-por-gmail
python3 scripts/probar_gmail.py
```

Tiene que decir `proveedor: gmail` y `resultado: enviado a niddo1998@gmail.com`, y el mail tiene que aparecer en la **bandeja de entrada** de niddo1998@gmail.com, no en spam. Si dice que Gmail rechazó el usuario o la contraseña, volvé al paso 2 y generá otra.

Hace falta el entorno de Python del proyecto (ver [Para el agente que sigue](#para-el-agente-que-sigue)).

### Paso 6. Mergear el PR #11 y probar en producción

1. Mergear [#11](https://github.com/niddo1998/Niddo/pull/11) cuando el check de Vercel esté en verde.
2. Esperar el deploy de producción.
3. Probar algo real que mande un mail: aprobar un vecino de prueba, o enviar una liquidación de prueba a una unidad cuyo mail sea tuyo.
4. En la app, en el historial de envíos de la liquidación, tiene que figurar como «enviado».

### Paso 7. Confirmar los backups de Neon

En console.neon.tech → proyecto **Niddo-SP** → Settings, fijate cuántos días de restauración (*history retention*) permite el plan. Anotalo acá: es lo que se le contesta a un administrador que pregunta «¿y si se pierde todo?».

### Paso 8. Probar un mes real de punta a punta

Es lo más importante antes de mostrárselo a un administrador. Tomá la liquidación real de un edificio que conozcas y cargala completa en Niddo: unidades con m², saldos anteriores, gastos con comprobante, reglamento y matrícula. Después liquidá y compará el PDF **peso por peso** contra el que emitió el administrador. Cada diferencia es un bug o un dato mal cargado. Esa liquidación es también la mejor demo de venta.

### Paso 9. Revisión legal

Que un abogado lea `/terminos` y `/privacidad`. Están escritas siguiendo las leyes 25.326 (datos personales) y 24.240 (consumidor), pero no son asesoramiento legal. Cuando exista la sociedad, se cargan `NIDDO_RAZON_SOCIAL`, `NIDDO_CUIT` y `NIDDO_DOMICILIO` en Vercel y aparecen solas.

### Paso 10. Revisar los textos de la landing

Los botones dicen «Empezar Demo», pero varios textos siguen hablando de «el piloto» («Buscamos diez administraciones para el piloto», «Gratis durante el piloto»). Además, la landing promete «una llamada cada dos semanas» y «pasamos tu primer edificio juntos». Decidí qué se mantiene y pedile al agente que lo cambie en `templates/index.html`.

### Pendientes de producto (decisiones, no urgentes)

| Tema | Estado | Nota |
|---|---|---|
| Votaciones | Backend sin pantalla | `/api/votaciones` y `/api/admin/votaciones` existen, pero ni el admin ni el vecino tienen dónde usarlas |
| Monitoreo de errores | Sólo logs de Vercel | Nadie avisa cuando algo falla |
| Mails a escala | Gmail, ~500 por día | Para más volumen: dominio propio + Resend (ya soportado en `correo.py`) |
| Mercado Pago | Apagado | Se prende agregando la pantalla de conexión (está en el historial del PR #5) |
| Sueldos SUTERH, fondo de reserva, equipo del admin, facturación ARCA | No existen | Ver la sección «Tanda 2» de la auditoría |

---

## Para el agente que sigue

**Leé esto antes de tocar nada.** El `AGENTS.md` del home de Pedro habla de Cloudflare Workers y D1: **no aplica a este repo.**

### Stack

- **Flask** en un solo `app.py` (~8.000 líneas), con **Postgres en Neon** (proyecto Niddo-SP, São Paulo). Deploy en **Vercel** (team niddoar, región gru1).
- `db.py` imita el cliente de Supabase (`supabase.table(...).select().eq()...execute()`) sobre psycopg. La variable se sigue llamando `supabase` a propósito.
- Login con **Auth0**. El rol se elige al entrar; los admins nuevos quedan pendientes hasta que los aprueba un superadmin.
- Módulos aparte: `correo.py` (mails), `liquidacion_pdf.py` (PDF), `recurrentes.py`, `cifrado.py` y `mercadopago_niddo.py` (este último apagado).
- Migraciones: archivos `supabase_schema_vNN.sql`, a mano, sólo agregando. `schema.sql` es la base completa. La última es la v24, ya aplicada.

### Correr los tests

```bash
python3.13 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt pypdfium2 pymupdf
.venv/bin/python -m pytest -q
```

Al 16/10 pasan 631 y se saltean 16 (los de `tests/test_db.py`, que necesitan `NIDDO_TEST_DATABASE_URL` apuntando a una rama de prueba, **nunca** a la principal). Los tests usan un doble de la base en memoria (`tests/conftest.py`) y nunca mandan mails reales.

### Mirar pantallas sin tocar la base

```bash
.venv/bin/python scripts/devserver_datos_falsos.py 5056
```

Después entrá a `http://localhost:5056/dev/entrar/admin` o `/dev/entrar/vecino`. Los datos están en memoria y se pierden al cortar el servidor.

### Scripts útiles

| Script | Para qué |
|---|---|
| `scripts/probar_gmail.py [mail]` | Manda un mail de prueba con las credenciales del `.env` |
| `scripts/push_prueba.py <mail> [título] [texto]` | Manda un push a los dispositivos de ese usuario (necesita la clave privada de push) |
| `scripts/vapid.py` | Genera claves de push sin mostrarlas. **No hace falta:** ya están en Vercel |
| `scripts/devserver_datos_falsos.py` | Niddo con datos falsos, para revisar pantallas |

### Cómo trabaja Pedro

- **Todo en español rioplatense:** textos de la app, commits y PRs. Commits con el formato `feat: …` / `fix: …` y explicación del porqué.
- **Cada cambio va en una rama y un PR** con alcance, pruebas y rollback. Pedro aprueba cada merge: preguntá antes de mergear.
- **Preguntá antes de suponer** decisiones de producto.
- **Migraciones:** las que sólo agregan se pueden aplicar; cualquier cosa destructiva, preguntar primero.
- **Secretos:** nunca en el chat ni en el repo. Usá comandos con `pbcopy`/`pbpaste`.
- **Probá en el navegador** con el servidor de datos falsos antes de decir que algo visual está listo.
- **Mapa interno:** `/superadmin/mapa/lanzamiento` muestra el estado del lanzamiento. Si cerrás algo de esa lista, actualizá `templates/superadmin_mapa_lanzamiento.html`.

### Auditorías

- [docs/auditorias/2026-10-16-que-falta-para-pilotos.md](auditorias/2026-10-16-que-falta-para-pilotos.md): la comparación con la competencia que dio origen a todo esto. Varias cosas de ahí ya se hicieron o se descartaron; manda este documento.
- La auditoría de seguridad de julio **no está en el repo a propósito**: el repo es público y describe cómo explotar fallas, la mayoría ya arregladas (hay tests de pertenencia y de escapado que las cubren). Pedro la tiene en local, en `docs/auditorias/` (ignorada por git). Si hace falta, pedísela por un canal privado.
- **El repo es público.** Nada de secretos, datos de clientes ni detalles de vulnerabilidades en commits, PRs o issues.
