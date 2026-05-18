# Certificados de firma digital

⚠️ **NUNCA commitear archivos .pfx, .p12, .key, .pem reales.**

Esta carpeta se monta en `/opt/odoo/certificates` dentro del container.
Los módulos de EDI leerán los certificados desde aquí.

Para BETA SUNAT puedes usar el certificado **demo Llama-PE** (gratuito, solo BETA):
- Ubicación esperada: `certificates/llama_pe_demo.pfx`
- Password por defecto: `123456`
- Se descargará automáticamente por `make deps` o se documentará por separado.

Para producción: usa tu certificado real emitido por una entidad acreditada
(LLAMA.PE, Camerfirma Perú, ESign Perú, etc.).
