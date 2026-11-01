# OCR 0.8.33: robustez de extracción

Tres fallos reproducidos antes del cambio: PNG transparente con texto negro ilegible tras convertir a RGB; texto digital de más de 30000 caracteres truncado sin indicación; fallo inesperado de una página que abortaba la lectura de las demás.

Se compone la transparencia sobre blanco, se declara texto_truncado y cobertura parcial con aviso visible, y se conserva un estado no_leida por cada página fallida continuando con las demás. Un PDF inválido que no puede abrirse sigue produciendo error de archivo completo. No se muestran trazas internas.

Pruebas permanentes con OCR real de PNG transparente y páginas vacías PNG/JPEG, recorte, fallo de página simulado y documentos dañados. Continúan los límites de cinco páginas, 15 MB y revisión humana. No garantiza reconocimiento de fotos borrosas o manuscritos.
