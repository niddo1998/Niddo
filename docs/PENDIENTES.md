# Pendientes de Pedro

**Actualizado:** 12 de noviembre de 2026

Lo que falta y **sólo puede hacer Pedro**: tocan cuentas, claves o decisiones de producto. El código ya está en `main` y en producción; lo que falta es de su lado.

Si sos un agente y te preguntan «qué falta», respondé con esta lista. Cuando Pedro te diga que hizo algo, sacalo de acá (o movelo a «Hecho», abajo, con la fecha) y commiteá el cambio. Si encontrás algo nuevo que sólo puede hacer él, sumalo. **Nunca pidas ni anotes claves acá:** el repo es público.

---

## 1. Prender el cobro con Mercado Pago

El débito automático está programado pero apagado hasta que estén las credenciales. Paso a paso en [mercadopago-suscripciones.md](mercadopago-suscripciones.md).

- [ ] Crear la aplicación en mercadopago.com.ar/developers, con la cuenta donde tiene que entrar la plata (producto «Suscripciones»).
- [ ] Cargar el access token de producción en Vercel como `MP_NIDDO_ACCESS_TOKEN` (sólo Production).
- [ ] Configurar el webhook `https://niddo-eta.vercel.app/webhooks/mercadopago-niddo` con los eventos de «Planes y suscripciones», y cargar su clave secreta en Vercel como `MP_NIDDO_WEBHOOK_SECRET`.
- [ ] Redeploy en Vercel y verificar en /superadmin → Comercial → Cómo cobramos que aparezcan los dos ✅.
- [ ] Probar con una cuenta de administrador de prueba: activar el débito y cancelarlo.

## 2. Repo privado

- [ ] GitHub → `niddo1998/Niddo` → Settings → Danger Zone → Change visibility → Private. Lo tiene que hacer la cuenta **niddo1998** (la de Pedro no es admin del repo).
- [ ] Después, un push de prueba: confirmar que Vercel sigue desplegando (el plan Hobby puede bloquear commits de quien no es dueño de la cuenta en repos privados).
- [ ] Mirar el consumo de GitHub Actions el primer mes (Settings → Billing): en privado hay 2.000 minutos gratis y los avisos por hora usan unos 750.

Mientras el repo sea público, la clave de Finanzas del superadmin se puede leer en el código.

## 3. Mails por Gmail

Hasta que esto esté, Niddo no manda mails. Detalle en `docs/ESTADO.md` del PR #11.

- [ ] Activar la verificación en 2 pasos en la cuenta de Google de Niddo.
- [ ] Generar una contraseña de aplicación (myaccount.google.com/apppasswords) y cargarla en el `.env` local y en Vercel como `GMAIL_APP_PASSWORD`, junto con `GMAIL_USUARIO`.
- [ ] Probar con `python3 scripts/probar_gmail.py` (está en la rama del PR #11).
- [ ] Mergear el [PR #11](https://github.com/niddo1998/Niddo/pull/11).

## 4. Revisar los precios de los planes

- [ ] Hoy: hasta 10 unidades $20.000, hasta 25 $45.000, hasta 60 $90.000, más de 60 $150.000, por edificio y por mes. Se cambian en /superadmin → Comercial → Editar planes.

## 5. Antes de mostrárselo a un administrador

- [ ] **Backups de Neon:** en console.neon.tech → proyecto Niddo-SP → Settings, ver cuántos días de restauración da el plan y anotarlo (es la respuesta a «¿y si se pierde todo?»).
- [ ] **Un mes real de punta a punta:** cargar la liquidación real de un edificio conocido y comparar el PDF peso por peso con el del administrador.
- [ ] **Revisión legal:** que un abogado lea `/terminos` y `/privacidad`.
- [ ] **Textos de la landing:** varios siguen hablando de «el piloto» y prometen una llamada cada dos semanas; decidir qué queda y pedir el cambio en `templates/index.html`.

## 6. Decisiones de producto (sin apuro)

- [ ] Votaciones: el backend existe pero no hay pantalla. ¿Se hace o se saca?
- [ ] Monitoreo de errores: hoy sólo están los logs de Vercel y nadie avisa cuando algo falla.

---

## Hecho

- 12/11/2026 — La cuenta de Pedro quedó aprobada y como superadmin; las tres cuentas del equipo, siempre gratis.
- 12/11/2026 — Migraciones 025, 026 y 027 aplicadas en Neon.
