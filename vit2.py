import cv2
import numpy as np
import tensorflow as tf
import os

# --- CONFIGURATION ---
# Remplace par le chemin de ta vidéo de test
VIDEO_PATH = "detection_finale (1).mp4" 
MODEL_PATH = "MoViNets-for-Violence-Detection-in-Live-Video-Streaming-main\MoViNets-for-Violence-Detection-in-Live-Video-Streaming-main\model.tflite"
IMG_SIZE = 172  # Taille spécifiée dans le notebook MoViNet
CLASSES = ['Violence (Fight)', 'Normal (No_Fight)']

# 1. CHARGEMENT DU MODÈLE
if not os.path.exists(MODEL_PATH):
    print(f"Erreur : Modèle introuvable à {MODEL_PATH}")
    exit()

interpreter = tf.lite.Interpreter(model_path=MODEL_PATH)
runner = interpreter.get_signature_runner()

# 2. INITIALISATION DES ÉTATS (C'est la mémoire du modèle)
# On récupère les dimensions des buffers d'état du modèle
init_states = {
    name: tf.zeros(x['shape'], dtype=x['dtype'])
    for name, x in runner.get_input_details().items()
}
# On retire 'image' car c'est l'entrée du flux, pas un état interne
if 'image' in init_states:
    del init_states['image']

states = init_states

# 3. TRAITEMENT DE LA VIDÉO
cap = cv2.VideoCapture(VIDEO_PATH)

print("Analyse en cours... Appuyez sur 'q' pour quitter.")

while cap.isOpened():
    ret, frame = cap.read()
    if not ret:
        break

    # Prétraitement de l'image
    # 1. Redimensionner à 172x172
    # 2. Convertir BGR vers RGB
    # 3. Normaliser entre [0, 1]
    input_img = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    input_img = cv2.resize(input_img, (IMG_SIZE, IMG_SIZE))
    input_img = input_img.astype(np.float32) / 255.0
    
    # Ajouter les dimensions Batch et Time : [Batch=1, Time=1, H, W, C]
    input_tensor = input_img[np.newaxis, np.newaxis, ...]

    # 4. INFÉRENCE AVEC ÉTATS
    # On passe l'image ET les états précédents. Le modèle renvoie les nouveaux états.
    outputs = runner(**states, image=input_tensor)
    logits = outputs.pop('logits')[0]
    states = outputs  # Mise à jour de la mémoire pour la frame suivante

    # 5. RÉSULTATS (Softmax pour avoir des probabilités)
    probs = tf.nn.softmax(logits)
    prediction_id = np.argmax(probs)
    confiance = probs[prediction_id]

    # AFFICHAGE
    label = f"{CLASSES[prediction_id]}: {confiance:.2f}"
    color = (0, 0, 255) if prediction_id == 0 else (0, 255, 0) # Rouge pour violence

    cv2.putText(frame, label, (20, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, color, 2)
    cv2.imshow("Detection Violence MoViNet", frame)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
print("Test terminé.")