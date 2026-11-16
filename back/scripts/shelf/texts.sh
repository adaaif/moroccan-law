#!/usr/bin/env bash
# The shelf's missing texts (27 Oct 2026, run first on a database of their own): the criminal procedure (22.01), the
# commerce code (15.95), the nationality code (dahir 1.58.250), access to information (31.13), personal data (09.08)
# and urbanism control (66.12), from Adala, free, into the database DATABASE_URL names, from back/. Each file is
# fetched once into CORPUS_DIR/sources/adala (or registered as kept, with its hash), then its French beside it. Their
# original BO issues are read by Haiku with `process_issue`, one issue at a time.
set -uo pipefail
cd "$(dirname "$0")/../.."
M() { nice -n 10 .venv/bin/python manage.py "$@" 2>&1 | tail -1; }
while IFS=$'\t' read -r name lang url; do
  if [ -f "${CORPUS_DIR:-../data}/sources/adala/$name.pdf" ]; then
    M fetch_adala "$url" --kept "sources/adala/$name.pdf" --language "$lang"
  else
    M fetch_adala "$url" --name "$name" --language "$lang" --fetch
  fi
done < scripts/shelf/adala.tsv
L() { echo "== $1"; shift; M load_adala "$@"; }
L 22.01 sources/adala/criminal_procedure_22_01.pdf --article-word المادة
L 15.95 sources/adala/commerce_15_95.pdf --article-word المادة
L 1.58.250 sources/adala/nationality_1_58_250.pdf --article-word الفصل
L 09.08 samples/adala/adala_09_08.pdf --article-word المادة --as-of 2009-02-23
L 31.13 samples/adala/adala_31_13.pdf --article-word المادة --as-of 2018-03-12
L 66.12 sources/adala/urbanism_control_66_12.pdf --article-word المادة --as-of 2016-09-19
F() { echo "== $3"; M load_adala_french "$@"; }
F sources/adala/commerce_15_95_fr.pdf --text /akn/ma/act/loi/15-95 --as-of 2019-12-19 --issue 4418 --issue-date 1996-10-03 --title "Dahir n° 1-96-83 du 15 rabii I 1417 (1er août 1996) portant promulgation de la loi n° 15-95 formant code de commerce"
F sources/adala/nationality_1_58_250_fr.pdf --text /akn/ma/act/dahir/1-58-250 --as-of 2024-05-16 --issue 2394 --issue-date 1958-09-12 --title "Dahir n° 1-58-250 du 21 safar 1378 (6 septembre 1958) portant code de la nationalité marocaine"
F sources/adala/personal_data_09_08_fr.pdf --text /akn/ma/act/loi/9-08 --as-of 2009-03-05 --issue 5714 --issue-date 2009-03-05 --title "Loi n° 09-08 relative à la protection des personnes physiques à l'égard du traitement des données à caractère personnel"
F sources/adala/access_information_31_13_fr.pdf --text /akn/ma/act/loi/31-13 --as-of 2018-05-03 --issue 6670 --issue-date 2018-05-03 --title "Loi n° 31-13 relative au droit d'accès à l'information"
echo "== loaded"
