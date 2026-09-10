-- =============================================================================
-- Migração run_id — adiciona coluna run_id a tabelas existentes (idempotente)
-- =============================================================================
-- Uso: executar em BDs já criadas com 01/02 (não faz DROP, é seguro em prod).
-- Para novas BDs, 01_criar_tabelas.sql e 02_criar_tabela_erros.sql já incluem
-- a coluna — este script é NO-OP nesses casos.
-- Schema: stg_nunotome
-- =============================================================================

IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = 'stg_nunotome')
    EXEC('CREATE SCHEMA stg_nunotome');
GO

-- nif_pt
IF COL_LENGTH('stg_nunotome.nif_pt', 'run_id') IS NULL
    ALTER TABLE stg_nunotome.nif_pt ADD run_id NVARCHAR(36) NULL;
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'ix_nif_pt_run_id' AND object_id = OBJECT_ID('stg_nunotome.nif_pt'))
    CREATE INDEX ix_nif_pt_run_id ON stg_nunotome.nif_pt(run_id);
GO

-- nif_pt_stg
IF COL_LENGTH('stg_nunotome.nif_pt_stg', 'run_id') IS NULL
    ALTER TABLE stg_nunotome.nif_pt_stg ADD run_id NVARCHAR(36) NULL;
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'ix_nif_pt_stg_run_id' AND object_id = OBJECT_ID('stg_nunotome.nif_pt_stg'))
    CREATE INDEX ix_nif_pt_stg_run_id ON stg_nunotome.nif_pt_stg(run_id);
GO

-- nif_api_erros
IF COL_LENGTH('stg_nunotome.nif_api_erros', 'run_id') IS NULL
    ALTER TABLE stg_nunotome.nif_api_erros ADD run_id NVARCHAR(36) NULL;
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'ix_nif_api_erros_run_id' AND object_id = OBJECT_ID('stg_nunotome.nif_api_erros'))
    CREATE INDEX ix_nif_api_erros_run_id ON stg_nunotome.nif_api_erros(run_id);
GO

-- Verificação
-- SELECT TABLE_NAME, COLUMN_NAME, DATA_TYPE FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME IN ('nif_pt','nif_pt_stg','nif_api_erros') AND COLUMN_NAME='run_id';
