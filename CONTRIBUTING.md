# Guia de Contribuição — nif-pt

## 1. Fluxo de Branches

```
feature/*  →  dev  →  prod
hotfix/*   →  dev  →  prod
```

* `prod` estável (tag `v1.1.0`), `dev` desenvolvimento.
* Nunca commit direto em `prod` — via PR `dev → prod`.

## 2. Convenção de Commits (Conventional Commits)

```
<type>(<scope>): <descrição PT-PT>

feat: adicionar validação Mod-11 em consulta_nif.py
feat: adicionar validação cache SQLite em cache_validator.py
fix: corrigir requirements.txt yaml→pyyaml
docs: atualizar MANUAL.md com payload ignorado
refactor: remover Azure SQL e pyodbc
chore: ignorar venv e *.db em .gitignore
```

| Type | Uso |
|------|-----|
| `feat` | Nova funcionalidade |
| `fix` | Correção bug |
| `docs` | Documentação |
| `refactor` | Refactor sem feat/fix |
| `chore` | Infra, deps |

## 3. Setup Dev

```bash
git clone https://github.com/nunoetome/nif-pt.git
cd nif-pt
git checkout dev
python -m venv .venv
source .venv/Scripts/activate  # ou .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp config/.env.example config/.env
# preencher NIF-PT-KEY
```

> `requirements.txt` v1.2.0 só tem `requests`, `pyyaml`, `python-dotenv` (sem `pyodbc`).

## 4. Checklist PR

- [ ] `pip install -r requirements.txt` sem erro (`pyyaml`, não `yaml`; sem `pyodbc`)
- [ ] `python consulta_nif.py 509442013` → JSON `erro: null` + `run_id`
- [ ] `python consulta_nif.py 509442013 | python importar_nif_sqlite.py` → `stderr` “Guardado em SQLite”
- [ ] `python consulta_nif.py 509442013` 2ª vez em < `cache_antiguidade_dias` → JSON `ignorado:true` + `nif_ignorados` com registo + `importar_nif_sqlite.py` faz skip
- [ ] `MANUAL.md` e `docs/` atualizados se pipeline/config/BD mudou (sem referências Azure/`importar_nif.py`/`pyodbc`/`sql/0*`)
- [ ] `CHANGELOG.md` com entrada em `[Unreleased]`
- [ ] Sem segredos commitados (`git grep -i "NIF-PT-KEY"`)
- [ ] Diagramas Mermaid validados em https://mermaid.live

## 5. Versionamento

* SemVer: `MAJOR.MINOR.PATCH` + `alpha`/`beta`.
* `v.0.1.0-alpha` tem `.` a mais — usar `v0.1.0-alpha` daqui em diante.
* Breaking em `v1.2.0` (remoção Azure) → `MINOR` em `0.x` aceitável; em `1.x` seria `MAJOR` mas foi `MINOR` por stack só SQLite ser simplificação — documentado em `CHANGELOG.md`.

## 6. Issues

Usar labels `bug`, `enhancement`, `docs`, `good first issue` em https://github.com/nunoetome/nif-pt/issues.

## 7. Contacto

Repositório: https://github.com/nunoetome/nif-pt
