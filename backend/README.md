# technique-agent backend

Backend dedicated to the technical interview agent.

This backend powers the technical interview application.

## Current status

The backend is aligned around the technical interview flow with LangChain orchestration.

## Planned responsibilities

- technical interview orchestration
- CV ingestion
- technical PDF ingestion
- technical RAG retrieval
- technical scoring
- technical final reporting

## Target API namespace

- `/tech/sessions`
- `/tech/sessions/{session_id}/message`
- `/tech/sessions/{session_id}/cv`
- `/tech/sessions/{session_id}/docs`
- `/tech/sessions/{session_id}/finalize`

## Suggested local port

- `8001`

## Test emotion model on one image

Pour tester le modele d'emotion sans attendre le live camera, lance une analyse sur une image fixe :

```powershell
python backend/test_emotion_image.py .\chemin\vers\image.jpg --raw-model-only
```

Tu peux aussi passer plusieurs images dans la meme commande pour charger le modele une seule fois :

```powershell
python backend/test_emotion_image.py .\img1.jpg .\img2.jpg .\img3.jpg --raw-model-only
```

Le script utilise le meme modele custom que l'API live et retourne le label, la confiance et les probabilites brutes au format JSON.
