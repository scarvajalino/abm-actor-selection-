"""Run M1/M2 regression and M3 verification; retain data, provenance and report."""
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
from article9.economic_random import EconomicRandom
from article9.event_random import EventRandom
from article9.export import environment, source_hashes, write_json
from article9.m2_config import DiffusionConfig
from article9.m3_config import EconomicConfig, M3_VERSION
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
    for module, folder in [("M1", "m1_regression_data"), ("M2", "m2_demonstrations"), ("M3", "m3_demonstrations")]:
        env[f"{module}_ACCEPTANCE_OUTPUT"] = str(output / folder)
    env["PYTHONPATH"] = str(ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    xml = output / "pytest_results.xml"
    process = subprocess.run([sys.executable, "-m", "pytest", "-q", "tests", "--junitxml", str(xml)],
                             cwd=ROOT, env=env, capture_output=True, text=True)
    log = process.stdout + process.stderr
    (output / "pytest_output.txt").write_text(log, encoding="utf-8")
    print(log, end="")
    cases = []
    if xml.exists():
        for case in ET.parse(xml).getroot().iter("testcase"):
            match = re.search(r"[TUV]\d{2}", case.attrib.get("name", ""))
            if not match:
                continue
            failure, error, skipped = case.find("failure"), case.find("error"), case.find("skipped")
            status = "failed" if failure is not None or error is not None else "skipped" if skipped is not None else "passed"
            evidence = [json.loads(p.attrib["value"]) for p in case.findall("./properties/property") if p.attrib.get("name") == "evidence"]
            cases.append({"test_id": match.group(), "name": case.attrib["name"], "status": status,
                "seconds": float(case.attrib.get("time", 0)), "evidence": evidence,
                "error": (failure.text or "") if failure is not None else (error.text or "") if error is not None else ""})
    expected = {f"T{i:02d}" for i in range(1, 20)} | {f"U{i:02d}" for i in range(1, 23)} | {f"V{i:02d}" for i in range(1, 23)}
    complete = len(cases) == 63 and {c["test_id"] for c in cases} == expected and all(c["status"] == "passed" for c in cases) and process.returncode == 0
    date = datetime.now(ZoneInfo("America/Bogota")).isoformat(timespec="seconds")
    report = {"m3_version": M3_VERSION, "generated_at": date, "status": "passed" if complete else "failed",
        "pytest_exit_code": process.returncode, "tests_expected": 63, "tests_executed": len(cases),
        "tests_passed": sum(c["status"] == "passed" for c in cases), "m1_tests": 19, "m2_tests": 22, "m3_tests": 22,
        "scope": "verification_not_main_experiment", "environment": environment(), "code_sha256": source_hashes(), "tests": cases}
    base = Config()
    write_json(output / "Article_9_M3_Configuracion_y_semillas_v0.3.json", {
        "m3_version": M3_VERSION, "m1_parameters": base.to_dict(), "m2_parameters": DiffusionConfig().to_dict(),
        "m3_parameters": EconomicConfig().to_dict(), "m1_stream_identifiers": STREAM_IDS,
        "verification_repetitions": [0, 1, 2], "master_seed": base.master_seed,
        "m2_event_random": {str(r): EventRandom(base.master_seed, r).record() for r in range(3)},
        "m3_event_random": {str(r): EconomicRandom(base.master_seed, r).record() for r in range(3)},
        "supplementary": {"repetition": 0, "policies": ["random", "predicted_revenue"],
                          "repurchase_probability": .05, "attribution_alpha": [0, .5, 1]},
        "scope": "21_base_and_6_supplementary_verification_campaigns_not_main_experiment"})
    lines = ["# Artículo 9. Implementación y verificación de M3", "",
        f"Versión {M3_VERSION}. Fecha: {date}.", "",
        f"**Resultado: {report['tests_passed']} de 63 pruebas aprobadas.** Estado: {'APROBADO' if complete else 'REQUIERE CORRECCIÓN'}.", "",
        "M3 agrega compras, recompra opcional, costos, utilidad, atribución económica y evaluación condicional del liderazgo previsto. Los valores son unidades monetarias abstractas y los parámetros son supuestos teóricos, sin calibración empírica.", "",
        "## Pruebas", "", "Se preservan 19 pruebas de M1 y 22 de M2, y se agregan 22 de M3. Los casos pequeños usan resultados calculados a mano; las campañas de 600 personas usan los sorteos normales del modelo.", "",
        "| Prueba | Estado | Evidencia |", "|---|---|---|"]
    for c in cases:
        detail = json.dumps(c["evidence"], ensure_ascii=False, sort_keys=True).replace("|", "/")
        lines.append(f"| {c['test_id']} | {c['status']} | {detail} |")
    summary_path = output / "m3_demonstrations/summary_all.csv"
    if summary_path.exists():
        table = pd.read_csv(summary_path)
        report["diagnostic_warnings"] = ["all_base_campaigns_at_least_95_percent_adoption"] if (table.adoption_fraction >= .95).all() else []
        report["base_campaigns"] = {"count": len(table), "initial_purchases": int(table.initial_purchases.sum()),
            "adoption_min": int(table.adoption_count.min()), "adoption_max": int(table.adoption_count.max()),
            "revenue_min": float(table.revenue.min()), "revenue_max": float(table.revenue.max()),
            "profit_min": float(table.profit.min()), "profit_max": float(table.profit.max())}
        lines += ["", "## Campañas base", "",
            "Tres poblaciones, siete políticas, 600 personas, 20 seleccionados y 60 meses: **21 campañas económicas**. Las trazas de M2 y los atributos de M1 se vinculan por rutas relativas y hashes de contenido. La prueba V21 compara 84 hashes de entrada.", "",
            "Promedios de tres repeticiones por política; solo diagnósticos de verificación:", "",
            "| Política | Adopciones | Ingresos (u.m.) | Utilidad (u.m.) | Precisión condicional | Recall condicional |",
            "|---|---:|---:|---:|---:|---:|"]
        fields = ["adoption_count", "revenue", "profit", "conditional_leader_precision", "conditional_leader_recall"]
        for policy, row in table.groupby("policy")[fields].mean().iterrows():
            lines.append(f"| {policy} | " + " | ".join(f"{v:.4f}" for v in row) + " |")
        b = report["base_campaigns"]
        lines += ["", f"Compras iniciales registradas: {b['initial_purchases']:,}. Ingresos por campaña: {b['revenue_min']:.2f}–{b['revenue_max']:.2f} u.m. Utilidad: {b['profit_min']:.2f}–{b['profit_max']:.2f} u.m.", "",
            "Con la configuración base, la recompra está desactivada, el servicio cuesta 20% del ingreso y cada seleccionado cuesta 1 u.m. Por construcción, utilidad = 0,8 × ingresos − 20. Por tanto, el ranking por utilidad coincide con el de ingresos en estas condiciones; M3 no demuestra una divergencia entre ambos objetivos.", "",
            f"**Saturación heredada de M2:** {b['adoption_min']}–{b['adoption_max']} adoptantes de 600. No se modificaron parámetros para aumentar la separación entre políticas. Antes del experimento principal deben analizarse las trayectorias y la sensibilidad."]
    lines += ["", "## Comprobaciones económicas", "",
        "- Cada adoptante compra una sola vez inicialmente; una exposición adicional no crea una segunda compra inicial.",
        "- El costo de activación se cobra en el mes 0 a todos los seleccionados, incluidos quienes rechazan.",
        "- Comprador, recomendador inmediato, raíz y atribución ponderada son vistas alternativas. Cada vista completa suma los ingresos de la empresa; no se suman entre sí.",
        "- La atribución ponderada reparte 1−α al recomendador inmediato y α a la raíz; cuando coinciden, acumula un único crédito. Los costos de servicio siguen esas fracciones. El costo de activación permanece en el seleccionado.",
        "- Se verificaron seis escenarios adicionales: dos políticas de la repetición 0, recompra base de 0,05 y α en 0, 0,5 y 1. Cambiar α conserva compras, ingresos y utilidad de la empresa. Sus trazas se conservan en m3_supplementary.", "",
        "## Alcance de la evaluación predictiva", "",
        "El universo son los 20 seleccionados de cada campaña. Se comparan los cuatro con mayor índice ex ante con las raíces de mayor ingreso realizado. Los empates positivos en el límite realizado se incluyen completos; el ingreso cero no convierte a nadie en líder. La precisión, el recall, Spearman y el error de rango son condicionales a la campaña y a esa cartera, sin estimar qué habrían generado los 580 no seleccionados como raíces.", "",
        "El MAE monetario corresponde exclusivamente al valor previsto de compra frente a la compra inicial observada entre adoptantes. No se resta el índice de liderazgo a ingresos monetarios. La atribución no identifica contribución causal incremental.", "",
        "## Reproducción y siguiente paso", "", "```bash", "python -m pip install -r requirements-lock.txt", "python scripts/verify_m3.py --out outputs/m3_verification", "```", "",
        "Usar una carpeta nueva. La verificación completa no es el experimento principal. El siguiente paso es un piloto de sensibilidad para revisar saturación, tiempos de adopción y estabilidad económica antes de fijar condiciones y ejecutar al menos 100 repeticiones por condición principal.", ""]
    write_json(output / "verification_report.json", report)
    (output / "Article_9_M3_Informe_verificacion_v0.3.md").write_text("\n".join(lines), encoding="utf-8")
    return 0 if complete else 1


if __name__ == "__main__":
    raise SystemExit(main())
