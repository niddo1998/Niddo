# Auditoría — qué falta para tener administradores testeando Niddo

**Fecha:** 16 de octubre de 2026
**Pregunta:** ¿qué separa a Niddo de poder salir a buscar los primeros administradores piloto?
**Referencias:** Octopus (OctoApp), CONSO, Unitify, ExpensasPagas y la normativa vigente de CABA (Ley 941 y disposiciones de la DGDyPC).
**Método:** lectura del código actual (`app.py`, `liquidacion_pdf.py`, `schema.sql`, templates, `vercel.json`) contrastada con el mapa `/superadmin/mapa/lanzamiento` y con lo que ofrecen los competidores. No se ejecutó nada contra la base de producción.

---

## Veredicto en una línea

El producto ya hace más que suficiente para un piloto: carga de gastos con IA, prorrateo, PDF formato Ley 941, deuda del vecino, reclamos, reservas, votaciones, mensajería, push, onboarding con aprobación. **Lo que frena no es funcionalidad: es confianza.** Hoy un administrador que entra a la landing lee cosas que no existen, recibe una liquidación que no cumple dos disposiciones vigentes de CABA, y no tiene cómo traer la deuda de sus vecinos desde el sistema que usa ahora.

---

## 🔴 Tanda 0 — Antes de mostrárselo a nadie (≈ 2–3 días)

### 1. La landing promete cosas que Niddo no hace

`templates/index.html` dice hoy:

| Lo que dice la landing | Realidad en el código |
|---|---|
| "+300 administradores activos", "+10K vecinos", "99.9% disponibilidad" | Son números inventados. |
| "Liquidación inteligente con **QR obligatorio CABA**" | El PDF no tiene QR (ver punto 2). |
| "**Conciliación bancaria**" | No existe. |
| "Sueldos por convenio, aguinaldos, vacaciones y **presentación de cargas sociales**" | No existe (el mapa lo marca "falta"). |
| "**Inversión del float** — el capital en tránsito genera rendimiento" | No existe y además es una actividad financiera regulada. |
| "White label y **API abierta**", "trabajo en equipo multiusuario" | No existe ninguno. |
| "Pagá tu expensa con **QR / cualquier billetera**" | El vecino informa un pago con comprobante; no paga desde la app. |

**Por qué es lo primero:** el público son administradores, que se conocen entre sí y comparan. El primero que se registra por la conciliación bancaria y no la encuentra no vuelve, y lo comenta. Además es publicidad engañosa (Ley 24.240, art. 8).

**Qué hacer:** reescribir la landing con lo que sí hay, y mover lo demás a una sección "Próximamente" si se quiere. Cambiar "Registrarme gratis" por **"Quiero ser piloto"** con WhatsApp directo — con 5–10 clientes, la conversación vale más que el self-service.

### 2. La liquidación no cumple dos disposiciones vigentes de CABA

Todos los competidores ya las resolvieron; es lo primero que un administrador de CABA revisa.

- **QR o link a los comprobantes del período** — Disp. DGDyPC 1146/2024, exigible desde las expensas de julio de 2024. El administrador debe imprimir en la liquidación un QR o hipervínculo visible que lleve a los comprobantes escaneados. Niddo **ya guarda los comprobantes** (`comprobantes_gastos`, `/api/gastos/<gid>/comprobante`); falta una página pública por liquidación con un token no adivinable que los liste, y el QR en `liquidacion_pdf.py`. `grep -i qr liquidacion_pdf.py` → nada.
- **Manual de Buenas Prácticas Consorciales + Reglamento de Propiedad Horizontal** — Disp. 521/2025, desde el 1/4/2025 deben acompañar cada liquidación (QR, link o mail). No existe dónde cargar el reglamento por consorcio. Se resuelve con el mismo mecanismo: un archivo fijo por consorcio (ya existe `archivos_consorcio`) incluido en la página del QR.

### 3. La matrícula RPA no sale en la liquidación (sigue abierto)

Verificado hoy: `CAMPOS_PERFIL_EDITABLES['admin']` (`app.py:4639`) sigue siendo `('nombre', 'nombre_contacto', 'telefono')`. Las columnas `cuit`, `matricula` y `direccion` existen y el PDF las imprime si tienen valor, pero no hay pantalla para cargarlas. Es ~1 hora.

### 4. El envío masivo se corta por timeout (sigue abierto)

Verificado hoy: `api_liquidaciones_enviar` sigue haciendo `resend.Emails.send()` + insert en `resumen_envios` de a uno, en serie. `vercel.json` sigue en formato `builds/routes` sin `maxDuration`. Con un edificio de 40 UF el envío queda a medio publicar **en la demo**. Usar `resend.Batch.send` (hasta 100 por llamada) y un solo insert masivo.

### 5. Términos, privacidad y monitoreo

- **Términos y condiciones + política de privacidad**: no existen (`grep` en templates → nada). Niddo guarda datos personales de terceros (vecinos) por cuenta del administrador: el contrato tiene que decir que el administrador es el responsable y Niddo el encargado del tratamiento (Ley 25.326). Un administrador serio lo va a pedir, y el registro de bases ante la AAIP también.
- **Sentry o equivalente**: no hay. En un piloto, enterarte de un error por WhatsApp del cliente es lo que más confianza destruye.
- **Dominio verificado en Resend (SPF/DKIM)**: si los mails de expensas caen en spam, para el vecino "Niddo no funciona".

---

## 🟠 Tanda 1 — Lo que el primer administrador te va a pedir en la primera semana

### 6. Migrar su cartera: saldos iniciales por unidad

Ningún administrador arranca de cero: viene de SIPAC, Octopus o un Excel, con vecinos que deben 3 meses. Hoy Niddo tiene `saldo_inicial` **del consorcio** en la liquidación, pero no encontré cómo cargar la **deuda inicial de cada unidad**. Sin eso el primer mes sale mal en todos los morosos, que son justo los que reclaman.

Agregar una columna "saldo anterior" a la plantilla de carga masiva de unidades (que ya existe) y que genere un cobro de arrastre. Es el corazón del onboarding: si migrar es fácil, el piloto arranca; si no, se queda en "lo pruebo con un edificio de juguete".

### 7. Cerrar el circuito del cobro

Hoy: el vecino sube comprobante → el admin lo aprueba a mano. Alcanza para 1–2 edificios, pero es la diferencia más visible contra la competencia:

| | Niddo | Octopus | ExpensasPagas | CONSO |
|---|---|---|---|---|
| Vecino paga desde la app | ❌ | ✅ | ✅ (código de pago, Pago Fácil, homebanking) | — |
| Pago identificado por unidad | ❌ (manual) | ✅ | ✅ informes diarios por consorcio y UF | — |
| Imputación automática | ❌ | ✅ | ✅ | ✅ conciliación bancaria |

**Para el piloto no hace falta construir esto.** Dos caminos baratos:
- **Mercado Pago Checkout** con `external_reference = cobro_id` y webhook que marca el cobro como pagado. Resuelve "pagar desde la app" y la imputación a la vez.
- **Integrarse a ExpensasPagas** (muchos administradores ya lo usan): importar su informe diario de pagos por UF. Ahorrás construir cobranza y te subís a algo que el cliente ya conoce.

Mientras tanto, mejora barata: mostrar el **CBU/alias del consorcio con el monto exacto** y un botón "ya pagué" que pida el comprobante (casi está: `medios_pago` + `avisos_pago`).

### 8. Probar un mes real de punta a punta

Sigue marcado como bloqueante en tu mapa y tiene razón. Tomá una liquidación real de un edificio que conozcas (la de tu propio edificio sirve), cargala completa en Niddo y compará el PDF contra el que emitió el administrador, peso por peso. Es la mejor demo de venta que vas a tener: "esta es tu liquidación de septiembre, hecha en Niddo".

### 9. Backups

No hay política escrita. Neon tiene restauración a un punto en el tiempo, pero la ventana depende del plan. Confirmar la ventana del plan actual y anotarla: es lo que contestás cuando el administrador pregunta "¿y si se pierde todo?".

---

## 🟡 Tanda 2 — Lo que pesa en la decisión de pasar todos los edificios (post-piloto)

Ordenado por cuánto lo mencionan los competidores y por cuánto le duele al administrador:

| Funcionalidad | Quién la tiene | Estado en Niddo |
|---|---|---|
| **Sueldos SUTERH + F.931** | CONSO (escala SUTERH, seguimiento F.931) | Falta. Hay `clave_suterh` en consorcios, nada más. Es el mayor costo de tiempo del administrador después de la liquidación. |
| **Fondo de reserva** | CONSO ("fondos por edificio") | Falta. Lo pide cualquier asamblea. |
| **Mora automática** (interés por día al vencimiento) | Todos | Parcial: hay `tasa_interes_mora` por consorcio, pero el interés no se aplica solo al vencer. |
| **Recordatorios automáticos** (vencimiento, deuda) | Octopus | Falta. Con push ya funcionando, es barato. |
| **Equipo del administrador** (empleados con permisos) | Octopus, CONSO | Falta. Las administraciones medianas tienen 2–5 personas. |
| **Facturación electrónica ARCA (ex AFIP)** | Octopus | Falta. |
| **Presupuestos a proveedores** | Octopus | Falta. |
| **Rendición anual / balance normativo** | Todos | Parcial. |
| **App en las tiendas** | Octopus, Consorcio Abierto | Hay PWA (manifest + service worker + push). Para el piloto alcanza. |

---

## 💡 Lo que Niddo ya tiene que conviene vender

Para el pitch del piloto, estos son diferenciales reales:

1. **Leer la factura con IA** y la carga masiva de gastos — ahorra horas por mes.
2. **Liquidación con prorrateo flexible** (A, B, C, E y por m²) y PDF con el detalle que pide la Ley 941.
3. **El vecino ve el detalle de sus gastos por mes** y baja su resumen — transparencia, el dolor número uno del consorcista.
4. **Reclamos como conversación**, reservas con calendario, votaciones, comunicados con lectura, push.
5. **Alta de vecinos con aprobación del admin** — nadie entra a un edificio sin permiso.

---

## 💰 Modelo comercial del piloto (decisión tuya)

Referencias: CONSO publica ARS 2.950 + IVA por UF/mes con 30 días gratis; Octopus cobra un fee por unidad; Unitify tiene un plan gratuito real.

Propuesta: **piloto gratis por 3 meses para 5–10 administradores**, a cambio de una llamada de feedback cada dos semanas y permiso para usarlos como caso. Después, precio por UF por debajo de CONSO. No hace falta integrar cobros de suscripción para esto: se factura a mano.

---

## Orden sugerido

| # | Qué | Quién | Esfuerzo |
|---|---|---|---|
| 1 | Reescribir la landing sin promesas falsas + CTA "Quiero ser piloto" | código + tuyo (copy) | medio día |
| 2 | Matrícula / CUIT / dirección en Mi perfil | código | 1 h |
| 3 | Envío por lotes en Resend + `maxDuration` | código | media tarde |
| 4 | QR a comprobantes + reglamento/manual en la liquidación | código | 1–2 días |
| 5 | Sentry + SPF/DKIM en Resend | tuyo (cuentas) + código | 2 h |
| 6 | Términos y privacidad | tuyo (abogado o modelo revisado) | — |
| 7 | Saldo inicial por unidad en la carga masiva | código | 1 día |
| 8 | Mes real de punta a punta | tuyo | medio día |
| 9 | Confirmar backups de Neon | tuyo | 30 min |
| — | **Salir a buscar pilotos** | | |
| 10 | Mercado Pago o ExpensasPagas | código + cuenta | 2–3 días |
| 11 | Mora automática + recordatorios | código | 1 día |
| 12 | Fondo de reserva, SUTERH, equipo | código | según feedback del piloto |

Los puntos 5, 6 y 9 son tuyos y no dependen del código: conviene arrancarlos hoy, en paralelo.

---

## Fuentes

- Disp. DGDyPC 1146/2024 (QR/link a comprobantes): [abogados.com.ar](https://abogados.com.ar/codigo-qr-o-hipervinculo-en-las-liquidaciones-de-expensas-comunes-para-conocer-la-documentacion-por-los-gastos-y-erogaciones-en-los-consorcios-de-la-caba/35245), [Boletín Oficial CABA — Disp. 2373/2024](https://boletinoficial.buenosaires.gob.ar/normativaba/norma/724002)
- Disp. 521/2025 (Manual de buenas prácticas + reglamento): [Boletín Oficial CABA](https://boletinoficial.buenosaires.gob.ar/normativaba/norma/776269), [Liga del Consorcista](https://ligadelconsorcista.org/caba-disposicion-521-2025-manual-de-buenas-practicas-consorciales-)
- Octopus: [Forbes Argentina](https://www.forbesargentina.com/innovacion/vio-oportunidad-crear-mercado-libre-consorcios-puso-manos-obra-asi-octopus-proptech-n24010), [iProfesional](https://www.iprofesional.com/tecnologia/376688-octopus-lanza-aplicacion-para-gestiones-de-consorcios), [descubre.vc](https://www.descubre.vc/noticia/octopus-anuncia-el-lanzamiento-de-octuapp-2023-01-30)
- CONSO: [Capterra](https://www.capterra.es/software/1111352/CONSO)
- Unitify: [unitify.com](https://unitify.com/argentina)
- ExpensasPagas: [Mercado](https://mercado.com.ar/protagonistas/expensaspagas-ahora-tambien-con-pago-facil)
