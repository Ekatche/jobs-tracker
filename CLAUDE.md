<!-- code-review-graph MCP tools -->
## MCP Tools: code-review-graph

**This project has a knowledge graph. Start with the code-review-graph
MCP tools to narrow scope, then read the source.** The graph is cheaper than scanning files and
gives you structural context (callers, dependents, test coverage) that file search cannot.

### When to use graph tools FIRST

- **Exploring code**: `semantic_search_nodes_tool` or `query_graph_tool` instead of Grep
- **Understanding impact**: `get_impact_radius_tool` instead of manually tracing imports
- **Code review**: `detect_changes_tool` + `get_review_context_tool` instead of reading entire files
- **Finding relationships**: `query_graph_tool` with callers_of/callees_of/imports_of/tests_for
- **Architecture questions**: `get_architecture_overview_tool` + `list_communities_tool`

### Verify in the source

- Narrow scope with the graph, then read the source. Do not change code from graph output alone.
- For any non-trivial change, read the implementation and the relevant tests before concluding.
- Verify the exact source when touching behavior, database logic, migrations, retries, fallbacks,
  recovery, or compatibility code.
- When the graph and the source disagree, the source wins. The graph may be stale or may not
  model that relationship.
- An empty graph result can mean "not indexed" or "not statically visible", not "does not exist".

### Key Tools

| Tool | Use when |
| ------ | ---------- |
| `detect_changes_tool` | Reviewing code changes — gives risk-scored analysis |
| `get_review_context_tool` | Need source snippets for review — token-efficient |
| `get_impact_radius_tool` | Understanding blast radius of a change |
| `get_affected_flows_tool` | Finding which execution paths are impacted |
| `query_graph_tool` | Tracing callers, callees, imports, tests, dependencies |
| `semantic_search_nodes_tool` | Finding functions/classes by name or keyword |
| `get_architecture_overview_tool` | Understanding high-level codebase structure |
| `refactor_tool` | Planning renames, finding dead code |

### Workflow

1. The graph auto-updates on file changes (via hooks).
2. Use `detect_changes_tool` for code review.
3. Use `get_affected_flows_tool` to understand impact.
4. Use `query_graph_tool` pattern="tests_for" to check coverage.
<!-- /code-review-graph MCP tools -->

## Directives pour la gestion, l'audit et la suppression des tests

### Objectif : Ne conserver que des tests pertinents et à forte valeur ajoutée

Pour maintenir une suite de tests rapide, fiable et pertinente, appliquez systématiquement ces règles :

#### 1. Critères de pertinence (Tests à conserver et prioriser)
Un test est jugé **pertinent** et indispensable lorsqu'il couvre au moins l'un des aspects suivants :
- **Logique métier & invariants** : Algorithmes de matching/scoring d'offres, détection d'offres closes (404, dates d'expiration JSON-LD, mentions textuelles), calculs de périodes et d'expériences, fusion des profils multi-sources.
- **Gardes-fous et résilience IA** : Gardes anti-hallucination (`letter_guards`), intégrité des templates de CV (`test_cv_guards`), quotas et consommation de tokens (`usage_tracker`).
- **Contrats d'API & Sécurité** : Codes de statut HTTP, schémas de validation Pydantic, ségrégation des accès utilisateurs, intégrité des données partagées (ex: éditer une candidature ne doit jamais écraser l'offre source partagée).
- **Rendu et parité graphique** : Rendu PDF sans régression visuelle, parité du registre des templates de CV.

#### 2. Critères de suppression (Quand et comment élaguer des tests)
Supprimez ou consolidez sans hésiter les tests correspondant aux cas suivants :
- **Obsolescence** : Le code, l'endpoint, le modèle ou le comportement cible a été déprécié ou supprimé. Ne jamais maintenir des tests obsolètes sous perfusion de mocks artificiels.
- **Redondance pure (Doublons)** : Plusieurs tests vérifient la même branche de code avec les mêmes assertions sous des noms différents (ex: tests de normalisation de chaînes basiques dupliqués entre plusieurs fichiers).
- **Test tautologique / Sur-mocking** : Un test qui ne vérifie que la configuration d'un mock sans exécuter la moindre logique réelle du projet n'apporte aucune garantie et doit être supprimé.
- **Flakiness structurelle** : Tests dépendant d'un timing non maîtrisé (`sleep`), d'accès réseau non mockés vers des API tierces, ou de collisions sur la base de données de test partagée.

#### 3. Procédure pour supprimer ou actualiser des tests
Avant toute suppression ou refonte de tests :
1. **Cartographier l'impact avec code-review-graph** :
   - Exécutez `query_graph_tool` avec `pattern="tests_for"` sur la fonction ou classe ciblée pour identifier l'ensemble des tests associés.
2. **Évaluer la couverture résiduelle** :
   - Assurez-vous que les cas limites nominaux restent couverts par un test unitaire ou d'intégration plus concis et robuste.
3. **Supprimer le code mort** :
   - Retirez la fonction de test dans `backend/tests/test_*.py` ainsi que les fixtures/données de mock associées devenues orphelines.
4. **Vérifier l'exécution** :
   - Lancez `pytest backend/tests/test_<nom>.py -v` pour valider que la suite restante passe intégralement au vert.

