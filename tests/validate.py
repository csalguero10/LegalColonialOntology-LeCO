from rdflib import Graph
from pyshacl import validate

ontology_file = "ontology/LeCO_v0_3_gap_resolved.ttl"
shapes_file = "shapes/LeCO_v0_3_shapes.ttl"
data_file = "data/LeCO_SHACL_example_Pineda.ttl"

# 1. Cargar ontología
ontology = Graph()
ontology.parse(ontology_file, format="turtle")

print(f"Ontología cargada: {len(ontology)} triples")

# 2. Cargar datos
data = Graph()
data.parse(data_file, format="turtle")

print(f"Datos cargados: {len(data)} triples")

# 3. Cargar SHACL
shapes = Graph()
shapes.parse(shapes_file, format="turtle")

print(f"Shapes cargadas: {len(shapes)} triples")

# 4. Validar
conforms, results_graph, results_text = validate(
    data_graph=data,
    shacl_graph=shapes,
    ont_graph=ontology,
    inference="rdfs",
    abort_on_first=False,
    allow_infos=True,
    allow_warnings=True,
)

print("\n=== RESULTADO ===")
print("Conforma:", conforms)

print("\n=== REPORTE SHACL ===")
print(results_text)