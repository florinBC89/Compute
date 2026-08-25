-- Verifies the exact SQL that app/services/lookup.py generates, against the
-- table states each conformance scenario produces.
--
-- This exists because the Python suite mocks nothing but also never creates the
-- states only a real database produces: tied timestamps, partial-index
-- predicates, constraint interactions. Run it against a scratch database:
--
--   createdb computelayer_lookup_check
--   psql -d computelayer_lookup_check -v ON_ERROR_STOP=1 \
--        -f migrations/schema.sql -f apps/api/tests/lookup_semantics.sql
--
-- Every check RAISEs on failure, so a clean exit means everything passed.
--
-- The two queries under test, as the ORM emits them:
--   find_exact:    ... fingerprint = $f AND status='SUCCEEDED' AND reusable = true
--                  ORDER BY seq DESC LIMIT 1
--   find_previous: ... logical_key = $l AND status='SUCCEEDED'
--                  ORDER BY seq DESC LIMIT 1

\set W '''11111111-1111-1111-1111-111111111111'''
\set P '''22222222-2222-2222-2222-222222222222'''

INSERT INTO workspaces (id, name) VALUES (:W, 'w');
INSERT INTO projects (id, workspace_id, name, slug) VALUES (:P, :W, 'p', 'p');

CREATE FUNCTION h(seed text) RETURNS text LANGUAGE sql IMMUTABLE AS
$$ SELECT md5(seed) || md5('x' || seed) $$;

CREATE FUNCTION add_comp(
    nm text, lk text, fp text, st text, cs text,
    is_reusable boolean, ts timestamptz, out_json jsonb DEFAULT '{}'::jsonb
) RETURNS uuid LANGUAGE sql AS $$
    INSERT INTO computations (id, workspace_id, project_id, name, logical_key,
                              fingerprint, status, cache_status, output_json,
                              output_hash, cost_usd, reusable, created_at)
    VALUES (gen_random_uuid(),
            '11111111-1111-1111-1111-111111111111',
            '22222222-2222-2222-2222-222222222222',
            nm, h(lk), h(fp), st, cs, out_json, h('out' || fp), 0.18,
            is_reusable, ts)
    RETURNING id;
$$;

-- find_exact / find_previous as the ORM writes them
CREATE FUNCTION find_exact(fp text) RETURNS uuid LANGUAGE sql AS $$
    SELECT id FROM computations
    WHERE workspace_id = '11111111-1111-1111-1111-111111111111'
      AND project_id   = '22222222-2222-2222-2222-222222222222'
      AND fingerprint  = h(fp)
      AND status = 'SUCCEEDED'
      AND reusable = true
    ORDER BY seq DESC LIMIT 1;
$$;

CREATE FUNCTION find_previous(lk text) RETURNS uuid LANGUAGE sql AS $$
    SELECT id FROM computations
    WHERE workspace_id = '11111111-1111-1111-1111-111111111111'
      AND project_id   = '22222222-2222-2222-2222-222222222222'
      AND logical_key  = h(lk)
      AND status = 'SUCCEEDED'
    ORDER BY seq DESC LIMIT 1;
$$;

-- classify(), transcribed from computelayer/semantics.py
CREATE FUNCTION classify(lk text, fp text, forced boolean DEFAULT false)
RETURNS text LANGUAGE plpgsql AS $$
DECLARE ex uuid; prev uuid;
BEGIN
    IF forced THEN RETURN 'FORCED'; END IF;
    ex   := find_exact(fp);
    prev := find_previous(lk);
    IF ex IS NOT NULL THEN RETURN 'HIT'; END IF;
    IF prev IS NOT NULL THEN RETURN 'STALE'; END IF;
    RETURN 'MISS';
END $$;

CREATE FUNCTION expect(label text, got text, want text) RETURNS void
LANGUAGE plpgsql AS $$
BEGIN
    IF got IS DISTINCT FROM want THEN
        RAISE EXCEPTION 'FAIL % : got % want %', label, got, want;
    END IF;
    RAISE NOTICE 'ok   % -> %', label, got;
END $$;

-- ---------------------------------------------------------------- scenarios

-- 1. nothing recorded
SELECT expect('empty table', classify('L1', 'F1'), 'MISS');

-- 2. one successful execution
SELECT add_comp('a', 'L1', 'F1', 'SUCCEEDED', 'MISS', true, now());
SELECT expect('after success', classify('L1', 'F1'), 'HIT');

-- 3. changed fingerprint, same logical key
SELECT expect('changed dependency', classify('L1', 'F2'), 'STALE');

-- 4. a failure must not be reusable, and must not make a new run STALE
SELECT add_comp('b', 'L9', 'F9', 'FAILED', 'MISS', false, now());
SELECT expect('after failure', classify('L9', 'F9'), 'MISS');

-- 5. reusable=false is recorded but never reused
SELECT add_comp('c', 'L5', 'F5', 'SUCCEEDED', 'MISS', false, now());
SELECT expect('reusable=false', classify('L5', 'F5'), 'STALE');

-- 6. THE IMPORTANT ONE: a HIT observation row shares the fingerprint of the
--    row it reused. It must never itself satisfy find_exact, or reuse would
--    start chaining off rows that carry no output.
SELECT add_comp('a', 'L1', 'F1', 'SUCCEEDED', 'HIT', false, now(), NULL);
SELECT expect('hit observation ignored', classify('L1', 'F1'), 'HIT');
SELECT expect(
    'find_exact skipped the observation',
    (SELECT cache_status FROM computations WHERE id = find_exact('F1')),
    'MISS'
);
SELECT expect(
    'reused row still carries its output',
    (SELECT (output_json IS NOT NULL)::text
     FROM computations WHERE id = find_exact('F1')),
    'true'
);

-- 7. newest successful row wins (§21: a forced result becomes the latest)
SELECT add_comp('d', 'L7', 'F7', 'SUCCEEDED', 'MISS',   true, now() - interval '2 h',
                '{"generation": 1}'::jsonb);
SELECT add_comp('d', 'L7', 'F7', 'SUCCEEDED', 'FORCED', true, now() - interval '1 h',
                '{"generation": 2}'::jsonb);
SELECT expect(
    'newest row wins',
    (SELECT output_json->>'generation' FROM computations WHERE id = find_exact('F7')),
    '2'
);

-- 8. tie-break: two rows with an identical created_at. now() is transaction
--    time, so any two rows written in one transaction tie exactly.
SELECT add_comp('e', 'L8', 'F8', 'SUCCEEDED', 'MISS', true,
                '2026-08-25 12:00:00+00', '{"generation": 1}'::jsonb);
SELECT add_comp('e', 'L8', 'F8', 'SUCCEEDED', 'MISS', true,
                '2026-08-25 12:00:00+00', '{"generation": 2}'::jsonb);

\echo ''
\echo '--- tie-break determinism (identical created_at), 8 consecutive runs ---'
SELECT string_agg(g, ' ') AS generations_returned
FROM (
    SELECT (SELECT output_json->>'generation'
            FROM computations WHERE id = find_exact('F8')) AS g
    FROM generate_series(1, 8)
) t;
