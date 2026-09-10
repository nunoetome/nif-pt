-- =============================================================================
-- Criação das tabelas nif_pt e nif_pt_stg
-- =============================================================================
-- Uso: SQL Server Management Studio / Azure Data Studio / sqlcmd
-- Schema: stg_nunotome (ajustar conforme necessário)
-- =============================================================================

-- Esquema (criar se não existir)
IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = 'stg_nunotome')
    EXEC('CREATE SCHEMA stg_nunotome');
GO

-- =============================================================================
-- Tabela principal: nif_pt
-- Guarda o registo mais recente de cada NIF.
-- =============================================================================
IF OBJECT_ID('stg_nunotome.nif_pt', 'U') IS NOT NULL
    DROP TABLE stg_nunotome.nif_pt;
GO

CREATE TABLE stg_nunotome.nif_pt (
    -- Chave e controlo
    nif                     BIGINT          NOT NULL,
    nif_valido_formato      BIT             NULL,
    data_consulta           DATETIME2       NOT NULL DEFAULT GETDATE(),
    consulta_origem         NVARCHAR(50)    NULL DEFAULT 'nif.pt',

    -- Identificação
    seo_url                 NVARCHAR(255)   NULL,
    title                   NVARCHAR(500)   NULL,
    alias                   NVARCHAR(500)   NULL,
    status                  NVARCHAR(50)    NULL,
    start_date              DATE            NULL,
    activity                NVARCHAR(MAX)   NULL,

    -- Morada (place)
    place_address           NVARCHAR(500)   NULL,
    place_pc4               NVARCHAR(10)    NULL,
    place_pc3               NVARCHAR(10)    NULL,
    place_city              NVARCHAR(100)   NULL,

    -- Morada (address — campo adicional da API)
    address                 NVARCHAR(500)   NULL,
    pc4                     NVARCHAR(10)    NULL,
    pc3                     NVARCHAR(10)    NULL,
    city                    NVARCHAR(100)   NULL,

    -- Geolocalização
    geo_region              NVARCHAR(100)   NULL,
    geo_county              NVARCHAR(100)   NULL,
    geo_parish              NVARCHAR(100)   NULL,

    -- Contactos
    contacts_email          NVARCHAR(255)   NULL,
    contacts_phone          NVARCHAR(50)    NULL,
    contacts_website        NVARCHAR(255)   NULL,
    contacts_fax            NVARCHAR(50)    NULL,

    -- Estrutura legal
    structure_nature        NVARCHAR(50)    NULL,
    structure_capital       DECIMAL(18,2)   NULL,
    structure_capital_currency NVARCHAR(10) NULL,

    -- Classificação de atividade
    cae                     NVARCHAR(500)   NULL,

    -- Ligações externas
    racius                  NVARCHAR(500)   NULL,
    portugalio              NVARCHAR(500)   NULL,

    -- Créditos da consulta
    creditos_used           NVARCHAR(50)    NULL,
    creditos_left_month     INT             NULL,
    creditos_left_day       INT             NULL,
    creditos_left_hour      INT             NULL,
    creditos_left_minute    INT             NULL,
    creditos_left_paid      INT             NULL,

    -- Rastreabilidade por execução
    run_id                  NVARCHAR(36)    NULL,

    -- Constraints
    CONSTRAINT pk_nif_pt PRIMARY KEY CLUSTERED (nif)
);
GO

CREATE INDEX ix_nif_pt_run_id ON stg_nunotome.nif_pt(run_id);
GO

-- =============================================================================
-- Tabela de staging: nif_pt_stg
-- Recebe registos duplicados (NIF já existente em nif_pt).
-- Um procedure de update posterior fará o merge.
-- =============================================================================
IF OBJECT_ID('stg_nunotome.nif_pt_stg', 'U') IS NOT NULL
    DROP TABLE stg_nunotome.nif_pt_stg;
GO

CREATE TABLE stg_nunotome.nif_pt_stg (
    -- Chave e controlo
    id                      BIGINT          IDENTITY(1,1) NOT NULL,
    nif                     BIGINT          NOT NULL,
    nif_valido_formato      BIT             NULL,
    data_consulta           DATETIME2       NOT NULL DEFAULT GETDATE(),
    consulta_origem         NVARCHAR(50)    NULL DEFAULT 'nif.pt',
    data_staging            DATETIME2       NOT NULL DEFAULT GETDATE(),
    processado              BIT             NOT NULL DEFAULT 0,

    -- Identificação
    seo_url                 NVARCHAR(255)   NULL,
    title                   NVARCHAR(500)   NULL,
    alias                   NVARCHAR(500)   NULL,
    status                  NVARCHAR(50)    NULL,
    start_date              DATE            NULL,
    activity                NVARCHAR(MAX)   NULL,

    -- Morada (place)
    place_address           NVARCHAR(500)   NULL,
    place_pc4               NVARCHAR(10)    NULL,
    place_pc3               NVARCHAR(10)    NULL,
    place_city              NVARCHAR(100)   NULL,

    -- Morada (address)
    address                 NVARCHAR(500)   NULL,
    pc4                     NVARCHAR(10)    NULL,
    pc3                     NVARCHAR(10)    NULL,
    city                    NVARCHAR(100)   NULL,

    -- Geolocalização
    geo_region              NVARCHAR(100)   NULL,
    geo_county              NVARCHAR(100)   NULL,
    geo_parish              NVARCHAR(100)   NULL,

    -- Contactos
    contacts_email          NVARCHAR(255)   NULL,
    contacts_phone          NVARCHAR(50)    NULL,
    contacts_website        NVARCHAR(255)   NULL,
    contacts_fax            NVARCHAR(50)    NULL,

    -- Estrutura legal
    structure_nature        NVARCHAR(50)    NULL,
    structure_capital       DECIMAL(18,2)   NULL,
    structure_capital_currency NVARCHAR(10) NULL,

    -- Classificação de atividade
    cae                     NVARCHAR(500)   NULL,

    -- Ligações externas
    racius                  NVARCHAR(500)   NULL,
    portugalio              NVARCHAR(500)   NULL,

    -- Créditos da consulta
    creditos_used           NVARCHAR(50)    NULL,
    creditos_left_month     INT             NULL,
    creditos_left_day       INT             NULL,
    creditos_left_hour      INT             NULL,
    creditos_left_minute    INT             NULL,
    creditos_left_paid      INT             NULL,

    -- Rastreabilidade por execução
    run_id                  NVARCHAR(36)    NULL,

    -- Constraints
    CONSTRAINT pk_nif_pt_stg PRIMARY KEY CLUSTERED (id)
);
GO

CREATE INDEX ix_nif_pt_stg_run_id ON stg_nunotome.nif_pt_stg(run_id);
GO
