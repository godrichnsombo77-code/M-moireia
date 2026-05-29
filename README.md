# Systeme de Surveillance Intelligent

Application Gradio pour la detection de violence et d'armes dans des images ou videos.

## Fonctionnalites principales

- Connexion superviseur et technicien.
- Surveillance en temps reel depuis webcam, flux RTSP ou fichier video de test.
- Visualisation directe du flux annote avec boites de detection.
- Analyse ponctuelle image/video gardee comme outil secondaire de verification.
- Enregistrement des alertes dans SQLite.
- Classement des preuves par niveau d'alerte et par groupe visuel similaire.
- Tableau de bord compact avec alertes, statistiques et preuves archivees.
- Outils technicien pour tester webcam, flux RTSP et configuration.

## Installation

```bash
pip install -r requirements.txt
```

## Lancement

```bash
python app.py
```

Puis ouvrir :

```text
http://127.0.0.1:7860
```

## Comptes de demonstration

| Role | Utilisateur | Mot de passe |
| --- | --- | --- |
| Superviseur | superviseur | admin123 |
| Technicien | technicien | tech123 |

## Organisation

```text
app.py                  Point d'entree Gradio
pages/superviseur.py    Interface d'analyse, alertes, preuves, statistiques
pages/technicien.py     Configuration technique et tests cameras
utils/database.py       Acces SQLite et authentification
utils/detection.py      Detection OpenVINO
utils/alerte.py         Regles de priorite des alertes
utils/video_recorder.py Sauvegarde et classement des preuves
```
