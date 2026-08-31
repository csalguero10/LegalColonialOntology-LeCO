# LeCO — diagnóstico SHACL del corpus

## Objetivo

`analyze_shacl_reports.py` analiza los reportes Turtle generados por pySHACL para todos los documentos. No modifica TEI, RDF, ontología ni shapes.

La finalidad es separar empíricamente:

1. errores de integridad que deben seguir siendo `sh:Violation`;
2. ausencia de información histórica que puede ser más adecuada como `sh:Warning`;
3. problemas de mapping o vocabulario controlado;
4. patrones excepcionales que requieren revisión documental.

## Entrada

Por defecto:

```text
build/shacl_reports/*.ttl
```

## Ejecución

Desde la raíz del repositorio:

```bash
python scripts/analyze_shacl_reports.py
```

## Salidas

```text
build/shacl_analysis.csv
build/shacl_analysis_summary.csv
build/shacl_analysis.json
```

### `shacl_analysis.csv`

Una fila por `sh:ValidationResult`, con:

- `document`
- `report_file`
- `conforms`
- `severity`
- `focus_node`
- `source_shape`
- `constraint`
- `result_path`
- `value`
- `message`

### `shacl_analysis_summary.csv`

Agrupa problemas repetidos dentro de cada documento y añade `count`.

### `shacl_analysis.json`

Incluye:

- número de reportes;
- documentos conformes/no conformes;
- número total de resultados;
- recuento por severidad;
- estado de cada documento;
- patrones de constraint/propiedad en todo el corpus;
- detalle completo de los resultados.

## Interpretación metodológica

El script **no reclasifica** automáticamente una constraint de `Violation` a `Warning`. Esa decisión se toma después de examinar el patrón en los 19 documentos y regresar a la evidencia cuando sea necesario.

Un `MinCountConstraintComponent` frecuente sobre `leco:withinJurisdiction`, por ejemplo, no demuestra por sí mismo que la shape sea demasiado estricta. Solo muestra que la propiedad falta repetidamente. Habrá que determinar si la ausencia corresponde a:

- una relación que sí está sustentada pero no fue migrada;
- una inferencia estructural justificable;
- una carencia real de la fuente;
- o un requisito SHACL que debería ser de calidad/completitud y no de integridad.

## Próximo paso

Después de ejecutar el análisis, revisar primero los patrones más frecuentes y los casos que afectan a mayor número de documentos. Solo después se modifica `LeCO_shapes.ttl`, el mapping o el enriquecedor.
