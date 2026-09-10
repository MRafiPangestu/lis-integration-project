--
-- Canonical legacy schema (M9.0 Phase 2C)
--
-- Deterministic derivation of the pre-M1 legacy schema.
-- Source artifact : backend/schema/legacy_schema.sql
-- Source SHA-256  : 93d902f67e334c0d6b7ea0ce36a2c81cbb5292781b7d45a920b5cbc67199c81e
--
-- Removed from the source (approved dump/session directives only):
--   R1  psql restrict/unrestrict meta-commands            (2)
--   R2  pg_dump session configuration directives         (12)
--   R3  search_path reset directive                       (1)
--   R4  public-schema comment mutation                    (1)
--   R5  section header of the directive removed by R4     (1)
--
-- Deliberately worded to contain no executable SQL token, so that
-- automated checks over this file cannot match header prose.
--
-- No schema DDL was added, removed or transformed. SERIAL sequence
-- mechanism (sequence + OWNED BY + nextval) is preserved verbatim.
-- patients.nomor_rm is intentionally NON-UNIQUE here: that is legacy
-- truth. F-2 is a separate later revision and must not be folded in.
--

--
-- PostgreSQL database dump
--


-- Dumped from database version 18.6
-- Dumped by pg_dump version 18.6


--
-- Name: public; Type: SCHEMA; Schema: -; Owner: -
--

-- *not* creating schema, since initdb creates it







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
