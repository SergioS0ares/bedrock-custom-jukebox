import os
import json
import shutil
import zipfile
from pydub import AudioSegment  # Requer: pip install pydub

# --- Configurações ---
NOME_ADDON = "JukeboxPro"
PASTA_SOURCE = "addon_source"
PASTA_MUSICA = "user_music"
PASTA_SAIDA = "build"

# Template do JavaScript que será injetado
# Ele cria uma logica simples: Bater no bloco com o disco muda a musica
JS_TEMPLATE = """
import { world, system } from "@minecraft/server";

// LISTA DE MUSICAS GERADA PELO PYTHON
const MUSIC_TRACKS = %MUSICAS_ARRAY%;

world.beforeEvents.itemUseOn.subscribe((event) => {
    const { source, itemStack, block } = event;

    // Verifica se é a nossa Jukebox (ajuste o ID conforme seu bloco)
    if (block.typeId === "meu_addon:custom_jukebox") {
        
        // Exemplo simples: Toca uma música aleatória da lista ao clicar
        const randomTrack = MUSIC_TRACKS[Math.floor(Math.random() * MUSIC_TRACKS.length)];
        
        // Toca o som no mundo
        source.runCommandAsync(`playsound ${randomTrack} @a[r=20] ${block.location.x} ${block.location.y} ${block.location.z}`);
        
        // Avisa o jogador
        source.sendMessage(`§aTocando: ${randomTrack}`);
    }
});
"""

def main():
    print(f"--- Iniciando Super Build do {NOME_ADDON} ---")

    # 1. Limpar e Copiar Base
    if os.path.exists(PASTA_SAIDA):
        shutil.rmtree(PASTA_SAIDA)
    shutil.copytree(PASTA_SOURCE, PASTA_SAIDA)

    # 2. Preparar pastas
    caminho_sons_rp = os.path.join(PASTA_SAIDA, "RP", "sounds", "music")
    os.makedirs(caminho_sons_rp, exist_ok=True)
    
    arquivos = os.listdir(PASTA_MUSICA)
    musicas_ids = []
    sound_defs = {"format_version": "1.14.0", "sound_definitions": {}}

    print("--- Convertendo Áudios ---")

    # 3. Conversão e Registro
    contador = 0
    for arquivo in arquivos:
        caminho_origem = os.path.join(PASTA_MUSICA, arquivo)
        nome_base = os.path.splitext(arquivo)[0]
        
        # Define caminho de saída (sempre .ogg)
        caminho_destino = os.path.join(caminho_sons_rp, f"{nome_base}.ogg")
        
        # Se for MP3, converte. Se for OGG, só copia.
        if arquivo.endswith(".mp3"):
            print(f"Convertendo: {arquivo} -> .ogg")
            try:
                audio = AudioSegment.from_mp3(caminho_origem)
                audio.export(caminho_destino, format="ogg")
            except Exception as e:
                print(f"ERRO ao converter {arquivo}. Você instalou o FFmpeg? \nErro: {e}")
                continue
        elif arquivo.endswith(".ogg"):
            shutil.copy2(caminho_origem, caminho_destino)
        else:
            continue # Pula arquivos que não são audio

        # Registrar no JSON
        id_som = f"custom.music.{contador}"
        sound_defs["sound_definitions"][id_som] = {
            "category": "record",
            "sounds": [f"sounds/music/{nome_base}"]
        }
        musicas_ids.append(id_som)
        contador += 1

    # 4. Salvar sound_definitions.json
    with open(os.path.join(PASTA_SAIDA, "RP", "sound_definitions.json"), "w") as f:
        json.dump(sound_defs, f, indent=4)

    # 5. GERAR O JAVASCRIPT DINAMICAMENTE
    print("--- Gerando Script API ---")
    caminho_script = os.path.join(PASTA_SAIDA, "BP", "scripts", "main.js")
    
    # Transforma a lista do Python em string de Array do JS
    js_final = JS_TEMPLATE.replace("%MUSICAS_ARRAY%", json.dumps(musicas_ids))
    
    # Garante que a pasta scripts existe
    os.makedirs(os.path.dirname(caminho_script), exist_ok=True)
    
    with open(caminho_script, "w") as f:
        f.write(js_final)

    # 6. Empacotar .mcaddon
    print("--- Empacotando ---")
    output_filename = f"{NOME_ADDON}.mcaddon"
    with zipfile.ZipFile(output_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(PASTA_SAIDA):
            for file in files:
                filepath = os.path.join(root, file)
                arcname = os.path.relpath(filepath, PASTA_SAIDA)
                zipf.write(filepath, arcname)

    print(f"✅ FEITO! Addon gerado com {contador} músicas.")

if __name__ == "__main__":
    main()