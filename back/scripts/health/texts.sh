#!/usr/bin/env bash
# The health review (27 Oct 2026): the health topic's texts into the database DATABASE_URL names, from back/.
# Adala's files, free (fetched once into CORPUS_DIR/sources/adala, kept with their hashes), then their French. The texts
# only the BO holds (orders 2517.05, 2518.05, 2519.05, 2284.05, 456.11; 65.00 as printed in 2002 and the laws that
# amended it) are read by Haiku with `process_issue`, one Bulletin issue at a time, and fixed by hand
# after that.
set -uo pipefail
cd "$(dirname "$0")/../.."
M() { nice -n 10 .venv/bin/python manage.py "$@" 2>&1 | tail -1; }
while IFS=$'\t' read -r name lang url; do
  [ "$name" = admin_courts_41_90 ] && continue          # repealed by 58.25 (art. 644): fetched, not loaded
  [ -f "${CORPUS_DIR:-../data}/sources/adala/$name.pdf" ] || M fetch_adala "$url" --name "$name" --language "$lang" --fetch
done < scripts/health/adala.tsv
L() { echo "== $1"; shift; M load_adala "$@"; }
L 16.98 sources/adala/organ_donation_16_98.pdf --article-word المادة
L 28.13 sources/adala/biomedical_research_28_13.pdf --article-word المادة --as-of 2015-10-01
L 47.14 sources/adala/assisted_reproduction_47_14.pdf --article-word المادة --as-of 2019-04-04
L 15.91 sources/adala/smoking_15_91.pdf --article-word المادة --as-of 1995-08-02
L 97.13 sources/adala/disability_97_13.pdf --article-word المادة --as-of 2016-05-19
L 12.01 sources/adala/labs_12_01.pdf --article-word المادة --as-of 2002-11-07
L 84.12 sources/adala/medical_devices_84_12.pdf --article-word المادة --as-of 2013-09-19
L 08.12 sources/adala/doctors_order_08_12.pdf --article-word المادة
L 43.13 sources/adala/nursing_43_13.pdf --article-word المادة --as-of 2016-07-07
L 44.13 sources/adala/midwives_44_13.pdf --article-word المادة --as-of 2016-07-07
L 08.22 sources/adala/health_groups_08_22.pdf --article-word المادة --as-of 2023-07-17
L 1.57.187 sources/adala/mutual_1_57_187.pdf --article-word الفصل
L 116.12 sources/adala/students_amo_116_12.pdf --article-word المادة
L 2.05.733 sources/adala/amo_deadlines_2_05_733.pdf --article-word المادة --as-of 2005-08-18
L 2.05.736 sources/adala/amo_rates_cnops_2_05_736.pdf --article-word المادة --as-of 2005-08-18
L 2.05.737 sources/adala/amo_rates_cnss_2_05_737.pdf --article-word المادة
L 2.05.738 sources/adala/amo_registration_2_05_738.pdf --article-word المادة --as-of 2005-08-18
L 2.99.80 sources/adala/hospital_fees_2_99_80.pdf --article-word المادة --as-of 1999-04-15
F() { echo "== $2"; M load_adala_french "$@"; }
F sources/adala/biomedical_research_28_13_fr.pdf --text /akn/ma/act/loi/28-13 --as-of 2015-09-17 --issue 6396 --issue-date 2015-09-17 --title "Loi n° 28-13 relative à la protection des personnes participant aux recherches biomédicales"
F sources/adala/assisted_reproduction_47_14_fr.pdf --text /akn/ma/act/loi/47-14 --as-of 2019-04-04 --issue 6766 --issue-date 2019-04-04 --title "Loi n° 47-14 relative à l'assistance médicale à la procréation"
F sources/adala/disability_97_13_fr.pdf --text /akn/ma/act/loi/97-13 --as-of 2016-05-19 --issue 6466 --issue-date 2016-05-19 --title "Loi-cadre n° 97-13 relative à la protection et à la promotion des droits des personnes en situation de handicap"
F sources/adala/medical_devices_84_12_fr.pdf --text /akn/ma/act/loi/84-12 --as-of 2013-09-19 --issue 6188 --issue-date 2013-09-19 --title "Loi n° 84-12 relative aux dispositifs médicaux"
F sources/adala/doctors_order_08_12_fr.pdf --text /akn/ma/act/loi/8-12 --as-of 2013-04-18 --issue 6144 --issue-date 2013-04-18 --title "Loi n° 08-12 relative à l'Ordre national des médecins"
F sources/adala/nursing_43_13_fr.pdf --text /akn/ma/act/loi/43-13 --as-of 2016-09-15 --issue 6500 --issue-date 2016-09-15 --title "Loi n° 43-13 relative à l'exercice des professions infirmières"
F sources/adala/midwives_44_13_fr.pdf --text /akn/ma/act/loi/44-13 --as-of 2016-09-15 --issue 6500 --issue-date 2016-09-15 --title "Loi n° 44-13 relative à l'exercice de la profession de sage-femme"
F sources/adala/health_system_06_22_fr.pdf --text /akn/ma/act/loi/6-22 --as-of 2023-03-16 --issue 7178 --issue-date 2023-03-16 --title "Loi-cadre n° 06-22 relative au système national de santé"
F sources/adala/amo_independents_98_15_fr.pdf --text /akn/ma/act/loi/98-15 --as-of 2018-04-05 --issue 6662 --issue-date 2018-04-05 --title "Loi n° 98-15 relative au régime de l'assurance maladie obligatoire de base pour les catégories des professionnels, des travailleurs indépendants et des personnes non salariées exerçant une activité libérale"
F sources/adala/hospital_rules_456_11_fr.pdf --text /akn/ma/act/arrete/456-11 --as-of 2011-03-17 --issue 5926 --issue-date 2011-03-17 --title "Arrêté de la ministre de la santé n° 456-11 portant règlement intérieur des hôpitaux"
echo "== loaded"
