#!/bin/bash
#SBATCH -J cross_model_finalize
#SBATCH -p AMD
#SBATCH -N 1
#SBATCH -n 1
#SBATCH -c 4
#SBATCH --mem=8G
#SBATCH --time=00:30:00
#SBATCH -o logs/%x-%j.out
#SBATCH -e logs/%x-%j.err

set -euo pipefail
BASE=/public/home/yinyifan/protein_design
PYTHON=$BASE/envs/boltz/bin/python
RUN_DIR=$BASE/examples/epitope_scaffold/cross_model_prediction_top3_5tpn_20260628
REF=$BASE/examples/epitope_scaffold/input/5TPN.pdb
MOTIF=$BASE/examples/epitope_scaffold/motif_residues.tsv
MANIFEST=$RUN_DIR/canonical/canonical_manifest.tsv
cd "$RUN_DIR"
mkdir -p reports logs predictions_flat/boltz predictions_flat/rf3_mappings predictions_flat/boltz_mappings
"$PYTHON" $BASE/scripts/make_motif_mapping_from_sequence.py --reference_pdb "$REF" --motif_tsv "$MOTIF" --pdb_dir predictions_flat/rf3 --out_dir predictions_flat/rf3_mappings
"$PYTHON" $BASE/scripts/filter_designs.py --input_dir predictions_flat/rf3 --pdb_dir predictions_flat/rf3 --trb_dir predictions_flat/rf3_mappings --reference_pdb "$REF" --motif_tsv "$MOTIF" --output_csv reports/rf3_filter_summary.csv --min_plddt 70 --max_pae 10 --max_motif_rmsd 2.0 --max_clashes 20
if find predictions_flat/boltz -maxdepth 1 -type f \( -name "*.json" -o -name "*.pdb" -o -name "*.cif" \) | grep -q .; then
  "$PYTHON" $BASE/scripts/make_motif_mapping_from_sequence.py --reference_pdb "$REF" --motif_tsv "$MOTIF" --pdb_dir predictions_flat/boltz --out_dir predictions_flat/boltz_mappings
  "$PYTHON" $BASE/scripts/filter_designs.py --input_dir predictions_flat/boltz --pdb_dir predictions_flat/boltz --trb_dir predictions_flat/boltz_mappings --reference_pdb "$REF" --motif_tsv "$MOTIF" --output_csv reports/boltz_filter_summary.csv --min_plddt 70 --max_pae 10 --max_motif_rmsd 2.0 --max_clashes 20
else
  "$PYTHON" - <<"PY"
import csv, pathlib
run=pathlib.Path("/public/home/yinyifan/protein_design/examples/epitope_scaffold/cross_model_prediction_top3_5tpn_20260628")
manifest=run/"canonical/canonical_manifest.tsv"
err="Boltz prediction failed before structure output: compute node network unreachable during CCD/model cache download; see logs/boltz_predict-123387.err"
fields=["design_id","confidence_file","model_pdb","plddt_mean","ptm","iptm","pae_mean","ranking_score","prediction_has_clash","motif_rmsd","motif_atoms_compared","motif_atoms_missing","clash_count","pass","parse_error"]
rows=[]
with manifest.open() as handle:
    for row in csv.DictReader(handle, delimiter="\t"):
        rows.append({"design_id": row["job_name"], "confidence_file":"", "model_pdb":"", "plddt_mean":"", "ptm":"", "iptm":"", "pae_mean":"", "ranking_score":"", "prediction_has_clash":"", "motif_rmsd":"", "motif_atoms_compared":"", "motif_atoms_missing":"", "clash_count":"", "pass":"FAIL", "parse_error": err})
out=run/"reports/boltz_filter_summary.csv"
out.parent.mkdir(parents=True, exist_ok=True)
with out.open("w", newline="") as handle:
    writer=csv.DictWriter(handle, fieldnames=fields)
    writer.writeheader(); writer.writerows(rows)
PY
fi
"$PYTHON" $BASE/scripts/compare_prediction_backends.py --canonical_manifest "$MANIFEST" --filter_summary af3=reports/af3_filter_summary.csv --filter_summary rf3=reports/rf3_filter_summary.csv --filter_summary boltz=reports/boltz_filter_summary.csv --output_csv reports/consensus_summary.csv --summary_json reports/consensus_summary.json --summary_md reports/cross_model_prediction_report.md
"$PYTHON" - <<"PY"
import json, pathlib
run=pathlib.Path("/public/home/yinyifan/protein_design/examples/epitope_scaffold/cross_model_prediction_top3_5tpn_20260628")
summary=json.loads((run/"reports/consensus_summary.json").read_text())
report={
  "run_dir": str(run),
  "af3_status": "existing_primary_predictions_reused",
  "rf3_status": "completed" if summary["rf3_success_count"] else "no_successful_outputs",
  "boltz_status": "failed_network_unreachable_during_cache_download" if not summary["boltz_success_count"] else "completed",
  "summary": summary,
  "job_ids_file": str(run/"job_ids.env"),
}
if not summary["boltz_success_count"]:
    report["boltz_failure_reason"] = "urllib.error.URLError: <urlopen error [Errno 101] Network is unreachable> while downloading Boltz CCD/model cache on RTX3090 compute node"
(run/"reports/run_report.json").write_text(json.dumps(report, indent=2, sort_keys=True)+"\n")
print(json.dumps(report, sort_keys=True))
PY
