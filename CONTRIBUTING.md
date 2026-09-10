# Guia de Contribuição — nif-pt

## 1. Fluxo de Branches

```
feature/*  →  dev  →  prod
hotfix/*   →  dev  →  prod
```

* `prod` estável (tag `v0.2.0-beta`), `dev` desenvolvimento, `dev_new`/`prod_new` órfãos (conteúdo `a956190` não fundido).
* Nunca commit direto em `prod` — via PR `dev → prod`.

## 2. Convenção de Commits (Conventional Commits)

```
<type>(<scope>): <descrição PT-PT>

feat: adicionar validação Mod-11 em consulta_nif.py
fix: corrigir requirements.txt yaml→pyyaml
docs: atualizar MANUAL.md com PowerShell Tee-Object
refactor: centralizar config em config.py
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
python -m venv venv
source venv/Scripts/activate  # ou .\venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp config/.env.example config/.env
# preencher NIF-PT-KEY
```

## 4. Checklist PR

- [ ] `pip install -r requirements.txt` sem erro (`pyyaml`, não `yaml`)
- [ ] `python consulta_nif.py 509442013` → JSON `erro: null`
- [ ] `python consulta_nif.py 509442013 | python importar_nif_sqlite.py` → `stderr` “guardado”
- [ ] `MANUAL.md` e `docs/` atualizados se pipeline/config/BD mudou
- [ ] `CHANGELOG.md` com entrada em `[Unreleased]`
- [ ] Sem segredos commitados (`git grep -i "NIF-PT-KEY\|AZURE_PALAVRA"`)
- [ ] Diagramas Mermaid validados em https://mermaid.live

## 5. Versionamento

* SemVer: `MAJOR.MINOR.PATCH` + `alpha`/`beta`.
* `v.0.1.0-alpha` tem `.` a mais — usar `v0.1.0-alpha` daqui em diante.
* Breaking (ex: SQLite JSON em `v0.2.0-beta`) → `MINOR` em `0.x` (aceitável); em `1.x` seria `MAJOR`.

## 6. Issues

Usar labels `bug`, `enhancement`, `docs`, `good first issue` em https://github.com/nunoetome/nif-pt/issues.

## 7. Contacto

Repositório: https://github.com/nunoetome/nif-pt
