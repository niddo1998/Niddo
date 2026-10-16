"""Mandar mails por Gmail (SMTP) o por Resend.

Gmail es el camino gratis. Lo que importa: una sola conexión para todo el lote,
que un mail que falla no voltee a los demás, y que el límite diario corte el
envío con un motivo claro en vez de seguir golpeando.
"""

import smtplib

import pytest

import correo


class SMTPFalso:
    instancias = []

    def __init__(self, host, puerto, timeout=None):
        self.host, self.puerto = host, puerto
        self.enviados, self.logueado = [], None
        self.fallar_en = {}
        SMTPFalso.instancias.append(self)

    def starttls(self):
        pass

    def login(self, usuario, clave):
        if clave != 'abcdabcdabcdabcd':
            raise smtplib.SMTPAuthenticationError(535, b'bad')
        self.logueado = usuario

    def send_message(self, msg):
        n = len(self.enviados)
        if n in self.fallar_en:
            raise self.fallar_en.pop(n)
        self.enviados.append(msg)

    def quit(self):
        pass


@pytest.fixture
def gmail(monkeypatch):
    SMTPFalso.instancias = []
    monkeypatch.setattr(smtplib, 'SMTP', SMTPFalso)
    monkeypatch.setenv('GMAIL_USUARIO', 'niddo1998@gmail.com')
    monkeypatch.setenv('GMAIL_APP_PASSWORD', 'abcd abcd abcd abcd')   # Google la muestra con espacios
    return SMTPFalso


def _m(n):
    return [{'to': [f'v{i}@test'], 'subject': f'Asunto {i}', 'html': f'<p>Hola <b>{i}</b></p>'} for i in range(n)]


def test_gmail_gana_si_esta_configurado(gmail, monkeypatch):
    monkeypatch.setenv('RESEND_API_KEY', 're_x')
    assert correo.proveedor() == 'gmail'


def test_sin_nada_configurado_no_manda_y_dice_por_que():
    assert correo.proveedor() is None
    assert correo.enviar(_m(2)) == [correo.motivo_sin_proveedor()] * 2


def test_un_lote_usa_una_sola_conexion(gmail):
    assert correo.enviar(_m(40)) == [None] * 40
    assert len(gmail.instancias) == 1
    assert len(gmail.instancias[0].enviados) == 40
    assert gmail.instancias[0].logueado == 'niddo1998@gmail.com'


def test_el_mail_sale_desde_niddo_con_html_y_texto(gmail):
    correo.enviar(_m(1))
    msg = gmail.instancias[0].enviados[0]
    assert msg['From'] == 'Niddo <niddo1998@gmail.com>'
    assert msg['To'] == 'v0@test'
    tipos = [p.get_content_type() for p in msg.iter_parts()]
    assert tipos == ['text/plain', 'text/html']
    assert 'Hola 0' in msg.get_body(('plain',)).get_content()


def test_clave_mal_falla_todo_con_motivo(gmail, monkeypatch):
    monkeypatch.setenv('GMAIL_APP_PASSWORD', 'otra')
    errores = correo.enviar(_m(3))
    assert all('contraseña de aplicación' in e for e in errores)


def test_un_mail_rechazado_no_voltea_a_los_demas(gmail, monkeypatch):
    original = SMTPFalso.__init__

    def init(self, *a, **k):
        original(self, *a, **k)
        self.fallar_en = {1: smtplib.SMTPRecipientsRefused({'v1@test': (550, b'no existe')})}
    monkeypatch.setattr(SMTPFalso, '__init__', init)
    errores = correo.enviar(_m(3))
    assert errores[0] is None and errores[2] is None
    assert errores[1]


def test_si_gmail_corta_la_conexion_se_reconecta(gmail, monkeypatch):
    original = SMTPFalso.__init__

    def init(self, *a, **k):
        original(self, *a, **k)
        if len(SMTPFalso.instancias) == 1:
            self.fallar_en = {2: smtplib.SMTPServerDisconnected('chau')}
    monkeypatch.setattr(SMTPFalso, '__init__', init)
    assert correo.enviar(_m(4)) == [None] * 4
    assert len(gmail.instancias) == 2


def test_el_limite_diario_corta_el_resto(gmail, monkeypatch):
    original = SMTPFalso.__init__

    def init(self, *a, **k):
        original(self, *a, **k)
        self.fallar_en = {2: smtplib.SMTPDataError(550, b'5.4.5 Daily user sending limit exceeded')}
    monkeypatch.setattr(SMTPFalso, '__init__', init)
    errores = correo.enviar(_m(5))
    assert errores[:2] == [None, None]
    assert all('límite diario' in e for e in errores[2:])


def test_resend_sigue_andando_como_alternativa(monkeypatch):
    lotes = []

    class _Batch:
        @staticmethod
        def send(m):
            lotes.append(m)

    import resend
    monkeypatch.setattr(resend, 'Batch', _Batch)
    monkeypatch.setenv('RESEND_API_KEY', 're_x')
    assert correo.enviar(_m(150)) == [None] * 150
    assert [len(l) for l in lotes] == [100, 50]
    assert all('from' in m for m in lotes[0])
