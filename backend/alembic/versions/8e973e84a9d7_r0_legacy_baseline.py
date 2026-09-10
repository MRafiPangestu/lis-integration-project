"""r0_legacy_baseline

Revision ID: 8e973e84a9d7
Revises:
Create Date: 2026-09-10 10:40:00.000000

R0 — pre-M1 legacy baseline.

This is the first (root) revision of the Alembic graph. It establishes the exact
schema of the RS Marina Permata LIS database as it existed *before* the M1
refactor, so that ``alembic upgrade head`` can provision a truly empty database
(the F-1 defect from the M9.0 investigation).

Provenance
----------
* Derived from : backend/schema/canonical_legacy_schema.sql
* Evidence artifact          : backend/schema/legacy_schema.sql
* Evidence commit            : 1c14380  (docs(m9.0): preserve legacy schema capture)
* Canonical baseline commit  : f16081f  (docs(m9.0): preserve canonical legacy schema baseline)
* Evidence  SHA-256 : 93d902f67e334c0d6b7ea0ce36a2c81cbb5292781b7d45a920b5cbc67199c81e
* Canonical SHA-256 : a75046a8dd9b5da4454581ffa8552c5af0e7af7bc380ace6092ddab293e7125d
* R0 payload SHA-256 (this file's ``R0_LEGACY_BASELINE_SQL`` constant, i.e. the
  canonical file's executable DDL body verbatim from the "doctors" TABLE section
  through the "dump complete" banner, pg_dump section comments kept, one
  trailing newline):
  536c4e46435828151f0ca1bef10f5ca7af2e6f8aae24dc8222b03aab57520ee4
* Source database   : lis_marina_permata   (stable PoC — inspected read-only,
  never migrated, stamped, altered or seeded by M9.0)
* PostgreSQL server / client at capture : 18.6
* Capture timestamp (local) : 2026-09-10 08:37:18
* Source structural fingerprint :
  591d162adb4c1949963708ca2d4faa318b603ae7121935bacc115fc4d83dfeec

Fidelity notes (R0 reproduces legacy truth; it does NOT normalise it)
--------------------------------------------------------------------
* The payload is the canonical DDL executed verbatim: SERIAL is preserved as
  ``CREATE SEQUENCE`` + ``ALTER SEQUENCE ... OWNED BY`` + ``ALTER COLUMN ... SET
  DEFAULT nextval(...)`` — NOT ``GENERATED ... AS IDENTITY``.
* ``patients.nomor_rm`` is ``character varying(50) NOT NULL`` and is
  intentionally **NON-UNIQUE** here. That is the legacy truth. F-2 (adding
  ``UNIQUE(patients.nomor_rm)``) is a SEPARATE later remediation and MUST NOT be
  folded into R0.
* Legacy-only columns that M1 immediately removes are present on purpose
  (orders.no_registrasi, orders.id_pasien, results.id_order, results.id_instrument,
  results.id_message, results.status_hasil, results.divalidasi_oleh,
  results.waktu_validasi) — ``b1f9dbe772fa`` is the delta that drops them.
* Legacy defaults are kept exactly: ``'Success'::character varying``,
  ``'Diproses'::character varying``, ``'Menunggu Validasi'::character varying``,
  and ``CURRENT_TIMESTAMP``.
* All 8 foreign keys keep legacy behaviour: no ON DELETE / no ON UPDATE action.
* Exact legacy constraint names are preserved because
  ``b1f9dbe772fa.upgrade()`` drops several of them by name
  (orders_no_registrasi_key, orders_id_pasien_fkey, unique_order_test,
  results_id_message_fkey, results_id_instrument_fkey, results_id_order_fkey).
* Intentionally ABSENT from R0: visits, test_runs, results.id_run, orders.id_visit,
  instrument_messages.error_detail, instruments.connection_status,
  instruments.last_status_at, instrument_messages.message_class,
  instrument_messages.classification_rule, uk_run_parameter,
  uk_order_run_sequence, idx_unique_final_run_per_order, the four M8.4 indexes,
  patients_nomor_rm_key, and alembic_version (Alembic manages that table itself).
* F-4 / M-1 (``b1f9dbe772fa.downgrade()`` drops unnamed FKs and is broken) is a
  pre-existing, SEPARATE remediation. R0 does not fix it and does not claim to.

Expected result of ``upgrade()`` (matches the source structural fingerprint):
9 tables, 49 columns, 9 sequences, 42 constraints (9 PRIMARY KEY, 4 UNIQUE,
8 FOREIGN KEY, 21 NOT NULL, 0 CHECK), 13 indexes (PK/UNIQUE backing only —
zero standalone ``CREATE INDEX``).

Downgrade safety
----------------
``downgrade()`` is DESTRUCTIVE: it drops the entire legacy baseline schema and
therefore any data in it. It is appropriate only for disposable / fresh-install /
scratch databases. It MUST NOT be run against a populated production or
development database unless an explicit operational policy later permits it.
Downgrading past R0 leaves an empty ``public`` schema.
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '8e973e84a9d7'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ---------------------------------------------------------------------------
# R0 payload — the executable DDL body of
# backend/schema/canonical_legacy_schema.sql, sliced verbatim from the
# "-- Name: doctors; Type: TABLE" section through "PostgreSQL database dump
# complete". pg_dump section comments are retained for traceability. Nothing
# was added, removed, reordered or rewritten. SHA-256 of this exact constant:
#   536c4e46435828151f0ca1bef10f5ca7af2e6f8aae24dc8222b03aab57520ee4
# ---------------------------------------------------------------------------
R0_LEGACY_BASELINE_SQL = """\
--
-- Name: doctors; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.doctors (
    id_dokter integer NOT NULL,
    nama_dokter character varying(150) NOT NULL,
    spesialisasi character varying(100)
);


--
-- Name: doctors_id_dokter_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.doctors_id_dokter_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: doctors_id_dokter_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.doctors_id_dokter_seq OWNED BY public.doctors.id_dokter;


--
-- Name: instrument_messages; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.instrument_messages (
    id_message integer NOT NULL,
    id_instrument integer,
    raw_message text NOT NULL,
    parse_status character varying(50) DEFAULT 'Success'::character varying,
    received_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: instrument_messages_id_message_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.instrument_messages_id_message_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: instrument_messages_id_message_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.instrument_messages_id_message_seq OWNED BY public.instrument_messages.id_message;


--
-- Name: instruments; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.instruments (
    id_instrument integer NOT NULL,
    nama_mesin character varying(100) NOT NULL,
    protokol character varying(50),
    tipe_koneksi character varying(50)
);


--
-- Name: instruments_id_instrument_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.instruments_id_instrument_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: instruments_id_instrument_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.instruments_id_instrument_seq OWNED BY public.instruments.id_instrument;


--
-- Name: orders; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.orders (
    id_order integer NOT NULL,
    no_registrasi character varying(50),
    id_pasien integer,
    id_unit integer,
    id_dokter integer,
    diagnosa text,
    waktu_order timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    status_order character varying(50) DEFAULT 'Diproses'::character varying
);


--
-- Name: orders_id_order_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.orders_id_order_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: orders_id_order_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.orders_id_order_seq OWNED BY public.orders.id_order;


--
-- Name: patients; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.patients (
    id_pasien integer NOT NULL,
    nomor_rm character varying(50) NOT NULL,
    nama_lengkap character varying(200) NOT NULL,
    tanggal_lahir date,
    jenis_kelamin character(1)
);


--
-- Name: patients_id_pasien_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.patients_id_pasien_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: patients_id_pasien_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.patients_id_pasien_seq OWNED BY public.patients.id_pasien;


--
-- Name: results; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.results (
    id_hasil integer NOT NULL,
    id_order integer,
    id_instrument integer,
    id_message integer,
    parameter_tes character varying(50) NOT NULL,
    nilai_hasil character varying(50) NOT NULL,
    satuan character varying(20),
    flag_abnormalitas character varying(10),
    reference_range_snapshot character varying(100),
    status_hasil character varying(20) DEFAULT 'Menunggu Validasi'::character varying,
    divalidasi_oleh character varying(150),
    waktu_validasi timestamp without time zone,
    waktu_hasil timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: results_id_hasil_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.results_id_hasil_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: results_id_hasil_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.results_id_hasil_seq OWNED BY public.results.id_hasil;


--
-- Name: test_groups; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.test_groups (
    id_group integer NOT NULL,
    nama_group character varying(100) NOT NULL,
    urutan_tampil integer
);


--
-- Name: test_groups_id_group_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.test_groups_id_group_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: test_groups_id_group_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.test_groups_id_group_seq OWNED BY public.test_groups.id_group;


--
-- Name: tests; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.tests (
    id_test integer NOT NULL,
    id_group integer,
    kode_tes character varying(50) NOT NULL,
    nama_tes character varying(100) NOT NULL,
    satuan_default character varying(20)
);


--
-- Name: tests_id_test_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.tests_id_test_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: tests_id_test_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.tests_id_test_seq OWNED BY public.tests.id_test;


--
-- Name: units; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.units (
    id_unit integer NOT NULL,
    kode_unit character varying(20) NOT NULL,
    nama_unit character varying(100) NOT NULL
);


--
-- Name: units_id_unit_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.units_id_unit_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: units_id_unit_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.units_id_unit_seq OWNED BY public.units.id_unit;


--
-- Name: doctors id_dokter; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.doctors ALTER COLUMN id_dokter SET DEFAULT nextval('public.doctors_id_dokter_seq'::regclass);


--
-- Name: instrument_messages id_message; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.instrument_messages ALTER COLUMN id_message SET DEFAULT nextval('public.instrument_messages_id_message_seq'::regclass);


--
-- Name: instruments id_instrument; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.instruments ALTER COLUMN id_instrument SET DEFAULT nextval('public.instruments_id_instrument_seq'::regclass);


--
-- Name: orders id_order; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.orders ALTER COLUMN id_order SET DEFAULT nextval('public.orders_id_order_seq'::regclass);


--
-- Name: patients id_pasien; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.patients ALTER COLUMN id_pasien SET DEFAULT nextval('public.patients_id_pasien_seq'::regclass);


--
-- Name: results id_hasil; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.results ALTER COLUMN id_hasil SET DEFAULT nextval('public.results_id_hasil_seq'::regclass);


--
-- Name: test_groups id_group; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.test_groups ALTER COLUMN id_group SET DEFAULT nextval('public.test_groups_id_group_seq'::regclass);


--
-- Name: tests id_test; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tests ALTER COLUMN id_test SET DEFAULT nextval('public.tests_id_test_seq'::regclass);


--
-- Name: units id_unit; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.units ALTER COLUMN id_unit SET DEFAULT nextval('public.units_id_unit_seq'::regclass);


--
-- Name: doctors doctors_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.doctors
    ADD CONSTRAINT doctors_pkey PRIMARY KEY (id_dokter);


--
-- Name: instrument_messages instrument_messages_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.instrument_messages
    ADD CONSTRAINT instrument_messages_pkey PRIMARY KEY (id_message);


--
-- Name: instruments instruments_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.instruments
    ADD CONSTRAINT instruments_pkey PRIMARY KEY (id_instrument);


--
-- Name: orders orders_no_registrasi_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.orders
    ADD CONSTRAINT orders_no_registrasi_key UNIQUE (no_registrasi);


--
-- Name: orders orders_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.orders
    ADD CONSTRAINT orders_pkey PRIMARY KEY (id_order);


--
-- Name: patients patients_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.patients
    ADD CONSTRAINT patients_pkey PRIMARY KEY (id_pasien);


--
-- Name: results results_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.results
    ADD CONSTRAINT results_pkey PRIMARY KEY (id_hasil);


--
-- Name: test_groups test_groups_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.test_groups
    ADD CONSTRAINT test_groups_pkey PRIMARY KEY (id_group);


--
-- Name: tests tests_kode_tes_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tests
    ADD CONSTRAINT tests_kode_tes_key UNIQUE (kode_tes);


--
-- Name: tests tests_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tests
    ADD CONSTRAINT tests_pkey PRIMARY KEY (id_test);


--
-- Name: results unique_order_test; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.results
    ADD CONSTRAINT unique_order_test UNIQUE (id_order, parameter_tes);


--
-- Name: units units_kode_unit_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.units
    ADD CONSTRAINT units_kode_unit_key UNIQUE (kode_unit);


--
-- Name: units units_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.units
    ADD CONSTRAINT units_pkey PRIMARY KEY (id_unit);


--
-- Name: instrument_messages instrument_messages_id_instrument_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.instrument_messages
    ADD CONSTRAINT instrument_messages_id_instrument_fkey FOREIGN KEY (id_instrument) REFERENCES public.instruments(id_instrument);


--
-- Name: orders orders_id_dokter_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.orders
    ADD CONSTRAINT orders_id_dokter_fkey FOREIGN KEY (id_dokter) REFERENCES public.doctors(id_dokter);


--
-- Name: orders orders_id_pasien_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.orders
    ADD CONSTRAINT orders_id_pasien_fkey FOREIGN KEY (id_pasien) REFERENCES public.patients(id_pasien);


--
-- Name: orders orders_id_unit_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.orders
    ADD CONSTRAINT orders_id_unit_fkey FOREIGN KEY (id_unit) REFERENCES public.units(id_unit);


--
-- Name: results results_id_instrument_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.results
    ADD CONSTRAINT results_id_instrument_fkey FOREIGN KEY (id_instrument) REFERENCES public.instruments(id_instrument);


--
-- Name: results results_id_message_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.results
    ADD CONSTRAINT results_id_message_fkey FOREIGN KEY (id_message) REFERENCES public.instrument_messages(id_message);


--
-- Name: results results_id_order_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.results
    ADD CONSTRAINT results_id_order_fkey FOREIGN KEY (id_order) REFERENCES public.orders(id_order);


--
-- Name: tests tests_id_group_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tests
    ADD CONSTRAINT tests_id_group_fkey FOREIGN KEY (id_group) REFERENCES public.test_groups(id_group);


--
-- PostgreSQL database dump complete
--
"""

# Reverse dependency order for downgrade (children before parents). Each table's
# owned SERIAL sequence is dropped with it; CASCADE covers the inter-table FKs.
_R0_TABLES_DROP_ORDER: tuple[str, ...] = (
    "results",
    "orders",
    "tests",
    "instrument_messages",
    "patients",
    "units",
    "doctors",
    "test_groups",
    "instruments",
)


def upgrade() -> None:
    """Create the exact pre-M1 legacy schema by executing the canonical DDL."""
    op.execute(R0_LEGACY_BASELINE_SQL)


def downgrade() -> None:
    """DESTRUCTIVE — drop the entire R0 legacy baseline schema.

    Only safe on a disposable / fresh-install / scratch database. See the module
    docstring. This does not touch any object outside the nine R0 tables and
    their owned sequences.
    """
    for table in _R0_TABLES_DROP_ORDER:
        op.execute(f"DROP TABLE IF EXISTS public.{table} CASCADE")
