-- =====================================================================
-- A.E.G.I.S. // Fictitious PostGIS database bootstrap
-- Matches the schema/tables/columns expected by agent.py & server.py:
--   * schema  : schema1            (TARGET_SCHEMA / hardcoded in prompts)
--   * auth     : login table, 1st column = clearance (server.py result[0])
--   * parks    : has a real `geom` column (MultiPolygon, SRID 4326)
--   * fermate_metro / hospitals : NO geom, only longitude/latitude columns
-- Theme: city of Milan (matches the analyst prompts in agent.py).
-- =====================================================================

CREATE EXTENSION IF NOT EXISTS postgis;

CREATE SCHEMA IF NOT EXISTS schema1;
SET search_path TO schema1, public;

-- ---------------------------------------------------------------------
-- AUTH  (used by /api/login -> SELECT * ... ; result[0] is the clearance)
-- ---------------------------------------------------------------------
DROP TABLE IF EXISTS schema1.auth;
CREATE TABLE schema1.auth (
    clearance  VARCHAR(32)  NOT NULL,   -- result[0] -> "ACCESS GRANTED // LEVEL <clearance>"
    username   VARCHAR(64)  NOT NULL,   -- maps to operator_id
    password   VARCHAR(128) NOT NULL,   -- maps to access_key
    PRIMARY KEY (username)
);

INSERT INTO schema1.auth (clearance, username, password) VALUES
    ('OMEGA-9', 'CMD_USR_0001', 'tango-down'),
    ('ALPHA-3', 'CMD_USR_0042', 'falcon99'),
    ('SIGMA-7', 'OP_ADMIN',     'aegis2026');

-- ---------------------------------------------------------------------
-- PARKS  (has a real geom column -> read by gpd.read_postgis geom_col='geom')
-- ---------------------------------------------------------------------
DROP TABLE IF EXISTS schema1.parks;
CREATE TABLE schema1.parks (
    id        SERIAL PRIMARY KEY,
    name      VARCHAR(120) NOT NULL,
    area_sqm  INTEGER,
    geom      geometry(MultiPolygon, 4326)
);

-- Small fictitious envelopes (xmin, ymin, xmax, ymax) around real Milan parks.
INSERT INTO schema1.parks (name, area_sqm, geom) VALUES
    ('Parco Sempione',                   386000, ST_Multi(ST_SetSRID(ST_MakeEnvelope(9.1735, 45.4690, 9.1825, 45.4755), 4326))),
    ('Giardini Pubblici Indro Montanelli',172000, ST_Multi(ST_SetSRID(ST_MakeEnvelope(9.1955, 45.4710, 9.2045, 45.4760), 4326))),
    ('Parco Lambro',                     773000, ST_Multi(ST_SetSRID(ST_MakeEnvelope(9.2460, 45.4920, 9.2580, 45.5020), 4326))),
    ('Biblioteca degli Alberi (BAM)',     90000, ST_Multi(ST_SetSRID(ST_MakeEnvelope(9.1865, 45.4840, 9.1935, 45.4885), 4326))),
    ('Parco delle Basiliche',             45000, ST_Multi(ST_SetSRID(ST_MakeEnvelope(9.1805, 45.4535, 9.1875, 45.4585), 4326))),
    ('CityLife Park',                    168000, ST_Multi(ST_SetSRID(ST_MakeEnvelope(9.1520, 45.4760, 9.1600, 45.4820), 4326)));

CREATE INDEX parks_geom_gix ON schema1.parks USING GIST (geom);

-- ---------------------------------------------------------------------
-- FERMATE_METRO  (NO geom; geometry built at query time from lon/lat)
-- ---------------------------------------------------------------------
DROP TABLE IF EXISTS schema1.fermate_metro;
CREATE TABLE schema1.fermate_metro (
    id         SERIAL PRIMARY KEY,
    name       VARCHAR(120) NOT NULL,
    line       VARCHAR(8)   NOT NULL,   -- e.g. M1, M2, M3, M4, M5
    longitude  DOUBLE PRECISION NOT NULL,
    latitude   DOUBLE PRECISION NOT NULL
);

INSERT INTO schema1.fermate_metro (name, line, longitude, latitude) VALUES
    -- M1 (Red)
    ('Duomo',                  'M1', 9.1860, 45.4640),
    ('Cairoli Castello',       'M1', 9.1810, 45.4680),
    ('Cadorna FN',             'M1', 9.1745, 45.4675),
    ('San Babila',             'M1', 9.1980, 45.4660),
    ('Pagano',                 'M1', 9.1640, 45.4670),
    ('Sesto 1 Maggio FS',      'M1', 9.2380, 45.5370),
    -- M2 (Green)
    ('Centrale FS',            'M2', 9.2040, 45.4860),
    ('Garibaldi FS',           'M2', 9.1870, 45.4840),
    ('Lanza',                  'M2', 9.1830, 45.4720),
    ('Loreto',                 'M2', 9.2160, 45.4860),
    ('Porta Genova FS',        'M2', 9.1730, 45.4540),
    -- M3 (Yellow)
    ('Repubblica',             'M3', 9.1980, 45.4790),
    ('Montenapoleone',         'M3', 9.1950, 45.4690),
    ('Missori',                'M3', 9.1880, 45.4600),
    -- M4 (Blue)
    ('Linate Aeroporto',       'M4', 9.2780, 45.4500),
    ('Sforza Policlinico',     'M4', 9.1940, 45.4590),
    ('Dateo',                  'M4', 9.2150, 45.4660),
    -- M5 (Lilac)
    ('Isola',                  'M5', 9.1890, 45.4880),
    ('Zara',                   'M5', 9.1960, 45.4920),
    ('San Siro Stadio',        'M5', 9.1240, 45.4780);

-- ---------------------------------------------------------------------
-- HOSPITALS  (NO geom; another lon/lat table for infrastructure queries)
-- ---------------------------------------------------------------------
DROP TABLE IF EXISTS schema1.hospitals;
CREATE TABLE schema1.hospitals (
    id         SERIAL PRIMARY KEY,
    name       VARCHAR(150) NOT NULL,
    type       VARCHAR(60),
    longitude  DOUBLE PRECISION NOT NULL,
    latitude   DOUBLE PRECISION NOT NULL
);

INSERT INTO schema1.hospitals (name, type, longitude, latitude) VALUES
    ('Ospedale Niguarda',                 'General',     9.1900, 45.5160),
    ('Policlinico di Milano',             'University',  9.1960, 45.4580),
    ('Ospedale San Raffaele',             'Research',    9.2640, 45.5050),
    ('Ospedale Fatebenefratelli',         'General',     9.1920, 45.4720),
    ('Ospedale San Carlo Borromeo',       'General',     9.1080, 45.4560),
    ('Istituto Nazionale dei Tumori',     'Oncology',    9.2300, 45.4750);

-- ---------------------------------------------------------------------
-- Sanity: report what was created
-- ---------------------------------------------------------------------
DO $$
DECLARE n_auth INT; n_parks INT; n_metro INT; n_hosp INT;
BEGIN
    SELECT count(*) INTO n_auth  FROM schema1.auth;
    SELECT count(*) INTO n_parks FROM schema1.parks;
    SELECT count(*) INTO n_metro FROM schema1.fermate_metro;
    SELECT count(*) INTO n_hosp  FROM schema1.hospitals;
    RAISE NOTICE 'AEGIS seed complete: auth=%, parks=%, fermate_metro=%, hospitals=%',
        n_auth, n_parks, n_metro, n_hosp;
END $$;
