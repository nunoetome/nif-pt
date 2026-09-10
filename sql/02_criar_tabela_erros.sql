-- =============================================================================
-- Tabela de erros nif_api_erros — camada de tratamento de erros nif.pt
-- =============================================================================
-- Guarda todas as respostas de erro da API para auditoria e decisão de retry.
-- Uso: SQL Server Management Studio / Azure Data Studio / sqlcmd
-- Schema: stg_nunotome (ajustar conforme necessário)
-- =============================================================================

IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = 'stg_nunotome')
    EXEC('CREATE SCHEMA stg_nunotome');
GO

-- SQLite usa DDL em utils/error_handler.py:DDL_ERROS (CREATE TABLE IF NOT EXISTS).
-- Abaixo apenas DDL para Azure SQL (idempotente via OBJECT_ID).

IF OBJECT_ID('stg_nunotome.nif_api_erros', 'U') IS NOT NULL
    DROP TABLE stg_nunotome.nif_api_erros;
GO

CREATE TABLE stg_nunotome.nif_api_erros (
    id                      BIGINT          IDENTITY(1,1) NOT NULL,
    nif                     BIGINT          NULL,
    data_erro               DATETIME2       NOT NULL DEFAULT GETDATE(),
    tipo_erro               NVARCHAR(50)    NOT NULL,   -- rate_limit_minute/hour/day/month/paid/unknown/generic_error
    codigo_erro             NVARCHAR(50)    NULL,       -- result da API (ex: "error")
    mensagem                NVARCHAR(500)   NULL,       -- message da API
    left_month              INT             NULL,
    left_day                INT             NULL,
    left_hour               INT             NULL,
    left_minute             INT             NULL,
    left_paid               INT             NULL,
    dados_json              NVARCHAR(MAX)   NOT NULL,   -- JSON completo da API
    acao                    NVARCHAR(50)    NULL,       -- retry_60s / retry_3600s / abort_day / abort_month / none
    run_id                  NVARCHAR(36)    NULL,       -- identificador da execução (UUID v4)
    resolvido               BIT             NOT NULL DEFAULT 0,
    CONSTRAINT pk_nif_api_erros PRIMARY KEY CLUSTERED (id)
);
GO

CREATE INDEX ix_nif_api_erros_nif ON stg_nunotome.nif_api_erros(nif);
GO
CREATE INDEX ix_nif_api_erros_tipo ON stg_nunotome.nif_api_erros(tipo_erro);
GO
CREATE INDEX ix_nif_api_erros_data ON stg_nunotome.nif_api_erros(data_erro);
GO
CREATE INDEX ix_nif_api_erros_run_id ON stg_nunotome.nif_api_erros(run_id);
GO
