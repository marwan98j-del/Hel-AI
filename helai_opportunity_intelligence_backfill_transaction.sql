-- GENERATED FROM groups.SAFE_REVIEWED_BACKFILL.
-- REVIEW ONLY. Do not execute until the exact 15-row backfill is approved.
BEGIN;

LOCK TABLE public.opportunities IN SHARE ROW EXCLUSIVE MODE;
LOCK TABLE public.matches IN SHARE MODE;
LOCK TABLE public.notifications IN SHARE MODE;

DO $backfill$
DECLARE
    -- Canonical manifest. Every later scope derives from this single value.
    approved_titles constant jsonb := jsonb_build_object(
        'afcc85f3-91fd-4b7c-8bf2-27876c80355b', 'How to Write a Winning Mastercard Foundation Scholarship Essay',
        '82a18662-c566-418c-9e40-6e40fcd086be', '30 Masters, Ph.D and Other Scholarship Opportunities Currently Open – September 16, 2026',
        '49a62059-2428-4f53-9f8a-1e4b98e3b2c1', 'AUIS Presidential Scholarship 2026',
        '85389c1a-1592-46c6-9137-fffc05d6393c', 'UNDP Youth Leadership Programme Iraq',
        '6cbb02df-e653-406c-9603-4694e890fd22', 'Yenching Academy at Peking University 2027 – Full Scholarship for Master’s Study in China',
        '7f472825-3767-4434-aec3-698475f4983a', 'ChangemakerXchange Program Lead 2026',
        '454698a9-be87-48f0-bbf9-17acd7b305a5', 'Chase Leadership Development Program – Summer Analyst 2027',
        'd336206b-3984-4b7c-a29d-a660f3c36016', 'Nivishe Mental Health Fellowship Cohort 7',
        '93f8b7ed-dce3-4f0b-a0a8-497785494faa', 'Voqal Partners Fellowship 2027',
        '80396480-626a-4625-b386-850cf7125dc9', 'LeadGreen Fellowship Cohort 4',
        '82b6d9c0-3184-46f0-bc50-1a13a7355b97', 'Global Changemaker Fellowship 2026',
        'bd922ef3-bbec-4804-b387-6d74e9991cf9', 'Gates Cambridge Scholarships 2027-2028',
        'e9ef1a0b-00c7-4502-babf-f25cb586bdd4', 'Leaders of Africa Institute Research Communication Program 2026',
        '15346abe-d279-4bb4-a90f-3e6f4f9532b4', 'Harris Social Impact Fellowship 2027-2028',
        '4fda1241-7012-48b7-84d4-939383ba6726', 'Mathematics in Africa Grant 2026'
    );
    non_opportunity_ids constant uuid[] := ARRAY[
        'afcc85f3-91fd-4b7c-8bf2-27876c80355b'::uuid,
        '82a18662-c566-418c-9e40-6e40fcd086be'::uuid
    ];
    approved_ids uuid[];
    individual_ids uuid[];
    approved_count integer;
    changed_non_opportunities integer;
    changed_individuals integer;
    resulting_count integer;
BEGIN
    SELECT array_agg(key::uuid ORDER BY key)
      INTO approved_ids
      FROM jsonb_each_text(approved_titles);
    SELECT array_agg(id ORDER BY id)
      INTO individual_ids
      FROM unnest(approved_ids) AS id
     WHERE NOT (id = ANY(non_opportunity_ids));

    IF cardinality(approved_ids) <> 15
       OR cardinality(non_opportunity_ids) <> 2
       OR cardinality(individual_ids) <> 13 THEN
        RAISE EXCEPTION 'Safety stop: generated approved scope is not 15 = 2 + 13';
    END IF;
    IF (SELECT count(*) FROM public.opportunities) <> 122 THEN
        RAISE EXCEPTION 'Safety stop: expected 122 opportunities';
    END IF;
    IF (SELECT count(*) FROM public.matches) <> 224 THEN
        RAISE EXCEPTION 'Safety stop: expected 224 matches';
    END IF;

    SELECT count(*) INTO approved_count
      FROM public.opportunities o
      JOIN jsonb_each_text(approved_titles) a
        ON o.id = a.key::uuid AND o.title = a.value;
    IF approved_count <> 15 THEN
        RAISE EXCEPTION 'Safety stop: exact approved ID/title count is %, expected 15', approved_count;
    END IF;

    IF (SELECT count(*) FROM public.opportunities
         WHERE id = ANY(approved_ids)
           AND applicant_type IS NULL
           AND eligible_applicant_types IS NULL
           AND applicant_type_reviewed IS FALSE
           AND record_kind = 'unknown'
           AND record_kind_reviewed IS FALSE) <> 15 THEN
        RAISE EXCEPTION 'Safety stop: approved intelligence old values drifted';
    END IF;

    UPDATE public.opportunities
       SET record_kind = CASE id
            WHEN non_opportunity_ids[1] THEN 'informational'
            WHEN non_opportunity_ids[2] THEN 'roundup'
           END,
           record_kind_reviewed = TRUE
     WHERE id = ANY(non_opportunity_ids);
    GET DIAGNOSTICS changed_non_opportunities = ROW_COUNT;
    IF changed_non_opportunities <> 2 THEN
        RAISE EXCEPTION 'Safety stop: non-opportunity update changed % rows, expected 2', changed_non_opportunities;
    END IF;

    UPDATE public.opportunities
       SET applicant_type = 'individual',
           eligible_applicant_types = '["individual"]'::jsonb,
           applicant_type_reviewed = TRUE
     WHERE id = ANY(individual_ids);
    GET DIAGNOSTICS changed_individuals = ROW_COUNT;
    IF changed_individuals <> 13 THEN
        RAISE EXCEPTION 'Safety stop: individual update changed % rows, expected 13', changed_individuals;
    END IF;
    IF changed_non_opportunities + changed_individuals <> 15 THEN
        RAISE EXCEPTION 'Safety stop: total update count is not 15';
    END IF;

    SELECT count(*) INTO resulting_count
      FROM public.opportunities
     WHERE (id = non_opportunity_ids[1]
            AND record_kind = 'informational' AND record_kind_reviewed IS TRUE
            AND applicant_type IS NULL AND eligible_applicant_types IS NULL
            AND applicant_type_reviewed IS FALSE)
        OR (id = non_opportunity_ids[2]
            AND record_kind = 'roundup' AND record_kind_reviewed IS TRUE
            AND applicant_type IS NULL AND eligible_applicant_types IS NULL
            AND applicant_type_reviewed IS FALSE)
        OR (id = ANY(individual_ids)
            AND applicant_type = 'individual'
            AND eligible_applicant_types = '["individual"]'::jsonb
            AND applicant_type_reviewed IS TRUE
            AND record_kind = 'unknown' AND record_kind_reviewed IS FALSE);
    IF resulting_count <> 15 THEN
        RAISE EXCEPTION 'Safety stop: resulting approved-value count is %, expected 15', resulting_count;
    END IF;

    IF (SELECT count(*) FROM public.opportunities) <> 122
       OR (SELECT count(*) FROM public.matches) <> 224 THEN
        RAISE EXCEPTION 'Safety stop: global row counts changed unexpectedly';
    END IF;
END
$backfill$;

COMMIT;
