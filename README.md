# VERU MVP

Auditoría automática de contenido de marketing de creadores en TikTok. Verifica la divulgación publicitaria, el cumplimiento del brief, la aparición del producto y un checklist de compliance por país, y emite un veredicto semaforizado (APROBADO, OBSERVADO o RECHAZADO) con motivos y marcas de tiempo.

> **Estado:** prototipo (MVP) en desarrollo. Las reglas de compliance de `reglas/pe.json` son un **borrador pendiente de validación legal**.

## Qué hace

1. Recibe un video (MP4 o link público de TikTok), la marca y los requisitos de la campaña.
2. Detecta la etiqueta publicitaria en la descripción (metadatos) y en pantalla (OCR).
3. Con Gemini transcribe el audio, evalúa el brief y verifica si el producto aparece.
4. Aplica el checklist de compliance del país (Perú / Indecopi, borrador).
5. Genera un reporte PDF y guarda la auditoría en Supabase.
6. Borra el video temporal (local y en Gemini).

## Semáforo

| Veredicto | Significado |
|---|---|
| APROBADO | Divulgación, brief, producto y checklist cumplen |
| OBSERVADO | Hay algo dudoso (equivalencia, coincidencia aproximada, ítems por revisar): requiere revisión humana |
| RECHAZADO | Falta divulgación, incumple el brief o el producto no es visible |

## Arquitectura

```
URL o MP4
   │
   ├─► Metadatos (yt-dlp)  ─┐
   ├─► OCR (EasyOCR, solo si no hay etiqueta en metadatos) ─┤► Divulgación
   └─► Gemini (transcripción, brief, producto, compliance) ─┘
                                   │
                         Checklist por país (reglas/*.json)
                                   │
                          Semáforo ─► PDF ─► Supabase
```

## Estructura del proyecto

```
veru-mvp/
├── main.py                  # API FastAPI (endpoints y auth)
├── reglas/
│   └── pe.json              # Reglas de compliance por país (borrador)
├── app/
│   ├── modules/
│   │   ├── ocr.py           # Lectura de texto en frames
│   │   ├── metadata.py      # Descripción y hashtags del post
│   │   ├── divulgacion.py   # Combina metadatos + OCR
│   │   ├── brief.py         # Gemini: brief, producto, transcripción
│   │   ├── compliance.py    # Evalúa el checklist del país
│   │   ├── semaforo.py      # Veredicto final
│   │   ├── reporte.py       # Generación del PDF
│   │   └── db.py            # Supabase: auditorías y auth
│   ├── mock/                # Respuesta guardada de Gemini (pruebas)
│   ├── uploads/             # Videos temporales (se borran)
│   └── reports/             # PDFs generados
└── test_*.py                # Scripts de prueba por módulo
```

## Requisitos

- Python 3.12 (3.15 aún no tiene soporte de varias librerías)
- ffmpeg instalado y en el PATH
- Cuenta de Google AI Studio (API key de Gemini)
- Proyecto de Supabase

## Instalación

```bash
git clone https://github.com/Dacc03/veru-mvp.git
cd veru-mvp
py -3.12 -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

## Configuración

Crea un archivo `.env` en la raíz (nunca lo subas al repositorio):

```env
GEMINI_API_KEY=
GEMINI_MODEL=gemini-3.6-flash
GEMINI_MOCK=0
SUPABASE_URL=
SUPABASE_KEY=            # anon key (registro y login)
SUPABASE_SERVICE_KEY=    # service_role (solo servidor)
```

Hay un `.env.example` de referencia. `GEMINI_MOCK=1` usa la última respuesta guardada de Gemini y no gasta cuota; sirve para probar PDF, endpoints y base de datos.

### Base de datos

Tabla `auditorias` en Supabase con RLS activado. Columnas: `id`, `marca`, `video_url`, `veredicto`, `motivos` (jsonb), `resultado` (jsonb), `reporte_pdf`, `divulgacion_detectada`, `producto_detectado`, `brief_cumplido`, `user_id`, `created_at`.

## Ejecutar

```bash
uvicorn main:app --reload
```

Documentación interactiva en `http://127.0.0.1:8000/docs`.

## Endpoints

| Método | Ruta | Descripción |
|---|---|---|
| POST | `/auth/register` | Registro de usuario |
| POST | `/auth/login` | Login, devuelve el token |
| POST | `/audit` | Audita un video (link o MP4) y genera el PDF |
| GET | `/audits` | Historial del usuario |
| GET | `/audits/{id}/report` | Descarga el PDF |

Los endpoints de auditoría requieren `Authorization: Bearer <token>`. Cada usuario ve solo sus auditorías.

## Pruebas por módulo

```bash
python test_ocr.py app/uploads/video1.mp4
python test_meta.py "<link>"
python test_divulgacion.py "<link>" app/uploads/video1.mp4
python test_brief.py app/uploads/video1.mp4
python test_pdf.py "<link>" app/uploads/video1.mp4
```

## Privacidad y seguridad

- Los videos son temporales: se borran del disco tras auditar y de Gemini al terminar.
- Acceso solo para usuarios registrados; cada uno ve únicamente lo suyo.
- Las claves van en `.env`; la `service_role` nunca debe exponerse fuera del servidor.
- Pendiente: política de privacidad y consentimiento conforme a la Ley N.º 29733.

## Limitaciones conocidas

- `APROBADO` indica que la etiqueta publicitaria está presente, no que sea legalmente suficiente. Un hashtag como `#publicidad` puede usarse solo por alcance.
- No se puede leer el rótulo oficial de TikTok ("Contenido promocional"), porque no está en el video ni en los metadatos accesibles.
- El OCR en CPU es lento (decenas de segundos); el objetivo de menos de 1 minuto depende del hardware.
- El plan gratuito de Gemini limita las llamadas diarias por modelo.
- Los timestamps de la transcripción son orientativos.
- La precisión (detección ≥ 80 %, falsos positivos ≤ 15 %) está pendiente de medir con un set de videos etiquetados por humanos.

## Hoja de ruta

- [x] Divulgación (metadatos + OCR)
- [x] Brief, producto y transcripción con Gemini
- [x] Semáforo y reporte PDF
- [x] API con auth y guardado en Supabase
- [x] Checklist por país (Perú, borrador)
- [ ] Validación legal de las reglas
- [ ] Evaluación de precisión con videos reales
- [ ] Errores parciales (si Gemini falla, pedir revisión humana)
- [ ] PDFs en Supabase Storage
- [ ] Reglas para México, Chile y Brasil