# Imagen base de Odoo 18 CE + deps para firma XAdES (XML signature).
#
# La imagen oficial odoo:18.0 NO trae libxmlsec1 ni python-xmlsec.
# Además, xmlsec compilado contra libxml2 distinto al que lxml usa rompe en
# runtime con "lxml & xmlsec libxml2 library version mismatch". Por eso
# RECOMPILAMOS lxml y xmlsec desde fuente contra la misma libxml2 del sistema.

FROM odoo:18.0

USER root

# ─── Deps del sistema para compilar lxml + xmlsec ──────────────────────
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libxmlsec1-dev \
        libxml2-dev \
        libxslt1-dev \
        python3-dev \
        zlib1g-dev \
        libssl-dev \
        pkg-config \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

# ─── Python deps para EDI peruano ──────────────────────────────────────
# --no-binary=lxml,xmlsec FUERZA compilar desde fuente contra el libxml2 del
# sistema → mismo binario en runtime → sin version mismatch.
RUN pip install --break-system-packages \
        --force-reinstall \
        --no-binary=lxml,xmlsec \
        lxml \
        xmlsec \
    && pip install --break-system-packages \
        qrcode \
        zeep \
        httpx \
    && rm -rf /root/.cache/pip

USER odoo
