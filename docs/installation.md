# Instalación

## Prerrequisitos

- Docker + Docker Compose (o Colima en macOS)
- `git`, `make`
- (Opcional) Python 3.12 para herramientas de dev en host

## 1. Clonar el repo

```bash
git clone https://github.com/your-org/odoo-l10n-peru-ce.git
cd odoo-l10n-peru-ce
```

## 2. Clonar dependencias OCA

```bash
make deps
```

Esto pobla `oca-deps/` con: `server-tools`, `server-ux`, `account-financial-reporting`,
`reporting-engine`, `queue`, `web` (todos en branch 18.0).

## 3. Configurar entorno

```bash
cp .env.example .env
$EDITOR .env
```

Mínimo cambia `POSTGRES_PASSWORD`. Los puertos por defecto (8169/8172) evitan choque
con otros stacks de Odoo. Si tu 8169 está libre déjalos así.

## 4. Levantar stack

```bash
make up
make logs
```

Cuando veas `HTTP service (werkzeug) running on ...:8069` (interno; expuesto en 8169)
abre <http://localhost:8169>.

## 5. Crear la primera BD

En el formulario "Create Database":

- **Master Password**: `admin` (definido en `config/odoo.conf` → cámbialo después)
- **Database Name**: `peru_dev` (o lo que quieras)
- **Email** / **Password**: del usuario admin
- **Language**: `Spanish (PE) / Español (Perú)`
- **Country**: `Peru` ← dispara la instalación de `l10n_pe` core
- **Demo data**: marca en dev

## 6. Instalar nuestros módulos

```bash
# Empezando por el más bajo en la cadena de dependencias:
make install MOD=l10n_pe_base_extras DB=peru_dev
make install MOD=l10n_pe_coa_pcge2019 DB=peru_dev
make install MOD=l10n_pe_taxes_extras DB=peru_dev
# ... etc.
```

O instala todos los que quieras desde **Apps** en la UI tras `Update Apps List`.

## 7. (Cuando llegues a EDI) Configurar certificado de firma

Coloca tu `.pfx` en `certificates/`. **No commitear.** Para BETA puedes usar el
certificado demo de SUNAT (formato Llama-PE) que el módulo `l10n_pe_edi` incluirá
como fallback con un flag `production=False`.

## Comandos comunes

```bash
make up         # levantar
make down       # detener (preserva datos)
make logs       # tail logs Odoo
make restart    # reiniciar Odoo (tras editar odoo.conf)
make psql       # psql a la BD
make shell      # bash en container Odoo
make install MOD=<mod> DB=<db>
make update  MOD=<mod> DB=<db>
make test    MOD=<mod> DB=<db>
make test-all
make lint
make fresh      # DESTRUCTIVO: borra BD + filestore
```
