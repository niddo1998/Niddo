# Débito automático con Mercado Pago

Lo que Niddo le cobra a cada administrador sale por una suscripción de Mercado Pago (preapproval) a la cuenta de Niddo. El código está en `suscripciones_mp.py` y en el bloque «Débito automático con Mercado Pago» de `app.py`. Mientras no esté cargado `MP_NIDDO_ACCESS_TOKEN`, todo queda apagado y el administrador ve «muy pronto vas a poder pagar con Mercado Pago».

## Cómo funciona

1. En **Mi plan**, el administrador toca **Activar débito automático**. Niddo crea una suscripción por el total de sus edificios y lo manda a Mercado Pago, donde elige la tarjeta.
2. Si tiene pase gratis (fundador o prueba), el primer cobro queda agendado para el día después de que vence.
3. Mercado Pago cobra solo cada mes y avisa al webhook. Cada cobro aprobado marca como pagado el cobro del mes y entra como ingreso en **Finanzas** (categoría Suscripciones).
4. Si el total cambia (pasa de plan, agrega o borra un edificio o unidades, o cambian los precios), Niddo actualiza el monto en Mercado Pago. Si se le da pase gratis a alguien con débito activo, se pausa, y el cron diario lo reactiva cuando vence.

## Lo que hay que hacer para prenderlo

1. **Cuenta.** Entrar a [mercadopago.com.ar/developers/panel](https://www.mercadopago.com.ar/developers/panel) con la cuenta de Mercado Pago donde tiene que entrar la plata y crear una aplicación (tipo «Pagos online», producto «Suscripciones»).
2. **Access token.** En la aplicación → **Credenciales de producción** → copiar el *Access Token* (empieza con `APP_USR-`). Cargarlo en Vercel → proyecto niddo → Settings → Environment Variables como `MP_NIDDO_ACCESS_TOKEN`, sólo en Production. No pegarlo en ningún chat.
3. **Webhook.** En la aplicación → **Webhooks** → modo productivo:
   - URL: `https://niddo-eta.vercel.app/webhooks/mercadopago-niddo` (también figura en /superadmin → Comercial → Cómo cobramos).
   - Eventos: **Planes y suscripciones** (los dos: suscripciones y pagos de suscripciones).
   - Guardar y copiar la **clave secreta** que muestra. Cargarla en Vercel como `MP_NIDDO_WEBHOOK_SECRET`.
4. **Redeploy** en Vercel para que tome las variables.
5. **Probar.** En /superadmin → Comercial → Cómo cobramos tienen que aparecer los dos ✅ y el nombre de la cuenta. Después, con una cuenta de administrador de prueba que tenga un edificio, activar el débito con una tarjeta real y cancelarlo desde Mi plan.

Para probar sin plata real se pueden usar las credenciales de prueba y los usuarios de prueba de Mercado Pago: en ese caso el `payer_email` tiene que ser el del comprador de prueba.
