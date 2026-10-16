"""Mandar mails, por Gmail o por Resend.

Gmail (SMTP con contraseña de aplicación) es el camino gratis: los mails salen
desde la cuenta de Niddo, los firma Google y llegan a la bandeja de entrada.
Su límite es de unos 500 destinatarios por día. Resend queda como alternativa
para el día que haya un dominio propio verificado.

Se elige solo:
  GMAIL_USUARIO + GMAIL_APP_PASSWORD   → Gmail
  si no, RESEND_API_KEY                → Resend
  si no hay ninguno                    → no se manda nada y se dice por qué

Vive aparte de `app.py` y no conoce la base: recibe mensajes y devuelve, para
cada uno, None si salió o el motivo si no.
"""

import html as html_mod
import os
import re
import smtplib
from email.message import EmailMessage
from email.utils import formataddr, make_msgid

SMTP_HOST = 'smtp.gmail.com'
SMTP_PUERTO = 587


def _gmail():
    usuario = os.environ.get('GMAIL_USUARIO', '').strip()
    clave = os.environ.get('GMAIL_APP_PASSWORD', '').replace(' ', '')
    return (usuario, clave) if usuario and clave else None


def proveedor():
    """'gmail', 'resend' o None."""
    if _gmail():
        return 'gmail'
    if os.environ.get('RESEND_API_KEY'):
        return 'resend'
    return None


def motivo_sin_proveedor():
    return 'No hay mail configurado (faltan GMAIL_USUARIO y GMAIL_APP_PASSWORD)'


def _texto_plano(html):
    """Versión de texto del HTML, para los clientes que no lo muestran."""
    t = re.sub(r'(?is)<(style|script)[^>]*>.*?</\1>', '', html or '')
    t = re.sub(r'(?i)<br\s*/?>|</(p|div|tr|h[1-6]|li)>', '\n', t)
    t = re.sub(r'<[^>]+>', '', t)
    t = html_mod.unescape(t)
    return re.sub(r'\n\s*\n+', '\n\n', re.sub(r'[ \t]+', ' ', t)).strip()


def _armar(usuario, nombre, m):
    msg = EmailMessage()
    msg['From'] = formataddr((nombre, usuario))
    msg['To'] = ', '.join(m['to'])
    msg['Subject'] = m['subject']
    msg['Message-ID'] = make_msgid(domain=usuario.split('@')[-1])
    msg.set_content(_texto_plano(m['html']))
    msg.add_alternative(m['html'], subtype='html')
    return msg


def _por_gmail(mensajes):
    """Una sola conexión para todo el lote: abrir una por mail tarda segundos."""
    usuario, clave = _gmail()
    nombre = os.environ.get('GMAIL_NOMBRE', 'Niddo')
    errores = [None] * len(mensajes)
    smtp = None

    def conectar():
        s = smtplib.SMTP(SMTP_HOST, SMTP_PUERTO, timeout=20)
        s.starttls()
        s.login(usuario, clave)
        return s

    try:
        smtp = conectar()
    except smtplib.SMTPAuthenticationError:
        return ['Gmail rechazó el usuario o la contraseña de aplicación'] * len(mensajes)
    except Exception as e:
        return [f'No se pudo conectar con Gmail: {e}'[:300]] * len(mensajes)

    for i, m in enumerate(mensajes):
        for intento in (1, 2):
            try:
                smtp.send_message(_armar(usuario, nombre, m))
                break
            except smtplib.SMTPServerDisconnected:
                # Gmail corta conexiones largas: se reconecta una vez y sigue.
                if intento == 2:
                    errores[i] = 'Gmail cortó la conexión'
                    break
                try:
                    smtp = conectar()
                except Exception as e:
                    errores[i] = f'No se pudo reconectar con Gmail: {e}'[:300]
                    break
            except (smtplib.SMTPDataError, smtplib.SMTPSenderRefused) as e:
                # 550 5.4.5: se pasó el límite diario. No tiene sentido seguir.
                if e.smtp_code == 550 and b'5.4.5' in (e.smtp_error or b''):
                    for j in range(i, len(mensajes)):
                        errores[j] = 'Se llegó al límite diario de Gmail; probá mañana'
                    return errores
                errores[i] = f'Gmail rechazó el mail: {e.smtp_code}'
                break
            except Exception as e:
                errores[i] = str(e)[:300]
                break
    try:
        smtp.quit()
    except Exception:
        pass
    return errores


def _por_resend(mensajes):
    import resend
    resend.api_key = os.environ.get('RESEND_API_KEY', '')
    remitente = os.environ.get('RESEND_FROM_EMAIL', 'Niddo <noreply@niddo.app>')
    errores = [None] * len(mensajes)
    for i in range(0, len(mensajes), 100):
        lote = mensajes[i:i + 100]
        try:
            resend.Batch.send([{'from': remitente, **m} for m in lote])
        except Exception as e:
            for j in range(i, i + len(lote)):
                errores[j] = str(e)[:500]
    return errores


def enviar(mensajes):
    """Manda [{'to': [...], 'subject': ..., 'html': ...}]. Nunca levanta excepción.

    Devuelve una lista del mismo largo: None si el mail salió, o el motivo.
    """
    if not mensajes:
        return []
    p = proveedor()
    if p == 'gmail':
        return _por_gmail(mensajes)
    if p == 'resend':
        return _por_resend(mensajes)
    return [motivo_sin_proveedor()] * len(mensajes)
