"""Run 19 M1 regression tests and 22 M2 tests; retain traceable examples."""
import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from zoneinfo import ZoneInfo
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from article9.config import Config
from article9.event_random import EventRandom
from article9.export import environment, source_hashes, write_json
from article9.m2_config import DiffusionConfig, M2_VERSION
from article9.randomness import STREAM_IDS


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    output = args.out.resolve()
    if output.exists() and any(output.iterdir()):
        parser.error("Use a new or empty output directory")
    output.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["M1_ACCEPTANCE_OUTPUT"] = str(output / "m1_regression_data")
    env["M2_ACCEPTANCE_OUTPUT"] = str(output / "m2_demonstrations")
    env["PYTHONPATH"] = str(ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    xml = output / "pytest_results.xml"
    process = subprocess.run([sys.executable, "-m", "pytest", "-q", "tests/test_acceptance.py", "tests/test_m2.py", "--junitxml", str(xml)],
                             cwd=ROOT, env=env, capture_output=True, text=True)
    log = process.stdout + process.stderr
    (output / "pytest_output.txt").write_text(log, encoding="utf-8")
    print(log, end="")
    cases = []
    if xml.exists():
        for case in ET.parse(xml).getroot().iter("testcase"):
            match = re.search(r"[TU]\d{2}", case.attrib.get("name", ""))
            if not match:
                continue
            failure, error, skipped = case.find("failure"), case.find("error"), case.find("skipped")
            status = "failed" if failure is not None or error is not None else "skipped" if skipped is not None else "passed"
            evidence = [json.loads(p.attrib["value"]) for p in case.findall("./properties/property") if p.attrib.get("name") == "evidence"]
            cases.append({"test_id": match.group(), "name": case.attrib["name"], "status": status,
                          "seconds": float(case.attrib.get("time", 0)), "evidence": evidence,
                          "error": (failure.text or "") if failure is not None else (error.text or "") if error is not None else ""})
    expected = {f"T{i:02d}" for i in range(1, 20)} | {f"U{i:02d}" for i in range(1, 23)}
    complete = (len(cases) == 41 and {c["test_id"] for c in cases} == expected and
                all(c["status"] == "passed" for c in cases) and process.returncode == 0)
    date = datetime.now(ZoneInfo("America/Bogota")).isoformat(timespec="seconds")
    report = {"m2_version": M2_VERSION, "m1_baseline_version": "0.1.0", "generated_at": date,
              "status": "passed" if complete else "failed", "pytest_exit_code": process.returncode,
              "tests_expected": 41, "tests_executed": len(cases), "tests_passed": sum(c["status"] == "passed" for c in cases),
              "m1_regression_tests": 19, "m2_tests": 22, "environment": environment(),
              "code_sha256": source_hashes(), "tests": cases, "scope": "verification_not_main_experiment"}
    write_json(output / "verification_report.json", report)
    base, config = Config(), DiffusionConfig()
    write_json(output / "m1_config_base.json", base.to_dict())
    write_json(output / "m2_config_base.json", config.to_dict())
    write_json(output / "Article_9_M2_Configuracion_y_semillas_v0.2.json", {
        "m2_version": M2_VERSION, "m1_parameters": base.to_dict(), "m2_parameters": config.to_dict(),
        "m1_stream_identifiers": STREAM_IDS, "m1_regression_repetitions": list(range(10)),
        "m2_demonstration_repetitions": list(range(3)), "master_seed": base.master_seed,
        "event_random_by_repetition": {str(r): EventRandom(base.master_seed, r).record() for r in range(3)},
        "scope": "21_verification_campaigns_not_main_experiment"})
    lines = ["# Artículo 9 Implementación y verificación de M2", "",
             f"**Versión:** {M2_VERSION}. **Fecha:** {date}.", "",
             f"**Resultado:** {report['tests_passed']} de 41 pruebas aprobadas. Estado: {'APROBADO' if complete else 'REQUIERE CORRECCIÓN'}.", "",
             "M2 incorpora evaluación del producto, adopción, experiencia y satisfacción, emisión de WOM positivo, selección de contactos sin repetición por emisor y trazabilidad de cascadas. Las reglas y los parámetros son supuestos teóricos ilustrativos sin calibración empírica.", "",
             "## Verificación", "",
             "Se ejecutaron las 19 pruebas de M1 y 22 pruebas de M2. Los registros JSON y JUnit permiten comprobar cada resultado.", "",
             "| Prueba | Estado | Evidencia |", "|---|---|---|"]
    for c in cases:
        detail = json.dumps(c["evidence"], ensure_ascii=False, sort_keys=True).replace("|", "/")
        lines.append(f"| {c['test_id']} | {c['status']} | {detail} |")
    lines += ["", "## Ejemplos integrados", ""]
    summary_path = output / "m2_demonstrations/summary_all.csv"
    if summary_path.exists():
        summaries = pd.read_csv(summary_path)
        diagnostic_warnings = []
        if (summaries.adoption_fraction >= .95).all():
            diagnostic_warnings.append("all_verification_campaigns_at_least_95_percent_adoption")
        report["diagnostic_warnings"] = diagnostic_warnings
        write_json(output / "verification_report.json", report)
        fields = ["awareness_count", "adoption_count", "wom_messages_cumulative", "wom_unique_reach", "repeated_wom_exposures"]
        lines += ["Se conservaron tres poblaciones con semillas de repetición 0, 1 y 2, siete políticas por población y 60 períodos por campaña: **21 campañas de verificación**. Cada población contiene 600 personas y cada política selecciona 20 actores. Todas las trazas se incluyen en los datos.", "",
                  "Promedios de los tres ejemplos por política:", "",
                  "| Política | Conocimiento de la oferta | Adopciones | Mensajes WOM | Alcance WOM único | Exposiciones WOM repetidas |",
                  "|---|---:|---:|---:|---:|---:|"]
        for policy, row in summaries.groupby("policy")[fields].mean().iterrows():
            lines.append(f"| {policy} | " + " | ".join(f"{v:.1f}" for v in row.tolist()) + " |")
        lines += ["", f"Adopciones finales observadas entre campañas: {int(summaries.adoption_count.min())}–{int(summaries.adoption_count.max())}. Mensajes WOM registrados: {int(summaries.wom_messages_cumulative.sum())}.", ""]
        if diagnostic_warnings:
            lines += ["**Diagnóstico de saturación:** todas las campañas verificadas superan el 95% de adopción. Con esta configuración, la adopción final ofrece poca separación entre políticas. Se deben examinar las trayectorias temporales y la sensibilidad de las reglas de adopción, satisfacción y comunicación antes de fijar el experimento principal. Este hallazgo no se corrigió ajustando parámetros para favorecer una política.", ""]
    lines += ["Estos ejemplos comprueban la integración y permiten revisar las trayectorias. Tres repeticiones no establecen un ranking robusto entre políticas ni sustituyen el piloto o el experimento principal. No se ajustaron parámetros para hacer ganar una política.", "",
              "## Decisiones operativas", "",
              "- Período 0: selección. Período 1: información directa, evaluación y posible adopción de seleccionados. Los nuevos adoptantes pueden enviar WOM desde el período siguiente.",
              "- Cada emisor contacta como máximo una vez a cada vecino no adoptante. Un receptor puede recibir varios emisores y acumular exposiciones repetidas.",
              "- Una sola decisión de adopción por receptor y período con nuevos mensajes; se usa la mayor señal creíble actual y el número acumulado de emisores distintos.",
              "- Solo los adoptantes satisfechos con actividad, disposición, capacidad y contactos disponibles pueden enviar WOM. La satisfacción no garantiza el envío.",
              "- Los sorteos se indexan por evento, período y actores; no incluyen la política y no dependen del orden de llamadas.",
              "- Cada adopción WOM tiene un único padre contable y hereda la raíz de su cascada. Esa atribución es una convención trazable, no una identificación causal del efecto de un mensaje.", "",
              "## Límites y siguiente módulo", "",
              "La experiencia se representa por una función simple de calidad y ajuste del producto; no hay aprendizaje o experiencias repetidas. La red, la necesidad y los atributos permanecen fijos. Se conserva el alcance positivo y no se incorporan WOM negativo, fatiga, incentivos o cambios de red. M2 aún no calcula ingresos, utilidad, recompra ni precisión del liderazgo económico previsto.", "",
              "El siguiente módulo es M3: compras valoradas, costos, ingresos y atribución monetaria sin doble conteo. El universo para comparar liderazgo previsto y realizado debe definirse antes de calcular precisión o recall.", "",
              "## Reproducción", "", "```bash", "python scripts/verify_m2.py --out outputs/m2_verification", "```", "",
              "Se requieren las versiones de `requirements-lock.txt`; usar una carpeta nueva de salida. El paquete contiene M1, M2, ambas baterías de pruebas, configuraciones simples y documentación. `run_m2.py` ejecuta campañas sin invocar toda la verificación.", ""]
    (output / "Article_9_M2_Informe_verificacion_v0.2.md").write_text("\n".join(lines), encoding="utf-8")
    return 0 if complete else 1


if __name__ == "__main__":
    raise SystemExit(main())
