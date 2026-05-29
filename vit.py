import tensorflow as tf

# Chemin vers ton modèle
model_path = r"MoViNets-for-Violence-Detection-in-Live-Video-Streaming-main\MoViNets-for-Violence-Detection-in-Live-Video-Streaming-main\model.tflite"

# Charger l'interpréteur
interpreter = tf.lite.Interpreter(model_path=model_path)
interpreter.allocate_tensors()

# 1. Vérifier les signatures (souvent les labels y sont)
try:
    signatures = interpreter.get_signature_list()
    print("Signatures du modèle :", signatures)
except:
    print("Pas de signatures détaillées trouvées.")

# 2. Afficher les détails des sorties (Output)
output_details = interpreter.get_output_details()
print("\nStructure de sortie :", output_details[0]['shape'])

# 3. Tenter d'extraire les labels des métadonnées (si présents)
from tflite_support import metadata
try:
    displayer = metadata.MetadataDisplayer.from_model_file(model_path)
    for file_name in displayer.get_packed_associated_file_list():
        print(f"\nFichier associé trouvé : {file_name}")
        # Si un fichier .txt est présent, c'est ta liste de classes
except:
    print("\nAucune métadonnée 'Associated Files' trouvée. Les classes sont probablement gérées par ton script de mapping (ex: 0 = Normal, 1 = Violence).")