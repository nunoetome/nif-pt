"""logging_template.py — Configuração do sistema de logging.

Este módulo disponibiliza uma configuração reutilizável de logging com:
- Níveis configuráveis para ficheiro e consola (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- "Ultra debug mode": formato alargado para mensagens DEBUG (com ficheiro, função e linha)
- Prefixo personalizado para fácil identificação das mensagens em logs agregados
- Rotação automática de logs por tamanho e/ou número de registos

Baseado em: https://github.com/nunoetome/my_python_starter_kit

Changelog:
- 2026-06-19 | Nuno Tomé | versão 2.1 — Adicionado livro de etilo de logs para AI e humanos
- 2026-06-02 | Nuno Tomé | versão 2.0 — RotatingFileHandler, docstrings PEP 257, setup_logging()
- 2026-06-02 | Nuno Tomé | adicionado RotatingFileHandler com rotação por tamanho/registos
- 2026-06-02 | Nuno Tomé | adicionadas variáveis globais LOG_MAX_BYTES, LOG_MAX_RECORDS, LOG_MAX_BACKUP
- 2026-06-02 | Nuno Tomé | adicionada função setup_logging(); ini_logging mantida como legacy
- 2026-06-02 | Nuno Tomé | removido import inspect não utilizado
- 2026-06-02 | Nuno Tomé | substituído block comment por module docstring (PEP 257)
- 2025-01-22 | Nuno Tomé | implementação do UTF-8 na escrita dos ficheiros de log
- 2025-01-06 | Nuno Tomé | adaptado ao projeto Base.gov.pt
- 2025-01-06 | Nuno Tomé | adaptado ao projeto EQS
- 2025-08-23 | Nuno Tomé | versão 1.0
- 2024-10-07 | Nuno Tomé | versão beta final
- 2024-10-06 | Nuno Tomé | versão alpha final
"""

import logging
import os


# --- Configuração de níveis ------------------------------------------------
# Descomente o nível pretendido. LOG_LEVEL_GLOBAL sobrepõe-se aos restantes.

LOG_LEVEL_GLOBAL = logging.INFO
LOG_LEVEL_FILE = logging.INFO
LOG_LEVEL_CONSOLE = logging.INFO

# --- Caminhos e prefixo ----------------------------------------------------
LOG_FOLDER = 'log_files'
LOG_OUTPUT_FILE = os.path.join(LOG_FOLDER, 'parse_eforms.log')
LOG_OUTPUT_PREFIX = '<<eqs>>'

# --- Formatos --------------------------------------------------------------
LOG_FORMAT_FILE = (
    LOG_OUTPUT_PREFIX
    + ' %(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
LOG_FORMAT_CONSOLE = LOG_OUTPUT_PREFIX + ' %(levelname)s - %(message)s'

# --- Ultra debug mode ------------------------------------------------------
# Quando ativo, as mensagens DEBUG incluem ficheiro, função e linha.
FILE_ULTRA_DEBUG = True
CONSOLE_ULTRA_DEBUG = True

LOG_FORMAT_FILE_ULTRA_DEBUG = (
    LOG_FORMAT_FILE + ' - [%(filename)s - %(funcName)s - %(lineno)d]'
)
LOG_FORMAT_CONSOLE_ULTRA_DEBUG = (
    LOG_FORMAT_CONSOLE + ' - [%(filename)s - %(funcName)s - %(lineno)d]'
)

# --- Rotação de logs -------------------------------------------------------
# 0 = desligado
LOG_MAX_BYTES = 10485760       # bytes
LOG_MAX_RECORDS = 5000     # número de registos
LOG_MAX_BACKUP = 10      # número máximo de ficheiros de arquivo
# ---------------------------------------------------------------------------


LOGGER = logging.getLogger(__name__)


class RotatingFileHandler(logging.Handler):
    """Handler com rotação automática por tamanho e/ou número de registos.

    A rotação ocorre quando o ficheiro atual atinge o limite de tamanho
    (LOG_MAX_BYTES) **ou** o limite de registos (LOG_MAX_RECORDS),
    conforme o que acontecer primeiro. Os ficheiros são renomeados em
    cascata (logrotate-style) até ao número máximo de arquivos definido
    em LOG_MAX_BACKUP.

    Arquivos gerados::

        p2_download_packages.log       ← ficheiro de escrita atual
        p2_download_packages_1.log     ← arquivo mais recente
        p2_download_packages_2.log     ← ...
        p2_download_packages_N.log     ← arquivo mais antigo (removido no próximo ciclo)
    """

    def __init__(self, filename, mode='a', encoding=None,
                 max_bytes=0, max_records=0, max_backup=0):
        super().__init__()
        self.filename = filename
        self.base_name, self.ext = os.path.splitext(filename)
        self.mode = mode
        self.encoding = encoding
        self.max_bytes = max_bytes
        self.max_records = max_records
        self.max_backup = max_backup
        self.record_count = 0
        self.terminator = '\n'
        self.stream = None
        self._open()

    def _open(self):
        dirname = os.path.dirname(self.filename)
        if dirname and not os.path.exists(dirname):
            os.makedirs(dirname)
        self.stream = open(self.filename, self.mode, encoding=self.encoding)
        self.record_count = 0

    def _archive_name(self, index):
        return f"{self.base_name}_{index}{self.ext}"

    def _should_rotate(self):
        if self.max_backup <= 0:
            return False
        if self.max_records > 0 and self.record_count >= self.max_records:
            return True
        if self.max_bytes > 0:
            try:
                if os.path.getsize(self.filename) >= self.max_bytes:
                    return True
            except OSError:
                pass
        return False

    def _rotate(self):
        self.stream.close()

        oldest = self._archive_name(self.max_backup)
        if os.path.exists(oldest):
            os.remove(oldest)

        for i in range(self.max_backup - 1, 0, -1):
            src = self._archive_name(i)
            dst = self._archive_name(i + 1)
            if os.path.exists(src):
                os.replace(src, dst)

        if os.path.exists(self.filename):
            os.replace(self.filename, self._archive_name(1))

        self._open()

    def emit(self, record):
        try:
            msg = self.format(record) + self.terminator
            self.stream.write(msg)
            self.record_count += 1
            self.flush()

            if self._should_rotate():
                self._rotate()
        except Exception:
            self.handleError(record)

    def flush(self):
        if self.stream and not self.stream.closed:
            self.stream.flush()

    def close(self):
        if self.stream and not self.stream.closed:
            self.stream.close()
        super().close()


def ini_logging():
    """[LEGACY] Configura e devolve o logger da aplicação.

    Mantida apenas para retrocompatibilidade. Para novos desenvolvimentos
    use :func:`setup_logging`.
    """
    if LOGGER.handlers:
        return LOGGER

    LOGGER.setLevel(LOG_LEVEL_GLOBAL)

    # FILE HANDLER
    file_handler = RotatingFileHandler(
        LOG_OUTPUT_FILE,
        mode="a",
        encoding="utf-8",
        max_bytes=LOG_MAX_BYTES,
        max_records=LOG_MAX_RECORDS,
        max_backup=LOG_MAX_BACKUP,
    )
    file_handler.setLevel(LOG_LEVEL_FILE)

    if FILE_ULTRA_DEBUG:
        class CustomDebugFormatteFile(logging.Formatter):
            def format(self, record):
                if record.levelno == logging.DEBUG:
                    self._style._fmt = LOG_FORMAT_FILE_ULTRA_DEBUG
                else:
                    self._style._fmt = LOG_FORMAT_FILE
                return super().format(record)
        file_handler.setFormatter(CustomDebugFormatteFile())
    else:
        file_handler.setFormatter(logging.Formatter(LOG_FORMAT_FILE))

    LOGGER.addHandler(file_handler)

    # CONSOLE HANDLER
    console_handler = logging.StreamHandler()
    console_handler.setLevel(LOG_LEVEL_CONSOLE)

    if CONSOLE_ULTRA_DEBUG:
        class CustomDebugFormatter(logging.Formatter):
            def format(self, record):
                if record.levelno == logging.DEBUG:
                    self._style._fmt = LOG_FORMAT_CONSOLE_ULTRA_DEBUG
                else:
                    self._style._fmt = LOG_FORMAT_CONSOLE
                return super().format(record)
        console_handler.setFormatter(CustomDebugFormatter())
    else:
        console_handler.setFormatter(logging.Formatter(LOG_FORMAT_CONSOLE))

    LOGGER.addHandler(console_handler)

    return LOGGER


def setup_logging():
    """Configura e devolve o logger da aplicação.

    Wrapper que chama :func:`ini_logging` para garantir
    retrocompatibilidade.
    """
    return ini_logging()


# =================================================================
# LIVRO DE ESTILO DE LOGS — Especificação para AI e Humanos
# =================================================================
#
# Este bloco define as convenções visuais para o CONTEÚDO textual
# das mensagens de log (não o formato do LogRecord — isso é feito
# pelos Formatters já configurados). O objetivo é garantir
# consistência visual em todas as aplicações que usam este template.
#
# Cada estilo é definido por um conjunto fixo de campos para que
# uma AI (ou humano) consiga aplicá-lo de forma determinística.
#
# -----------------------------------------------------------------
# REGRAS GLOBAIS (aplicam-se a todos os estilos)
# -----------------------------------------------------------------
#
#   R1. WIDTH padrão = 49 colunas. NUNCA exceder 79 colunas.
#   R2. Caracteres por nível hierárquico:
#       Aplicação → '='
#       Secção    → '-'
#       Função    → '~'   (discreto, para passos internos)
#       Separador → '-'   (pode ser '-' ou '.' conforme contexto)
#   R3. Banners (app / secção / função) são sempre 3 linhas:
#       linha 1: char * width
#       linha 2: título formatado (center para início, right para fim)
#       linha 3: char * width
#   R4. Tags de contexto usam o formato [tag] no INÍCIO da mensagem,
#       colado ao texto (sem espaço entre ] e o texto).
#       Tags em lowercase, sem underscores (ex: [pdf], [db], [api]).
#   R5. Rodapés (APP_END, SECTION_END) usam o MESMO carácter e
#       largura do banner de abertura correspondente. O texto
#       alinha à direita com o padrão " Fim <nome> " ou " <nome> finalizado ".
#   R6. Para todos os alinhamentos, usar f-strings com alignment
#       specs do Python (:<width, :^width, :>width) preenchidas
#       com o carácter do estilo.
#   R7. Nível de log: Banners e separadores usam INFO.
#       Tags herdam o nível do contexto onde são usadas.
#       Box usa o nível do conteúdo que está a emoldurar.
#   R8. Se o título for maior que width-4, truncar com "…" no final
#       para caber. Se for menor, centrar com espaços simétricos.
#
# -----------------------------------------------------------------
# STYLE 1: BANNER_APP_START
#   Usage:    Início da aplicação. Colocar imediatamente após a
#             configuração do logger (setup_logging / ini_logging).
#   Severity: INFO
#   Rule:     Título centrado "<nome> a iniciar". 3 linhas com '='.
#   Width:    49
#   Char:     =
#   Align:    center (linha do título)
#   Lines:    3
#
#   Output:
#     ===================================================
#     ============== AppX v1.0 a iniciar ===============
#     ===================================================
#
#   Code:
#     LOGGER.info("=" * 49)
#     LOGGER.info(f"{' AppX v1.0 a iniciar ':=^49}")
#     LOGGER.info("=" * 49)
#
# -----------------------------------------------------------------
# STYLE 2: BANNER_APP_END
#   Usage:    Fecho da aplicação, última mensagem antes de terminar.
#   Severity: INFO
#   Rule:     Texto alinhado à direita. Mesmo char e width do
#             BANNER_APP_START. Padrão: " <nome> finalizado ".
#   Width:    49
#   Char:     =
#   Align:    right (linha do título)
#   Lines:    3
#
#   Output:
#     ===================================================
#     ============== AppX v1.0 finalizado ===============
#     ===================================================
#
#   Code:
#     LOGGER.info("=" * 49)
#     LOGGER.info(f"{' AppX v1.0 finalizado ':=^49}")
#     LOGGER.info("=" * 49)
#
# -----------------------------------------------------------------
# STYLE 3: BANNER_SECTION_START
#   Usage:    Início de uma sub-secção lógica da aplicação
#             (ex: "Processar PDFs", "Exportar dados", "Validar formulários").
#   Severity: INFO
#   Rule:     Título centrado com '-'. Mais discreto que o banner principal.
#   Width:    49
#   Char:     -
#   Align:    center
#   Lines:    3
#
#   Output:
#     ---------------------------------------------------
#     ---------------- Processar PDFs ------------------
#     ---------------------------------------------------
#
#   Code:
#     LOGGER.info("-" * 49)
#     LOGGER.info(f"{' Processar PDFs ':-^49}")
#     LOGGER.info("-" * 49)
#
# -----------------------------------------------------------------
# STYLE 4: BANNER_SECTION_END
#   Usage:    Fecho de uma sub-secção. Espelha o BANNER_SECTION_START.
#   Severity: INFO
#   Rule:     Texto alinhado à direita. Padrão: " Fim <nome> ".
#   Width:    49
#   Char:     -
#   Align:    right
#   Lines:    3
#
#   Output:
#     ---------------------------------------------------
#     ---------------- Fim Processar PDFs ---------------
#     ---------------------------------------------------
#
#   Code:
#     LOGGER.info("-" * 49)
#     LOGGER.info(f"{' Fim Processar PDFs ':-^49}")
#     LOGGER.info("-" * 49)
#
# -----------------------------------------------------------------
# STYLE 5: BANNER_FUNCTION
#   Usage:    Início de uma função/método crítico cuja execução
#             se quer destacar no log (ex: init_db, parse_xml).
#             NÃO usar em todas as funções — só nas relevantes.
#   Severity: DEBUG
#   Rule:     Título centrado com '~'. Mais discreto e curto.
#             Formato: "~~~ nome_funcao() ~~~" ou "~~~ descrição ~~~".
#   Width:    49
#   Char:     ~
#   Align:    center
#   Lines:    1 (apenas a linha do título, sem barras superior/inferior)
#
#   Output:
#     ~~~~~~~~~~~~~~~~~ init_database() ~~~~~~~~~~~~~~~~~~
#
#   Code:
#     LOGGER.debug(f"{' init_database() ':~^49}")
#
# -----------------------------------------------------------------
# STYLE 6: TAG
#   Usage:    Prefixar mensagens com o nome do componente, serviço
#             ou módulo que as gerou. Facilita filtragem e leitura
#             de logs agregados.
#   Severity: qualquer (herda o nível da mensagem)
#   Rule:     [tag] no início, colado à mensagem. Tag em lowercase,
#             sem underscores, sem espaços. Máximo 12 caracteres.
#   Width:    N/A
#   Char:     N/A
#   Align:    left
#
#   Output:
#     [pdf] A processar documento 123
#     [pdf] Documento 123 convertido com sucesso
#     [db] Ligação à base de dados estabelecida
#     [db] Query executada em 0.34s
#     [api] GET /users -> 200 OK
#     [api] POST /invoice -> 201 Created
#
#   Code:
#     LOGGER.info("[pdf] A processar documento %d", doc_id)
#     LOGGER.info("[pdf] Documento %d convertido com sucesso", doc_id)
#     LOGGER.info("[db] Ligação à base de dados estabelecida")
#     LOGGER.info("[db] Query executada em %.2fs", elapsed)
#     LOGGER.info("[api] GET /users -> 200 OK")
#     LOGGER.info("[api] POST /invoice -> 201 Created")
#
# -----------------------------------------------------------------
# STYLE 7: SEPARATOR
#   Usage:    Separar visualmente blocos de log dentro de uma secção
#             ou entre iterações de um loop relevante.
#   Severity: DEBUG
#   Rule:     Linha única com o carácter repetido width vezes.
#   Width:    49
#   Char:     -  (pode usar '.' para separadores ainda mais discretos)
#   Align:    N/A
#   Lines:    1
#
#   Output:
#     ---------------------------------------------------
#
#   Code:
#     LOGGER.debug("-" * 49)
#
# -----------------------------------------------------------------
# STYLE 8: BOX
#   Usage:    Emoldurar informação estruturada como tabelas, resumos
#             de processamento, ou dados multi-linha que beneficiem
#             de destaque visual.
#   Severity: mesmo nível dos dados que contém (geralmente INFO)
#   Rule:     Linha de topo com título (se existir), linhas de
#             conteúdo prefixadas com "| ", linha de base.
#             Bordas usam '-' (horizontal) e '|' (vertical).
#   Width:    49 (conteúdo interno: width - 4 para margens)
#   Char:     - (horizontal), | (vertical)
#   Align:    left (conteúdo)
#   Lines:    N+2 (N linhas de conteúdo + topo + base)
#
#   Output:
#     ---------------------------------------------------
#     | Resumo do processamento                         |
#     |-------------------------------------------------|
#     | Documentos processados  : 150                   |
#     | Sucesso                 : 145                   |
#     | Erros                   : 5                     |
#     | Tempo total             : 12.4s                 |
#     ---------------------------------------------------
#
#   Code:
#     lines = [
#         "| Resumo do processamento                         |",
#         "|-------------------------------------------------|",
#         "| Documentos processados  : 150                   |",
#         "| Sucesso                 : 145                   |",
#         "| Erros                   : 5                     |",
#         "| Tempo total             : 12.4s                 |",
#     ]
#     for line in lines:
#         LOGGER.info(line)
#     # Nota: as bordas superior e inferior podem ser geradas
#     # com SEPARATOR se o alinhamento com '|' não for crítico,
#     # ou construídas manualmente para corresponder à largura
#     # exacta das linhas de conteúdo (neste caso 51 caracteres).
#
# -----------------------------------------------------------------
# STYLE 9: TIMING
#   Usage:    Medir e registar o tempo de execução de operações a
#             3 níveis: APP, SECTION, FUNCTION.
#   Severity: INFO (app/secção), DEBUG (função/bloco)
#   Rule:     Usar time.perf_counter() para medir o tempo decorrido.
#             O valor é sempre apresentado em segundos com 2 casas
#             decimais (centésimas de segundo) — %.2fs.
#             NUNCA converter para ms, µs ou outras unidades.
#   Unit:     centésimas de segundo (X.XXs)
#   Align:    left
#
#   --- VARIANT A: TIMING_APP ---
#   Usage:    Tempo total de execução da aplicação. Colocar
#             imediatamente ANTES do BANNER_APP_END.
#
#   Output:
#     Aplicação concluída em 142.35s
#
#   Code:
#     t_app_start = time.perf_counter()
#     # ... toda a lógica da aplicação ...
#     LOGGER.info("Aplicação concluída em %.2fs", time.perf_counter() - t_app_start)
#
#   --- VARIANT B: TIMING_SECTION ---
#   Usage:    Tempo de execução de uma sub-secção. Colocar
#             imediatamente ANTES do BANNER_SECTION_END.
#             Pode incluir contexto adicional entre parênteses.
#
#   Output:
#     Processar PDFs concluído em 12.40s (150 documentos)
#
#   Code:
#     t_sec = time.perf_counter()
#     # ... sub-processo ...
#     LOGGER.info("Processar PDFs concluído em %.2fs (%d docs)", time.perf_counter() - t_sec, count)
#
#   --- VARIANT C: TIMING_FUNCTION ---
#   Usage:    Tempo de uma função específica ou bloco de código
#             dentro de uma função. Usar para funções/blocos
#             críticos cuja performance se quer monitorizar.
#             Pode ser combinado com TAG (STYLE 6) para identificar
#             o componente.
#
#   Output:
#     init_database() -> 0.34s
#     [pdf] render_page() -> 0.12s
#     [db] batch_insert() -> 1.05s
#
#   Code:
#     t = time.perf_counter()
#     result = init_database()
#     LOGGER.debug("init_database() -> %.2fs", time.perf_counter() - t)
#     # combinado com TAG:
#     LOGGER.debug("[pdf] render_page() -> %.2fs", time.perf_counter() - t)
#
# -----------------------------------------------------------------
# EXEMPLO COMPLETO DE APLICAÇÃO DOS ESTILOS
# -----------------------------------------------------------------
#
# O ficheiro de log resultante de uma aplicação que siga este guia
# terá o seguinte aspecto (assumindo o prefixo e formato base já
# configurados no logger):
#
#   <<eqs>> 2025-06-18 10:00:01 - __main__ - INFO - ===================================================
#   <<eqs>> 2025-06-18 10:00:01 - __main__ - INFO - ============== AppX v1.0 a iniciar ===============
#   <<eqs>> 2025-06-18 10:00:01 - __main__ - INFO - ===================================================
#   <<eqs>> 2025-06-18 10:00:02 - __main__ - INFO - ---------------------------------------------------
#   <<eqs>> 2025-06-18 10:00:02 - __main__ - INFO - ---------------- Processar PDFs ------------------
#   <<eqs>> 2025-06-18 10:00:02 - __main__ - INFO - ---------------------------------------------------
#   <<eqs>> 2025-06-18 10:00:03 - __main__ - DEBUG - ~~~~~~~~~~~~~~~~~ init_database() ~~~~~~~~~~~~~~~~~~
#   <<eqs>> 2025-06-18 10:00:03 - __main__ - INFO - [pdf] A processar documento 1
#   <<eqs>> 2025-06-18 10:00:04 - __main__ - INFO - [pdf] A processar documento 2
#   <<eqs>> 2025-06-18 10:00:04 - __main__ - DEBUG - ---------------------------------------------------
#   <<eqs>> 2025-06-18 10:00:05 - __main__ - INFO - [pdf] Documento 1 convertido com sucesso
#   <<eqs>> 2025-06-18 10:00:05 - __main__ - INFO - [pdf] Documento 2 convertido com sucesso
#   <<eqs>> 2025-06-18 10:00:05 - __main__ - DEBUG - [pdf] render_page() -> 0.12s
#   <<eqs>> 2025-06-18 10:00:05 - __main__ - INFO - ---------------------------------------------------
#   <<eqs>> 2025-06-18 10:00:05 - __main__ - INFO - | Resumo do processamento                         |
#   <<eqs>> 2025-06-18 10:00:05 - __main__ - INFO - |-------------------------------------------------|
#   <<eqs>> 2025-06-18 10:00:05 - __main__ - INFO - | Documentos processados  : 2                     |
#   <<eqs>> 2025-06-18 10:00:05 - __main__ - INFO - | Sucesso                 : 2                     |
#   <<eqs>> 2025-06-18 10:00:05 - __main__ - INFO - | Erros                   : 0                     |
#   <<eqs>> 2025-06-18 10:00:05 - __main__ - INFO - ---------------------------------------------------
#   <<eqs>> 2025-06-18 10:00:05 - __main__ - INFO - Processar PDFs concluído em 12.40s (2 documentos)
#   <<eqs>> 2025-06-18 10:00:05 - __main__ - INFO - ---------------------------------------------------
#   <<eqs>> 2025-06-18 10:00:05 - __main__ - INFO - ---------------- Fim Processar PDFs ---------------
#   <<eqs>> 2025-06-18 10:00:05 - __main__ - INFO - ---------------------------------------------------
#   <<eqs>> 2025-06-18 10:00:06 - __main__ - INFO - Aplicação concluída em 12.85s
#   <<eqs>> 2025-06-18 10:00:06 - __main__ - INFO - ===================================================
#   <<eqs>> 2025-06-18 10:00:06 - __main__ - INFO - ============== AppX v1.0 finalizado ===============
#   <<eqs>> 2025-06-18 10:00:06 - __main__ - INFO - ===================================================
#
# -----------------------------------------------------------------
# NOTAS PARA A AI
# -----------------------------------------------------------------
#
#   - Usar SEMPRE f-strings com alignment specs do Python
#     (:^width, :<width, :>width) para centrar/alinhar texto.
#   - NUNCA hardcodar espaços manualmente para alinhar — usar as
#     formatting specs que são determinísticas e não dependem de
#     contagem manual.
#   - Para o BOX, calcular a largura das bordas com base na linha
#     mais longa do conteúdo, garantindo pelo menos width-4 para
#     as margens internas.
#   - Tags devem ser curtas (<=12 chars) e descritivas do componente.
#     Evitar tags genéricas como [app] ou [main].
#   - Banners de função (STYLE 5) só devem ser usados em funções
#     realmente críticas (ex: init, parse, export, connect).
#     Não poluir o log com banners em funções triviais.
#   - Manter 1 linha em branco (logger.info("")) entre blocos
#     lógicos distintos para melhor legibilidade.
#   - Para medições de tempo (STYLE 9), usar SEMPRE
#     time.perf_counter() para maior precisão. Chamar uma VEZ no
#     início do bloco a medir e calcular elapsed no final.
#     NUNCA converter para ms/µs — ficar sempre em centésimas de
#     segundo com %.2fs.
# =================================================================
