-- HelAI opportunity-intelligence schema migration.
-- REVIEW ONLY: this file is intentionally not executed by the application.
-- NULL applicant fields mean "not determined". An empty JSON array remains
-- distinct and may only be used when a reviewer intentionally records it.

alter table public.opportunities
    add column if not exists applicant_type text,
    add column if not exists eligible_applicant_types jsonb,
    add column if not exists record_kind text not null default 'unknown',
    add column if not exists applicant_type_reviewed boolean not null default false,
    add column if not exists record_kind_reviewed boolean not null default false;

comment on column public.opportunities.applicant_type is
    'Primary normalized applicant classification; NULL means unknown.';
comment on column public.opportunities.eligible_applicant_types is
    'Explicit eligible applicant types as a JSON array; NULL means unknown.';
comment on column public.opportunities.record_kind is
    'Content kind: application_opportunity, informational, roundup, or unknown.';
comment on column public.opportunities.applicant_type_reviewed is
    'True when applicant fields were human-reviewed and must not be overwritten by automation.';
comment on column public.opportunities.record_kind_reviewed is
    'True when record_kind was human-reviewed and must not be overwritten by automation.';

do $$
begin
    if not exists (
        select 1 from pg_constraint
        where conname = 'opportunities_record_kind_check'
          and conrelid = 'public.opportunities'::regclass
    ) then
        alter table public.opportunities
            add constraint opportunities_record_kind_check
            check (record_kind in (
                'application_opportunity',
                'informational',
                'roundup',
                'unknown'
            ));
    end if;

    if not exists (
        select 1 from pg_constraint
        where conname = 'opportunities_eligible_applicant_types_array_check'
          and conrelid = 'public.opportunities'::regclass
    ) then
        alter table public.opportunities
            add constraint opportunities_eligible_applicant_types_array_check
            check (
                eligible_applicant_types is null
                or jsonb_typeof(eligible_applicant_types) = 'array'
            );
    end if;
end
$$;

-- Intentionally no restrictive applicant_type CHECK. The application
-- normalizes known values, while the database remains forward-compatible.
-- Intentionally no UPDATE/backfill statement. Existing rows remain unknown.
