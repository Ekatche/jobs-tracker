---
title: Passer la suppression de PDF en BackgroundTask
status: done
---

## User intent
L'utilisateur souhaite appliquer l'une des recommandations d'optimisation (passage en `BackgroundTasks`) pour réduire la latence. L'import GitHub nécessitant un changement lourd côté front (polling/websockets), nous appliquons l'optimisation la plus sûre : déléguer la suppression du fichier temporaire PDF sur le disque à une tâche de fond lors du parsing du CV.

## Surgical Scope
- `backend/app/routers/cover_letters.py`: modification de `import_cv_source` (anciennement upload_cv).

## Steps
- [x] 1. Ajouter `background_tasks: BackgroundTasks` aux paramètres de la route `import_cv_source`.
- [x] 2. Créer une fonction utilitaire asynchrone ou synchrone `_safe_remove(path: str)` pour supprimer le fichier sans planter silencieusement.
- [x] 3. Remplacer `os.remove(file_path)` par `background_tasks.add_task(_safe_remove, file_path)`.

## Definition of Done
- [x] Vérifier la présence de background_tasks dans import_cv_source : `grep -A 5 'def import_cv_source' backend/app/routers/cover_letters.py | grep 'BackgroundTasks'`

## Code Review
- **Security surface touched?** non
- **Performance:** légère amélioration de la latence de réponse I/O.
- **Testing:** API reste fonctionnelle (syntaxe vérifiée avec py_compile).
- Verdict: ✅ DONE

## Execution Log
- 17:13 : Création de la fonction helper `_safe_remove` avec logger.
- 17:13 : Injection de la dépendance `BackgroundTasks` dans `import_cv_source`.
- 17:13 : Modification du bloc `finally` pour déléguer la suppression I/O à l'arrière-plan.
- 17:14 : Validation syntaxique réussie (`py_compile`).
