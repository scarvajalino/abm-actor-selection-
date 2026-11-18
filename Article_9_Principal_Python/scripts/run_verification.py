"""Run T01--T19, retain ten populations and write evidence-backed reports."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from article9.config import Config
from article9.export import environment, source_hashes, write_json
from article9.randomness import STREAM_IDS, Streams


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    output = args.out.resolve()
    if output.exists() and any(output.iterdir()):
        parser.error("Use an empty/new output directory; verification artifacts are not overwritten")
    output.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["M1_ACCEPTANCE_OUTPUT"] = str(output / "data")
    env["PYTHONPATH"] = str(ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    xml = output / "pytest_results.xml"
    command = [sys.executable, "-m", "pytest", "-q", "tests/test_acceptance.py", "--junitxml", str(xml)]
    process = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True)
    log = process.stdout + process.stderr
    (output / "pytest_output.txt").write_text(log, encoding="utf-8")
    print(log, end="")
    cases = []
    if xml.exists():
        for case in ET.parse(xml).getroot().iter("testcase"):
            match = re.search(r"T\d{2}", case.attrib.get("name", ""))
            if not match:
                continue
            failure = case.find("failure")
            error = case.find("error")
            skipped = case.find("skipped")
            status = "failed" if failure is not None or error is not None else "skipped" if skipped is not None else "passed"
            properties = [json.loads(p.attrib["value"]) for p in case.findall("./properties/property") if p.attrib.get("name") == "evidence"]
            cases.append({"test_id": match.group(), "name": case.attrib["name"], "status": status,
                          "seconds": float(case.attrib.get("time", 0)), "evidence": properties,
                          "error": ((failure.text or "") if failure is not None else (error.text or "") if error is not None else "")})
    passed = sum(c["status"] == "passed" for c in cases)
    complete = len(cases) == 19 and passed == 19 and process.returncode == 0
    report = {"model_version": "0.1.0", "specification_version": "0.1", "status": "passed" if complete else "failed",
              "pytest_exit_code": process.returncode, "tests_expected": 19, "tests_executed": len(cases),
              "tests_passed": passed, "scope": "M1_network_attributes_selection",
              "diffusion_campaigns": 0, "environment": environment(), "code_sha256": source_hashes(), "tests": cases}
    write_json(output / "verification_report.json", report)
    config = Config()
    write_json(output / "config_base.json", config.to_dict())
    write_json(output / "Article_9_M1_Configuracion_y_semillas_v0.1.json",
               {"model_version": "0.1.0", "parameters": config.to_dict(), "repetitions": list(range(10)),
                "stream_identifiers": STREAM_IDS,
                "stream_seeds_by_repetition": {str(r): Streams(config.master_seed, r).record() for r in range(10)},
                "scope": "10_initializations_and_70_selections_not_diffusion_campaigns"})
    t19 = next((x for x in cases if x["test_id"] == "T19"), None)
    inspection = t19["evidence"][0] if t19 and t19["evidence"] else {}
    inspection_lines = []
    if inspection and (output / "data/network_diagnostics_all.csv").exists():
        networks = pd.read_csv(output / "data/network_diagnostics_all.csv")
        policies = pd.read_csv(output / "data/policy_diagnostics_all.csv")
        inspection_lines = ["| Diagnóstico estructural | Mínimo | Máximo |", "|---|---:|---:|"]
        for column, label in [("n_edges", "Vínculos"), ("degree_mean", "Grado medio"),
                              ("average_clustering", "Agrupamiento medio"), ("modularity", "Modularidad"),
                              ("largest_component_fraction", "Fracción en componente mayor")]:
            inspection_lines.append(f"| {label} | {networks[column].min():.4f} | {networks[column].max():.4f} |")
        inspection_lines += ["", "Promedios descriptivos de las diez inicializaciones:", "",
                             "| Política | Vecinos potenciales únicos | Grado de seleccionados | Actividad de seleccionados | Puntaje de opinión |",
                             "|---|---:|---:|---:|---:|"]
        fields = ["potential_unique_neighbors", "degree_mean", "activity_mean", "opinion_score_mean"]
        for policy, row in policies.groupby("policy")[fields].mean().iterrows():
            inspection_lines.append(f"| {policy} | {row.iloc[0]:.1f} | {row.iloc[1]:.2f} | {row.iloc[2]:.3f} | {row.iloc[3]:.3f} |")
        inspection_lines += ["", "Estos promedios describen las selecciones y sus contactos potenciales. No miden difusión, adopción o ingresos y no establecen una política comercialmente superior.", ""]
    lines = ["# Artículo 9 Informe de implementación y verificación M1", "",
             "**Versión del código:** 0.1.0. **Especificación:** M1 v0.1. **Fecha:** 25 de septiembre de 2026.", "",
             f"**Resultado:** {passed} de 19 pruebas aprobadas. Estado general: {'APROBADO' if complete else 'REQUIERE CORRECCIÓN'}.", "",
             "## Alcance", "",
             "Se implementaron en Python la red modular fija, los atributos continuos, los valores económicos latentes separados, los puntajes y las siete políticas de selección. Cada política usa información anterior a la campaña. Los estados iniciales permiten marcar la selección sin crear adopción, satisfacción, comunicación o ingresos.", "",
             "Se exportan configuraciones, semillas, tablas de nodos y enlaces, selecciones, auditoría de decisiones, estados iniciales, diagnósticos y huellas SHA-256. Las salidas existentes se protegen contra sobrescritura accidental.", "",
             "## Evidencia de verificación", "",
             "| Prueba | Resultado | Evidencia |", "|---|---|---|"]
    for case in cases:
        evidence = json.dumps(case["evidence"], ensure_ascii=False, sort_keys=True).replace("|", "/")
        lines.append(f"| {case['test_id']} | {case['status']} | {evidence} |")
    lines += ["", "## Inspección de diez poblaciones", "",
              f"Registro obtenido de T19: `{json.dumps(inspection, ensure_ascii=False, sort_keys=True)}`.", "",
              "La semilla maestra es 20260925 y se conservaron las repeticiones 0 a 9. Cada población tiene 600 personas, seis comunidades y siete selecciones de 20 actores. Son 70 conjuntos seleccionados y 1400 plazas registradas, no 70 campañas de difusión. No se descartaron redes para favorecer resultados.", "",
              *inspection_lines,
              "Las pruebas incluyen cálculos manuales de métricas y puntajes, ausencia de uso de resultados futuros, cuotas comunitarias, rankings híbridos coincidentes, empates, estados iniciales, redes vacías y completas, reproducción de archivos, independencia del orden de políticas y lectura de exportaciones.", "",
              "## Decisiones técnicas", "",
              "La implementación sigue los supuestos de la especificación. Se incorporó `initial_states.csv` como exportación adicional para comprobar directamente que seleccionar no activa adopción ni WOM. `require_modular=False` se utiliza exclusivamente para controles extremos, como la red vacía. El escenario base conserva `require_modular=True`.", "",
              "`verification_report.json` y el registro JUnit corresponden a la batería completa y se guardan en el nivel general de verificación; no se duplican en cada repetición. Las tablas de diagnóstico acumuladas reúnen las diez inicializaciones. Los valores ausentes tienen una razón explícita cuando una métrica no está definida.", "",
              "## Interpretación y límites", "",
              "El resultado verifica la correspondencia entre código y reglas, no valida empíricamente las hipótesis. La audiencia potencial depende de los vecinos disponibles a un paso; no representa alcance observado ni permite declarar una política comercialmente superior. La red base utiliza bloques estocásticos y no incorpora hubs de cola pesada ni cierre triádico deliberado.", "",
              "Los atributos se generan de manera independiente en esta versión. Aún faltan las correlaciones controladas, la adopción, la satisfacción, la difusión, la atribución de ingresos y la evaluación del liderazgo realizado. El siguiente módulo es M2, antes del piloto de campañas y de los experimentos principales.", "",
              "## Reproducción", "", "Consultar `README.md` del paquete de código. La verificación se reproduce con:", "",
              "```bash", "python scripts/run_verification.py --out outputs/verification", "```", "",
              "Usar una ruta nueva para cada ejecución. Las versiones verificadas están en `requirements-lock.txt` y el entorno efectivo en `verification_report.json`. Las fechas y la duración de las pruebas pueden cambiar; los datos deterministas se comparan por sus huellas.", "",
              "## Referencias técnicas", "",
              "- [NumPy random sampling](https://numpy.org/doc/stable/reference/random/index.html)",
              "- [NetworkX average clustering](https://networkx.org/documentation/stable/reference/algorithms/generated/networkx.algorithms.cluster.average_clustering.html)",
              "- [NetworkX modularity](https://networkx.org/documentation/stable/reference/algorithms/generated/networkx.algorithms.community.quality.modularity.html)", ""]
    (output / "Article_9_M1_Informe_verificacion_v0.1.md").write_text("\n".join(lines), encoding="utf-8")
    return 0 if complete else 1


if __name__ == "__main__":
    raise SystemExit(main())
