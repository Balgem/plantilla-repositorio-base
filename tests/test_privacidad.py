"""Gate 2, criterio 3: huellas con clave y redacción de datos personales."""
import hashlib

import pytest

import privacidad as pv


@pytest.mark.parametrize("texto, tipos", [
    ("escríbeme a ana.perez@example.com", ["correo"]),
    ("mi rut es 12.345.678-9", ["rut"]),
    ("llámame al +56 9 1234 5678", ["telefono"]),
    ("o al 912345678", ["telefono"]),
    ("sigan mi canal en bit.ly/regalo", ["link"]),
    ("compren en https://otra-tienda.cl/k7", ["link"]),
    ("el link oficial es https://ejemplo.cl/r/k7", []),
    ("el K7 cuesta 59.990 CLP y el envío 3.990", []),          # precios: no son teléfonos
    ("cuánto cuesta el teclado??", []),
])
def test_detecta_cada_tipo_de_pii(texto, tipos):
    assert pv.contiene_pii(texto) == tipos


def test_redactar_reemplaza_y_deja_el_link_oficial():
    texto = "soy ana.perez@example.com, rut 12.345.678-9, +56 9 1234 5678, ver bit.ly/x o https://ejemplo.cl/r/k7"
    assert pv.redactar(texto) == "soy [correo], rut [rut], [telefono], ver [link] o https://ejemplo.cl/r/k7"


def test_huella_estable_con_clave_y_distinta_de_sha256(monkeypatch):
    monkeypatch.setenv("CLAVE_HUELLAS", "clave-de-prueba")
    pv._clave.cache_clear()
    a = pv.huella("juli_k")
    assert a == pv.huella("juli_k") and len(a) == 12
    assert a != hashlib.sha256(b"juli_k").hexdigest()[:12]
    monkeypatch.setenv("CLAVE_HUELLAS", "otra-clave")
    pv._clave.cache_clear()
    assert pv.huella("juli_k") != a          # sin la clave, no se puede reproducir
    pv._clave.cache_clear()


def test_sin_clave_en_env_se_crea_un_archivo_privado(monkeypatch, tmp_path):
    monkeypatch.delenv("CLAVE_HUELLAS", raising=False)
    monkeypatch.setattr(pv, "ARCHIVO_CLAVE", tmp_path / ".clave_huellas")
    pv._clave.cache_clear()
    primera = pv.huella("x")
    assert (tmp_path / ".clave_huellas").exists() and oct((tmp_path / ".clave_huellas").stat().st_mode)[-3:] == "600"
    pv._clave.cache_clear()
    assert pv.huella("x") == primera          # misma clave en la corrida siguiente
    pv._clave.cache_clear()


def test_resumen_texto_no_guarda_el_texto():
    r = pv.resumen_texto("mi correo es a@b.cl")
    assert r == {"largo": 19, "huella": pv.huella("mi correo es a@b.cl"), "pii": ["correo"]}
