--
-- PostgreSQL database dump
--

\restrict UIk2cDLL8j39eAmmlUcM1khNBPyZq3K6JeItjDqlFcfco9uGPVbZZA2TGgdQTA2

-- Dumped from database version 15.16
-- Dumped by pg_dump version 15.16

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: account_snapshots; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.account_snapshots (
    id integer NOT NULL,
    equity numeric,
    used_margin numeric,
    available numeric,
    created_at timestamp without time zone DEFAULT now()
);


ALTER TABLE public.account_snapshots OWNER TO postgres;

--
-- Name: account_snapshots_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.account_snapshots_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.account_snapshots_id_seq OWNER TO postgres;

--
-- Name: account_snapshots_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.account_snapshots_id_seq OWNED BY public.account_snapshots.id;


--
-- Name: bot_logs; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.bot_logs (
    id bigint NOT NULL,
    level character varying(10),
    symbol character varying(20),
    message text NOT NULL,
    context jsonb,
    created_at timestamp without time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.bot_logs OWNER TO postgres;

--
-- Name: bot_logs_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.bot_logs_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.bot_logs_id_seq OWNER TO postgres;

--
-- Name: bot_logs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.bot_logs_id_seq OWNED BY public.bot_logs.id;


--
-- Name: bot_state; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.bot_state (
    id integer NOT NULL,
    state_json jsonb NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL,
    CONSTRAINT bot_state_id_check CHECK ((id = 1))
);


ALTER TABLE public.bot_state OWNER TO postgres;

--
-- Name: equity_snapshots; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.equity_snapshots (
    id bigint NOT NULL,
    total_balance numeric(20,10),
    available_balance numeric(20,10),
    unrealized_pnl numeric(20,10),
    created_at timestamp without time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.equity_snapshots OWNER TO postgres;

--
-- Name: equity_snapshots_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.equity_snapshots_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.equity_snapshots_id_seq OWNER TO postgres;

--
-- Name: equity_snapshots_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.equity_snapshots_id_seq OWNED BY public.equity_snapshots.id;


--
-- Name: order_events; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.order_events (
    id bigint NOT NULL,
    order_id bigint NOT NULL,
    event_type character varying(30),
    exchange_status character varying(30),
    payload jsonb,
    created_at timestamp without time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.order_events OWNER TO postgres;

--
-- Name: order_events_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.order_events_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.order_events_id_seq OWNER TO postgres;

--
-- Name: order_events_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.order_events_id_seq OWNED BY public.order_events.id;


--
-- Name: orders; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.orders (
    id bigint NOT NULL,
    position_id bigint,
    symbol character varying(20) NOT NULL,
    side character varying(10),
    order_type character varying(30),
    is_reduce_only boolean,
    is_close_position boolean,
    exchange_order_id bigint,
    exchange_algo_id bigint,
    is_algo boolean DEFAULT false NOT NULL,
    price numeric(20,10),
    stop_price numeric(20,10),
    status character varying(30),
    raw_response jsonb NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.orders OWNER TO postgres;

--
-- Name: orders_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.orders_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.orders_id_seq OWNER TO postgres;

--
-- Name: orders_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.orders_id_seq OWNED BY public.orders.id;


--
-- Name: position_events; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.position_events (
    id integer NOT NULL,
    position_id integer,
    event_type text,
    price numeric,
    created_at timestamp without time zone DEFAULT now(),
    payload jsonb
);


ALTER TABLE public.position_events OWNER TO postgres;

--
-- Name: position_events_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.position_events_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.position_events_id_seq OWNER TO postgres;

--
-- Name: position_events_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.position_events_id_seq OWNED BY public.position_events.id;


--
-- Name: position_stops; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.position_stops (
    id bigint NOT NULL,
    position_id bigint NOT NULL,
    stop_price numeric(20,10) NOT NULL,
    exchange_algo_id bigint,
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    canceled_at timestamp without time zone
);


ALTER TABLE public.position_stops OWNER TO postgres;

--
-- Name: position_stops_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.position_stops_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.position_stops_id_seq OWNER TO postgres;

--
-- Name: position_stops_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.position_stops_id_seq OWNED BY public.position_stops.id;


--
-- Name: positions; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.positions (
    id bigint NOT NULL,
    symbol character varying(20) NOT NULL,
    side character varying(10) NOT NULL,
    qty numeric(20,10) NOT NULL,
    entry_price numeric(20,10) NOT NULL,
    status character varying(20) NOT NULL,
    opened_at timestamp without time zone DEFAULT now() NOT NULL,
    closed_at timestamp without time zone,
    exit_price numeric(20,10),
    realized_pnl numeric(20,10),
    strategy_tag character varying(50),
    commission numeric(20,10) DEFAULT 0,
    commission_pct numeric(8,6) DEFAULT 0,
    signal_features jsonb,
    CONSTRAINT positions_side_check CHECK (((side)::text = ANY ((ARRAY['LONG'::character varying, 'SHORT'::character varying])::text[]))),
    CONSTRAINT positions_status_check CHECK (((status)::text = ANY ((ARRAY['OPEN'::character varying, 'CLOSED'::character varying])::text[])))
);


ALTER TABLE public.positions OWNER TO postgres;

--
-- Name: positions_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.positions_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.positions_id_seq OWNER TO postgres;

--
-- Name: positions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.positions_id_seq OWNED BY public.positions.id;


--
-- Name: account_snapshots id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.account_snapshots ALTER COLUMN id SET DEFAULT nextval('public.account_snapshots_id_seq'::regclass);


--
-- Name: bot_logs id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.bot_logs ALTER COLUMN id SET DEFAULT nextval('public.bot_logs_id_seq'::regclass);


--
-- Name: equity_snapshots id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.equity_snapshots ALTER COLUMN id SET DEFAULT nextval('public.equity_snapshots_id_seq'::regclass);


--
-- Name: order_events id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.order_events ALTER COLUMN id SET DEFAULT nextval('public.order_events_id_seq'::regclass);


--
-- Name: orders id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.orders ALTER COLUMN id SET DEFAULT nextval('public.orders_id_seq'::regclass);


--
-- Name: position_events id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.position_events ALTER COLUMN id SET DEFAULT nextval('public.position_events_id_seq'::regclass);


--
-- Name: position_stops id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.position_stops ALTER COLUMN id SET DEFAULT nextval('public.position_stops_id_seq'::regclass);


--
-- Name: positions id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.positions ALTER COLUMN id SET DEFAULT nextval('public.positions_id_seq'::regclass);


--
-- Name: account_snapshots account_snapshots_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.account_snapshots
    ADD CONSTRAINT account_snapshots_pkey PRIMARY KEY (id);


--
-- Name: bot_logs bot_logs_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.bot_logs
    ADD CONSTRAINT bot_logs_pkey PRIMARY KEY (id);


--
-- Name: bot_state bot_state_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.bot_state
    ADD CONSTRAINT bot_state_pkey PRIMARY KEY (id);


--
-- Name: equity_snapshots equity_snapshots_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.equity_snapshots
    ADD CONSTRAINT equity_snapshots_pkey PRIMARY KEY (id);


--
-- Name: order_events order_events_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.order_events
    ADD CONSTRAINT order_events_pkey PRIMARY KEY (id);


--
-- Name: orders orders_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.orders
    ADD CONSTRAINT orders_pkey PRIMARY KEY (id);


--
-- Name: position_events position_events_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.position_events
    ADD CONSTRAINT position_events_pkey PRIMARY KEY (id);


--
-- Name: position_stops position_stops_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.position_stops
    ADD CONSTRAINT position_stops_pkey PRIMARY KEY (id);


--
-- Name: positions positions_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.positions
    ADD CONSTRAINT positions_pkey PRIMARY KEY (id);


--
-- Name: idx_equity_created; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_equity_created ON public.equity_snapshots USING btree (created_at);


--
-- Name: idx_logs_created; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_logs_created ON public.bot_logs USING btree (created_at);


--
-- Name: idx_order_events_order; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_order_events_order ON public.order_events USING btree (order_id);


--
-- Name: idx_orders_algo; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_orders_algo ON public.orders USING btree (exchange_algo_id);


--
-- Name: idx_orders_position; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_orders_position ON public.orders USING btree (position_id);


--
-- Name: idx_orders_symbol; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_orders_symbol ON public.orders USING btree (symbol);


--
-- Name: idx_position_stops_active; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_position_stops_active ON public.position_stops USING btree (position_id, is_active);


--
-- Name: idx_positions_symbol_status; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_positions_symbol_status ON public.positions USING btree (symbol, status);


--
-- Name: order_events order_events_order_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.order_events
    ADD CONSTRAINT order_events_order_id_fkey FOREIGN KEY (order_id) REFERENCES public.orders(id) ON DELETE CASCADE;


--
-- Name: orders orders_position_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.orders
    ADD CONSTRAINT orders_position_id_fkey FOREIGN KEY (position_id) REFERENCES public.positions(id) ON DELETE SET NULL;


--
-- Name: position_stops position_stops_position_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.position_stops
    ADD CONSTRAINT position_stops_position_id_fkey FOREIGN KEY (position_id) REFERENCES public.positions(id) ON DELETE CASCADE;


--
-- PostgreSQL database dump complete
--

\unrestrict UIk2cDLL8j39eAmmlUcM1khNBPyZq3K6JeItjDqlFcfco9uGPVbZZA2TGgdQTA2

