-- ============================================================================
-- Peuplement de dim_date sur une plage large (2023-01-01 -> 2027-12-31)
-- Rejouable sans risque (ON CONFLICT DO NOTHING).
-- ============================================================================

INSERT INTO dwh.dim_date (
    date_id, date_complete, jour, jour_semaine, nom_jour, semaine_annee,
    mois, nom_mois, trimestre, annee, annee_mois, est_weekend, est_jour_ferie
)
SELECT
    TO_CHAR(d, 'YYYYMMDD')::INTEGER,
    d,
    EXTRACT(DAY FROM d)::SMALLINT,
    EXTRACT(ISODOW FROM d)::SMALLINT,
    INITCAP(TO_CHAR(d, 'Day')),
    EXTRACT(WEEK FROM d)::SMALLINT,
    EXTRACT(MONTH FROM d)::SMALLINT,
    INITCAP(TO_CHAR(d, 'Month')),
    EXTRACT(QUARTER FROM d)::SMALLINT,
    EXTRACT(YEAR FROM d)::SMALLINT,
    TO_CHAR(d, 'YYYY-MM'),
    EXTRACT(ISODOW FROM d) IN (6, 7),
    FALSE
FROM GENERATE_SERIES('2023-01-01'::DATE, '2027-12-31'::DATE, '1 day'::INTERVAL) AS d
ON CONFLICT (date_id) DO NOTHING;

-- Quelques jours fériés fictifs (à titre d'illustration - Guinée)
UPDATE dwh.dim_date SET est_jour_ferie = TRUE
WHERE (mois = 1 AND jour = 1)     -- Jour de l'an
   OR (mois = 5 AND jour = 1)     -- Fête du travail
   OR (mois = 10 AND jour = 2)    -- Fête de l'indépendance (Guinée)
   OR (mois = 12 AND jour = 25);  -- Noël
