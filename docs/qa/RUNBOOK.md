# Runbook de QA de Niddo

Cómo trabaja Claude sobre Niddo sin que nadie le diga qué hacer en cada paso:
qué prueba, cómo reporta, qué arregla solo, qué pregunta y qué nunca toca.
La corrida diaria (todos los días a las 7:00, hora de Argentina) sigue este
documento. Si algo de acá cambia, cambia lo que hace Claude.

## 1. Ambiente de pruebas

Todo se prueba contra un ambiente propio, nunca contra producción.

| Pieza | Qué es |
|---|---|
| `qa/levantar.sh` | Levanta Postgres local, aplica `schema.sql` + `migraciones/*.sql`, carga `qa/seed.sql` y arranca la app en `http://localhost:5055`. Resetea la base en cada corrida. |
| `qa/seed.sql` | Datos 100% ficticios: 2 consorcios, 6 UF, 3 admins, 2 vecinos, gastos y amenities. Emails `@niddo.test` (dominio que nunca entrega). |
| `/qa/login/<quien>` | Entra sin Auth0. Solo existe con `NIDDO_QA_LOGIN=1` + modo local + fuera de Vercel (lo cuida `tests/test_qa_login.py`). Perfiles: `admin`, `superadmin`, `pendiente`, `vecino`, `vecino2`. |
| `qa/correr.sh` | Corre las tres capas y deja `qa/.salida/resumen.txt` y capturas. |
| `.github/workflows/qa.yml` | Lo mismo en cada PR: el check tiene que estar verde para mergear. |

Las integraciones externas (Resend, Groq, push, Mercado Pago) quedan apagadas
en este ambiente porque no tienen credenciales: no sale ningún mail ni pago.

**Ambiente de staging en la nube (pendiente, lo configura el equipo):** una rama
de Neon (`staging`) + las variables de Vercel en el entorno *Preview* apuntando a
esa rama. Así cada PR tiene su URL de preview con datos de prueba. Ver §7.

## 2. Las capas de prueba

1. **Unitarios** (`tests/`): lógica con el doble de la base de `conftest.py`.
2. **Postgres real** (`tests/test_db.py`): que `db.py` se comporte como PostgREST.
3. **E2E** (`qa/e2e/`): navegador real recorriendo la app por rol, en desktop y
   mobile. Falla ante errores de JS, `console.error`, respuestas 5xx o scroll
   horizontal en mobile.
4. **Exploratorio** (lo hace Claude mirando, no un script): navegar el ambiente
   como cada rol, leer las capturas, revisar que montos, fechas y textos tengan
   sentido, abrir los PDF/Excel generados y verificar los números. La
   [matriz de flujos](MATRIZ.md) dice qué recorrer y en qué orden.
5. **Producción, solo lectura** (cuando Santiago deja una sesión abierta en el
   navegador): mirar, nunca crear/editar/borrar datos reales.

## 3. La corrida diaria (7:00)

1. Actualizar `main`, correr `bash qa/correr.sh`.
2. Si `main` está en rojo: es P0 automáticamente, se abre/actualiza el issue y
   es lo primero que se arregla.
3. Exploratorio sobre 2–3 flujos de la matriz, rotando (los marcados como
   «último recorrido» más viejo primero) + todo lo que tocaron los merges de
   las últimas 24 h.
4. Cada hallazgo → issue (ver §4). Antes de abrir uno, buscar si ya existe.
5. Trabajar la cola (ver §5) hasta agotar el tiempo de la corrida.
6. Reporte del día (ver §6).

## 4. Cómo se reporta un bug

Un issue por bug, con el template `🐞 Bug`, labels `tipo: bug` + severidad +
`área: …` + `origen: qa-automático`. Siempre con:

- Pasos exactos para reproducir en el ambiente de pruebas (con el perfil de `/qa/login/…`).
- Esperado vs. actual.
- Evidencia: captura, error de consola o respuesta del servidor.
- Hipótesis de causa con archivo y línea, si ya la hay.

| Severidad | Criterio | Tiempo |
|---|---|---|
| **P0 crítico** | Rompe un flujo central (login, liquidación, cobro), expone datos de otro consorcio o pierde datos | Se ataca en la corrida en que aparece |
| **P1 alto** | Flujo importante roto con workaround, o error visible en una pantalla principal | Misma semana |
| **P2 medio** | Molesto, no bloquea | Cuando no hay P0/P1 |
| **P3 bajo** | Cosmético, bordes | Cuando sobra tiempo |

## 5. Qué hace Claude solo y qué pregunta

**Lo toma solo** (label `listo-para-claude` o bug con causa clara):
bugs con fix acotado, tests nuevos, textos, estilos, responsive, refactors
chicos sin cambio de comportamiento, mejoras al propio ambiente de QA.

**Pregunta primero** (comenta en el issue, label `Necesita decisión de founder`, y sigue con otra cosa):
- Regla de negocio ambigua (cómo se prorratea, cuándo corre la mora, qué ve cada rol).
- Cambios de esquema o migraciones nuevas.
- Auth, permisos, impersonación, cifrado.
- Pagos, mails o notificaciones a usuarios.
- Un fix con más de una salida razonable o que cambia algo que el usuario ya ve.
- Backlog sin criterio claro de «terminado».

La pregunta va con opciones concretas y una recomendación, para que se pueda
contestar con una línea.

**Nunca:**
- Pushear a `main` ni mergear. El merge necesita el OK de Santiago o de su socio.
- Tocar la base de producción o la de Neon principal.
- Crear, editar o borrar datos reales en producción.
- Configurar credenciales/secretos o tipear contraseñas.
- Pagos reales (Mercado Pago solo en sandbox) o mails a direcciones reales.

## 6. Flujo de un fix

1. Label `en-progreso`, rama `fix/<n>-<slug>` desde `main` actualizado (backlog: `feat/<n>-<slug>`).
2. Test de regresión que falla **antes** del fix (unitario o E2E).
3. Fix mínimo. Sin cambios de estilo de paso.
4. `bash qa/correr.sh` en verde.
5. PR con el template, `Cierra #n`, capturas antes/después si toca UI. Label `en-revisión` en el issue.
6. P0/P1: un segundo agente, que no vio el fix, lo revisa contra el issue antes de pedir el OK.
7. Si el PR recibe comentarios, se atienden en la corrida siguiente.

Un PR por issue. Si un fix destapa otro bug, issue nuevo.

## 7. Reporte

Cada corrida termina con un reporte en el chat de Claude (y en el issue fijado
`📋 Reportes de QA` como comentario):

- Estado de las tres capas (verde/rojo, cantidades).
- Bugs nuevos (con link y severidad).
- PRs abiertos esperando OK.
- Preguntas pendientes (`Necesita decisión de founder`), primero.
- Qué flujos se recorrieron en el exploratorio.

## 8. Vistas útiles

- Esperan una decisión de founder: `is:open label:"Necesita decisión de founder"`
- PRs para aprobar: `is:pr is:open`
- Bugs abiertos por severidad: `is:open label:"tipo: bug" sort:created-desc`
- Backlog: `is:open label:"tipo: backlog"`
